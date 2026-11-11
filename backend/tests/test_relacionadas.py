"""
The decisions suggested as treating the same subject, against PostgreSQL.

What these protect is the one promise the feature makes: that a suggestion is
about the *subject*, not about the procedural prose every decision shares. The
measurement behind it is in `related.py`; a test that only checked "something
came back" would pass for a method that returns whatever mentions `recurso`.

So the fixture is built around that distinction. Two decisions share a rare
word, two others share only common ones, and the suite asserts that the first
pair finds each other and the second pair does not.
"""

from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from tests.conftest import needs_database

pytestmark = needs_database

SOURCE = "stj-teste"

# Both ementas are about an oil spill; both also carry the procedural words.
POLUICAO = (
    "RECURSO ESPECIAL. Indenizacao a pescador artesanal por poluicao "
    "decorrente de derramamento de nafta. Responsabilidade do poluidor."
)
POLUICAO_OUTRA = (
    "AGRAVO. Dano a pescador artesanal. Derramamento de nafta e poluicao "
    "ambiental. Poluidor responde objetivamente."
)
# These two are built from the filler vocabulary and nothing else, so every
# word they carry sits in two hundred decisions and weighs almost nothing.
# An earlier version wrote "Dano configurado" here and the test failed for a
# good reason: `configurado` appears twice in the whole fixture, which makes
# it rare, and the decision was correctly matched to the other one carrying
# it. A word is procedural only if the collection says so.
PROCESSUAL = "RECURSO ESPECIAL. Responsabilidade. Indenizacao. Dano."
PROCESSUAL_OUTRA = "Dano. Indenizacao. RECURSO ESPECIAL. Responsabilidade."
# Shares exactly one rare word with POLUICAO, and nothing else.
UM_TERMO_SO = "MANDADO DE SEGURANCA. Licenca para pesca de nafta apreendida."

COLUMNS = (
    "fonte_codigo, identificador_fonte, tribunal_sigla, data_referencia, ementa,"
    " turma_recursal, possui_inteiro_teor, url_fonte, link_valido, ementa_busca"
)


def decidir(db: psycopg.Connection[DictRow], identificador: str, ementa: str) -> None:
    db.execute(
        f"INSERT INTO core.decisao ({COLUMNS}) VALUES ("
        "  %(source)s, %(id)s, 'STJ', '2026-03-10', %(ementa)s,"
        "  FALSE, FALSE, 'https://example.com/' || %(id)s, TRUE,"
        "  TO_TSVECTOR('portugues_sem_acento', %(ementa)s)"
        ")",
        {"source": SOURCE, "id": identificador, "ementa": ementa},
    )


def pesar(db: psycopg.Connection[DictRow]) -> None:
    """
    Fill the weights and the norms the way the pipeline does.

    The formulas are restated here rather than imported because the models are
    SQL files SQLMesh owns. They are the same two: the weight is the natural
    log of the collection over the decisions carrying the term, and the norm is
    the length of the decision's weighted vector.
    """
    db.execute(
        """
        INSERT INTO core.termo_judicial (termo, decisoes, peso)
        SELECT t.lexeme, COUNT(*),
               LN((SELECT COUNT(*)::DOUBLE PRECISION FROM core.decisao)
                  / GREATEST(COUNT(*), 1))
        FROM core.decisao AS d
        CROSS JOIN LATERAL UNNEST(d.ementa_busca) AS t
        WHERE LENGTH(t.lexeme) >= 4
        GROUP BY t.lexeme
        """
    )
    db.execute(
        """
        INSERT INTO core.decisao_norma
            (fonte_codigo, identificador_fonte, data_referencia, norma)
        SELECT d.fonte_codigo, d.identificador_fonte, d.data_referencia,
               SQRT(SUM(POWER(j.peso * (1 + LN(ARRAY_LENGTH(t.positions, 1))), 2)))
        FROM core.decisao AS d
        CROSS JOIN LATERAL UNNEST(d.ementa_busca) AS t
        JOIN core.termo_judicial AS j ON j.termo = t.lexeme
        GROUP BY d.fonte_codigo, d.identificador_fonte, d.data_referencia
        """
    )


# The floor the endpoint searches on is a weight of 4,5, which is
# `LN(collection / decisions carrying the term)`. It is a property of the
# collection's size, not of the fixture: with seven decisions the rarest
# possible term weighs LN(7/1) = 1,95 and nothing can ever clear the floor.
# For a word in two decisions to reach 4,5 the collection needs at least
# e^4,5 × 2 ≈ 180. So the fixture builds a collection, and the threshold under
# test is the real one rather than a number lowered to make the suite pass.
ENCHIMENTO = 200


def encher(
    db: psycopg.Connection[DictRow],
    quantas: int = ENCHIMENTO,
    prefixo: str = "f",
) -> None:
    """Decisions made only of the words every decision has."""
    db.execute(
        f"INSERT INTO core.decisao ({COLUMNS}) "
        "SELECT %(source)s, %(prefixo)s || n, 'STJ', '2026-03-10',"
        "       'RECURSO ESPECIAL. Indenizacao. Responsabilidade. Dano.',"
        "       FALSE, FALSE, 'https://example.com/' || %(prefixo)s || n, TRUE,"
        "       TO_TSVECTOR('portugues_sem_acento',"
        "         'RECURSO ESPECIAL. Indenizacao. Responsabilidade. Dano.')"
        "FROM GENERATE_SERIES(1, %(quantas)s) AS n",
        {"source": SOURCE, "quantas": quantas, "prefixo": prefixo},
    )


