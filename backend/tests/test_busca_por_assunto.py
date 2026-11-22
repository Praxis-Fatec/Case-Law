"""
The block of decisions found by subject, and the four ways it comes back empty.

Everything here is about `subject_matches`. The list beside it, `results`, is
the search that existed before and is pinned unchanged in
`test_busca_lexica_intacta.py`.

The vectors are built by hand rather than by the model: a query at `e1` and a
decision at `cos(t)·e1 + sin(t)·e2` sit at a cosine distance of exactly
`1 - cos(t)`, so a test can ask for 0,10 or 0,50 and mean it. What is being
tested is the statement, not the model that feeds it.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from app.api import decisions
from tests.conftest import needs_database

pytestmark = needs_database

DIM = decisions.VECTOR_DIMENSIONS
LONGA = "ATRASO DE AERONAVE. " * 12
CURTA = "Demora. Prejudicado."


def vetor(distancia: float) -> str:
    """A unit vector whose cosine distance to `consulta()` is `distancia`."""
    cosseno = 1 - distancia
    valores = [cosseno, math.sqrt(max(0.0, 1 - cosseno**2))] + [0.0] * (DIM - 2)
    return "[" + ",".join(f"{v:.6f}" for v in valores) + "]"


def consulta() -> str:
    return "[" + ",".join(["1.0"] + ["0.0"] * (DIM - 1)) + "]"


DECISOES = (
    ("perto-longa", 0.10, LONGA, "Atraso de aeronave e cancelamento."),
    ("media-longa", 0.30, LONGA, "Overbooking e impedimento de embarque."),
    ("longe-longa", 0.50, LONGA, "Tributario. Nada a ver com o tema."),
    ("perto-curta", 0.05, CURTA, CURTA),
    ("perto-com-palavra", 0.12, LONGA, "demora no voo registrada pela companhia"),
)


@pytest.fixture
def acervo_vetorial(
    db_rolled_back: psycopg.Connection[DictRow],
) -> Iterator[psycopg.Connection[DictRow]]:
    conn = db_rolled_back
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.execute(
        f"""
        CREATE TABLE core.decisao_vetor (
            fonte_codigo TEXT, identificador_fonte VARCHAR,
            modelo TEXT, revisao TEXT, vetor halfvec({DIM})
        )
        """
    )
    for identificador, distancia, ementa, extra in DECISOES:
        conn.execute(
            """
            INSERT INTO core.decisao (
                fonte_codigo, identificador_fonte, tribunal_sigla,
                data_referencia, ementa, turma_recursal, possui_inteiro_teor,
                url_fonte, ementa_busca
            ) VALUES ('stj-espelhos', %s, 'STJ', DATE '2026-01-10', %s,
                      FALSE, FALSE, 'https://exemplo.test/1',
                      TO_TSVECTOR('portugues_sem_acento', %s))
            """,
            (identificador, f"{ementa} {extra}", f"{ementa} {extra}"),
        )
        conn.execute(
            "INSERT INTO core.decisao_vetor VALUES"
            " ('stj-espelhos', %s, 'BAAI/bge-m3', 'teste', %s)",
            (identificador, vetor(distancia)),
        )
    yield conn


def procurar(cliente: TestClient, **extra: Any) -> dict[str, Any]:
    resposta = cliente.get("/decisions", params={"q": "demora no voo", **extra})
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


@pytest.fixture
def cliente(
    acervo_vetorial: psycopg.Connection[DictRow],
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    monkeypatch.setattr(decisions.embeddings, "embed", lambda _: consulta())
    return client


def identificadores(corpo: dict[str, Any]) -> list[str]:
    return [m["identifier"] for m in corpo["subject_matches"]]


def test_traz_as_decisoes_proximas_em_sentido(cliente: TestClient) -> None:
    assert "perto-longa" in identificadores(procurar(cliente))


def test_ordena_da_mais_proxima_para_a_mais_distante(cliente: TestClient) -> None:
    achadas = identificadores(procurar(cliente))

    assert achadas.index("perto-longa") < achadas.index("media-longa")


def test_o_piso_de_distancia_corta_o_que_nao_e_do_assunto(cliente: TestClient) -> None:
    """
    A busca vetorial sempre tem um vizinho mais próximo, mesmo quando nada no
    acervo trata do assunto. Sem o piso, uma pergunta fora do direito recebe
    dez decisões com cara de resposta.
    """
    assert "longe-longa" not in identificadores(procurar(cliente))


def test_o_piso_de_ementa_corta_os_tocos(cliente: TestClient) -> None:
    """
    "Demora. Prejudicado." é a ementa inteira, e o sentido que ela carrega é o
    de uma palavra só — que atropela decisões inteiras sobre o assunto. Aqui
    ela é a mais próxima de todas e ainda assim não entra.
    """
    assert "perto-curta" not in identificadores(procurar(cliente))


def test_nao_repete_o_que_a_busca_por_palavra_ja_achou(cliente: TestClient) -> None:
    corpo = procurar(cliente)
    por_palavra = {m["identifier"] for m in corpo["results"]}

    assert "perto-com-palavra" in por_palavra
    assert "perto-com-palavra" not in identificadores(corpo)


def test_respeita_os_filtros_da_tela(cliente: TestClient) -> None:
    """Um filtro que não vale para o bloco por assunto é um filtro mentiroso."""
    corpo = procurar(cliente, tribunal="TJDFT")

    assert identificadores(corpo) == []


def test_palavras_exatas_nao_traz_bloco_nenhum(cliente: TestClient) -> None:
    assert procurar(cliente, mode="exact")["subject_matches"] == []


def test_o_bloco_so_existe_na_primeira_pagina(cliente: TestClient) -> None:
    """
    Uma oferta, não uma segunda lista de resultados. Repetida em cada página
    ela ocuparia espaço sem acrescentar nada, e custaria uma consulta vetorial
    por página.
    """
    assert procurar(cliente, page=2)["subject_matches"] == []


def test_os_dois_modos_devolvem_as_mesmas_decisoes_na_mesma_ordem(
    cliente: TestClient,
) -> None:
    """
    A promessa do desenho inteiro: a busca por assunto acrescenta, nunca
    altera. Se esta igualdade quebrar, quem escolheu "palavras exatas" deixou
    de receber o que recebia antes de a funcionalidade existir.
    """
    exatas = procurar(cliente, mode="exact")
    assuntos = procurar(cliente, mode="subjects")

    sem_rotulo = lambda pagina: [  # noqa: E731
        {campo: valor for campo, valor in m.items() if campo != "proximity"}
        for m in pagina["results"]
    ]

    assert [m["identifier"] for m in exatas["results"]] == [
        m["identifier"] for m in assuntos["results"]
    ]
    assert sem_rotulo(exatas) == sem_rotulo(assuntos)
    assert exatas["total"] == assuntos["total"]
    assert exatas["range_from"] == assuntos["range_from"]
    assert exatas["range_to"] == assuntos["range_to"]


def test_palavras_exatas_nao_rotula_proximidade(cliente: TestClient) -> None:
    """Sem vetorizar a consulta não há proximidade a afirmar, e inventar uma
    seria pior do que não ter."""
    assert all(m["proximity"] is None for m in procurar(cliente, mode="exact")["results"])


def test_a_busca_ampliada_rotula_o_que_tem_vetor(cliente: TestClient) -> None:
    rotulos = {m["proximity"] for m in procurar(cliente)["subject_matches"]}

    assert rotulos <= {"high", "medium", "low"}
    assert None not in rotulos


def test_sem_modelo_a_busca_responde_por_palavra(
    acervo_vetorial: psycopg.Connection[DictRow],
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Um servidor sem modelo responde como antes, não com erro."""
    monkeypatch.setattr(decisions.embeddings, "embed", lambda _: None)
    corpo = procurar(client)

    assert corpo["subject_matches"] == []
    assert corpo["total"] >= 1


def test_sem_a_tabela_de_vetores_a_busca_responde_por_palavra(
    db_rolled_back: psycopg.Connection[DictRow],
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    O deploy pode chegar antes da base que o acompanha — já aconteceu nesta
    sprint. Enquanto a tabela não chega, responder por palavra é a resposta
    certa; erro 500 não é.
    """
    monkeypatch.setattr(decisions.embeddings, "embed", lambda _: consulta())
    corpo = procurar(client)

    assert corpo["subject_matches"] == []
