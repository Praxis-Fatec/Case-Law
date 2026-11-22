"""
A lista reordenada por sentido, e o que entra nela.

Em `mode=subjects` a busca por palavra e a busca por sentido viram uma lista
só, do mais parecido para o menos. Em `mode=exact` nada disso acontece e a
página é a que a busca sempre devolveu.

Os vetores são construídos à mão em vez de pelo modelo: uma consulta em `e1` e
uma decisão em `cos(t)·e1 + sin(t)·e2` ficam a uma distância de cosseno de
exatamente `1 - cos(t)`, então um teste pode pedir 0,10 ou 0,50 e querer dizer
isso. O que está sendo testado é a afirmação, não o modelo que a alimenta.
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
    """Um vetor unitário cuja distância de cosseno até `consulta()` é essa."""
    cosseno = 1 - distancia
    valores = [cosseno, math.sqrt(max(0.0, 1 - cosseno**2))] + [0.0] * (DIM - 2)
    return "[" + ",".join(f"{v:.6f}" for v in valores) + "]"


def consulta() -> str:
    return "[" + ",".join(["1.0"] + ["0.0"] * (DIM - 1)) + "]"


DECISOES = (
    ("perto-longa", 0.10, LONGA, "Atraso de aeronave e cancelamento."),
    ("com-palavra", 0.12, LONGA, "demora no voo registrada pela companhia"),
    ("media-longa", 0.30, LONGA, "Overbooking e impedimento de embarque."),
    ("longe-longa", 0.50, LONGA, "Tributario. Nada a ver com o tema."),
    ("perto-curta", 0.05, CURTA, CURTA),
)


@pytest.fixture
def acervo_vetorial(
    db_rolled_back: psycopg.Connection[DictRow],
) -> Iterator[psycopg.Connection[DictRow]]:
    conn = db_rolled_back
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.execute("DROP TABLE IF EXISTS core.decisao_vetor")
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


@pytest.fixture
def cliente(
    acervo_vetorial: psycopg.Connection[DictRow],
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    monkeypatch.setattr(decisions.embeddings, "embed", lambda _: consulta())
    return client


def procurar(cliente: TestClient, **extra: Any) -> dict[str, Any]:
    resposta = cliente.get("/decisions", params={"q": "demora no voo", **extra})
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def achadas(corpo: dict[str, Any]) -> list[str]:
    return [m["identifier"] for m in corpo["results"]]


def test_a_lista_vem_do_mais_parecido_para_o_menos(cliente: TestClient) -> None:
    """
    O pedido inteiro desta tela: o mais parecido em sentido no topo.

    `perto-longa` está a 0,10 e não contém nenhuma das palavras digitadas;
    `com-palavra` está a 0,12 e contém todas. A ordem é pela distância, não
    pela origem — senão a busca por palavra continuaria mandando na lista.
    """
    assert achadas(procurar(cliente)) == ["perto-longa", "com-palavra", "media-longa"]


def test_marca_o_que_so_o_sentido_encontrou(cliente: TestClient) -> None:
    por_assunto = {m["identifier"]: m["by_subject"] for m in procurar(cliente)["results"]}

    assert por_assunto == {
        "perto-longa": True,
        "com-palavra": False,
        "media-longa": True,
    }


def test_o_piso_de_distancia_corta_o_que_nao_e_do_assunto(cliente: TestClient) -> None:
    """
    A busca vetorial sempre tem um vizinho mais próximo, mesmo quando nada no
    acervo trata do assunto. Sem o piso, uma pergunta fora do direito recebe
    dez decisões com cara de resposta.
    """
    assert "longe-longa" not in achadas(procurar(cliente))


def test_o_piso_de_ementa_corta_os_tocos(cliente: TestClient) -> None:
    """
    "Demora. Prejudicado." é a ementa inteira, e o sentido que ela carrega é o
    de uma palavra só — que atropela decisões inteiras sobre o assunto. Aqui
    ela é a mais próxima de todas e ainda assim não entra.
    """
    assert "perto-curta" not in achadas(procurar(cliente))


def test_rotula_a_proximidade_de_cada_uma(cliente: TestClient) -> None:
    rotulos = {m["identifier"]: m["proximity"] for m in procurar(cliente)["results"]}

    assert rotulos == {
        "perto-longa": "high",
        "com-palavra": "high",
        "media-longa": "medium",
    }


def test_so_as_minhas_palavras_devolve_a_busca_de_sempre(cliente: TestClient) -> None:
    """
    Quem escolhe palavras exatas recebe o que recebia antes de a
    funcionalidade existir: só o que casa, na ordem da palavra, sem rótulo e
    sem decisão acrescentada.
    """
    corpo = procurar(cliente, mode="exact")

    assert achadas(corpo) == ["com-palavra"]
    assert all(m["proximity"] is None for m in corpo["results"])
    assert all(m["by_subject"] is False for m in corpo["results"])


def test_o_total_conta_as_que_entraram_por_sentido(cliente: TestClient) -> None:
    assert procurar(cliente, mode="exact")["total"] == 1
    assert procurar(cliente)["total"] == 3


def test_sem_modelo_a_busca_responde_por_palavra(
    acervo_vetorial: psycopg.Connection[DictRow],
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Um servidor sem modelo responde como antes, não com erro."""
    monkeypatch.setattr(decisions.embeddings, "embed", lambda _: None)
    corpo = procurar(client)

    assert achadas(corpo) == ["com-palavra"]
    assert all(m["proximity"] is None for m in corpo["results"])


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

    assert all(m["by_subject"] is False for m in corpo["results"])


