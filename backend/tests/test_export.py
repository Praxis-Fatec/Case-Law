"""Export collection agrees with the search without inheriting its page size."""

from collections.abc import Iterator
from datetime import date
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import IsolationLevel
from psycopg.rows import DictRow

from app.config import settings
from app.export import ExportRefused, collect_export
from tests.conftest import TEST_DATABASE_URL, needs_database

pytestmark = needs_database


@pytest.fixture
def collection(
    db_rolled_back: psycopg.Connection[DictRow],
) -> Iterator[psycopg.Connection[DictRow]]:
    db_rolled_back.isolation_level = IsolationLevel.REPEATABLE_READ
    db_rolled_back.execute("DELETE FROM core.decisao")
    db_rolled_back.execute(
        """INSERT INTO core.decisao (
            fonte_codigo, identificador_fonte, tribunal_sigla, processo,
            data_referencia, data_julgamento, data_publicacao, ementa,
            orgao_julgador, relator, classe_cnj, resultado,
            turma_recursal, possui_inteiro_teor, url_fonte, link_valido, ementa_busca
        ) SELECT 'export-test', n::text, 'STJ', 'processo-' || n,
            '2024-01-01'::date + n % 3, '2024-01-01'::date + n % 3,
            '2024-02-01'::date, text, 'TURMA A', 'RELATOR A', 198, 'provido',
            FALSE, FALSE, 'https://example.test/' || n, TRUE,
            to_tsvector('portugues_sem_acento', text)
        FROM generate_series(1, 18) n
        CROSS JOIN LATERAL (
            SELECT CASE WHEN n % 2 = 0 THEN 'Dano moral. Dano moral.'
                        ELSE 'Dano moral. Outros fundamentos e explicações.' END AS text
        ) e"""
    )
    # The same identifier in another source is a different decision.
    db_rolled_back.execute(
        """INSERT INTO core.decisao
        SELECT 'export-other', identificador_fonte, tribunal_sigla, processo,
            orgao_julgador, relator, classe_cnj, data_julgamento, data_publicacao,
            data_referencia, ementa, tipo_texto, decisao_texto, resultado,
            deliberacao, turma_recursal, possui_inteiro_teor, url_fonte,
            link_valido, ementa_busca
        FROM core.decisao WHERE identificador_fonte = '1'"""
    )
    yield db_rolled_back


@pytest.mark.parametrize("order", ["relevance", "date"])
def test_collects_every_page_in_the_same_stable_order_as_the_search(
    client: TestClient, collection: psycopg.Connection[DictRow], order: Any
) -> None:
    expected = []
    for page in range(1, 5):
        response = client.get(
            "/decisions", params={"q": "dano moral", "order": order, "page": page}
        )
        assert response.status_code == 200
        expected.extend(response.json()["results"])
    exported = collect_export(collection, "dano moral", order=order)
    assert exported.total == len(exported.decisions) == len(expected) == 19
    assert exported.order == order
    assert exported.query == "dano moral"
    assert all("Dano" in row["snippet"] for row in exported.decisions)
    assert [
        (r["fonte_codigo"], r["identificador_fonte"]) for r in exported.decisions
    ] == [(r["source"], r["identifier"]) for r in expected]
    assert (
        len({(r["fonte_codigo"], r["identificador_fonte"]) for r in exported.decisions})
        == 19
    )


@pytest.mark.parametrize(
    ("column", "wrong"),
    [
        ("tribunal_sigla", "TJDFT"),
        ("orgao_julgador", "OUTRA TURMA"),
        ("relator", "OUTRO RELATOR"),
        ("classe_cnj", 213),
        ("resultado", "negado"),
        ("data_referencia", date(2024, 1, 4)),
        ("data_publicacao", date(2024, 2, 2)),
    ],
)
def test_composes_all_search_filters_before_collecting(
    client: TestClient,
    collection: psycopg.Connection[DictRow],
    column: str,
    wrong: Any,
) -> None:
    from psycopg import sql

    collection.execute(
        sql.SQL(
            "UPDATE core.decisao SET {} = %s WHERE identificador_fonte = '1'"
        ).format(sql.Identifier(column)),
        (wrong,),
    )
    params: dict[str, Any] = {
        "q": "dano moral",
        "tribunal": ["STJ", "STJ"],
        "orgao_julgador": ["TURMA A"],
        "relator": ["RELATOR A"],
        "classe_cnj": [198],
        "resultado": ["provido", "provido"],
        "date_from": date(2024, 1, 1),
        "date_to": date(2024, 1, 3),
        "published_from": date(2024, 2, 1),
        "published_to": date(2024, 2, 1),
        "order": "date",
    }
    response = client.get("/decisions", params={**params, "page_size": 100})
    assert response.status_code == 200
    result = collect_export(collection, **params)
    assert result.total == len(result.decisions) == response.json()["total"] == 17
    assert all(row["identificador_fonte"] != "1" for row in result.decisions)
    assert result.query == params["q"]
    assert result.filters == {
        "tribunais": ["STJ"],
        "orgao_julgador": ["TURMA A"],
        "relator": ["RELATOR A"],
        "classe_cnj": [198],
        "resultado": ["provido"],
        "date_from": date(2024, 1, 1),
        "date_to": date(2024, 1, 3),
        "published_from": date(2024, 2, 1),
        "published_to": date(2024, 2, 1),
    }


