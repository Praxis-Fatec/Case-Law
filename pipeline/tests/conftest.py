"""Shared setup for the tests that need a real PostgreSQL."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

RAIZ = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"

TEST_DATABASE_URL = os.getenv("PIPELINE_TEST_DATABASE_URL", "")

needs_database = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="set PIPELINE_TEST_DATABASE_URL to run the tests that build models",
)


@pytest.fixture(scope="session")
def banco() -> Iterator[str]:
    """
    A database the tests may drop schemas in, which is why the name is checked.

    The fixture replaces `raw`, `core` and `verificacao` wholesale. Pointed at
    a collection somebody cares about it would destroy it, and the mistake is
    one connection string away.
    """
    nome = psycopg.conninfo.conninfo_to_dict(TEST_DATABASE_URL).get("dbname")
    if not str(nome).endswith("_test"):
        raise RuntimeError(
            "PIPELINE_TEST_DATABASE_URL must name a database ending in _test; "
            "the fixtures drop core, raw and verificacao."
        )

    # Before anything builds a Context. Where SQLMesh has state, a rendered
    # model points at the physical table that state names instead of at the
    # schema the fixture just created, and the tests read a collection nobody
    # wrote. Left over from an earlier `sqlmesh plan` against this database,
    # that is a failure with no visible cause.
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as conn:
        esquemas = conn.execute(
            "SELECT nspname FROM pg_namespace WHERE nspname LIKE 'sqlmesh%'"
        ).fetchall()
        for (esquema,) in esquemas:
            conn.execute(f'DROP SCHEMA IF EXISTS "{esquema}" CASCADE')

    yield TEST_DATABASE_URL


@pytest.fixture
def acervo(banco: str) -> Iterator[psycopg.Connection]:
    """The minimal collection, rebuilt for each test that asks for it."""
    with psycopg.connect(banco, autocommit=True) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
        conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        existe = conn.execute(
            "SELECT 1 FROM pg_ts_config WHERE cfgname = 'portugues_sem_acento'"
        ).fetchone()
        if not existe:
            conn.execute(
                "CREATE TEXT SEARCH CONFIGURATION portugues_sem_acento"
                " ( COPY = portuguese )"
            )
            conn.execute(
                "ALTER TEXT SEARCH CONFIGURATION portugues_sem_acento"
                " ALTER MAPPING FOR hword, hword_part, word"
                " WITH unaccent, portuguese_stem"
            )
        conn.execute((FIXTURES / "raw_minimo.sql").read_text(encoding="utf-8"))
        _semear(conn)
        yield conn


SEMENTES = {
    "fonte": "codigo TEXT, nome TEXT, conteudo TEXT, tribunal_sigla TEXT,"
    " url_base TEXT, url_documento_template TEXT, status TEXT,"
    " cobertura_inicio DATE, cobertura_fim DATE, observacoes TEXT",
    "classe_processual": "codigo_cnj BIGINT, codigo_pai BIGINT, nome TEXT",
    "tribunal": "sigla TEXT, nome TEXT, esfera TEXT, uf TEXT",
}


def _semear(conn: psycopg.Connection) -> None:
    """
    The seeds as real tables, from the same CSVs the project ships.

    SQLMesh loads them itself in a real run; here the models are rendered and
    executed directly, so they have to be on the database like any other table.
    Reading the CSVs rather than restating them keeps the fixture from drifting
    away from the catalogue the models actually resolve against.
    """
    sementes = RAIZ / "transformations" / "seeds"
    for nome, colunas in SEMENTES.items():
        conn.execute(f"CREATE TABLE core.{nome} ({colunas})")
        with open(sementes / f"{nome}.csv", encoding="utf-8") as arquivo:
            with conn.cursor().copy(
                f"COPY core.{nome} FROM STDIN WITH (FORMAT csv, HEADER true)"
            ) as copia:
                copia.write(arquivo.read())
