"""
The evaluation set for search, and the score the current search gets on it.

A model cannot be chosen by reading its name. `acordaosSimilares` — the related
judgements the STJ publishes beside each mirror — is the only judgement of
similarity in this collection that the project did not compute itself, so it is
the only thing a method can be scored against without scoring it against our
own opinion.

Two things are built here and nothing else depends on them at serving time:

  avaliacao.par        the pairs, after resolution and after the exclusions
  avaliacao.resultado  where the current search ranked each pair's target

The score is written down so a later model has something to beat. What the
numbers mean, and why these pairs and not the 1.309.628 the field contains, is
in documentation/architecture/search-evaluation.md.

    uv run python evaluate_search.py --build
    uv run python evaluate_search.py --prepare --measure
    uv run python evaluate_search.py --report --export pares.csv
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import os
import sys
from pathlib import Path
from typing import Any

import psycopg2

SCHEMA = "avaliacao"
PAIRS = f"{SCHEMA}.par"
RESULTS = f"{SCHEMA}.resultado"

# Indexed copies of what the ranking reads. The real `core` carries no indexes
# — `publish.py` creates them on the way out — so a measurement against it
# sequentially scans 1,4 million rows twice per query. Copying first turns
# hours into minutes and changes no number.
DOCS = f"{SCHEMA}.documento"
TERMS = f"{SCHEMA}.termo"
NORMS = f"{SCHEMA}.norma"

SOURCE = "stj-espelhos"

# The same three numbers `related.py` serves RF20 with. The baseline has to be
# the search as it is, not a version of it tuned for this measurement.
RARITY_FLOOR = 4.5
SEARCH_TERMS = 12
MINIMUM_TERMS = 2

# Where a reader looks. Ten is one screen of results; a hundred is as far as
# anyone pages before rephrasing.
CUTS = (1, 10, 100)

CREATE = f"CREATE SCHEMA IF NOT EXISTS {SCHEMA};"

# The registry number identifies the case, the judgement date identifies which
# judgement of it. Resolving on the registry alone links to a different
# judgement of the same case 95,65% of the time — measured in
# similar-acordaos.md — so both are required.
BUILD = f"""
DROP TABLE IF EXISTS {PAIRS};
CREATE TABLE {PAIRS} AS
WITH citacao AS (
  SELECT
    e.id AS consulta,
    REPLACE(REPLACE(
      (REGEXP_MATCH(s.value, '([0-9]{{4}}/[0-9]{{7}}-[0-9])'))[1], '/', ''), '-', ''
    ) AS registro,
    TO_DATE(
      (REGEXP_MATCH(s.value, 'decis[a\u00e3]o:\\s*([0-9]{{2}}/[0-9]{{2}}/[0-9]{{4}})', 'i'))[1],
      'DD/MM/YYYY'
    ) AS julgada_em
  FROM raw."espelho_stj\u25b6acordaosSimilares" AS s
  JOIN raw.espelho_stj AS e ON e._dlt_id = s._dlt_parent_id
),

resolvida AS (
  SELECT
    c.consulta,
    MIN(d.identificador_fonte) AS relevante,
    COUNT(d.identificador_fonte) AS alvos
  FROM citacao AS c
  JOIN core.decisao AS d
    ON d.fonte_codigo = '{SOURCE}'
   AND d.identificador_documento = c.registro
   AND d.data_julgamento = c.julgada_em
  WHERE c.registro IS NOT NULL AND c.julgada_em IS NOT NULL
  GROUP BY c.consulta, c.registro, c.julgada_em
)

SELECT DISTINCT r.consulta, r.relevante
FROM resolvida AS r
JOIN core.decisao AS o
  ON o.fonte_codigo = '{SOURCE}' AND o.identificador_fonte = r.consulta
JOIN core.decisao AS a
  ON a.fonte_codigo = '{SOURCE}' AND a.identificador_fonte = r.relevante
