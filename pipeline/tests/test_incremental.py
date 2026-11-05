"""
That building by date range gives exactly what building everything gives.

The conversion to `INCREMENTAL_BY_TIME_RANGE` is only safe if the two paths
agree. A divergence between them is silent by nature: the full build is the one
nobody runs after the first week, so whatever the incremental path gets wrong
stays wrong until a reader notices a decision that reads differently from the
one beside it.

So both paths are run here over the same rows and compared column by column.
The fixture is built for the cases that can only go wrong incrementally — a
decision judged in one window and published in the next, one with no judgement
date at all, and two decisions six months apart that share a source link.
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

import psycopg
import pytest
from sqlmesh.core.context import Context

from tests.conftest import TEST_DATABASE_URL, needs_database

pytestmark = needs_database

PROJETO = Path(__file__).resolve().parents[1] / "transformations"

PRIMEIRA = date(2026, 1, 1)
ULTIMA = date(2026, 12, 31)

# `carregado_em` is `NOW()`: it says when the build ran, not what it read, and
# two builds of the same rows differ in it by design.
VOLATEIS = {"carregado_em"}


@pytest.fixture(scope="session")
def contexto(banco: str) -> Context:
    partes = psycopg.conninfo.conninfo_to_dict(TEST_DATABASE_URL)
    os.environ["POSTGRES_DB"] = str(partes.get("dbname"))
    os.environ["POSTGRES_HOST"] = str(partes.get("host", "localhost"))
    os.environ["POSTGRES_PORT"] = str(partes.get("port", "5432"))
    os.environ["POSTGRES_USER"] = str(partes.get("user", "postgres"))
    os.environ["POSTGRES_PASSWORD"] = str(partes.get("password", "postgres"))
    return Context(paths=PROJETO)


def _consulta(contexto: Context, modelo: str, inicio: date, fim: date) -> str:
    return contexto.render(modelo, start=inicio, end=fim).sql(dialect="postgres")


def _semanas(inicio: date, fim: date) -> list[tuple[date, date]]:
    janelas = []
    corrente = inicio
    while corrente <= fim:
        termino = min(corrente + timedelta(days=6), fim)
        janelas.append((corrente, termino))
        corrente = termino + timedelta(days=1)
    return janelas


def de_uma_vez(
    conn: psycopg.Connection, contexto: Context, modelo: str, alvo: str
) -> None:
    conn.execute(f"DROP TABLE IF EXISTS {alvo}")
    conn.execute(f"CREATE TABLE {alvo} AS {_consulta(contexto, modelo, PRIMEIRA, ULTIMA)}")


def semana_a_semana(
    conn: psycopg.Connection, contexto: Context, modelo: str, alvo: str
) -> int:
    """Build the model one window at a time, as a weekly ingestion would."""
    conn.execute(f"DROP TABLE IF EXISTS {alvo}")
    criada = False
    janelas = 0
    for inicio, fim in _semanas(PRIMEIRA, ULTIMA):
        consulta = _consulta(contexto, modelo, inicio, fim)
        if not criada:
            conn.execute(f"CREATE TABLE {alvo} AS {consulta}")
            criada = True
        else:
            conn.execute(f"INSERT INTO {alvo} {consulta}")
        janelas += 1
    return janelas


def colunas(conn: psycopg.Connection, tabela: str) -> list[str]:
    esquema, nome = tabela.split(".")
    linhas = conn.execute(
        "SELECT column_name FROM information_schema.columns"
        " WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
        (esquema.strip('"'), nome.strip('"')),
    ).fetchall()
    return [c for (c,) in linhas if c not in VOLATEIS]


def divergencias(
    conn: psycopg.Connection, completo: str, incremental: str
) -> tuple[list, list]:
    campos = ", ".join(f'"{c}"' for c in colunas(conn, completo))
    so_no_completo = conn.execute(
        f"SELECT {campos} FROM {completo}"
        f" EXCEPT ALL SELECT {campos} FROM {incremental}"
    ).fetchall()
    so_no_incremental = conn.execute(
        f"SELECT {campos} FROM {incremental}"
        f" EXCEPT ALL SELECT {campos} FROM {completo}"
    ).fetchall()
    return so_no_completo, so_no_incremental


def test_decisao_construida_por_faixa_e_igual_a_completa(
    acervo: psycopg.Connection, contexto: Context
) -> None:
    de_uma_vez(acervo, contexto, "core.decisao", "core.decisao_completo")
    janelas = semana_a_semana(acervo, contexto, "core.decisao", "core.decisao_incremental")

    total = acervo.execute("SELECT COUNT(*) FROM core.decisao_completo").fetchone()[0]
    assert total > 0, "o acervo de teste ficou vazio; o resto não prova nada"
    assert janelas > 50, "a janela precisa dividir o acervo para o teste valer"

    faltando, sobrando = divergencias(
        acervo, "core.decisao_completo", "core.decisao_incremental"
    )
    assert faltando == [], f"a construção por faixa perdeu {len(faltando)} linha(s)"
    assert sobrando == [], f"a construção por faixa inventou {len(sobrando)} linha(s)"


def test_nenhuma_decisao_cai_em_duas_janelas(
    acervo: psycopg.Connection, contexto: Context
) -> None:
    """
    A decision belongs to exactly one window.

    The window filters on the same expression the model publishes as
    `data_referencia`. Filtering on a different date — the judgement date, say,
    while publishing the publication date — would put a row in a window and
    leave it there again in the next, and the duplicate only shows as a decision
    listed twice.
    """
    semana_a_semana(acervo, contexto, "core.decisao", "core.decisao_incremental")

    repetidas = acervo.execute(
        "SELECT fonte_codigo, identificador_fonte, COUNT(*)"
        " FROM core.decisao_incremental"
        " GROUP BY 1, 2 HAVING COUNT(*) > 1"
    ).fetchall()

    assert repetidas == [], f"decisões em mais de uma janela: {repetidas}"


ORIGEM_SQL = """
SELECT 'tjdft-jurisdf' AS fonte_codigo,
       identificador   AS identificador_fonte,
       COALESCE("dataJulgamento"::DATE, "dataPublicacao"::DATE) AS data_referencia
