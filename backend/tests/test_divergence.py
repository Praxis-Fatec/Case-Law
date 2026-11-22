"""The real SQL and HTTP contract, with a test-only approved catalogue."""

from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from app import divergence as rule
from app.db import get_connection
from app.main import app
from app.sessions import gate
from tests.conftest import needs_database
from tests.test_divergence_rule import group

pytestmark = needs_database


@pytest.fixture(autouse=True)
def scoped(
    db_rolled_back: psycopg.Connection[DictRow], monkeypatch: pytest.MonkeyPatch
) -> None:
    db_rolled_back.execute("DELETE FROM core.decisao_precedente")
    db_rolled_back.execute("DELETE FROM core.decisao")
    monkeypatch.setattr(
        rule,
        "load_catalogue",
        lambda: rule.GroupCatalogue(version="test-only", groups=[group()]),
    )


def add(
    db: psycopg.Connection[DictRow],
    panel: str | None,
    values: tuple[int, int, int],
    *,
    unknown: int = 0,
    court: str = "STJ",
    code: int | None = 198,
    prefix: str | None = None,
    date: str = "2026-03-10",
    published: str = "2026-03-15",
    judge: str = "ANA",
    text: str = "Dano moral configurado.",
) -> list[str]:
    ids = []
    base = prefix or f"{court}-{panel}-{code}"
    outcomes = [
        outcome for outcome, count in zip(rule.OUTCOMES, values) for _ in range(count)
    ] + [None] * unknown
    with db.cursor() as cursor:
        cursor.executemany(
            """INSERT INTO core.decisao
            (fonte_codigo, identificador_fonte, tribunal_sigla, orgao_julgador, classe_cnj,
             processo, resultado, data_referencia, data_julgamento, data_publicacao,
             relator, ementa, ementa_busca, turma_recursal, possui_inteiro_teor, url_fonte)
            VALUES ('rf22-fixture',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    TO_TSVECTOR('portugues_sem_acento',%s),FALSE,FALSE,'https://example.test')""",
            [
                (
                    f"{base}-{i + 1}",
                    court,
                    panel,
                    code,
                    f"{base}-{i + 1}",
                    outcome,
                    date,
                    date,
                    published,
                    judge,
                    text,
                    text,
                )
                for i, outcome in enumerate(outcomes)
            ],
        )
    ids = [f"{base}-{i + 1}" for i in range(len(outcomes))]
    return ids


def read(client: TestClient, **params: Any) -> dict[str, Any]:
    response = client.get(
        "/indicators/divergence", params={"q": "dano moral", **params}
    )
    assert response.status_code == 200, response.text
    return dict(response.json())


def test_returns_per_panel_counts_and_signals_only_when_all_gates_pass(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    add(db_rolled_back, "A", (80, 10, 10))
    add(db_rolled_back, "B", (20, 10, 70))
    result = read(client)
    assert result["documents"] == 200 and len(result["panels"]) == 2
    assert result["rule_version"] == "RF22-v1"
    assert result["tested_pairs"] == 1
    pair = result["pairs"][0]
    assert pair["signal"] and pair["reason"] == "difference"
    assert pair["group_id"] == "fixture-only"
    assert pair["statistic"] == 81
    assert pair["adjusted_p"] == pytest.approx(2.576757109154981e-18)
    assert pair["effect"] == 0.6
    assert pair["left"]["processes"] == 100 and pair["left"]["classified"] == 100
    assert result["panels"][0]["outcomes"] == {
        "denied": 80,
        "granted": 10,
        "partially_granted": 10,
    }
    assert result["publication_reference"] is None


@pytest.mark.parametrize("n", [0, 5, 49])
def test_below_the_floor_never_reports_a_p_value_or_signal(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow], n: int
) -> None:
    add(db_rolled_back, "A", (n, 0, 0))
    add(db_rolled_back, "B", (0, 50, 0))
    result = read(client)
    assert not any(p["signal"] for p in result["pairs"])
    assert result["tested_pairs"] == 0
    if n:
        pair = result["pairs"][0]
        assert pair["reason"] == "insufficient_sample"
        assert pair["raw_p"] is None and pair["adjusted_p"] is None
        assert pair["left"]["classified"] == n


