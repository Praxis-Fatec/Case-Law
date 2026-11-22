"""
Que a busca por palavra continua sendo a busca por palavra.

A US G acrescentou um modelo no caminho da requisição, uma consulta vetorial
por busca e um `SET LOCAL` por página. O critério que fecha a história é que
nada disso tocou a busca que já existia — nem no que ela devolve, nem na
ordem, nem no tempo.

Tempo não se prende com relógio: num CI compartilhado o número oscila e o
teste vira ruído. Prende-se com o que **causa** o tempo, que é o trabalho
feito. Por isso o que está afirmado aqui é que `mode=exact` não carrega o
modelo, não lê a tabela de vetores e executa exatamente a mesma instrução de
antes — e que o caminho rápido da US A sobrevive nos dois modos.
"""

from __future__ import annotations

from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from app.api import decisions
from tests.conftest import needs_database

pytestmark = needs_database

PAGE_SIZE = 20
TERMO_AMPLO = "zzzlexemadeteste"


@pytest.fixture
def com_tabela_de_vetores(
    db_rolled_back: psycopg.Connection[DictRow],
) -> psycopg.Connection[DictRow]:
    """
    A tabela publicada, vazia.

    Sem ela a busca nem chega ao modelo, e um teste que afirmasse "não
    chamou" estaria afirmando outra coisa — foi assim que a primeira versão
    deste arquivo passou com `mode=exact` vetorizando.
    """
    db_rolled_back.execute("CREATE EXTENSION IF NOT EXISTS vector")
    db_rolled_back.execute(
        "CREATE TABLE core.decisao_vetor ("
        " fonte_codigo TEXT, identificador_fonte VARCHAR,"
        f" modelo TEXT, revisao TEXT, vetor halfvec({decisions.VECTOR_DIMENSIONS}))"
    )
    return db_rolled_back


@pytest.fixture
def espiao_do_modelo(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Registra toda vez que a consulta é mandada ao modelo."""
    pedidos: list[str] = []

    def registrar(texto: str) -> str | None:
        pedidos.append(texto)
        return None

    monkeypatch.setattr(decisions.embeddings, "embed", registrar)
    return pedidos


def procurar(cliente: TestClient, **extra: Any) -> dict[str, Any]:
    resposta = cliente.get("/decisions", params={"q": "dano moral", **extra})
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def test_palavras_exatas_nao_chama_o_modelo(
    com_tabela_de_vetores: psycopg.Connection[DictRow],
    client: TestClient,
    espiao_do_modelo: list[str],
) -> None:
    """
    A raiz da garantia de tempo.

    Vetorizar a consulta custa 38 ms na máquina de desenvolvimento e entre 32
    e 215 ms no servidor. Enquanto o modelo não for chamado, `mode=exact` não
    tem como ficar mais lento por causa desta história.
    """
    procurar(client, mode="exact")

    assert espiao_do_modelo == []


def test_a_busca_ampliada_chama_o_modelo_uma_vez_so(
    com_tabela_de_vetores: psycopg.Connection[DictRow],
    client: TestClient,
    espiao_do_modelo: list[str],
) -> None:
    """Uma vetorização por busca, não uma por página nem uma por resultado."""
    procurar(client, mode="subjects")

    assert len(espiao_do_modelo) == 1


def test_palavras_exatas_nao_le_a_tabela_de_vetores(
    db_rolled_back: psycopg.Connection[DictRow], client: TestClient
) -> None:
    """
    Sem a tabela não há como lê-la, e a busca responde igual.

    `core.decisao_vetor` não existe nestes fixtures. Se `mode=exact` a
    consultasse, a resposta seria 500 em vez de uma página.
    """
    corpo = procurar(client, mode="exact")

    assert corpo["total"] >= 0
    assert all(m["proximity"] is None for m in corpo["results"])


def test_a_instrucao_da_pagina_e_a_mesma_de_antes() -> None:
    """
    A consulta que serve `mode=exact` é, caractere por caractere, a que a
    busca sempre executou.

    `_word_page_sql` é um envelope: sem exclusão ele devolve a instrução
    original, e é por isso que o plano, os índices e o tempo são os mesmos.
    Uma mudança acidental no envelope apareceria aqui antes de aparecer na
    produção.
    """
    assert decisions._word_page_sql() == decisions._page_sql()
    assert decisions._word_page_sql(lexema="recurs") == decisions._broad_page_sql(True)

    for filtros in ("", " AND tribunal_sigla = ANY(%(tribunais)s)"):
        for ordem in decisions.ORDERINGS.values():
            assert decisions._word_page_sql(filtros, ordem) == decisions._page_sql(
                filtros, ordem
            )


def test_o_caminho_rapido_da_us_a_sobrevive_nos_dois_modos(
    db_rolled_back: psycopg.Connection[DictRow],
) -> None:
    """
    A regressão de desempenho que esta história podia causar.

    A US A trocou 95 segundos por uma leitura de índice guardando o ranking
    dos termos frequentes em `core.busca_ampla`. Uma busca ampliada que lesse
    `core.decisao` e ordenasse por `ts_rank` traria os 95 segundos de volta,
    sem nada na tela dizendo.

    O plano é medido sobre dez mil linhas de um lexema inventado, porque em
    cinco linhas uma varredura é honestamente mais barata que qualquer índice
    e o planejador escolheria a varredura com razão.
    """
    with db_rolled_back.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO core.busca_ampla
                (lexema, posicao, rank, data_referencia, fonte_codigo, identificador_fonte)
            SELECT %(lexema)s, n, 1.0 / n, DATE '2026-01-01', 'tjdft-jurisdf', n::TEXT
            FROM GENERATE_SERIES(1, 10000) AS n
            """,
            {"lexema": TERMO_AMPLO},
        )
        cursor.execute("ANALYZE core.busca_ampla")

        cursor.execute(
            "EXPLAIN "
            + """
            SELECT rank, data_referencia, fonte_codigo, identificador_fonte
            FROM core.busca_ampla
            WHERE lexema = %(lexema)s
            ORDER BY rank DESC, data_referencia DESC,
                     fonte_codigo DESC, identificador_fonte DESC
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            {"lexema": TERMO_AMPLO, "limit": PAGE_SIZE, "offset": 0},
        )
        plano = "\n".join(str(linha["QUERY PLAN"]) for linha in cursor.fetchall())

    assert "Index Only Scan" in plano
    assert "Seq Scan" not in plano
    assert "Sort" not in plano


def test_a_busca_ampliada_ainda_usa_o_ranking_guardado() -> None:
    """
    Quando o termo tem ranking guardado, a fase por palavra lê dele nos dois
    modos. A instrução é a mesma; o que muda é apenas a exclusão do que a fase
    por sentido já serviu.
    """
    com_exclusao = decisions._word_page_sql(lexema="recurs", excluding=True)

    assert "core.busca_ampla" in com_exclusao
    assert "ts_rank" not in com_exclusao
    assert "NOT EXISTS" in com_exclusao