FROM raw.acordao_tjdft
WHERE NOT COALESCE("segredoJustica", FALSE)
UNION ALL
SELECT 'stj-espelhos',
       id,
       COALESCE(
           TO_DATE(NULLIF("dataDecisao", ''), 'YYYYMMDD'),
           TO_DATE((REGEXP_MATCH("dataPublicacao", '(\\d{2}/\\d{2}/\\d{4})'))[1], 'DD/MM/YYYY')
       )
FROM raw.espelho_stj
WHERE COALESCE(TRIM(ementa), '') <> ''
"""


def test_nenhuma_decisao_da_origem_fica_de_fora(
    acervo: psycopg.Connection, contexto: Context
) -> None:
    """
    Every decision the source offers lands in exactly one window.

    Comparing the two builds against each other cannot catch a window that
    filters on the wrong date: both would skip the same rows and agree. This
    compares against the source instead, which is the only thing that does not
    move when the filter is wrong — a decision with no judgement date is kept
    out by filtering on `data_julgamento`, and that is precisely the mistake
    the comparison alone reads as agreement.
    """
    semana_a_semana(acervo, contexto, "core.decisao", "core.decisao_incremental")

    esperado = acervo.execute(
        f"SELECT fonte_codigo, identificador_fonte, data_referencia"
        f" FROM ({ORIGEM_SQL}) AS origem ORDER BY 1, 2"
    ).fetchall()
    construido = acervo.execute(
        "SELECT fonte_codigo, identificador_fonte, data_referencia"
        " FROM core.decisao_incremental ORDER BY 1, 2"
    ).fetchall()

    assert len(esperado) > 0, "a origem do teste ficou vazia"
    assert construido == esperado, (
        "a construção por faixa não devolve o acervo da origem: "
        f"faltam {sorted(set(esperado) - set(construido))}, "
        f"sobram {sorted(set(construido) - set(esperado))}"
    )


def test_decisao_precedente_construida_por_faixa_e_igual_a_completa(
    acervo: psycopg.Connection, contexto: Context
) -> None:
    de_uma_vez(acervo, contexto, "core.decisao", "core.decisao")
    de_uma_vez(acervo, contexto, "core.decisao_precedente", "core.precedente_completo")
    semana_a_semana(
        acervo, contexto, "core.decisao_precedente", "core.precedente_incremental"
    )

    total = acervo.execute("SELECT COUNT(*) FROM core.precedente_completo").fetchone()[0]
    assert total > 0, "nenhuma citação no acervo de teste; o resto não prova nada"

    faltando, sobrando = divergencias(
        acervo, "core.precedente_completo", "core.precedente_incremental"
    )
    assert faltando == [], f"a construção por faixa perdeu {len(faltando)} citação(ões)"
    assert sobrando == [], f"a construção por faixa inventou {len(sobrando)} citação(ões)"


def test_link_dividido_entre_janelas_marca_as_duas_decisoes(
    acervo: psycopg.Connection, contexto: Context
) -> None:
    """
    The case that forced `url_compartilhada` out of `core.decisao`.

    Two decisions six months apart build the same source URL. Each sits in its
    own window, and inside either one alone the link looks unique. Only a model
    that reads the whole collection can answer this, which is why it is one.
    """
    semana_a_semana(acervo, contexto, "core.decisao", "core.decisao")
    de_uma_vez(acervo, contexto, "core.url_compartilhada", "core.url_compartilhada")

    marcadas = acervo.execute(
        "SELECT identificador_fonte FROM core.url_compartilhada"
        " WHERE url_compartilhada ORDER BY identificador_fonte"
    ).fetchall()

    assert [i for (i,) in marcadas] == ["stj-001", "stj-002"]

    sozinhas = acervo.execute(
        "SELECT COUNT(*) FROM core.url_compartilhada WHERE NOT url_compartilhada"
    ).fetchone()[0]
    assert sozinhas > 0, "todas marcadas: a regra não está distinguindo nada"
