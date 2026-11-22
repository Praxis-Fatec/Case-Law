"""
A atribuição da carga à fonte, que é de onde sai "última coleta" no RF16.

O dlt não registra qual extrator rodou: as coletas compartilham o mesmo
`pipeline_name` e o mesmo `_dlt_loads`. A fonte sai de qual tabela crua recebeu
linha naquela carga, e isso quer dizer que `core.carga` tem um ramo escrito à
mão por fonte. Fonte nova sem ramo não dá erro: a carga fica com fonte nula, e
a tela passa a afirmar "nunca coletada" sobre uma fonte que entregou registros
— uma afirmação falsa, que é pior do que a ausência que o RF16 manda declarar.

Foi o que aconteceu com o `cnj-bnp`: a fonte entrou no catálogo e na coleta, e
o ramo ficou faltando. Este teste é a guarda que não existia.
"""

from __future__ import annotations

from typing import Any

import psycopg
import pytest
from sqlmesh.core.context import Context

from tests.conftest import needs_database

pytestmark = needs_database

ALVO = "core.carga_atribuicao_teste"

# Uma tabela crua por fonte coletada, com a coluna que o modelo lê.
CRUAS = {
    "tjdft-jurisdf": ("acordao_tjdft", '"segredoJustica" BOOLEAN, identificador TEXT'),
    "stj-espelhos": ("espelho_stj", "processo TEXT"),
    "stj-precedentes": ("precedente_stj", '"numeroPrecedente" TEXT'),
    "stj-bdjur": ("doutrina_bdjur", "identificador_oai TEXT"),
    "stf-jurisprudencia": ("acordao_stf", "identificador TEXT"),
    "cnj-bnp": ("precedente_pangea", "id TEXT"),
}

CARGA = "carga-de-todas"
# A carga que só o registro oficial escreveu. É ela que expõe o ramo faltante:
# com uma carga que todas escreveram, os outros cinco ramos já dão fonte à
# linha, e a ausência do sexto passa despercebida.
CARGA_SO_BNP = "carga-so-do-bnp"


def _acervo_de_cargas(conn: psycopg.Connection) -> None:
    """
    Duas cargas: uma que todas as tabelas escreveram, e uma que só o BNP.
    """
    conn.execute("DROP TABLE IF EXISTS raw._dlt_loads CASCADE")
    conn.execute(
        "CREATE TABLE raw._dlt_loads (load_id TEXT, status INT,"
        " inserted_at TIMESTAMPTZ)"
    )
    conn.execute(
        "INSERT INTO raw._dlt_loads VALUES"
        " (%s, 0, '2026-11-20 10:00:00+00'),"
        " (%s, 0, '2026-11-20 11:00:00+00')",
        (CARGA, CARGA_SO_BNP),
    )

    conn.execute("DROP TABLE IF EXISTS verificacao.link CASCADE")
    conn.execute("CREATE SCHEMA IF NOT EXISTS verificacao")
    conn.execute(
        "CREATE TABLE verificacao.link (identificador TEXT, valido BOOLEAN)"
    )

    for tabela, colunas in CRUAS.values():
        conn.execute(f'DROP TABLE IF EXISTS raw."{tabela}" CASCADE')
        conn.execute(
            f'CREATE TABLE raw."{tabela}" ({colunas}, _dlt_load_id TEXT)'
        )
        primeira = colunas.split(",")[0].strip().split(" ")[0]
        valor = "FALSE" if "BOOLEAN" in colunas.split(",")[0] else "'x'"
        conn.execute(
            f'INSERT INTO raw."{tabela}" ({primeira}, _dlt_load_id)'
            f" VALUES ({valor}, %s)",
            (CARGA,),
        )

    conn.execute(
        'INSERT INTO raw."precedente_pangea" (id, _dlt_load_id)'
        " VALUES ('y', %s)",
        (CARGA_SO_BNP,),
    )


@pytest.fixture
def cargas(acervo: psycopg.Connection, contexto: Context) -> list[dict[str, Any]]:
    _acervo_de_cargas(acervo)

    consulta = contexto.render("core.carga").sql(dialect="postgres")
    acervo.execute(f"DROP TABLE IF EXISTS {ALVO}")
    acervo.execute(f"CREATE TABLE {ALVO} AS {consulta}")

    with acervo.cursor(row_factory=psycopg.rows.dict_row) as cursor:
        cursor.execute(f"SELECT * FROM {ALVO}")
        return cursor.fetchall()


def test_toda_fonte_coletada_reivindica_a_carga(
    cargas: list[dict[str, Any]],
) -> None:
    """
    O teste que faltava. Fonte coletada sem ramo no modelo não reivindica a
    carga, e a tela afirma que ela nunca foi coletada.
    """
    reivindicadas = {l["fonte_codigo"] for l in cargas if l["fonte_codigo"]}

    assert reivindicadas == set(CRUAS)


def test_a_carga_que_so_o_registro_escreveu_nao_fica_orfa(
    cargas: list[dict[str, Any]],
) -> None:
    """
    Fonte nula é legítima na carga que não gravou nada — a janela incremental
    não achou novidade. Esta gravou, e só numa tabela, então nula aqui é ramo
    faltando. É o caso que a tela lê como "nunca coletada".
    """
    dela = [l for l in cargas if l["carga_id"] == CARGA_SO_BNP]

    assert [l["fonte_codigo"] for l in dela] == ["cnj-bnp"]


def test_o_registro_oficial_conta_o_que_gravou(
    cargas: list[dict[str, Any]],
) -> None:
    """
    O BNP não descarta por sigilo nem tem link verificado: zero ali afirmaria
    que nada foi descartado e que nenhum link falhou, quando ninguém olhou.
    """
    bnp = next(
        l
        for l in cargas
        if l["fonte_codigo"] == "cnj-bnp" and l["carga_id"] == CARGA
    )

    assert bnp["registros_lidos"] == 1
    assert bnp["registros_gravados"] == 1
    assert bnp["descartados_sigilo"] is None
    assert bnp["links_invalidos"] is None
    assert bnp["links_nao_verificados"] is None
