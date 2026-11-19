"""Bookmarks belong to accounts and survive a collection replacement."""

from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from app.db import get_connection
from app.main import app
from app.sessions import gate
from tests.conftest import needs_database
from tests.test_contas import header, manager, member

pytestmark = needs_database
KEY = {"source": "tjdft-jurisdf", "identifier": "1000001"}
PATH = "/saved-decisions/tjdft-jurisdf/1000001"


@pytest.fixture
def client(db_rolled_back: psycopg.Connection[DictRow]) -> Iterator[TestClient]:
    app.dependency_overrides.pop(gate, None)
    app.dependency_overrides[get_connection] = lambda: db_rolled_back
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def people(db_rolled_back: psycopg.Connection[DictRow]) -> list[dict[str, Any]]:
    boss = manager(db_rolled_back)
    return [boss, member(db_rolled_back, boss)]


def test_save_list_duplicate_and_remove(
    client: TestClient, people: list[dict[str, Any]]
) -> None:
    auth = header(people[1])
    saved = client.post("/saved-decisions", headers=auth, json=KEY)
    assert saved.status_code == 201, saved.text
    body = saved.json()
    assert body["court"] == "TJDFT"
    assert body["case_number"] == "0700001-11.2026.8.07.0001"
    assert body["available"] is True
    assert "Dano moral" in body["summary"]
    duplicate = client.post("/saved-decisions", headers=auth, json=KEY)
    assert duplicate.json() == body
    assert client.get("/saved-decisions", headers=auth).json() == {"decisions": [body]}
    assert client.delete(PATH, headers=auth).status_code == 204
    assert client.get("/saved-decisions", headers=auth).json() == {"decisions": []}


def test_accounts_cannot_list_or_delete_each_others_bookmarks(
    client: TestClient, people: list[dict[str, Any]]
) -> None:
    client.post(
        "/saved-decisions", headers=header(people[1]), json=KEY
    ).raise_for_status()
    # Even a manager cannot reach a member's bookmarks.
    auth = header(people[0])
    assert client.get("/saved-decisions", headers=auth).json() == {"decisions": []}
    foreign = client.delete(PATH, headers=auth)
    missing = client.delete("/saved-decisions/absent/absent", headers=auth)
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()
    assert (
        len(
            client.get("/saved-decisions", headers=header(people[1])).json()[
                "decisions"
            ]
        )
        == 1
    )


def test_bookmark_survives_core_replacement(
    client: TestClient,
    people: list[dict[str, Any]],
    db_rolled_back: psycopg.Connection[DictRow],
) -> None:
    auth = header(people[0])
    saved = client.post("/saved-decisions", headers=auth, json=KEY).json()
    db_rolled_back.execute("ALTER SCHEMA core RENAME TO core_bookmark_test")
    db_rolled_back.execute("CREATE SCHEMA core")
    db_rolled_back.execute(
        "CREATE TABLE core.decisao (LIKE core_bookmark_test.decisao INCLUDING ALL)"
    )
    listed = client.get("/saved-decisions", headers=auth)
    assert listed.status_code == 200, listed.text
    assert listed.json() == {"decisions": [{**saved, "available": False}]}
    assert client.delete(PATH, headers=auth).status_code == 204


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("GET", "/saved-decisions", None),
        ("POST", "/saved-decisions", KEY),
        ("DELETE", PATH, None),
    ],
)
def test_requires_authentication(
    client: TestClient, method: str, path: str, payload: dict[str, str] | None
) -> None:
    assert client.request(method, path, json=payload).status_code == 401


def test_missing_decision_and_forged_owner(
    client: TestClient, people: list[dict[str, Any]]
) -> None:
    auth = header(people[0])
    assert (
        client.post(
            "/saved-decisions",
            headers=auth,
            json={"source": "absent", "identifier": "absent"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/saved-decisions",
            headers=auth,
            json={**KEY, "usuario_id": str(people[1]["id"])},
        ).status_code
        == 422
    )
