"""
The decisions that may contradict the one being read, against PostgreSQL.

The endpoint computes nothing: `core.decisao_contraria` is built by the
pipeline, and what is under test here is the reading of it. So the fixture
writes the table directly, with the shapes the pipeline can produce — a pair
disputing one precedent, a pair disputing two, a pair whose outcomes differ and
a pair whose outcomes agree.

Three of these protect a promise the feature makes rather than a line of code.
That the reason always travels, because a list of contrary decisions that does
not say where they diverge is noise with the face of analysis. That the basis
sentence always travels, because `RF23` requires the indication to be told
apart from a settled legal conclusion. And that a missing table answers 503 and
not an empty list, because telling a lawyer there is no contradiction when
nobody looked is the one wrong answer this screen cannot afford.
"""

from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from app.api.opposing import BASIS
from tests.conftest import needs_database

pytestmark = needs_database

SOURCE = "stj-teste"

COLUNAS = (
    "fonte_codigo, identificador_fonte, tribunal_sigla, processo,"
    " data_referencia, ementa, resultado, turma_recursal, possui_inteiro_teor,"
    " url_fonte, link_valido"
)


def decidir(
    db: psycopg.Connection[DictRow],
    identificador: str,
    ementa: str,
    resultado: str | None = None,
) -> None:
    db.execute(
        f"INSERT INTO core.decisao ({COLUNAS}) VALUES ("
        "  %(source)s, %(id)s, 'STJ', 'REsp ' || %(id)s, '2026-03-10',"
        "  %(ementa)s, %(resultado)s, FALSE, FALSE,"
        "  'https://example.com/' || %(id)s, TRUE"
        ")",
        {
            "source": SOURCE,
            "id": identificador,
            "ementa": ementa,
            "resultado": resultado,
        },
    )


def contrariar(
    db: psycopg.Connection[DictRow],
    de: str,
    para: str,
    numero: int,
    aderencia: str = "seguiu",
    contraria_aderencia: str = "afastou",
    semelhanca: float = 0.40,
    termos: int = 5,
    resultado_oposto: bool = False,
    peso: float = 7.5,
) -> None:
    """
    One direction of one disputed precedent.

    The pipeline writes both directions of every pair — `contraria_e_simetrica`
    audits exactly that — so the tests that care about symmetry call this twice
    rather than relying on the endpoint to invent the missing half.
    """
    db.execute(
        """
        INSERT INTO core.decisao_contraria (
            fonte_codigo, identificador_fonte,
            contraria_fonte, contraria_identificador,
            corte, tipo, numero, aderencia, contraria_aderencia,
            termos_comuns, peso_precedente, semelhanca, resultado_oposto
        ) VALUES (
            %(source)s, %(de)s, %(source)s, %(para)s,
            'STJ', 'sumula', %(numero)s, %(aderencia)s, %(contraria)s,
            %(termos)s, %(peso)s, %(semelhanca)s, %(oposto)s
        )
        """,
        {
            "source": SOURCE,
            "de": de,
            "para": para,
            "numero": numero,
            "aderencia": aderencia,
            "contraria": contraria_aderencia,
            "termos": termos,
            "peso": peso,
            "semelhanca": semelhanca,
            "oposto": resultado_oposto,
        },
    )


@pytest.fixture
def acervo(db: psycopg.Connection[DictRow]) -> psycopg.Connection[DictRow]:
    decidir(db, "1", "Responsabilidade do poluidor por derramamento.", "provido")
    decidir(db, "2", "Poluidor nao responde sem nexo causal.", "negado")
    decidir(db, "3", "Prazo decadencial em mandado de seguranca.", "negado")
    decidir(db, "4", "Nexo causal presumido no dano ambiental.", "negado")

    # 1 × 2: the closest pair, two precedents disputed, outcomes differ.
    for numero in (85, 596):
        contrariar(db, "1", "2", numero, semelhanca=0.62, resultado_oposto=True)
        contrariar(
            db,
            "2",
            "1",
            numero,
            aderencia="afastou",
            contraria_aderencia="seguiu",
            semelhanca=0.62,
            resultado_oposto=True,
        )
    # 1 × 4: further away, one precedent, outcomes agree.
    contrariar(db, "1", "4", 596, semelhanca=0.21, termos=2)
    contrariar(
        db,
        "4",
        "1",
        596,
        aderencia="afastou",
        contraria_aderencia="seguiu",
        semelhanca=0.21,
        termos=2,
    )
    return db


