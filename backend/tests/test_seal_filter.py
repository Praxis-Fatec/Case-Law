from pathlib import Path

import psycopg
import pytest
from psycopg.rows import DictRow

from tests.conftest import FIXTURES, needs_database

pytestmark = needs_database

MODEL = (
    Path(__file__).resolve().parents[2]
    / "pipeline"
    / "transformations"
    / "models"
    / "core_decisao.sql"
)

SEALED = {"9000004", "9000005"}
OPEN = {"9000001", "9000002", "9000003", "9000006"}


def transformation() -> str:
    """
    The SELECT the model builds `core.decisao` from, read from the model itself.

    Reading the file rather than restating the query is the whole point: a test
    that carried its own copy of the filter would keep passing after someone
    removed the real one.
    """
    text = MODEL.read_text(encoding="utf-8")
    body = text.split("JINJA_STATEMENT_BEGIN", 1)[0]
    body = body.split("\n);\n", 1)[1]
    return body.strip().rstrip(";").strip()


@pytest.fixture
def transformed(db: psycopg.Connection[DictRow]) -> psycopg.Connection[DictRow]:
    db.execute((FIXTURES / "raw.sql").read_text(encoding="utf-8"))
    db.execute("DROP TABLE IF EXISTS core.decisao_transformada")
    db.execute(f"CREATE TABLE core.decisao_transformada AS {transformation()}")
    return db


def identifiers(db: psycopg.Connection[DictRow]) -> set[str]:
    with db.cursor() as cursor:
        cursor.execute("SELECT identificador_fonte FROM core.decisao_transformada")
        return {row["identificador_fonte"] for row in cursor.fetchall()}


def test_the_fixture_actually_contains_sealed_records(
    db: psycopg.Connection[DictRow],
) -> None:
    db.execute((FIXTURES / "raw.sql").read_text(encoding="utf-8"))

    with db.cursor() as cursor:
        cursor.execute(
            'SELECT COUNT(*) AS total FROM raw.acordao_tjdft WHERE "segredoJustica"'
        )
        row = cursor.fetchone()

    assert row is not None
    assert row["total"] == len(SEALED)


def test_no_sealed_record_survives_the_transformation(
    transformed: psycopg.Connection[DictRow],
) -> None:
    assert identifiers(transformed) & SEALED == set()


def test_every_open_record_survives_the_transformation(
    transformed: psycopg.Connection[DictRow],
) -> None:
    assert identifiers(transformed) == OPEN


def test_a_record_with_no_seal_flag_is_treated_as_open(
    transformed: psycopg.Connection[DictRow],
) -> None:
    assert "9000006" in identifiers(transformed)


def test_a_sealed_record_cannot_be_found_by_searching_its_own_words(
    transformed: psycopg.Connection[DictRow],
) -> None:
    with transformed.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*) AS total FROM core.decisao_transformada
            WHERE ementa_busca @@ websearch_to_tsquery(
                'portugues_sem_acento', 'estupro de vulneravel'
            )
            """
        )
        row = cursor.fetchone()

    assert row is not None
    assert row["total"] == 0


def test_removing_the_filter_would_let_a_sealed_record_through(
    db: psycopg.Connection[DictRow],
) -> None:
    """
    Guards the guard: if this ever fails, the fixture stopped exercising the
    filter and the tests above would pass for the wrong reason.
    """
    db.execute((FIXTURES / "raw.sql").read_text(encoding="utf-8"))
    without_filter = transformation().replace(
        'WHERE NOT COALESCE("segredoJustica", FALSE)', ""
    )

    db.execute("DROP TABLE IF EXISTS core.decisao_sem_filtro")
    db.execute(f"CREATE TABLE core.decisao_sem_filtro AS {without_filter}")

    with db.cursor() as cursor:
        cursor.execute("SELECT identificador_fonte FROM core.decisao_sem_filtro")
        found = {row["identificador_fonte"] for row in cursor.fetchall()}

    assert found & SEALED == SEALED


def test_the_model_still_carries_the_filter(db: psycopg.Connection[DictRow]) -> None:
    assert 'WHERE NOT COALESCE("segredoJustica", FALSE)' in transformation()