def test_50_is_inclusive_and_partial_grant_keeps_its_own_category(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    add(db_rolled_back, "A", (50, 0, 0))
    add(db_rolled_back, "B", (0, 0, 50))
    pair = read(client)["pairs"][0]
    assert pair["signal"]
    assert pair["right"]["outcomes"]["partially_granted"] == 50
    assert pair["right"]["outcomes"]["granted"] == 0
    assert pair["degrees_of_freedom"] == 1


def test_unknown_outcomes_reduce_coverage_instead_of_becoming_denials(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    add(db_rolled_back, "A", (40, 5, 5), unknown=20)
    add(db_rolled_back, "B", (5, 5, 40), unknown=20)
    db_rolled_back.execute(
        "UPDATE core.decisao SET resultado='unexpected' WHERE resultado IS NULL"
    )
    result = read(client)
    assert result["panels"][0]["unknown_documents"] == 20
    pair = result["pairs"][0]
    assert pair["reason"] == "insufficient_coverage" and not pair["signal"]
    assert pair["left"]["unknown"] == 20 and pair["left"]["processes"] == 70
    assert pair["left"]["outcomes"]["denied"] == 40


def test_latest_process_representative_is_selected_before_its_classification(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    ids = add(db_rolled_back, "A", (50, 0, 0))
    add(db_rolled_back, "B", (0, 50, 0))
    duplicate = add(
        db_rolled_back, "A", (0, 0, 0), unknown=1, prefix="newer", date="2026-04-01"
    )[0]
    db_rolled_back.execute(
        "UPDATE core.decisao SET processo=%s WHERE identificador_fonte=%s",
        (ids[0], duplicate),
    )
    result = read(client)
    assert result["panels"][0]["documents"] == 51
    assert result["panels"][0]["repeated_documents"] == 1
    pair = result["pairs"][0]
    assert pair["left"]["processes"] == 50 and pair["left"]["classified"] == 49
    assert pair["left"]["unknown"] == 1 and pair["reason"] == "insufficient_sample"


def test_process_format_normalization_and_shared_cases_are_excluded_from_both_sides(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    a = add(db_rolled_back, "A", (50, 0, 0))
    b = add(db_rolled_back, "B", (0, 50, 0))
    for identity, number in (
        (a[0], "0700001-11.2026.8.07.0001"),
        (b[0], "07000011120268070001"),
    ):
        db_rolled_back.execute(
            "UPDATE core.decisao SET processo=%s WHERE identificador_fonte=%s",
            (number, identity),
        )
    pair = read(client)["pairs"][0]
    assert (
        pair["left"]["shared_processes_excluded"]
        == pair["right"]["shared_processes_excluded"]
        == 1
    )
    assert pair["left"]["classified"] == pair["right"]["classified"] == 49
    assert not pair["signal"]


@pytest.mark.parametrize("number", [None, "", "sem número", "0000000"])
def test_missing_or_unusable_process_identity_is_not_an_observation(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow], number: str | None
) -> None:
    ids = add(db_rolled_back, "A", (50, 0, 0))
    add(db_rolled_back, "B", (0, 50, 0))
    db_rolled_back.execute(
        "UPDATE core.decisao SET processo=%s WHERE identificador_fonte=%s",
        (number, ids[0]),
    )
    result = read(client)
    assert result["panels"][0]["missing_process_documents"] == 1
    assert result["pairs"][0]["reason"] == "insufficient_sample"


def test_documents_with_missing_class_or_panel_stay_visible_without_inference(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    add(db_rolled_back, None, (3, 0, 0))
    add(db_rolled_back, "A", (4, 0, 0), code=None)
    result = read(client)
    assert result["documents"] == 7 and result["pairs"] == []
    assert {p["comparison_status"] for p in result["panels"]} == {
        "missing_class",
        "missing_panel",
    }


def test_different_courts_and_classes_cannot_be_pooled_to_meet_the_floor(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    add(db_rolled_back, "A", (30, 0, 0))
    add(db_rolled_back, "B", (0, 30, 0))
    add(db_rolled_back, "A", (30, 0, 0), code=213)
    add(db_rolled_back, "B", (0, 30, 0), code=213)
    add(db_rolled_back, "A", (30, 0, 0), court="TJDFT")
    add(db_rolled_back, "B", (0, 30, 0), court="TJDFT")
    result = read(client)
    assert result["documents"] == 180 and len(result["pairs"]) == 3
    assert not any(p["signal"] for p in result["pairs"])
    assert all(p["left"]["classified"] == 30 for p in result["pairs"])


def test_unapproved_catalogue_cannot_signal(
    client: TestClient,
    db_rolled_back: psycopg.Connection[DictRow],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    add(db_rolled_back, "A", (100, 0, 0))
    add(db_rolled_back, "B", (0, 100, 0))
    monkeypatch.setattr(
        rule,
        "load_catalogue",
        lambda: rule.GroupCatalogue(version="unapproved", groups=[]),
    )
    pair = read(client)["pairs"][0]
    assert (
        pair["reason"] == "unvalidated_group"
        and pair["raw_p"] is None
        and not pair["signal"]
    )


@pytest.mark.parametrize(
    "params",
    [
        {"tribunal": "TJDFT"},
        {"orgao_julgador": "B"},
        {"relator": "BRUNO"},
        {"classe_cnj": 213},
        {"date_from": "2026-04-01"},
        {"date_to": "2026-02-01"},
        {"published_from": "2026-04-01"},
        {"published_to": "2026-02-01"},
        {"orgao_julgador_excluido": "A"},
        {"relator_excluido": "ANA"},
        {"q": "penal"},
    ],
)
def test_every_search_filter_is_applied_before_aggregation(
    client: TestClient,
    db_rolled_back: psycopg.Connection[DictRow],
    params: dict[str, Any],
) -> None:
    add(db_rolled_back, "A", (3, 0, 0))
    assert read(client, **params)["documents"] == 0


def test_outcome_filter_is_preserved_and_suppresses_the_test(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    add(db_rolled_back, "A", (80, 10, 10))
    add(db_rolled_back, "B", (20, 10, 70))
    result = read(client, resultado="negado")
    assert result["documents"] == 100 and result["cut"]["resultado"] == ["negado"]
    assert (
        result["pairs"][0]["reason"] == "outcome_filter" and result["tested_pairs"] == 0
    )


def test_same_cut_agrees_with_the_search_count(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    add(db_rolled_back, "A", (4, 1, 0))
    add(db_rolled_back, "B", (1, 4, 0))
    params = {
        "q": "dano moral",
        "tribunal": "STJ",
        "orgao_julgador": "A",
        "date_from": "2026-03-10",
        "date_to": "2026-03-10",
        "published_from": "2026-03-15",
        "published_to": "2026-03-15",
    }
    result = read(client, **params)
    search = client.get("/decisions", params=params)
    assert search.status_code == 200, search.text
    assert result["documents"] == search.json()["total"] == 5
    assert len(result["panels"]) == 1 and result["pairs"] == []


@pytest.mark.parametrize(
    "params,status",
    [
        ({"q": "a"}, 422),
        ({"date_from": "2027-01-01", "date_to": "2026-01-01"}, 400),
        ({"published_from": "2027-01-01", "published_to": "2026-01-01"}, 400),
        ({"date_from": "bad-date"}, 422),
    ],
)
def test_invalid_cuts_are_rejected(
    client: TestClient, params: dict[str, str], status: int
) -> None:
    response = client.get(
        "/indicators/divergence", params={"q": "dano moral", **params}
    )
    assert response.status_code == status


def test_empty_cut_is_an_answer(client: TestClient) -> None:
    result = read(client)
    assert result["documents"] == 0 and result["panels"] == [] and result["pairs"] == []
    assert result["tested_pairs"] == 0


def test_route_requires_authentication(
    db_rolled_back: psycopg.Connection[DictRow],
) -> None:
    app.dependency_overrides.pop(gate, None)
    app.dependency_overrides[get_connection] = lambda: db_rolled_back
    assert (
        TestClient(app)
        .get("/indicators/divergence", params={"q": "dano moral"})
        .status_code
        == 401
    )


def test_broken_catalogue_is_not_an_empty_success(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken() -> rule.GroupCatalogue:
        raise OSError("missing file")

    monkeypatch.setattr(rule, "load_catalogue", broken)
    assert (
        client.get("/indicators/divergence", params={"q": "dano moral"}).status_code
        == 503
    )


def test_holm_includes_all_three_pairs_in_the_same_response(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    add(db_rolled_back, "A", (100, 0, 0))
    add(db_rolled_back, "B", (0, 100, 0))
    add(db_rolled_back, "C", (50, 50, 0))
    result = read(client)
    assert result["tested_pairs"] == 3
    pairs = sorted(result["pairs"], key=lambda item: item["raw_p"])
    assert pairs[0]["adjusted_p"] == pytest.approx(3 * pairs[0]["raw_p"])
    assert pairs[1]["adjusted_p"] == pytest.approx(2 * pairs[1]["raw_p"])
    assert pairs[2]["adjusted_p"] == pytest.approx(pairs[1]["adjusted_p"])
    assert all(item["signal"] for item in pairs)


def test_holm_family_is_not_split_by_court(
    client: TestClient,
    db_rolled_back: psycopg.Connection[DictRow],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approved = group()
    other = approved.model_copy(update={"court": "TJDFT", "id": "other-fixture"})
    monkeypatch.setattr(
        rule,
        "load_catalogue",
        lambda: rule.GroupCatalogue(version="fixture", groups=[approved, other]),
    )
    for court in ("STJ", "TJDFT"):
        add(db_rolled_back, "A", (80, 10, 10), court=court)
        add(db_rolled_back, "B", (20, 10, 70), court=court)
    result = read(client)
    assert result["tested_pairs"] == 2
    for item in result["pairs"]:
        assert item["adjusted_p"] == pytest.approx(2 * item["raw_p"])


def test_representative_tie_uses_the_source_key_not_a_favourable_outcome(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    original = add(db_rolled_back, "A", (50, 0, 0))
    add(db_rolled_back, "B", (0, 50, 0))
    newer = add(db_rolled_back, "A", (0, 0, 0), unknown=1, prefix="tie")[0]
    db_rolled_back.execute(
        "UPDATE core.decisao SET fonte_codigo='zz-fixture', processo=%s WHERE identificador_fonte=%s",
        (original[0], newer),
    )
    item = read(client)["pairs"][0]
    assert item["left"]["unknown"] == 1
    assert item["left"]["classified"] == 49
    assert not item["signal"]


def test_approval_interval_must_cover_all_documents_in_the_pair(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    add(db_rolled_back, "A", (80, 10, 10))
    add(db_rolled_back, "B", (20, 10, 70))
    add(db_rolled_back, "A", (1, 0, 0), prefix="old", date="1989-01-01")
    item = read(client)["pairs"][0]
    assert item["reason"] == "unvalidated_group"
    assert item["raw_p"] is None and not item["signal"]
