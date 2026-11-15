"""
The cited-legislation endpoint, against PostgreSQL.

What it has to protect is the difference between three answers that a careless
screen would show alike: the law the decision applied, the reference the parser
could not read, and no reference at all. The first is citable, the second is
the court's raw text and a warning, and the third is ordinary — two thirds of
the STJ collection carry a reference and the TJDFT collection carries none, so
"none" can never read as a failure.

A fake database would prove none of this: the rows come back with array columns
and nulls that only PostgreSQL produces, and `null` versus `[]` is exactly where
this endpoint's promises live.
"""

from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from tests.conftest import needs_database
from tests.test_courts import decide, register

pytestmark = needs_database


def cite(
    db: psycopg.Connection[DictRow],
    identifier: str,
    order: int = 0,
    sequence: int = 1,
    sphere: str | None = "FED",
    act_type: str | None = "DEL",
    number: int | None = 3365,
    year: int | None = 1941,
    article: str | None = "26",
    paragraphs: list[str] | None = None,
    items: list[str] | None = None,
    letters: list[str] | None = None,
    recognised: bool = True,
    raw: str | None = "LEG:FED DEL:003365 ANO:1941 ART:00026 PAR:00002",
) -> None:
    db.execute(
        "INSERT INTO core.referencia_legislativa ("
        "  fonte_codigo, identificador_fonte, ordem, sequencia, esfera,"
        "  tipo_ato, numero, ano, artigo, paragrafos, incisos, letras,"
        "  reconhecida, texto_bruto, data_referencia"
        ") VALUES ("
        "  'stj-teste', %s, %s, %s, %s, %s, %s, %s, %s, %s::TEXT[],"
        "  %s::TEXT[], %s::TEXT[], %s, %s, '2026-03-10'"
        ")",
        (
            identifier,
            order,
            sequence,
            sphere,
            act_type,
            number,
            year,
            article,
            paragraphs,
            items,
            letters,
            recognised,
            raw,
        ),
    )


@pytest.fixture
def collection(db_rolled_back: psycopg.Connection[DictRow]) -> Any:
    from app.db import get_connection
    from app.main import app

    db_rolled_back.execute("DELETE FROM core.decisao")
    register(db_rolled_back, "STJ")
    decide(db_rolled_back, "STJ", "com-lei")
    decide(db_rolled_back, "STJ", "sem-lei")

    app.dependency_overrides[get_connection] = lambda: db_rolled_back
    yield TestClient(app)
    app.dependency_overrides.clear()


def read(client: TestClient, identifier: str, source: str = "stj-teste") -> Any:
    response = client.get(f"/decisions/{source}/{identifier}/legislation")
    assert response.status_code == 200, response.text
    return response.json()["results"]