@pytest.fixture
def acervo(db: psycopg.Connection[DictRow]) -> psycopg.Connection[DictRow]:
    decidir(db, "1", POLUICAO)
    decidir(db, "2", POLUICAO_OUTRA)
    decidir(db, "3", PROCESSUAL)
    decidir(db, "4", PROCESSUAL_OUTRA)
    decidir(db, "5", UM_TERMO_SO)
    encher(db)
    pesar(db)
    return db


def proximas(client: TestClient, identificador: str) -> list[dict[str, Any]]:
    resposta = client.get(f"/decisions/{SOURCE}/{identificador}/related")
    assert resposta.status_code == 200
    return resposta.json()["results"]


def test_finds_the_decision_about_the_same_subject(
    acervo: psycopg.Connection[DictRow], client: TestClient
) -> None:
    encontradas = [d["identifier"] for d in proximas(client, "1")]

    assert "2" in encontradas


def test_sharing_only_procedural_words_is_not_being_related(
    acervo: psycopg.Connection[DictRow], client: TestClient
) -> None:
    """
    The whole point of weighing by rarity. `recurso`, `indenizacao`,
    `responsabilidade` and `dano` are in every decision here, and a decision
    built only from them must not be offered as related to anything.
    """
    assert proximas(client, "3") == []
    assert proximas(client, "4") == []


def test_a_single_shared_term_is_a_coincidence(
    acervo: psycopg.Connection[DictRow], client: TestClient
) -> None:
    encontradas = [d["identifier"] for d in proximas(client, "1")]

    assert "5" not in encontradas


def test_a_decision_is_never_related_to_itself(
    acervo: psycopg.Connection[DictRow], client: TestClient
) -> None:
    assert "1" not in [d["identifier"] for d in proximas(client, "1")]


def test_it_says_which_words_matched(
    acervo: psycopg.Connection[DictRow], client: TestClient
) -> None:
    """
    Not decoration: it is what lets a reader judge a suggestion without
    opening it, and `RF20` requires the relation to be explainable.
    """
    primeira = proximas(client, "1")[0]

    assert primeira["terms"] >= 2
    assert any(
        termo.startswith(("polui", "pescador", "artesanal", "derram", "nafta"))
        for termo in primeira["matched_on"]
    )


def test_it_always_states_the_method(
    acervo: psycopg.Connection[DictRow], client: TestClient
) -> None:
    """`RF20` asks for calculated similarity to be told apart from an official
    relation. The field says which one this is, including when empty."""
    cheia = client.get(f"/decisions/{SOURCE}/1/related").json()
    vazia = client.get(f"/decisions/{SOURCE}/3/related").json()

    assert cheia["method"] == "similaridade calculada"
    assert vazia["method"] == "similaridade calculada"


def test_similarity_orders_the_list(
    acervo: psycopg.Connection[DictRow], client: TestClient
) -> None:
    notas = [d["similarity"] for d in proximas(client, "1")]

    assert notas == sorted(notas, reverse=True)
    assert all(0 < nota <= 1 for nota in notas)


def test_a_decision_that_is_not_in_the_collection_answers_404(
    acervo: psycopg.Connection[DictRow], client: TestClient
) -> None:
    assert client.get(f"/decisions/{SOURCE}/9999/related").status_code == 404


def test_a_nul_byte_is_not_a_crash(
    acervo: psycopg.Connection[DictRow], client: TestClient
) -> None:
    """Both parts arrive from the URL, and PostgreSQL cannot be sent a NUL as
    text. Without the guard this is a stack trace instead of a 404."""
    resposta = client.get(f"/decisions/{SOURCE}/1%00/related")

    assert resposta.status_code == 404


def test_an_environment_without_the_weights_still_opens_the_decision(
    db: psycopg.Connection[DictRow], client: TestClient
) -> None:
    """
    The weights reach an environment only on the next publication, so a base
    published before them has the decisions and not the tables. The screen has
    to keep working: an empty list, never a 500.
    """
    decidir(db, "1", POLUICAO)
    decidir(db, "2", POLUICAO_OUTRA)
    db.execute("DROP TABLE core.termo_judicial")

    resposta = client.get(f"/decisions/{SOURCE}/1/related")

    assert resposta.status_code == 200
    assert resposta.json() == {"results": [], "method": "similaridade calculada"}


def test_the_limit_is_honoured(
    acervo: psycopg.Connection[DictRow], client: TestClient
) -> None:
    # A third decision carrying the same rare words divides their weight:
    # with 205 decisions `LN(205/3)` is 4,2 and falls under the floor. The
    # collection grows with it, which is what happens in the real one too.
    decidir(acervo, "6", POLUICAO_OUTRA)
    encher(acervo, 150, prefixo="g")
    acervo.execute("TRUNCATE core.termo_judicial, core.decisao_norma")
    pesar(acervo)

    resposta = client.get(f"/decisions/{SOURCE}/1/related?limit=1")

    assert len(resposta.json()["results"]) == 1