def recorded_queries(
    monkeypatch: pytest.MonkeyPatch,
) -> list[str]:
    queries: list[str] = []
    original = psycopg.Connection.execute

    def execute(self: Any, query: Any, params: Any = None, **kwargs: Any) -> Any:
        queries.append(str(query))
        return original(self, query, params, **kwargs)

    monkeypatch.setattr(psycopg.Connection, "execute", execute)
    return queries


@pytest.mark.parametrize(("limit", "code"), [(18, "limit_exceeded"), (1000, "empty")])
def test_refuses_before_reading_or_sorting_references(
    collection: psycopg.Connection[DictRow],
    monkeypatch: pytest.MonkeyPatch,
    limit: int,
    code: str,
) -> None:
    monkeypatch.setattr(settings, "export_max_decisions", limit)
    queries = recorded_queries(monkeypatch)
    with pytest.raises(ExportRefused) as failure:
        collect_export(
            collection, "dano moral" if code == "limit_exceeded" else "inexistente"
        )
    assert failure.value.code == code
    assert failure.value.limit == limit
    assert failure.value.total == (19 if code == "limit_exceeded" else 0)
    if code == "limit_exceeded":
        assert "19" in str(failure.value) and "18" in str(failure.value)
        assert "filters" in str(failure.value)
    assert any("COUNT(*)" in query for query in queries)
    assert not any("ORDER BY" in query or "ts_rank" in query for query in queries)


def test_accepts_exactly_the_limit_and_retains_reference_metadata(
    collection: psycopg.Connection[DictRow],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "export_max_decisions", 19)
    collection.execute(
        "UPDATE core.decisao SET relator = NULL, link_valido = FALSE "
        "WHERE identificador_fonte = '1'"
    )
    result = collect_export(collection, "dano moral")
    assert result.total == len(result.decisions) == 19
    missing = [row for row in result.decisions if row["identificador_fonte"] == "1"]
    assert len(missing) == 2
    assert all(
        row["relator"] is None and row["link_valido"] is False for row in missing
    )


@pytest.mark.parametrize("size", [1000, 1001])
def test_one_thousand_is_complete_and_one_thousand_and_one_is_refused(
    collection: psycopg.Connection[DictRow],
    size: int,
) -> None:
    collection.execute(
        """INSERT INTO core.decisao (
            fonte_codigo, identificador_fonte, tribunal_sigla, data_referencia,
            ementa, turma_recursal, possui_inteiro_teor, url_fonte, ementa_busca
        ) SELECT 'export-large', n::text, 'STJ', '2024-01-01', 'Amostra exportável',
            FALSE, FALSE, 'https://example.test/' || n,
            to_tsvector('portugues_sem_acento', 'Amostra exportável')
        FROM generate_series(1, %s) n""",
        (size,),
    )
    if size > 1000:
        with pytest.raises(ExportRefused) as failure:
            collect_export(collection, "amostra exportável")
        assert failure.value.code == "limit_exceeded"
        assert failure.value.total == 1001
        assert failure.value.limit == 1000
        return
    result = collect_export(collection, "amostra exportável")
    assert result.total == len(result.decisions) == 1000
    assert {row["identificador_fonte"] for row in result.decisions} == {
        str(n) for n in range(1, 1001)
    }


def test_idle_connection_owns_a_read_only_snapshot(
    db: psycopg.Connection[DictRow],
) -> None:
    result = collect_export(db, "dano moral")
    assert result.total == len(result.decisions) > 0
    assert db.info.transaction_status == psycopg.pq.TransactionStatus.IDLE


def test_active_read_committed_transaction_cannot_mix_two_snapshots(
    db_rolled_back: psycopg.Connection[DictRow],
) -> None:
    db_rolled_back.execute("SELECT 1")
    with pytest.raises(ValueError, match="repeatable snapshot"):
        collect_export(db_rolled_back, "dano moral")


def test_concurrent_publication_cannot_change_the_counted_set(
    db: psycopg.Connection[DictRow],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = psycopg.Connection.execute
    inserted = False
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as writer:

        def execute(self: Any, query: Any, params: Any = None, **kwargs: Any) -> Any:
            nonlocal inserted
            cursor = original(self, query, params, **kwargs)
            if self is db and "SELECT COUNT(*)" in str(query):
                writer.execute(
                    """INSERT INTO core.decisao (
                        fonte_codigo, identificador_fonte, tribunal_sigla,
                        data_referencia, ementa, turma_recursal,
                        possui_inteiro_teor, url_fonte, ementa_busca
                    ) VALUES ('export-concurrent', 'after-count', 'TJDFT',
                        '2024-01-01', 'Dano moral', FALSE, FALSE,
                        'https://example.test/after-count',
                        to_tsvector('portugues_sem_acento', 'Dano moral'))"""
                )
                inserted = True
            return cursor

        monkeypatch.setattr(psycopg.Connection, "execute", execute)
        try:
            result = collect_export(db, "dano moral")
            assert inserted, "the publication must commit between count and read"
            assert result.total == len(result.decisions)
            assert all(
                row["fonte_codigo"] != "export-concurrent" for row in result.decisions
            )
        finally:
            writer.execute(
                "DELETE FROM core.decisao WHERE fonte_codigo = 'export-concurrent'"
            )
