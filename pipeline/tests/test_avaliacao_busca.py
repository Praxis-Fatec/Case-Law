"""
Which of the court's similar acórdãos become an evaluation pair, and which do not.

Everything a later model is judged by rests on this set, so the exclusions
matter more than the inclusions. Each case below is a shape the collection
actually contains and the reason it is excluded is measured in
documentation/architecture/search-evaluation.md: a decision the court lists as
similar to itself, another judgement of the same case, a citation that names a
case the collection holds under a different judgement date, and a registry the
collection holds twice.
"""

from __future__ import annotations

from datetime import date

import psycopg
import pytest
from sqlmesh.core.context import Context

import evaluate_search
from tests.conftest import needs_database

pytestmark = needs_database

PRIMEIRA = date(2026, 1, 1)
ULTIMA = date(2026, 12, 31)

DECISOES = (
    ("sim-a", "202600000011", "20260210", "CONSULTA. Usucapiao extraordinario."),
    ("sim-b", "202600000022", "20260310", "ALVO. Usucapiao extraordinario. Posse."),
    ("sim-c", "202600000033", "20260410", "AMBIGUO. Primeiro dos dois."),
    ("sim-c2", "202600000033", "20260410", "AMBIGUO. Segundo dos dois."),
    ("sim-d", "202600000044", "20260510", "DATA DIFERENTE. Outro julgamento."),
    ("sim-e", "202600000055", "20260610", "ALVO EM CAIXA ALTA. Posse velha."),
    ("sim-a2", "202600000011", "20260910", "MESMO PROCESSO QUE A CONSULTA."),
)

# All six cited by `sim-a`, which is the only query this fixture offers.
CITACOES = (
    ("REsp 1 SP 2026/0000001-1 Decisão:10/02/2026", "auto-referencia"),
    ("REsp 2 SP 2026/0000002-2 Decisão:10/03/2026", "par-valido"),
    ("REsp 3 SP 2026/0000001-1 Decisão:10/09/2026", "mesmo-processo"),
    ("REsp 4 SP 2026/0000003-3 Decisão:10/04/2026", "alvo-ambiguo"),
    ("REsp 5 SP 2026/0000004-4 Decisão:01/01/2026", "data-que-nao-casa"),
    ("RESP 6 SP 2026/0000005-5 DECISÃO:10/06/2026", "caixa-alta"),
)


@pytest.fixture
def pares(acervo: psycopg.Connection, contexto: Context) -> set[tuple[str, str]]:
    """The evaluation set the script builds over this fixture."""
    with acervo.cursor() as cursor:
        cursor.executemany(
            'INSERT INTO raw.espelho_stj (id, "numeroProcesso", "numeroRegistro",'
            ' "descricaoClasse", "nomeOrgaoJulgador", "ministroRelator",'
            ' "dataPublicacao", ementa, "dataDecisao", decisao, _dlt_load_id, _dlt_id)'
            " VALUES (%s, %s, %s, 'RECURSO ESPECIAL', 'TERCEIRA TURMA', 'MIN. X',"
            " 'DJE DATA:20/10/2026', %s, %s, 'Negaram provimento.', 'carga-1', %s)",
            [
                (identificador, "2026/0000000-0", registro, ementa, julgada, f"dlt-{identificador}")
                for identificador, registro, julgada, ementa in DECISOES
            ],
        )
        cursor.executemany(
            'INSERT INTO raw."espelho_stj▶acordaosSimilares"'
            " (value, _dlt_parent_id, _dlt_list_idx, _dlt_id) VALUES (%s, 'dlt-sim-a', %s, %s)",
            [(valor, indice, rotulo) for indice, (valor, rotulo) in enumerate(CITACOES)],
        )

    consulta = contexto.render("core.decisao", start=PRIMEIRA, end=ULTIMA).sql(
        dialect="postgres"
    )
    acervo.execute("DROP TABLE IF EXISTS core.decisao")
    acervo.execute(f"CREATE TABLE core.decisao AS {consulta}")

    acervo.execute(evaluate_search.CREATE)
    acervo.execute(evaluate_search.BUILD)

    with acervo.cursor() as cursor:
        cursor.execute(f"SELECT consulta, relevante FROM {evaluate_search.PAIRS}")
        return {(linha[0], linha[1]) for linha in cursor.fetchall()}


def test_o_par_que_o_tribunal_nomeou_entra(pares: set[tuple[str, str]]) -> None:
    assert ("sim-a", "sim-b") in pares


def test_a_citacao_em_caixa_alta_tambem_e_lida(pares: set[tuple[str, str]]) -> None:
    # The older mirrors write `DECISÃO:`, the newer ones `Decisão:`. A
    # case-sensitive read loses 294.000 entries and never says so.
    assert ("sim-a", "sim-e") in pares


def test_a_decisao_que_se_cita_nao_vira_par(pares: set[tuple[str, str]]) -> None:
    # Retrieving itself is not agreement with the court, and 1.184 of the
    # resolved entries are exactly this.
    assert ("sim-a", "sim-a") not in pares


def test_outro_julgamento_do_mesmo_processo_nao_vira_par(
    pares: set[tuple[str, str]],
) -> None:
    # Near-identical text, trivially retrievable by any method, which would
    # flatter every score equally and measure nothing.
    assert ("sim-a", "sim-a2") not in pares


def test_o_registro_que_o_acervo_tem_duas_vezes_fica_de_fora(
    pares: set[tuple[str, str]],
) -> None:
    assert not {p for p in pares if p[1] in {"sim-c", "sim-c2"}}


def test_a_data_que_nao_casa_nao_resolve(pares: set[tuple[str, str]]) -> None:
    # The registry names the case, not the judgement. Resolving on it alone
    # would link to a different judgement and present it as the one named.
    assert ("sim-a", "sim-d") not in pares


def test_o_conjunto_tem_so_os_dois_pares_validos(pares: set[tuple[str, str]]) -> None:
    assert pares == {("sim-a", "sim-b"), ("sim-a", "sim-e")}
