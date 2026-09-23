"""
The indicators, starting with how recent the data is.

A reader has to know the age of the collection before drawing a conclusion from
it, so this is as much a part of the answer as the decisions are.
"""

from collections.abc import Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from app.db import get_connection
from app.main import app
from tests.conftest import needs_database

pytestmark = needs_database


@pytest.fixture
def client(db: psycopg.Connection[DictRow]) -> Iterator[TestClient]:
    app.dependency_overrides[get_connection] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_it_answers_with_the_last_successful_load(
    client: TestClient, db: psycopg.Connection[DictRow]
) -> None:
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT concluida_em, registros_gravados FROM core.carga "
            "WHERE status = 'concluida' ORDER BY concluida_em DESC LIMIT 1"
        )
        row = cursor.fetchone()

    assert row is not None
    body = client.get("/indicators/last-update").json()

    assert body["updated_at"].startswith(row["concluida_em"].date().isoformat())
    assert body["records"] == row["registros_gravados"]


def test_the_date_is_the_most_recent_one_not_just_any(
    client: TestClient, db: psycopg.Connection[DictRow]
) -> None:
    """
    Ordering by the wrong column, or not ordering at all, gives whichever row
    PostgreSQL happens to return first — right on a small table, wrong later.
    """
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT max(concluida_em) AS latest FROM core.carga "
            "WHERE status = 'concluida'"
        )
        row = cursor.fetchone()

    assert row is not None
    body = client.get("/indicators/last-update").json()

    assert body["updated_at"].startswith(row["latest"].date().isoformat())


def test_it_reads_the_data_that_travelled_with_the_decisions(
    client: TestClient,
) -> None:
    """
    The date comes from the load record published alongside the decisions, not
    from the clock of the machine answering. A server that has not been
    refreshed must keep reporting its own older date.
    """
    from app.api.indicators import LAST_LOAD_SQL

    assert "core.carga" in LAST_LOAD_SQL
    assert "NOW()" not in LAST_LOAD_SQL.upper()
