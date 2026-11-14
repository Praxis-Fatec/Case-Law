"""
O período que cada fonte cobre, e a auditoria que o mantém preenchido.

O SCRUM-156 apontou duas colunas de cobertura com tipo errado e sem dado. O
tipo errado vinha de célula vazia no CSV, e o dado faltava porque ninguém
preenche à mão uma data que muda a cada carga. Os dois defeitos são o mesmo
defeito, e é por isso que o período passou a ser derivado.

O que estes testes seguram é o que não falharia sozinho: uma fonte que
desaparece da tabela, um período que volta a ficar vazio, e um dia inventado
onde a fonte só publicou o ano.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
import pytest
from sqlmesh.core.context import Context

from tests.conftest import TEST_DATABASE_URL, needs_database

pytestmark = needs_database

PROJETO = Path(__file__).resolve().parents[1] / "transformations"
REGRAS = PROJETO / "audits" / "regras.sql"

ALVO = "core.cobertura_fonte_teste"


@pytest.fixture(scope="session")
def contexto(banco: str) -> Context:
    partes = psycopg.conninfo.conninfo_to_dict(TEST_DATABASE_URL)
    os.environ["POSTGRES_DB"] = str(partes.get("dbname"))
    os.environ["POSTGRES_HOST"] = str(partes.get("host", "localhost"))
    os.environ["POSTGRES_PORT"] = str(partes.get("port", "5432"))
    os.environ["POSTGRES_USER"] = str(partes.get("user", "postgres"))
    os.environ["POSTGRES_PASSWORD"] = str(partes.get("password", "postgres"))
    return Context(paths=PROJETO)


def _dependencias(conn: psycopg.Connection) -> None:
    """
    As tabelas que o modelo lê, com uma linha por caso que interessa.

    `core.precedente` já vem do fixture. Faltam as decisões e a doutrina, e é
    aqui que entram os três casos: data por dia, data por ano, e fonte que não
    entregou nada.
    """
    conn.execute("DROP TABLE IF EXISTS core.decisao_cobertura_teste")
    conn.execute(
        "CREATE TABLE core.decisao ("
        " fonte_codigo TEXT, identificador_fonte TEXT, data_julgamento DATE)"
    )
    conn.execute(
        "INSERT INTO core.decisao VALUES"
        " ('tjdft-jurisdf', 'a', '2025-09-17'),"
        " ('tjdft-jurisdf', 'b', '2026-09-17'),"
        " ('stj-espelhos', 'c', '1989-02-19'),"
        " ('stj-espelhos', 'd', '2026-08-26'),"
        " ('stj-espelhos', 'e', NULL)"
    )
    conn.execute("CREATE TABLE core.doutrina (repositorio TEXT, ano BIGINT)")
    conn.execute(
        "INSERT INTO core.doutrina VALUES ('bdjur', 1953), ('bdjur', 2026)"
    )


@pytest.fixture
def cobertura(
    acervo: psycopg.Connection, contexto: Context
) -> list[dict[str, Any]]:
    _dependencias(acervo)
    consulta = contexto.render("core.cobertura_fonte").sql(dialect="postgres")
    acervo.execute(f"DROP TABLE IF EXISTS {ALVO}")
    acervo.execute(f"CREATE TABLE {ALVO} AS {consulta}")

    with acervo.cursor(row_factory=psycopg.rows.dict_row) as cursor:
        cursor.execute(f"SELECT * FROM {ALVO} ORDER BY fonte_codigo")
        return cursor.fetchall()


def _por_fonte(linhas: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {linha["fonte_codigo"]: linha for linha in linhas}


def test_toda_fonte_do_catalogo_aparece(cobertura: list[dict[str, Any]]) -> None:
    """
    Uma linha por fonte, venha ela com item ou sem nenhum.

    Fonte que não aparece na tabela não aparece na tela, e a ausência lá se lê
    como "esta fonte não existe" em vez de "esta fonte não entregou nada" —
    que é informação, e é a que o RF16 pede.
    """
    assert _por_fonte(cobertura).keys() == {
        "tjdft-jurisdf",
        "stj-espelhos",
        "stj-precedentes",
        "stj-bdjur",
    }


def test_o_periodo_sai_das_decisoes_da_fonte(
    cobertura: list[dict[str, Any]],
) -> None:
    linhas = _por_fonte(cobertura)

    assert linhas["tjdft-jurisdf"]["cobertura_inicio"] == date(2025, 9, 17)
    assert linhas["tjdft-jurisdf"]["cobertura_fim"] == date(2026, 9, 17)
    assert linhas["tjdft-jurisdf"]["itens"] == 2
    assert linhas["tjdft-jurisdf"]["precisao"] == "dia"


def test_decisao_sem_data_e_contada_em_vez_de_escondida(
    cobertura: list[dict[str, Any]],
) -> None:
    """
    O período é calculado sobre as decisões datadas, e as outras aparecem na
    contagem. Sem a contagem, um acervo em que metade das decisões não tem data
    mostraria um período de aparência completa.
    """
    espelhos = _por_fonte(cobertura)["stj-espelhos"]

    assert espelhos["itens"] == 3
    assert espelhos["itens_sem_data"] == 1
    assert espelhos["cobertura_inicio"] == date(1989, 2, 19)
    assert espelhos["cobertura_fim"] == date(2026, 8, 26)


def test_a_doutrina_declara_precisao_anual(
    cobertura: list[dict[str, Any]],
) -> None:
    """
    O BDJur publica ano, não data. Guardar 1953-01-01 sem dizer que o dia saiu
    de lugar nenhum é afirmar um 1º de janeiro que ninguém publicou, e o RF16
    proíbe substituir data desconhecida por valor estimado. A precisão é o que
    permite à tela escrever "1953".
    """
    bdjur = _por_fonte(cobertura)["stj-bdjur"]

    assert bdjur["precisao"] == "ano"
    assert bdjur["cobertura_inicio"] == date(1953, 1, 1)
    assert bdjur["cobertura_fim"] == date(2026, 1, 1)


def test_a_sumula_reconstruida_nao_conta_como_coleta_do_portal(
    cobertura: list[dict[str, Any]],
) -> None:
    """
    O fixture traz uma súmula reconstruída, sem data, e um tema do catálogo,
    com data. Só o segundo veio de coleta: contar o primeiro atribuiria ao
    portal do STJ um acervo que ele não forneceu.
    """
    precedentes = _por_fonte(cobertura)["stj-precedentes"]

    assert precedentes["itens"] == 1
    assert precedentes["cobertura_inicio"] == date(2017, 3, 15)


def test_fonte_sem_item_fica_sem_periodo_e_sem_precisao(
    acervo: psycopg.Connection, contexto: Context
) -> None:
    """
    Zero itens, nenhuma data e `precisao` dizendo que não há nenhuma. É o
    estado de uma fonte nova, e dizê-lo é diferente de deixar a célula vazia.
    """
    _dependencias(acervo)
    acervo.execute("DELETE FROM core.doutrina")
    consulta = contexto.render("core.cobertura_fonte").sql(dialect="postgres")
    acervo.execute(f"DROP TABLE IF EXISTS {ALVO}")
    acervo.execute(f"CREATE TABLE {ALVO} AS {consulta}")

    with acervo.cursor(row_factory=psycopg.rows.dict_row) as cursor:
        cursor.execute(f"SELECT * FROM {ALVO} WHERE fonte_codigo = 'stj-bdjur'")
        bdjur = cursor.fetchone()

    assert bdjur is not None
    assert bdjur["itens"] == 0
    assert bdjur["cobertura_inicio"] is None
    assert bdjur["cobertura_fim"] is None
    assert bdjur["precisao"] == "nenhuma"


def _auditoria(conn: psycopg.Connection) -> int:
    """A regra `cobertura_preenchida`, lida do arquivo e apontada para a tabela."""
    texto = REGRAS.read_text(encoding="utf-8")
    cabecalho = texto.index("name cobertura_preenchida")
    inicio = texto.index("SELECT *", cabecalho)
    consulta = texto[inicio : texto.index(";", inicio)]

    with conn.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM ({consulta.replace('@this_model', ALVO)}) AS r")
        contagem = cursor.fetchone()

    assert contagem is not None
    return int(contagem[0])


def test_a_auditoria_passa_sobre_a_tabela_construida(
    acervo: psycopg.Connection, cobertura: list[dict[str, Any]]
) -> None:
    assert _auditoria(acervo) == 0


def test_a_auditoria_reprova_periodo_apagado(
    acervo: psycopg.Connection, cobertura: list[dict[str, Any]]
) -> None:
    """
    Provada quebrando o dado de propósito: é esta a regressão do SCRUM-156, e
    sem a prova a regra poderia estar escrita de um jeito que nunca reprova.
    """
    acervo.execute(
        f"UPDATE {ALVO} SET cobertura_fim = NULL WHERE fonte_codigo = 'tjdft-jurisdf'"
    )

    assert _auditoria(acervo) == 1


def test_a_auditoria_reprova_precisao_inventada(
    acervo: psycopg.Connection, cobertura: list[dict[str, Any]]
) -> None:
    acervo.execute(
        f"UPDATE {ALVO} SET precisao = 'mes' WHERE fonte_codigo = 'stj-bdjur'"
    )

    assert _auditoria(acervo) == 1


def test_a_auditoria_reprova_periodo_invertido(
    acervo: psycopg.Connection, cobertura: list[dict[str, Any]]
) -> None:
    acervo.execute(
        f"UPDATE {ALVO} SET cobertura_inicio = cobertura_fim + 1"
        " WHERE fonte_codigo = 'stj-espelhos'"
    )

    assert _auditoria(acervo) == 1
