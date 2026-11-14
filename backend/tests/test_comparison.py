"""Court-local denominators and the same cut as search, against PostgreSQL."""

from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from tests.conftest import needs_database
from tests.test_aderencia_api import cite
from tests.test_courts import decide, register

pytestmark = needs_database


@pytest.fixture(autouse=True)
def compared(db_rolled_back: psycopg.Connection[DictRow]) -> None:
    db_rolled_back.execute("DELETE FROM core.decisao_precedente")
    db_rolled_back.execute("DELETE FROM core.decisao")
    register(db_rolled_back, "STJ")
    register(db_rolled_back, "TRF1")
    for court, identifier, outcome, deliberation in (
        ("STJ", "a", "negado", "unanime"),
        ("STJ", "b", None, None),
        ("TJDFT", "c", "provido", "maioria"),
    ):
        decide(db_rolled_back, court, identifier)
        db_rolled_back.execute(
            "UPDATE core.decisao SET resultado = %s, deliberacao = %s, "
            "orgao_julgador = %s, relator = %s, classe_cnj = 198, "
            "data_publicacao = '2026-03-12' WHERE identificador_fonte = %s",
            (
                outcome,
                deliberation,
                f"body-{identifier}",
                f"judge-{identifier}",
                identifier,
            ),
        )
    cite(db_rolled_back, "a", 7, "seguiu", source="stj-teste")
    cite(db_rolled_back, "a", 83, "seguiu", source="stj-teste")
    cite(db_rolled_back, "a", 999, "afastou", source="stj-teste")
    cite(db_rolled_back, "c", 7, "indeterminado", source="tjdft-teste")


def comparison(client: TestClient, **params: Any) -> dict[str, Any]:
    response = client.get(
        "/indicators/comparison", params={"q": "dano moral", **params}
    )
    assert response.status_code == 200, response.text
    return dict(response.json())


def category(
    court: dict[str, Any], indicator: str, value: str | None
) -> dict[str, Any]:
    return next(item for item in court[indicator] if item["value"] == value)


def test_each_court_uses_its_complete_cut_as_denominator(client: TestClient) -> None:
    body = comparison(client)
    courts = {court["abbreviation"]: court for court in body["courts"]}
    assert body["total"] == 3
    assert courts["STJ"]["total"] == 2
    assert courts["TJDFT"]["total"] == 1
    for indicator, value in (
        ("outcomes", "negado"),
        ("deliberations", "unanime"),
        ("adherences", "seguiu"),
    ):
        assert category(courts["STJ"], indicator, value) == {
            "value": value,
            "decisions": 1,
            "share": 50.0,
        }
    assert category(courts["TJDFT"], "outcomes", "provido")["share"] == 100.0
    assert category(courts["TJDFT"], "adherences", "indeterminado")["share"] == 100.0
    for indicator in ("outcomes", "deliberations", "adherences"):
        assert category(courts["STJ"], indicator, None)["decisions"] == 1


def test_citations_do_not_multiply_decisions(client: TestClient) -> None:
    court = comparison(client, tribunal="STJ")["courts"][0]
    assert court["total"] == 2
    assert category(court, "adherences", "seguiu")["decisions"] == 1
    assert category(court, "adherences", "afastou")["decisions"] == 1
    assert sum(item["decisions"] for item in court["outcomes"]) == 2
    assert sum(item["decisions"] for item in court["deliberations"]) == 2


@pytest.mark.parametrize(
    "params", [{}, {"q": "zzzzinexistente"}, {"date_from": "2030-01-01"}]
)
def test_zero_count_courts_remain_present(
    client: TestClient, params: dict[str, Any]
) -> None:
    body = comparison(client, **params)
    courts = {court["abbreviation"]: court for court in body["courts"]}
    assert list(courts) == ["STJ", "TJDFT", "TRF1"]
    assert courts["TRF1"]["total"] == 0
    for indicator in ("outcomes", "deliberations", "adherences"):
        assert courts["TRF1"][indicator]
        assert all(
            item["decisions"] == item["share"] == 0
            for item in courts["TRF1"][indicator]
        )
    if params:
        assert body["total"] == 0
        assert all(court["total"] == 0 for court in courts.values())


def test_court_selection_is_normalized_and_retains_empty_columns(
    client: TestClient,
) -> None:
    body = comparison(client, tribunal=[" STJ ", "STJ", "", "TRF1", "UNKNOWN"])
    assert [court["abbreviation"] for court in body["courts"]] == [
        "STJ",
        "TRF1",
        "UNKNOWN",
    ]
    assert [court["total"] for court in body["courts"]] == [2, 0, 0]


def test_court_without_seed_keeps_its_counts_and_name_fallback(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    db_rolled_back.execute("DELETE FROM core.tribunal WHERE sigla = 'STJ'")
    court = comparison(client, tribunal="STJ")["courts"][0]
    assert court["name"] == "STJ"
    assert court["total"] == 2


def test_empty_collection_retains_registered_courts(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    db_rolled_back.execute("DELETE FROM core.decisao_precedente")
    db_rolled_back.execute("DELETE FROM core.decisao")
    body = comparison(client)
    assert body["total"] == 0
    assert [court["abbreviation"] for court in body["courts"]] == [
        "STJ",
        "TJDFT",
        "TRF1",
    ]


@pytest.mark.parametrize(
    "params, status",
    [
        ({}, 422),
        ({"q": "a"}, 422),
        ({"q": "dano", "date_from": "invalid"}, 422),
        ({"q": "dano", "date_from": "2026-02-02", "date_to": "2026-02-01"}, 400),
        (
            {"q": "dano", "published_from": "2026-02-02", "published_to": "2026-02-01"},
            400,
        ),
    ],
)
def test_invalid_searches_use_the_existing_error_contract(
    client: TestClient, params: dict[str, Any], status: int
) -> None:
    assert client.get("/indicators/comparison", params=params).status_code == status


@pytest.mark.parametrize(
    "params",
    [
        {"orgao_julgador": ["body-a"]},
        {"relator": ["judge-c"]},
        {"classe_cnj": [213]},
        {"resultado": ["negado"]},
        {"date_from": "2026-03-11"},
        {"date_to": "2026-03-09"},
        {"published_from": "2026-03-13"},
        {"published_to": "2026-03-11"},
        {"orgao_julgador_excluido": ["body-a"]},
        {"relator_excluido": ["judge-c"]},
        {
            "tribunal": ["STJ", "TJDFT"],
            "orgao_julgador": ["body-a"],
            "relator": ["judge-a"],
            "classe_cnj": [198],
            "resultado": ["negado"],
            "date_from": "2026-03-10",
            "date_to": "2026-03-10",
            "published_from": "2026-03-12",
            "published_to": "2026-03-12",
        },
    ],
)
def test_filters_match_each_equivalent_search(
    client: TestClient, params: dict[str, Any]
) -> None:
    body = comparison(client, **params)
    for court in body["courts"]:
        searched = client.get(
            "/decisions",
            params={
                "q": "dano moral",
                **params,
                "tribunal": court["abbreviation"],
            },
        )
        assert searched.status_code == 200, searched.text
        assert court["total"] == searched.json()["total"]
    assert body["total"] == sum(court["total"] for court in body["courts"])
