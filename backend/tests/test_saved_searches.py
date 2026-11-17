"""Saved searches are scoped to their authenticated owner, against PostgreSQL."""

from collections.abc import Iterator
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from app.api.searches import NOT_FOUND
from app.db import get_connection
from app.main import app
from app.sessions import PUBLIC_PATHS, gate
from tests.conftest import needs_database
from tests.test_contas import header, manager, member

pytestmark = needs_database

PAYLOAD = {
    "name": "Dano moral",
    "filters": {
        "q": '"dano moral" -tributário',
        "tribunal": ["STJ", "TJDFT"],
        "orgao_julgador": ["CORTE ESPECIAL"],
        "relator": ["ANA CANTARINO"],
        "classe_cnj": [198, 213],
        "resultado": ["negado"],
        "date_from": "2026-01-01",
        "date_to": "2026-12-31",
        "published_from": "2026-02-01",
        "published_to": "2026-11-30",
        "orgao_julgador_excluido": ["TURMA A"],
        "relator_excluido": ["OUTRO RELATOR"],
        "future_filter": {"enabled": True, "values": [1, None]},
    },
}


@pytest.fixture
def client(db_rolled_back: psycopg.Connection[DictRow]) -> Iterator[TestClient]:
    # Ownership is part of the contract, so authentication stays real here.
    app.dependency_overrides.pop(gate, None)
    app.dependency_overrides[get_connection] = lambda: db_rolled_back
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def people(db_rolled_back: psycopg.Connection[DictRow]) -> list[dict[str, Any]]:
    boss = manager(db_rolled_back)
    return [boss, member(db_rolled_back, boss)]