def contrarias(
    client: TestClient, identificador: str, **parametros: Any
) -> list[dict[str, Any]]:
    resposta = client.get(
        f"/decisions/{SOURCE}/{identificador}/opposing", params=parametros
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()["results"]


def test_a_contraria_aparece_com_o_precedente_e_as_duas_aderencias(
    acervo: psycopg.Connection[DictRow], client: TestClient
) -> None:
    """
    The reason is the point. An entry that names no precedent, or names it
    without saying what each decision did with it, is the noise the story was
    written to avoid.
    """
    encontradas = contrarias(client, "1")

    proxima = encontradas[0]
    assert proxima["identifier"] == "2"

    motivos = {
        (m["court"], m["kind"], m["number"], m["this_decision"], m["other_decision"])
        for m in proxima["disagreements"]
    }
    assert motivos == {
        ("STJ", "sumula", 85, "seguiu", "afastou"),
        ("STJ", "sumula", 596, "seguiu", "afastou"),
    }


def test_o_motivo_nunca_vem_vazio(
    acervo: psycopg.Connection[DictRow], client: TestClient
) -> None:
    for entrada in contrarias(client, "1"):
        assert entrada["disagreements"], entrada["identifier"]


def test_um_par_com_dois_precedentes_e_uma_entrada_so(
    acervo: psycopg.Connection[DictRow], client: TestClient
) -> None:
    """
    Two disputed precedents are two rows in the table and one decision on the
    screen. Letting them through as two entries would show the same process
    twice and inflate every count the reader makes by eye.
    """
    encontradas = contrarias(client, "1")

    assert [e["identifier"] for e in encontradas] == ["2", "4"]
    assert len(encontradas[0]["disagreements"]) == 2


def test_ordena_pela_semelhanca_da_mais_proxima_para_a_mais_distante(
    acervo: psycopg.Connection[DictRow], client: TestClient
) -> None:
    semelhancas = [e["similarity"] for e in contrarias(client, "1")]

    assert semelhancas == sorted(semelhancas, reverse=True)


def test_a_direcao_oposta_recebe_a_mesma_resposta(
    acervo: psycopg.Connection[DictRow], client: TestClient
) -> None:
    """
    Whoever opens the decision that followed the precedent and whoever opens
    the one that departed from it are reading the same disagreement, and the
    adherences swap sides.
    """
    (entrada,) = contrarias(client, "4")

    assert entrada["identifier"] == "1"
    (motivo,) = entrada["disagreements"]
    assert (motivo["this_decision"], motivo["other_decision"]) == ("afastou", "seguiu")


def test_resultado_oposto_viaja_como_contexto_e_nao_cria_entrada(
    acervo: psycopg.Connection[DictRow], client: TestClient
) -> None:
    """
    The measurement behind `RF23` found opposite outcome pointing the other
    way, so it is carried and never relied on. The pair whose outcomes agree is
    in the list all the same.
    """
    por_id = {e["identifier"]: e for e in contrarias(client, "1")}

    assert por_id["2"]["opposite_outcome"] is True
    assert por_id["4"]["opposite_outcome"] is False


def test_a_base_da_indicacao_acompanha_a_resposta(
    acervo: psycopg.Connection[DictRow], client: TestClient
) -> None:
    """
    `RF23` requires the indication to be distinguished from a definitive legal
    conclusion, and this sentence is what does it. It travels even when there
    is nothing to show, because the empty answer is also an indication.
    """
    com = client.get(f"/decisions/{SOURCE}/1/opposing").json()
    sem = client.get(f"/decisions/{SOURCE}/3/opposing").json()

    assert com["basis"] == BASIS
    assert sem["basis"] == BASIS


def test_decisao_sem_contraria_responde_lista_vazia(
    acervo: psycopg.Connection[DictRow], client: TestClient
) -> None:
    """
    Nineteen decisions in twenty answer this way. It is the ordinary answer and
    never an error.
    """
    resposta = client.get(f"/decisions/{SOURCE}/3/opposing")

    assert resposta.status_code == 200
    assert resposta.json()["results"] == []


def test_identificador_fora_do_acervo_responde_404(
    acervo: psycopg.Connection[DictRow], client: TestClient
) -> None:
    assert client.get(f"/decisions/{SOURCE}/999/opposing").status_code == 404
    assert client.get("/decisions/nao-existe/1/opposing").status_code == 404


def test_byte_nulo_responde_404_e_nao_erro_de_servidor(
    acervo: psycopg.Connection[DictRow], client: TestClient
) -> None:
    """
    A NUL byte cannot be sent to PostgreSQL as text and both parts arrive from
    the URL. Without the guard this is a stack trace instead of "no such
    decision".
    """
    assert client.get(f"/decisions/{SOURCE}/1%00/opposing").status_code == 404
    assert client.get("/decisions/a%00b/1/opposing").status_code == 404


def test_o_limite_padrao_mostra_cinco(
    acervo: psycopg.Connection[DictRow], client: TestClient
) -> None:
    """
    The median decision that has any contrary has 21 of them, and the worst in
    the collection has 1.266, so the default is a cut and not a ceiling nobody
    reaches.
    """
    for i in range(10, 20):
        decidir(acervo, str(i), f"Dano ambiental caso {i}.", "negado")
        contrariar(acervo, "1", str(i), 596, semelhanca=0.10 + i / 1000)

    assert len(contrarias(client, "1")) == 5
    assert len(contrarias(client, "1", limit=20)) == 12


def test_o_limite_recusa_valores_fora_da_faixa(
    acervo: psycopg.Connection[DictRow], client: TestClient
) -> None:
    assert client.get(f"/decisions/{SOURCE}/1/opposing?limit=0").status_code == 422
    assert client.get(f"/decisions/{SOURCE}/1/opposing?limit=21").status_code == 422


def test_sem_a_tabela_a_resposta_e_503_e_nunca_lista_vazia(
    acervo: psycopg.Connection[DictRow], client: TestClient
) -> None:
    """
    The one wrong answer this screen cannot afford. An empty list reads as "no
    contradiction found", and saying that when the table was never published
    would be the tool asserting something it never looked at. Every other
    endpoint probes and falls back to an empty list; this one does not, and
    this test is what keeps a well-meant probe from being added later.
    """
    acervo.execute("DROP TABLE core.decisao_contraria")

    resposta = client.get(f"/decisions/{SOURCE}/1/opposing")

    assert resposta.status_code == 503