WHERE r.alvos = 1
  AND o.identificador_documento <> a.identificador_documento;

CREATE INDEX ON {PAIRS} (consulta);
ANALYZE {PAIRS};
"""

PREPARE_SQL = f"""
DROP TABLE IF EXISTS {DOCS};
CREATE TABLE {DOCS} AS
SELECT fonte_codigo, identificador_fonte, ementa_busca FROM core.decisao;
CREATE INDEX ON {DOCS} USING GIN (ementa_busca);
CREATE INDEX ON {DOCS} (fonte_codigo, identificador_fonte);

DROP TABLE IF EXISTS {TERMS};
CREATE TABLE {TERMS} AS SELECT termo, peso FROM core.termo_judicial;
CREATE INDEX ON {TERMS} (termo);

DROP TABLE IF EXISTS {NORMS};
CREATE TABLE {NORMS} AS
SELECT fonte_codigo, identificador_fonte, norma FROM core.decisao_norma;
CREATE INDEX ON {NORMS} (fonte_codigo, identificador_fonte);

ANALYZE {DOCS}; ANALYZE {TERMS}; ANALYZE {NORMS};
"""

# The ranking `related.py` produces, asked where each known-relevant decision
# landed. A target the candidate step never reached comes back NULL, which is a
# miss at every cut and not a missing measurement.
#
# Ranked once per query and not once per pair. The court gave one decision 97
# similars, and ranking the collection 97 times to read 97 rows off the same
# ordering is the same answer for 97 times the work.
MEASURE = f"""
DROP TABLE IF EXISTS {RESULTS};
CREATE TABLE {RESULTS} AS
SELECT q.consulta, r.relevante, r.posicao
FROM (SELECT DISTINCT consulta FROM {PAIRS}) AS q
CROSS JOIN LATERAL (
  WITH origem AS (
    SELECT
      t.lexeme AS termo,
      j.peso * (1 + LN(ARRAY_LENGTH(t.positions, 1))) AS valor,
      j.peso AS peso
    FROM {DOCS} AS d
    CROSS JOIN LATERAL UNNEST(d.ementa_busca) AS t
    JOIN {TERMS} AS j ON j.termo = t.lexeme
    WHERE d.fonte_codigo = '{SOURCE}' AND d.identificador_fonte = q.consulta
  ),

  raros AS (
    SELECT termo FROM origem
    WHERE peso >= {RARITY_FLOOR}
    ORDER BY peso DESC
    LIMIT {SEARCH_TERMS}
  ),

  candidatos AS (
    SELECT d.fonte_codigo, d.identificador_fonte, d.ementa_busca
    FROM {DOCS} AS d
    WHERE d.ementa_busca @@ TO_TSQUERY(
            'portugues_sem_acento', (SELECT STRING_AGG(termo, ' | ') FROM raros))
      AND NOT (d.fonte_codigo = '{SOURCE}' AND d.identificador_fonte = q.consulta)
  ),

  casamento AS (
    SELECT
      c.fonte_codigo,
      c.identificador_fonte,
      SUM(o.valor * (j.peso * (1 + LN(ARRAY_LENGTH(t.positions, 1))))) AS produto,
      COUNT(*) AS termos
    FROM candidatos AS c
    CROSS JOIN LATERAL UNNEST(c.ementa_busca) AS t
    JOIN origem AS o ON o.termo = t.lexeme
    JOIN {TERMS} AS j ON j.termo = t.lexeme
    GROUP BY c.fonte_codigo, c.identificador_fonte
  ),

  proxima AS (
    SELECT
      m.fonte_codigo,
      m.identificador_fonte,
      m.produto / (nc.norma * no.norma) AS semelhanca
    FROM casamento AS m
    JOIN {NORMS} AS nc
      ON nc.fonte_codigo = m.fonte_codigo
     AND nc.identificador_fonte = m.identificador_fonte
    CROSS JOIN (
      SELECT norma FROM {NORMS}
      WHERE fonte_codigo = '{SOURCE}' AND identificador_fonte = q.consulta
    ) AS no
    WHERE m.termos >= {MINIMUM_TERMS}
  ),

  ordenada AS (
    SELECT
      fonte_codigo,
      identificador_fonte,
      ROW_NUMBER() OVER (ORDER BY semelhanca DESC, identificador_fonte) AS posicao
    FROM proxima
  )

  SELECT p.relevante, o.posicao
  FROM {PAIRS} AS p
  LEFT JOIN ordenada AS o
    ON o.fonte_codigo = '{SOURCE}' AND o.identificador_fonte = p.relevante
  WHERE p.consulta = q.consulta
) AS r;
"""


def _connect(url: str) -> psycopg.Connection:
    conexao = psycopg2.connect(url)
    conexao.autocommit = True
    return conexao


def build(conexao: Any) -> int:
    with conexao.cursor() as cursor:
        cursor.execute(CREATE)
        cursor.execute(BUILD)
        cursor.execute(f"SELECT COUNT(*) FROM {PAIRS}")
        return int(cursor.fetchone()[0])


def prepare(conexao: Any) -> None:
    with conexao.cursor() as cursor:
        cursor.execute(PREPARE_SQL)


def measure(conexao: Any) -> int:
    with conexao.cursor() as cursor:
        cursor.execute(MEASURE)
        cursor.execute(f"SELECT COUNT(posicao) FROM {RESULTS}")
        return int(cursor.fetchone()[0])


def score(conexao: Any) -> dict[str, Any]:
    """
    Recall at each cut, over pairs, plus the reciprocal rank averaged per pair.

    Per pair and not per query: a query the court gave two similars to is two
    chances to agree with it, and collapsing them would weigh a query with one
    the same as a query with ninety-seven.
    """
    with conexao.cursor() as cursor:
        cursor.execute(f"SELECT posicao FROM {RESULTS}")
        posicoes = [linha[0] for linha in cursor.fetchall()]

    total = len(posicoes)
    if total == 0:
        raise RuntimeError(f"{RESULTS} is empty; run --measure first")

    encontradas = [p for p in posicoes if p is not None]
    medida: dict[str, Any] = {
        "pares": total,
        "alcancados": len(encontradas),
        "mrr": round(sum(1 / p for p in encontradas) / total, 4),
    }
    for corte in CUTS:
        acertos = sum(1 for p in encontradas if p <= corte)
        medida[f"recall@{corte}"] = round(100 * acertos / total, 2)
    return medida


def export(conexao: Any, destino: Path) -> int:
    with conexao.cursor() as cursor:
        cursor.execute(f"SELECT consulta, relevante FROM {PAIRS} ORDER BY 1, 2")
        linhas = cursor.fetchall()

    with destino.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(("consulta", "relevante"))
        escritor.writerows(linhas)
    return len(linhas)


def main(argv: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--build", action="store_true")
    analisador.add_argument("--prepare", action="store_true")
    analisador.add_argument("--measure", action="store_true")
    analisador.add_argument("--report", action="store_true")
    analisador.add_argument("--export", type=Path)
    argumentos = analisador.parse_args(argv)

    url = os.getenv("DATABASE_URL", "")
    if not url:
        print("set DATABASE_URL", file=sys.stderr)
        return 2

    with contextlib.closing(_connect(url)) as conexao:
        if argumentos.build:
            print(f"pairs: {build(conexao)}")
        if argumentos.prepare:
            prepare(conexao)
            print("prepared")
        if argumentos.measure:
            print(f"reached: {measure(conexao)}")
        if argumentos.report:
            for chave, valor in score(conexao).items():
                print(f"{chave}: {valor}")
        if argumentos.export:
            print(f"written: {export(conexao, argumentos.export)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
