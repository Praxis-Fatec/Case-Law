"""
What the base covers as a whole, run against PostgreSQL.

The panel is read before anyone trusts a search, so the numbers have to come
from the rows rather than from a fixture that agrees with itself.
"""

from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from tests.conftest import needs_database
from tests.test_courts import decide, register

pytestmark = needs_database


def coverage(client: TestClient) -> dict[str, Any]:
    response = client.get("/indicators/coverage")
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def two_courts(
    db_rolled_back: psycopg.Connection[DictRow],
) -> psycopg.Connection[DictRow]:
    """
    One court reaching back years and one holding a single recent month, which
    is the shape the base actually has and the reason each period is reported.
    """
    db_rolled_back.execute("DELETE FROM core.decisao")
    for abbreviation, dates in (
        ("STJ", ("1998-04-02", "2012-07-19", "2026-08-26")),
        ("TRF1", ("2026-09-01", "2026-09-17")),
    ):
        register(db_rolled_back, abbreviation)
        for n, day in enumerate(dates):
            identifier = f"{abbreviation}{n:04d}"
            decide(db_rolled_back, abbreviation, identifier)
            db_rolled_back.execute(
                "UPDATE core.decisao SET data_referencia = %s "
                "WHERE identificador_fonte = %s",
                (day, identifier),
            )
    return db_rolled_back


def test_it_counts_every_decision_in_the_base(
    client: TestClient, two_courts: psycopg.Connection[DictRow]
) -> None:
    body = coverage(client)

    assert body["documents"] == 5
    assert sum(court["documents"] for court in body["courts"]) == body["documents"]


def test_each_court_carries_its_own_period(
    client: TestClient, two_courts: psycopg.Connection[DictRow]
) -> None:
    """
    The reason the panel reports them separately. One court reaching back to
    1998 does not mean the base covers 1998 for the other, and a single span
    over both would say exactly that.
    """
    by_abbreviation = {c["abbreviation"]: c for c in coverage(client)["courts"]}

    assert by_abbreviation["STJ"]["first"] == "1998-04-02"
    assert by_abbreviation["STJ"]["last"] == "2026-08-26"
    assert by_abbreviation["TRF1"]["first"] == "2026-09-01"
    assert by_abbreviation["TRF1"]["last"] == "2026-09-17"


def test_the_span_reaches_from_the_oldest_to_the_newest(
    client: TestClient, two_courts: psycopg.Connection[DictRow]
) -> None:
    body = coverage(client)

    assert body["first"] == "1998-04-02"
    assert body["last"] == "2026-09-17"


def test_the_largest_court_comes_first(
    client: TestClient, two_courts: psycopg.Connection[DictRow]
) -> None:
    assert [c["abbreviation"] for c in coverage(client)["courts"]] == ["STJ", "TRF1"]


def test_an_empty_base_answers_rather_than_fails(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    """A new environment is not a broken one, so it gets an answer."""
    db_rolled_back.execute("DELETE FROM core.decisao")

    body = coverage(client)

    assert body["documents"] == 0
    assert body["courts"] == []
    assert body["first"] is None
    assert body["last"] is None


def test_the_freshness_agrees_with_the_endpoint_that_reports_it(
    client: TestClient, two_courts: psycopg.Connection[DictRow]
) -> None:
    """Both read it from the same place, so they cannot tell different stories."""
    body = coverage(client)
    reported = client.get("/indicators/last-update").json()

    assert body["state"] == reported["state"]
    assert body["updated_at"] == reported["updated_at"]


def test_the_endpoint_is_documented(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/indicators/coverage"]["get"]
    body = operation["responses"]["200"]["content"]["application/json"]["schema"]
    named = schema["components"]["schemas"][body["$ref"].rsplit("/", 1)[-1]]

    assert set(named["properties"]) == {
        "documents",
        "first",
        "last",
        "courts",
        "state",
        "updated_at",
    }
