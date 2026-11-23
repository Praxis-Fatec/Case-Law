"""
The state of each source and the date of its last collection — RF16.

The question behind it is whether a reader can trust the scope, and the four
answers that matter are the ones a single date cannot give: a source collected
and still being collected, one collected and then failing, one that has never
been collected, and one that can no longer be collected at all.

Every test here goes through the endpoint against PostgreSQL. The states are
built by changing the load record rather than by stubbing, because the states
are a reading of that record and a stub would prove the reading of a stub.
"""

from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from app.db import get_connection
from app.main import app
from tests.conftest import needs_database

pytestmark = needs_database


@pytest.fixture
def client(db_rolled_back: psycopg.Connection[DictRow]) -> Iterator[TestClient]:
    app.dependency_overrides[get_connection] = lambda: db_rolled_back
    yield TestClient(app)
    app.dependency_overrides.clear()


def _by_code(client: TestClient) -> dict[str, dict[str, Any]]:
    answer = client.get("/indicators/sources")

    assert answer.status_code == 200, answer.text
    return {source["code"]: source for source in answer.json()}


def test_every_source_in_the_catalogue_answers(client: TestClient) -> None:
    """
    Four sources, four rows. A source missing from the list reads as a source
    that does not exist, and "this connector has never run" is the answer RF16
    exists to give.
    """
    assert _by_code(client).keys() == {
        "tjdft-jurisdf",
        "stj-espelhos",
        "stj-precedentes",
        "stj-bdjur",
    }


def test_a_collected_source_carries_its_date_and_period(
    client: TestClient,
) -> None:
    jurisdf = _by_code(client)["tjdft-jurisdf"]

    assert jurisdf["state"] == "loaded"
    assert jurisdf["last_collection"].startswith("2026-03-17")
    assert jurisdf["items"] == 9
    assert jurisdf["first"] == "2026-02-02"
    assert jurisdf["last"] == "2026-03-11"
    assert jurisdf["precision"] == "dia"


def test_a_failed_attempt_does_not_become_the_collection_date(
    client: TestClient,
) -> None:
    """
    The JurisDF's last attempt failed, after two that finished. A reader has to
    see both: the data is from the 17th, and something has been broken since
    the 18th. Reporting only the newest date would date the data to a run that
    wrote nothing; reporting only the newest success would hide the breakage.
    """
    jurisdf = _by_code(client)["tjdft-jurisdf"]

    assert jurisdf["last_collection"].startswith("2026-03-17")
    assert jurisdf["last_attempt"].startswith("2026-03-18")
    assert jurisdf["last_attempt_failed"] is True


def test_a_healthy_source_reports_its_attempt_as_its_collection(
    client: TestClient,
) -> None:
    bdjur = _by_code(client)["stj-bdjur"]

    assert bdjur["last_collection"] == bdjur["last_attempt"]
    assert bdjur["last_attempt_failed"] is False


def test_a_source_never_collected_says_so(client: TestClient) -> None:
    """
    No load has ever been attributed to the precedent connector. It answers
    `never_loaded` with no date and no period — not an empty row, which would
    read as a source whose dates we lost.
    """
    precedentes = _by_code(client)["stj-precedentes"]

    assert precedentes["state"] == "never_loaded"
    assert precedentes["last_collection"] is None
    assert precedentes["last_attempt"] is None
    assert precedentes["last_attempt_failed"] is False
    assert precedentes["items"] == 0
    assert precedentes["first"] is None
    assert precedentes["precision"] == "nenhuma"


def test_a_source_whose_every_load_failed_is_not_a_source_never_loaded(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    """
    One is a connector to go and look at; the other is a connector nobody has
    turned on. Collapsing them would send somebody debugging a source that was
    never configured, or leave a broken one looking new.
    """
    db_rolled_back.execute(
        "UPDATE core.carga SET status = 'falhou' WHERE fonte_codigo = 'stj-bdjur'"
    )

    bdjur = _by_code(client)["stj-bdjur"]

    assert bdjur["state"] == "all_loads_failed"
    assert bdjur["last_collection"] is None
    assert bdjur["last_attempt"].startswith("2026-01-05")
    assert bdjur["last_attempt_failed"] is True


def test_a_blocked_source_keeps_what_it_delivered(client: TestClient) -> None:
    """
    The BDJur refuses automated access since October 2026. That is a decision
    of the library's, not a fault of the collection: the works already
    collected are still there, and the period still means what it meant.
    """
    bdjur = _by_code(client)["stj-bdjur"]

    assert bdjur["availability"] == "bloqueada"
    assert bdjur["state"] == "loaded"
    assert bdjur["items"] == 2


def test_the_year_only_source_declares_annual_precision(
    client: TestClient,
) -> None:
    """
    The BDJur publishes a year. The date carries a 1 January that nobody
    published, so the precision travels with it and the screen writes the year
    alone — RF16 forbids replacing an unknown date with an estimated one.
    """
    bdjur = _by_code(client)["stj-bdjur"]

    assert bdjur["precision"] == "ano"
    assert bdjur["first"] == "1953-01-01"
    assert bdjur["last"] == "2026-01-01"


def test_an_undated_item_is_counted_rather_than_hidden(
    client: TestClient,
) -> None:
    espelhos = _by_code(client)["stj-espelhos"]

    assert espelhos["items"] == 4
    assert espelhos["undated_items"] == 1
    assert espelhos["first"] == "1989-02-19"


def test_a_load_belonging_to_no_source_changes_no_source(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    """
    A run that wrote nothing cannot be attributed: the four collections share
    one dlt pipeline, and `_dlt_loads` does not record which of them ran. The
    date of such a run must not land under a source that may not have run at
    all, so it is excluded — and moving it later proves the exclusion holds.
    """
    before = _by_code(client)

    db_rolled_back.execute(
        "UPDATE core.carga SET concluida_em = '2027-01-01 00:00:00+00'"
        " WHERE fonte_codigo IS NULL"
    )

    assert _by_code(client) == before


def test_the_largest_source_comes_first(client: TestClient) -> None:
    """
    Ordered by what each delivered, so the scope is read before the footnotes.
    A source with nothing is last rather than absent.
    """
    answer = client.get("/indicators/sources").json()

    assert [source["code"] for source in answer] == [
        "tjdft-jurisdf",
        "stj-espelhos",
        "stj-bdjur",
        "stj-precedentes",
    ]


def test_the_coverage_endpoint_still_answers_without_the_new_table(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    """
    The reason the sources are a separate endpoint. An environment serving a
    publication older than this code has no `core.cobertura_fonte`, and the
    scope it does have is still worth answering: coverage keeps working and
    only the source list reports that it cannot be read.
    """
    db_rolled_back.execute("DROP TABLE core.cobertura_fonte")

    assert client.get("/indicators/coverage").status_code == 200
    assert client.get("/indicators/sources").status_code == 503