def test_a_faixa_nao_passa_do_piso() -> None:
    """
    Além de 0,42 não há o que afirmar.

    Uma decisão achada pelas palavras pode estar a qualquer distância: a
    primeira página de `recurso` mede de 0,483 a 0,640. Rotulá-las
    `relacionado` seria dizer que têm relação de sentido com a consulta
    quando, medido, elas não estão mais perto do que um par ao acaso.
    """
    assert decisions._band(0.200) == "high"
    assert decisions._band(0.272) == "high"
    assert decisions._band(0.300) == "medium"
    assert decisions._band(0.326) == "medium"
    assert decisions._band(0.400) == "low"
    assert decisions._band(0.420) == "low"
    assert decisions._band(0.421) is None
    assert decisions._band(0.640) is None
    assert decisions._band(None) is None


def test_passado_o_piso_a_ordem_volta_a_ser_a_da_palavra(
    cliente: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Reordenar por uma distância que não distingue é embaralhar.

    Com uma consulta longe de tudo — nenhuma decisão dentro do piso — a lista
    tem de sair exatamente como a busca por palavra a montou. Medido no
    acervo: `recurso` mede de 0,483 a 0,640, e sem esta regra a ordem que a
    US A construiu seria refeita por ruído.
    """
    # Ortogonal a todas as do acervo, que só usam as duas primeiras dimensões:
    # distância 1,0 de cada uma, bem além do piso.
    longe = "[" + ",".join(["0.0", "0.0", "1.0"] + ["0.0"] * (DIM - 3)) + "]"
    monkeypatch.setattr(decisions.embeddings, "embed", lambda _: longe)

    corpo = procurar(cliente)

    assert achadas(corpo) == achadas(procurar(cliente, mode="exact"))
    assert all(m["proximity"] is None for m in corpo["results"])
    assert all(m["by_subject"] is False for m in corpo["results"])


def test_a_que_tem_as_palavras_tambem_entra_pela_proximidade(
    cliente: TestClient,
) -> None:
    """
    A fase por sentido não exclui quem a palavra também acharia.

    `com-palavra` casa com tudo o que foi digitado e está a 0,12. Ela aparece
    entre as próximas, no lugar que a distância lhe dá — e sem o selo, porque
    a busca por palavra a traria de qualquer forma.
    """
    corpo = procurar(cliente)
    posicao = achadas(corpo).index("com-palavra")

    assert posicao == 1
    assert corpo["results"][posicao]["by_subject"] is False
    assert corpo["results"][posicao]["proximity"] == "high"


def test_uma_pagina_nao_repete_o_que_a_outra_mostrou(cliente: TestClient) -> None:
    """
    A emenda entre as duas fases é onde uma decisão apareceria duas vezes.

    A fase por palavra pula o que a por sentido já serviu, e a página que cai
    em cima da emenda é completada com a fase seguinte em vez de chegar curta.
    """
    primeira = achadas(procurar(cliente, page=1))
    segunda = achadas(procurar(cliente, page=2))

    assert set(primeira) & set(segunda) == set()
