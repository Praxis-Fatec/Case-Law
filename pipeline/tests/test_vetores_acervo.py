"""
What counts as work left to do, and the digest the whole run rests on.

The embedding run has no checkpoint file: it asks the database what is missing
and trusts the answer. A wrong answer fails silently and expensively — a vector
from an older revision sits in the index beside the new ones and nothing
complains, or seven hours of GPU are spent again on rows already done.
"""

from __future__ import annotations

import psycopg
import psycopg2
import pytest

import embed_corpus
from tests.conftest import TEST_DATABASE_URL, needs_database

pytestmark = needs_database

MODELO = "BAAI/bge-m3"
REVISAO = "5617a9f61b028005a4858fdac845db406aefb181"
OUTRA_REVISAO = "0000000000000000000000000000000000000000"

EMENTAS = {
    "nunca": "RECURSO ESPECIAL. Prescrição intercorrente em execução fiscal.",
    "pronta": "AGRAVO. Responsabilidade civil por atraso de aeronave.",
    "revisao-velha": "HABEAS CORPUS. Dosimetria da pena. Reincidência.",
    "texto-mudou": "EMBARGOS. Juros de mora sobre indébito tributário.",
    "outro-modelo": "APELAÇÃO. Dano moral por inscrição indevida.",
    "vazia": "   ",
}

VETOR = "[" + ",".join(["0.01"] * embed_corpus.DIM) + "]"


@pytest.fixture
def base(acervo: psycopg.Connection) -> psycopg.Connection:
    acervo.execute("CREATE EXTENSION IF NOT EXISTS vector")
    acervo.execute(f"DROP SCHEMA IF EXISTS {embed_corpus.SCHEMA} CASCADE")
    acervo.execute(
        "CREATE TABLE core.decisao ("
        " fonte_codigo TEXT, identificador_fonte VARCHAR, ementa VARCHAR)"
    )
    for identificador, ementa in EMENTAS.items():
        acervo.execute(
            "INSERT INTO core.decisao VALUES ('stj-espelhos', %s, %s)",
            (identificador, ementa),
        )
    acervo.execute(embed_corpus.CREATE)
    return acervo


def _gravar(
    conexao: psycopg.Connection,
    identificador: str,
    texto: str,
    modelo: str = MODELO,
    revisao: str = REVISAO,
) -> None:
    conexao.execute(
        f"INSERT INTO {embed_corpus.TABLE} (fonte_codigo, identificador_fonte,"
        " modelo, revisao, ementa_digest, vetor)"
        " VALUES ('stj-espelhos', %s, %s, %s, %s, %s)",
        (identificador, modelo, revisao, embed_corpus.digest(texto), VETOR),
    )


def _pendentes(conexao: psycopg.Connection) -> set[str]:
    linhas = conexao.execute(
        embed_corpus.PENDING,
        {"modelo": MODELO, "revisao": REVISAO, "fonte": ""},
    ).fetchall()
    return {linha[1] for linha in linhas}


def test_o_digest_do_python_e_o_do_postgres(base: psycopg.Connection) -> None:
    """
    The one invariant resumability rests on, checked over real accents.

    Two implementations of one idea in two languages, and nothing else in the
    run would notice them drifting apart.
    """
    for ementa in EMENTAS.values():
        (do_banco,) = base.execute(
            "SELECT SHA256(CONVERT_TO(%s::text, 'UTF8'))", (ementa,)
        ).fetchone()
        assert bytes(do_banco) == embed_corpus.digest(ementa), ementa


def test_uma_decisao_sem_vetor_esta_pendente(base: psycopg.Connection) -> None:
    assert "nunca" in _pendentes(base)


def test_uma_decisao_ja_embeddada_sai_da_lista(base: psycopg.Connection) -> None:
    _gravar(base, "pronta", EMENTAS["pronta"])
    assert "pronta" not in _pendentes(base)


def test_uma_revisao_antiga_volta_para_a_lista(base: psycopg.Connection) -> None:
    """A vector from another revision of the model is not this model's vector."""
    _gravar(base, "revisao-velha", EMENTAS["revisao-velha"], revisao=OUTRA_REVISAO)
    assert "revisao-velha" in _pendentes(base)


def test_outro_modelo_volta_para_a_lista(base: psycopg.Connection) -> None:
    _gravar(base, "outro-modelo", EMENTAS["outro-modelo"], modelo="outro/modelo")
    assert "outro-modelo" in _pendentes(base)


def test_uma_ementa_que_mudou_volta_para_a_lista(base: psycopg.Connection) -> None:
    """
    The case a checkpoint file would miss.

    A re-collected decision keeps its key and changes its text, so a run that
    only asked whether a row existed would keep a vector describing an ementa
    the collection no longer holds.
    """
    _gravar(base, "texto-mudou", EMENTAS["texto-mudou"])
    base.execute(
        "UPDATE core.decisao SET ementa = %s WHERE identificador_fonte = %s",
        ("EMBARGOS. Texto inteiramente recoletado.", "texto-mudou"),
    )
    assert "texto-mudou" in _pendentes(base)


def test_uma_ementa_vazia_nunca_entra_na_lista(base: psycopg.Connection) -> None:
    """Embedding whitespace produces a vector that would rank against real ones."""
    assert "vazia" not in _pendentes(base)


def test_a_escrita_preserva_o_vetor_e_o_digest(base: psycopg.Connection) -> None:
    """
    The COPY path, which formats six columns by hand.

    A vector written wrong is not a crash: `halfvec` takes a truncated list of
    numbers as long as the count matches, and the ranking is quietly about
    something else.
    """
    vetor = [i / embed_corpus.DIM for i in range(embed_corpus.DIM)]
    escrita = psycopg2.connect(TEST_DATABASE_URL)
    escrita.autocommit = True
    try:
        embed_corpus._escrever(
            escrita, MODELO, REVISAO,
            [("stj-espelhos", "nunca", EMENTAS["nunca"], vetor)],
        )
    finally:
        escrita.close()
    guardado, digest_guardado = base.execute(
        f"SELECT vetor::text, ementa_digest FROM {embed_corpus.TABLE}"
        " WHERE identificador_fonte = 'nunca'"
    ).fetchone()
    lidos = [float(p) for p in guardado.strip("[]").split(",")]

    assert len(lidos) == embed_corpus.DIM
    assert bytes(digest_guardado) == embed_corpus.digest(EMENTAS["nunca"])
    assert lidos == pytest.approx(vetor, abs=5e-4)
    assert "nunca" not in _pendentes(base)
