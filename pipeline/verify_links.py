"""
Checks that the link each decision carries still reaches a document.

Runs at load time, never inside a search request. The search reads what this
wrote, so a court portal that is down slows nothing down and takes nothing off
the screen — the record simply stays unverified until the next run.
"""

import os
import sys
from collections.abc import Callable
from typing import Any

import psycopg2

from datetime import date

from sources.tjdft import (
    REQUEST_INTERVAL,
    _Pacer,
    _windows,
    document_opens,
    documents_between,
)

SCHEMA = "verificacao"
TABLE = f"{SCHEMA}.link"

# What each source can be asked about its own documents. A source is absent
# because nothing here can answer for it, not because nobody got to it: the
# STJ's portal answers 200 and echoes back whatever sequential it is given, so
# a real acordao and an invented one are indistinguishable from outside.
CHECKS: dict[str, Callable[[str, str | None], bool]] = {
    "tjdft-jurisdf": document_opens,
}

# The sweep lists a collection by date window, which only the TJDFT's API does.
SWEEPABLE = "tjdft-jurisdf"

CREATE = f"""
CREATE SCHEMA IF NOT EXISTS {SCHEMA};
CREATE TABLE IF NOT EXISTS {TABLE} (
    fonte_codigo  TEXT        NOT NULL,
    identificador TEXT        NOT NULL,
    valido        BOOLEAN     NOT NULL,
    verificado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (fonte_codigo, identificador)
);
"""

# Every row written before the table knew about sources is the TJDFT's: it was
# the only collection there was.
MIGRATE = f"""
DO $do$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = '{SCHEMA}' AND table_name = 'link'
          AND column_name = 'fonte_codigo'
    ) THEN
        ALTER TABLE {TABLE} ADD COLUMN fonte_codigo TEXT;
        UPDATE {TABLE} SET fonte_codigo = 'tjdft-jurisdf';
        ALTER TABLE {TABLE} ALTER COLUMN fonte_codigo SET NOT NULL;
        ALTER TABLE {TABLE} DROP CONSTRAINT link_pkey;
        ALTER TABLE {TABLE} ADD PRIMARY KEY (fonte_codigo, identificador);
    END IF;
END $do$;
"""

# A record with no row here is unverified, which is not the same as invalid. A
# source with no check of its own stays that way on purpose: claiming a verdict
# nobody produced would be worse than admitting there is none.
PENDING = f"""
SELECT d.fonte_codigo, d.identificador_fonte, d.identificador_documento
FROM core.decisao AS d
LEFT JOIN {TABLE} AS v
  ON v.fonte_codigo = d.fonte_codigo
 AND v.identificador = d.identificador_fonte
WHERE v.identificador IS NULL
  AND d.fonte_codigo = ANY(%(fontes)s)
ORDER BY d.data_referencia DESC
LIMIT %(limit)s
"""

RECORD = f"""
INSERT INTO {TABLE} (fonte_codigo, identificador, valido, verificado_em)
VALUES (%(fonte)s, %(identificador)s, %(valido)s, NOW())
ON CONFLICT (fonte_codigo, identificador) DO UPDATE
SET valido = EXCLUDED.valido, verificado_em = EXCLUDED.verificado_em
"""

# Stops a run that is only producing failures: a portal that is down would
# otherwise be asked once per remaining record.
MAX_CONSECUTIVE_FAILURES = 10

SPAN = """
SELECT MIN(data_julgamento) AS first, MAX(data_julgamento) AS last
FROM core.decisao
WHERE data_julgamento IS NOT NULL
  AND fonte_codigo = %(fonte)s
"""

IN_WINDOW = """
SELECT identificador_fonte, identificador_documento
FROM core.decisao
WHERE data_julgamento BETWEEN %(first)s AND %(last)s
  AND fonte_codigo = %(fonte)s
"""


def _connection() -> Any:
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "caselaw"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
    )


def _limit() -> int:
    value = os.getenv("VERIFY_MAX", "").strip()
    return int(value) if value else 1000


