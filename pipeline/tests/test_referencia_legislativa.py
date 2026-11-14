"""
What the fixed-format parser reads out of a legislative reference.

The STJ writes each reference as one text field in a layout its own system
builds, so this is parsing and not extraction — and that is exactly why it has
to be pinned down: a layout read slightly wrong still produces a number that
looks like an article, and nothing anywhere fails. Each case in the fixture is
a shape the collection actually contains, counted in
documentation/architecture/legislative-references.md.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import psycopg
import pytest
from psycopg.rows import dict_row
from sqlmesh.core.context import Context

from tests.conftest import needs_database

pytestmark = needs_database

PRIMEIRA = date(2026, 1, 1)
ULTIMA = date(2026, 12, 31)


@pytest.fixture
def referencias(
    acervo: psycopg.Connection, contexto: Context
) -> dict[tuple[str, int, int], dict[str, Any]]:
    """The model built over the whole fixture, keyed by its own grain."""
    for modelo in ("core.decisao", "core.referencia_legislativa"):
        consulta = contexto.render(modelo, start=PRIMEIRA, end=ULTIMA).sql(
            dialect="postgres"
        )
        acervo.execute(f"DROP TABLE IF EXISTS {modelo}")
        acervo.execute(f"CREATE TABLE {modelo} AS {consulta}")

    with acervo.cursor(row_factory=dict_row) as cursor:
        cursor.execute("SELECT * FROM core.referencia_legislativa")
        return {
            (linha["identificador_fonte"], linha["ordem"], linha["sequencia"]): linha
            for linha in cursor.fetchall()
        }


def test_a_referencia_chega_ligada_a_decisao(
    referencias: dict[tuple[str, int, int], dict[str, Any]],
) -> None:
    referencia = referencias[("stj-001", 0, 1)]

    assert referencia["fonte_codigo"] == "stj-espelhos"
    assert referencia["esfera"] == "FED"
    assert referencia["tipo_ato"] == "DEL"
    assert referencia["numero"] == 3365
    assert referencia["ano"] == 1941
    assert referencia["artigo"] == "26"
    assert referencia["paragrafos"] == ["2"]
    assert referencia["reconhecida"] is True
    # The reference date is the citing decision's, because a citation has none
    # of its own, and it is what lets the model be built by date range.
    assert referencia["data_referencia"] == date(2026, 1, 15)


def test_cada_artigo_citado_rende_uma_linha(
    referencias: dict[tuple[str, int, int], dict[str, Any]],
) -> None:
    """
    17,88% das referências citam dois artigos ou mais, até 24 numa só. Uma linha
    por linha de origem guardaria o primeiro e perderia o resto sem avisar.
    """
    primeiro = referencias[("stj-001", 1, 1)]
    segundo = referencias[("stj-001", 1, 2)]

    assert primeiro["artigo"] == "926"
    assert segundo["artigo"] == "927"
    # The paragraphs follow their own ART: token, not the reference.
    assert primeiro["paragrafos"] is None
    assert segundo["paragrafos"] == ["3", "4"]
    assert ("stj-001", 1, 3) not in referencias


def test_o_artigo_com_letra_nao_vira_outro_numero(
    referencias: dict[tuple[str, int, int], dict[str, Any]],
) -> None:
    """
    `ART:0543B` é o art. 543-B. Lido como cinco dígitos sairia o artigo 5.434 —
    número plausível, de artigo que não foi citado. São 24.222 tokens assim.
    """
    referencia = referencias[("stj-001", 2, 1)]

    assert referencia["artigo"] == "543-B"
    assert referencia["incisos"] == ["3"]
    assert referencia["letras"] == ["A", "C"]


def test_a_esfera_fora_das_tres_fica_como_veio(
    referencias: dict[tuple[str, int, int], dict[str, Any]],
) -> None:
    """
    MUN, INT e IES são 0,426% da coleção e não traduzem para federal, estadual
    nem distrital. Apresentar lei municipal como estadual é resposta errada,
    então o código fica cru e a tela mostra o código.
    """
    referencia = referencias[("stj-001", 3, 1)]

    assert referencia["esfera"] == "MUN"
    assert referencia["reconhecida"] is True
    assert referencia["numero"] == 123


def test_a_referencia_sem_tipo_de_ato_fica_marcada_e_com_o_texto(
    referencias: dict[tuple[str, int, int], dict[str, Any]],
) -> None:
    """
    0,7090% das linhas da origem não trazem código de ato — súmula do STF e
    ADCT, sobretudo. A referência existe: ela é marcada, não descartada.
    """
    referencia = referencias[("stj-001", 4, 1)]

    assert referencia["reconhecida"] is False
    assert referencia["tipo_ato"] is None
    assert referencia["esfera"] == "FED"
    assert "SUM:000282" in referencia["texto_bruto"]


def test_nenhuma_linha_de_origem_fica_de_fora(
    acervo: psycopg.Connection,
    referencias: dict[tuple[str, int, int], dict[str, Any]],
) -> None:
    """
    Inclusive a que a origem manda em branco. São 12 na coleção real, e
    STRING_TO_ARRAY devolve vetor vazio para texto vazio: sem o COALESCE do
    modelo elas sairiam da tabela sem aparecer em auditoria nenhuma.
    """
    origem = acervo.execute(
        'SELECT COUNT(*) FROM raw."espelho_stj▶referenciasLegislativas" AS r'
        " JOIN raw.espelho_stj AS e ON e._dlt_id = r._dlt_parent_id"
        " JOIN core.decisao AS d ON d.identificador_fonte = e.id"
    ).fetchone()[0]

    no_modelo = len({(chave[0], chave[1]) for chave in referencias})

    assert no_modelo == origem
    assert referencias[("stj-001", 5, 1)]["texto_bruto"] is None
    assert referencias[("stj-001", 5, 1)]["reconhecida"] is False


def test_o_ato_sem_numero_mantem_o_ano(
    referencias: dict[tuple[str, int, int], dict[str, Any]],
) -> None:
    """
    `CFB:****** ANO:1988` é como o tribunal escreve a Constituição. Os asteriscos
    são ausência, não zero: 30,29% das referências não têm número e a tela diz
    o ato e o ano.
    """
    referencia = referencias[("stj-002", 0, 1)]

    assert referencia["tipo_ato"] == "CFB"
    assert referencia["numero"] is None
    assert referencia["ano"] == 1988
    assert referencia["artigo"] == "105"


def test_paragrafo_unico_e_lido_sem_acento_tambem(
    referencias: dict[tuple[str, int, int], dict[str, Any]],
) -> None:
    """`ÚNICO` 29.666 vezes e `UNICO` 8.042: a mesma coisa, escrita de dois jeitos."""
    assert referencias[("stj-002", 1, 1)]["paragrafos"] == ["único"]


LIMITE = "referencia_reconhecida_no_limite"


def _auditoria(contexto: Context, nome: str) -> str:
    """The rule as the project declares it, not a copy of it written here."""
    return contexto.standalone_audits[nome].query.sql(dialect="postgres")


@pytest.fixture
def taxa(acervo: psycopg.Connection, contexto: Context) -> Any:
    """
    A table of a size the rule actually looks at, whose rate the test sets.

    The fixture collection has eight references, and a rule about a proportion
    says nothing about eight rows — which is why the rule itself carries a
    floor of a hundred thousand. Proving it needs a table above that floor, so
    this builds one and each test below chooses how much of it the parser
    failed to read.
    """
    acervo.execute("DROP TABLE IF EXISTS core.referencia_legislativa")
    acervo.execute(
        "CREATE TABLE core.referencia_legislativa AS"
        " SELECT i AS ordem, TRUE AS reconhecida"
        " FROM GENERATE_SERIES(1, 150000) AS i"
    )

    def estragar(uma_em: int) -> list[tuple[Any, ...]]:
        acervo.execute("UPDATE core.referencia_legislativa SET reconhecida = TRUE")
        if uma_em:
            acervo.execute(
                "UPDATE core.referencia_legislativa SET reconhecida = FALSE"
                f" WHERE ordem % {uma_em} = 0"
            )
        return acervo.execute(_auditoria(contexto, LIMITE)).fetchall()

    return estragar


def test_o_limite_passa_na_taxa_medida_hoje(taxa: Any) -> None:
    """0,606% — uma em 165 — que é o que a coleção real traz."""
    assert taxa(165) == []


def test_o_limite_reprova_acima_de_um_por_cento(taxa: Any) -> None:
    """
    A prova de que a regra morde: 2% das linhas sem esfera ou sem tipo de ato, o
    que é o que se veria se o tribunal parasse de escrever o código do ato.
    """
    assert taxa(50) != []


def test_o_limite_nao_reprova_por_arredondamento(taxa: Any) -> None:
    """Uma em 101 é 0,99%: abaixo do limite, e tem que continuar passando."""
    assert taxa(101) == []


def test_o_limite_ignora_tabela_de_amostra(
    acervo: psycopg.Connection, contexto: Context
) -> None:
    """
    Abaixo de cem mil linhas a regra não opina. Sem esse piso, todo ambiente de
    amostra reprovaria a carga por uma proporção que não mede nada.
    """
    acervo.execute("DROP TABLE IF EXISTS core.referencia_legislativa")
    acervo.execute(
        "CREATE TABLE core.referencia_legislativa AS"
        " SELECT i AS ordem, FALSE AS reconhecida"
        " FROM GENERATE_SERIES(1, 50000) AS i"
    )

    assert acervo.execute(_auditoria(contexto, LIMITE)).fetchall() == []