def test_a_decisao_devolve_a_lei_que_aplicou(
    collection: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    """
    O critério de aceite da história: tipo de ato, número, ano e artigo. Sem os
    quatro o leitor não chega à norma, que é a razão de a história existir.
    """
    cite(db_rolled_back, "com-lei", paragraphs=["2"])

    referencia = read(collection, "com-lei")[0]

    assert referencia["act_type"] == "DEL"
    assert referencia["number"] == 3365
    assert referencia["year"] == 1941
    assert referencia["article"] == "26"
    assert referencia["paragraphs"] == ["2"]
    assert referencia["recognised"] is True


def test_a_decisao_sem_referencia_devolve_lista_vazia(collection: TestClient) -> None:
    """
    Um terço do acervo do STJ e todo o acervo do TJDFT respondem assim. Erro
    aqui transformaria o caso normal em tela quebrada.
    """
    assert read(collection, "sem-lei") == []


def test_o_identificador_inexistente_e_404(collection: TestClient) -> None:
    """
    Nenhuma referência e nenhuma decisão não são a mesma coisa. Responder lista
    vazia para um identificador que não existe diria ao leitor que a decisão
    está no acervo e não aplicou lei nenhuma.
    """
    response = collection.get("/decisions/stj-teste/nao-existe/legislation")

    assert response.status_code == 404
    assert response.json()["detail"] == "Decision not found."


def test_a_fonte_inexistente_e_404(collection: TestClient) -> None:
    response = collection.get("/decisions/nao-existe/com-lei/legislation")

    assert response.status_code == 404


def test_o_byte_nulo_no_identificador_e_404(collection: TestClient) -> None:
    """
    PostgreSQL recusa NUL em texto, e o identificador vem da URL. Sem a guarda
    a resposta é um erro de servidor em vez de "não existe".
    """
    response = collection.get("/decisions/stj-teste/%00/legislation")

    assert response.status_code == 404


def test_a_referencia_nao_reconhecida_chega_crua_e_marcada(
    collection: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    """
    0,61% do acervo. A citação é real: descartá-la mostraria uma decisão
    aplicando menos lei do que aplicou, e sem nada na tela dizendo isso.
    """
    bruto = "LEG:FED ***** SUM(STF) SUMULA DO SUPREMO TRIBUNAL FEDERAL SUM:000282"
    cite(
        db_rolled_back,
        "com-lei",
        act_type=None,
        number=None,
        year=None,
        article=None,
        recognised=False,
        raw=bruto,
    )

    referencia = read(collection, "com-lei")[0]

    assert referencia["recognised"] is False
    assert referencia["act_type"] is None
    assert referencia["raw"] == bruto


def test_a_esfera_fora_das_tres_nao_e_traduzida(
    collection: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    """
    MUN, INT e IES são 0,426% do acervo e não têm leitura entre federal,
    estadual e distrital. Responder lei municipal como estadual é resposta
    errada, e a API devolve o código do tribunal para a tela decidir.
    """
    cite(db_rolled_back, "com-lei", sphere="MUN", act_type="LEI", number=123, year=2009)

    assert read(collection, "com-lei")[0]["sphere"] == "MUN"


def test_o_ato_sem_numero_mantem_ano_e_artigo(
    collection: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    """
    `CFB:****** ANO:1988` é como o tribunal escreve a Constituição: 30,29% das
    referências não têm número, e nulo é ausência, não zero.
    """
    cite(
        db_rolled_back,
        "com-lei",
        act_type="CFB",
        number=None,
        year=1988,
        article="105",
        items=["3"],
        letters=["A"],
    )

    referencia = read(collection, "com-lei")[0]

    assert referencia["number"] is None
    assert referencia["year"] == 1988
    assert referencia["items"] == ["3"]
    assert referencia["letters"] == ["A"]


def test_as_colunas_vazias_viram_lista_e_nao_nulo(
    collection: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    """
    O modelo grava NULL onde o artigo não tem parágrafo nenhum. A tela recebe
    lista, sempre: um `null` onde ela espera lista é a diferença entre um bloco
    vazio e um bloco que não renderiza.
    """
    cite(db_rolled_back, "com-lei", paragraphs=None, items=None, letters=None)

    referencia = read(collection, "com-lei")[0]

    assert referencia["paragraphs"] == []
    assert referencia["items"] == []
    assert referencia["letters"] == []


def test_a_ordem_e_a_do_tribunal(
    collection: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    """
    `ordem` é a posição na lista que o tribunal publicou e `sequencia` o artigo
    dentro dela. Ordenar por outra coisa reorganizaria uma lista que não é
    nossa — e um artigo 927 antes do 926 da mesma lei não se lê como erro.
    """
    cite(db_rolled_back, "com-lei", order=1, sequence=2, article="927")
    cite(db_rolled_back, "com-lei", order=1, sequence=1, article="926")
    cite(db_rolled_back, "com-lei", order=0, sequence=1, article="26")

    assert [r["article"] for r in read(collection, "com-lei")] == ["26", "926", "927"]


def test_cada_artigo_citado_e_uma_entrada(
    collection: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    """
    17,88% das referências citam dois artigos ou mais. Uma entrada por
    referência mostraria o primeiro e calaria o resto.
    """
    cite(db_rolled_back, "com-lei", order=0, sequence=1, article="926")
    cite(
        db_rolled_back, "com-lei", order=0, sequence=2, article="927", paragraphs=["3"]
    )

    referencias = read(collection, "com-lei")

    assert len(referencias) == 2
    assert referencias[0]["paragraphs"] == []
    assert referencias[1]["paragraphs"] == ["3"]


def test_a_referencia_de_outra_decisao_nao_vaza(
    collection: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    cite(db_rolled_back, "com-lei")

    assert read(collection, "sem-lei") == []