def _interval() -> float:
    value = os.getenv("VERIFY_INTERVAL", "").strip()
    return float(value) if value else REQUEST_INTERVAL


def verify() -> int:
    pacer = _Pacer(_interval())
    checked = invalid = failed = 0
    consecutive = 0

    with _connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(CREATE)
            cursor.execute(MIGRATE)
            cursor.execute(
                PENDING, {"limit": _limit(), "fontes": list(CHECKS)}
            )
            pending = [(row[0], row[1], row[2]) for row in cursor.fetchall()]

        print(f"{len(pending)} to verify, from {', '.join(CHECKS)}", flush=True)

        for fonte, identificador, documento in pending:
            pacer.wait()
            try:
                exists = CHECKS[fonte](identificador, documento)
            except Exception as error:  # noqa: BLE001 — any failure is "unknown"
                failed += 1
                consecutive += 1
                if consecutive >= MAX_CONSECUTIVE_FAILURES:
                    print(f"  stopping: {consecutive} failures in a row", flush=True)
                    print(f"  last one: {error}", flush=True)
                    break
                continue

            consecutive = 0
            checked += 1
            invalid += not exists

            with connection.cursor() as cursor:
                cursor.execute(
                    RECORD,
                    {
                        "fonte": fonte,
                        "identificador": identificador,
                        "valido": exists,
                    },
                )
            connection.commit()

    print(f"verified {checked}, invalid {invalid}, unreachable {failed}", flush=True)
    return invalid


def sweep() -> int:
    """
    The same answer as `verify`, in a fraction of the requests.

    Reading a window costs one request per forty documents, so the collection
    is listed for about 2.700 requests instead of 107.828. The listing carries
    the document key as well, so the window settles both questions at once: the
    source still holds the record, and the key the link is built from is the
    one it reports.

    A record the listing does not match is a candidate, not a verdict: a
    corrected judgement date moves a record out of the window it was collected
    in, so each one is confirmed on its own before being written down as broken.
    """
    pacer = _Pacer(_interval())
    checked = invalid = 0

    with _connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(CREATE)
            cursor.execute(MIGRATE)
            cursor.execute(SPAN, {"fonte": SWEEPABLE})
            span = cursor.fetchone()

        if span is None or span[0] is None:
            print(f"nothing loaded for {SWEEPABLE}", flush=True)
            return 0

        first, last = span
        janelas = list(_windows(first, last, "month"))
        print(f"{first} to {last}, {len(janelas)} windows", flush=True)

        for inicio, fim in janelas:
            listed = documents_between(inicio, fim, _interval())

            with connection.cursor() as cursor:
                cursor.execute(
                    IN_WINDOW,
                    {"first": inicio, "last": fim, "fonte": SWEEPABLE},
                )
                ours = [(row[0], row[1]) for row in cursor.fetchall()]

            missing = [i for i, doc in ours if listed.get(i) != doc]
            print(
                f"  {inicio:%Y-%m}  listed {len(listed):>5}  ours {len(ours):>5}"
                f"  to confirm {len(missing)}",
                flush=True,
            )

            for identificador, documento in ours:
                if listed.get(identificador) == documento:
                    valido = True
                else:
                    pacer.wait()
                    try:
                        valido = CHECKS[SWEEPABLE](identificador, documento)
                    except Exception:  # noqa: BLE001
                        continue

                checked += 1
                invalid += not valido
                with connection.cursor() as cursor:
                    cursor.execute(
                        RECORD,
                        {
                            "fonte": SWEEPABLE,
                            "identificador": identificador,
                            "valido": valido,
                        },
                    )
            connection.commit()

    print(f"verified {checked}, invalid {invalid}", flush=True)
    return invalid


def main() -> None:
    modo = sys.argv[1] if len(sys.argv) > 1 else "sweep"
    try:
        sweep() if modo == "sweep" else verify()
    except KeyboardInterrupt:
        print("\ninterrupted — what was verified is already recorded", flush=True)
        sys.exit(130)


if __name__ == "__main__":
    main()