def save(
    client: TestClient, person: dict[str, Any], payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    response = client.post("/searches", headers=header(person), json=payload or PAYLOAD)
    assert response.status_code == 201, response.text
    return dict(response.json())


@pytest.mark.parametrize("person_index", [0, 1], ids=["manager", "member"])
def test_create_read_list_and_delete_work_for_the_owner(
    client: TestClient,
    people: list[dict[str, Any]],
    db_rolled_back: psycopg.Connection[DictRow],
    person_index: int,
) -> None:
    person = people[person_index]
    saved = save(client, person)
    assert set(saved) == {"id", "name", "filters", "created_at"}
    assert UUID(saved["id"])
    assert saved["name"] == PAYLOAD["name"]
    assert saved["filters"] == PAYLOAD["filters"]
    assert datetime.fromisoformat(saved["created_at"]).tzinfo is not None
    stored = db_rolled_back.execute(
        "SELECT usuario_id FROM pesquisa.salva WHERE id = %s", (saved["id"],)
    ).fetchone()
    assert stored == {"usuario_id": person["id"]}
    path = f"/searches/{saved['id']}"
    read = client.get(path, headers=header(person))
    assert read.status_code == 200
    assert read.json() == saved
    listed = client.get("/searches", headers=header(person))
    assert listed.status_code == 200
    assert listed.json() == {"searches": [saved]}
    deleted = client.delete(path, headers=header(person))
    assert deleted.status_code == 204
    assert deleted.content == b""
    for method in ("GET", "DELETE"):
        missing = client.request(method, path, headers=header(person))
        assert missing.status_code == 404
        assert missing.json() == {"detail": NOT_FOUND}
    assert client.get("/searches", headers=header(person)).json() == {"searches": []}


def test_the_list_excludes_every_other_person_and_orders_newest_first(
    client: TestClient,
    people: list[dict[str, Any]],
    db_rolled_back: psycopg.Connection[DictRow],
) -> None:
    foreign = save(client, people[0])
    own = [
        save(client, people[1], {**PAYLOAD, "name": name})
        for name in ("Old", "New A", "New B")
    ]
    for index, saved in enumerate(own):
        db_rolled_back.execute(
            "UPDATE pesquisa.salva SET criado_em = %s WHERE id = %s",
            ("2026-01-01" if index == 0 else "2026-02-01", saved["id"]),
        )
    response = client.get("/searches", headers=header(people[1]))
    assert response.status_code == 200
    identifiers = [row["id"] for row in response.json()["searches"]]
    assert identifiers == sorted([row["id"] for row in own[1:]], reverse=True) + [
        own[0]["id"]
    ]
    assert foreign["id"] not in identifiers
    assert client.get("/searches", headers=header(people[0])).json() == {
        "searches": [foreign]
    }


def test_a_person_with_no_saved_searches_sees_an_empty_list_not_someone_elses(
    client: TestClient,
    people: list[dict[str, Any]],
) -> None:
    save(client, people[0])
    response = client.get("/searches", headers=header(people[1]))
    assert response.status_code == 200
    assert response.json() == {"searches": []}


@pytest.mark.parametrize("operation", ["list", "read", "delete"])
def test_people_with_the_same_manager_do_not_share_saved_searches(
    client: TestClient,
    people: list[dict[str, Any]],
    db_rolled_back: psycopg.Connection[DictRow],
    operation: str,
) -> None:
    colleague = member(db_rolled_back, people[0], email="carla@almeidacosta.com.br")
    owners = [*people, colleague]
    # Identical names and filters must not make searches shared. Neither the
    # common manager nor the account's role substitutes for the actual owner.
    saved = [save(client, person) for person in owners]
    assert len({item["id"] for item in saved}) == len(owners)
    for owner_index, person in enumerate(owners):
        for other_index, foreign in enumerate(saved):
            if owner_index == other_index:
                continue
            if operation == "list":
                response = client.get(
                    "/searches",
                    headers=header(person),
                    params={"usuario_id": str(owners[other_index]["id"])},
                )
                assert response.status_code == 200
                assert response.json() == {"searches": [saved[owner_index]]}
            else:
                response = client.request(
                    "GET" if operation == "read" else "DELETE",
                    f"/searches/{foreign['id']}",
                    headers=header(person),
                )
                assert response.status_code == 404
                assert response.json() == {"detail": NOT_FOUND}
    # In particular, forbidden deletes must not erase anyone's search.
    for person, own in zip(owners, saved, strict=True):
        assert client.get("/searches", headers=header(person)).json() == {
            "searches": [own]
        }


def test_delete_removes_only_the_requested_search_from_the_authenticated_owner(
    client: TestClient, people: list[dict[str, Any]]
) -> None:
    foreign = save(client, people[0])
    target = save(client, people[1])
    retained = save(client, people[1])
    response = client.delete(f"/searches/{target['id']}", headers=header(people[1]))
    assert response.status_code == 204
    assert response.content == b""
    assert client.get("/searches", headers=header(people[1])).json() == {
        "searches": [retained]
    }
    assert client.get("/searches", headers=header(people[0])).json() == {
        "searches": [foreign]
    }
    assert (
        client.get(f"/searches/{target['id']}", headers=header(people[1])).status_code
        == 404
    )


@pytest.mark.parametrize("method", ["GET", "DELETE"])
@pytest.mark.parametrize("owner_index", [0, 1], ids=["manager-owner", "member-owner"])
def test_another_persons_search_is_indistinguishable_from_a_missing_search(
    client: TestClient,
    people: list[dict[str, Any]],
    method: str,
    owner_index: int,
) -> None:
    owner, other = people[owner_index], people[1 - owner_index]
    saved = save(client, owner)
    response = client.request(method, f"/searches/{saved['id']}", headers=header(other))
    missing = client.request(method, f"/searches/{uuid4()}", headers=header(other))
    assert response.status_code == missing.status_code == 404
    assert response.json() == missing.json() == {"detail": NOT_FOUND}
    assert response.content == missing.content
    # A failed attempt to read or delete must leave the owner's data intact.
    assert client.get(f"/searches/{saved['id']}", headers=header(owner)).json() == saved


@pytest.mark.parametrize("authentication", ["missing", "invalid", "revoked"])
@pytest.mark.parametrize(
    "method, path",
    [
        ("POST", "/searches"),
        ("GET", "/searches"),
        ("GET", "/searches/{identifier}"),
        ("DELETE", "/searches/{identifier}"),
    ],
)
def test_every_operation_is_behind_the_authentication_gate(
    client: TestClient,
    people: list[dict[str, Any]],
    db_rolled_back: psycopg.Connection[DictRow],
    authentication: str,
    method: str,
    path: str,
) -> None:
    person = people[1]
    saved = save(client, person)
    headers = {} if authentication == "missing" else {"Authorization": "Bearer invalid"}
    if authentication == "revoked":
        headers = header(person)
        db_rolled_back.execute(
            "UPDATE identidade.usuario SET ativo = FALSE, revogado_em = NOW() WHERE id = %s",
            (person["id"],),
        )
    response = client.request(
        method,
        path.format(identifier=saved["id"]),
        headers=headers,
        json=PAYLOAD if method == "POST" else None,
    )
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert "/searches" not in PUBLIC_PATHS
    stored = db_rolled_back.execute(
        "SELECT COUNT(*) AS total FROM pesquisa.salva WHERE usuario_id = %s",
        (person["id"],),
    ).fetchone()
    assert stored == {"total": 1}


@pytest.mark.parametrize(
    "field", ["usuario_id", "user_id", "owner_id", "id", "created_at"]
)
def test_a_caller_cannot_supply_the_owner_or_server_managed_fields(
    client: TestClient,
    people: list[dict[str, Any]],
    field: str,
) -> None:
    response = client.post(
        "/searches",
        headers=header(people[1]),
        json={**PAYLOAD, field: str(people[0]["id"])},
    )
    assert response.status_code == 422
    assert client.get("/searches", headers=header(people[0])).json() == {"searches": []}
    assert client.get("/searches", headers=header(people[1])).json() == {"searches": []}


@pytest.mark.parametrize("name", [None, "", "   ", "x" * 121, "Nome\x00inválido"])
def test_invalid_names_are_rejected_without_saving(
    client: TestClient,
    people: list[dict[str, Any]],
    name: Any,
) -> None:
    response = client.post(
        "/searches", headers=header(people[0]), json={**PAYLOAD, "name": name}
    )
    assert response.status_code == 422
    assert client.get("/searches", headers=header(people[0])).json() == {"searches": []}


@pytest.mark.parametrize(
    "filters",
    [
        None,
        [],
        "dano",
        {},
        {"q": None},
        {"q": 12},
        {"q": "  "},
        {"q": "a"},
        {"q": "da\x00no"},
    ],
)
def test_filters_require_an_object_with_a_usable_expression(
    client: TestClient,
    people: list[dict[str, Any]],
    filters: Any,
) -> None:
    response = client.post(
        "/searches", headers=header(people[0]), json={**PAYLOAD, "filters": filters}
    )
    assert response.status_code == 422
    assert client.get("/searches", headers=header(people[0])).json() == {"searches": []}


def test_the_name_is_trimmed_but_the_expression_and_filters_are_preserved(
    client: TestClient,
    people: list[dict[str, Any]],
) -> None:
    saved = save(client, people[1], {**PAYLOAD, "name": "  Minha pesquisa  "})
    assert saved["name"] == "Minha pesquisa"
    assert saved["filters"] == PAYLOAD["filters"]


def test_searches_can_be_saved_and_resumed_without_a_published_collection(
    client: TestClient,
    people: list[dict[str, Any]],
    db_rolled_back: psycopg.Connection[DictRow],
) -> None:
    db_rolled_back.execute("DROP SCHEMA core CASCADE")
    saved = save(client, people[1])
    path = f"/searches/{saved['id']}"
    assert client.get(path, headers=header(people[1])).json() == saved
    assert client.get("/searches", headers=header(people[1])).json() == {
        "searches": [saved]
    }
    assert client.delete(path, headers=header(people[1])).status_code == 204


def test_the_openapi_contract_documents_private_crud_and_an_empty_delete(
    client: TestClient,
) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert "201" in paths["/searches"]["post"]["responses"]
    for path, method in [
        ("/searches", "get"),
        ("/searches", "post"),
        ("/searches/{identifier}", "get"),
        ("/searches/{identifier}", "delete"),
    ]:
        assert "401" in paths[path][method]["responses"]
    for method in ["get", "delete"]:
        assert "404" in paths["/searches/{identifier}"][method]["responses"]
        assert "403" not in paths["/searches/{identifier}"][method]["responses"]
    assert (
        "content" not in paths["/searches/{identifier}"]["delete"]["responses"]["204"]
    )
