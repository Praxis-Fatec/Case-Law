"""
What the STF's acordaos become once they are read into the collection.

The connector's own tests cover reading the service. These cover the step
after: a source whose class names are abbreviated, whose oldest records predate
every other source by ninety-seven years, and whose "no ementa" case is a
sentence rather than an empty field.

Each test here stands for a measurement taken against the real collection and
recorded in the model. Without them the rules would be three regular
expressions that nobody could tell had stopped working.
"""

from datetime import date
from typing import Any

import psycopg
import psycopg.rows
import pytest
from sqlmesh.core.context import Context

from tests.conftest import needs_database

pytestmark = needs_database

CEDO = date(1892, 1, 1)
TARDE = date(2026, 12, 31)


@pytest.fixture
def decisoes(
    acervo: psycopg.Connection, contexto: Context
) -> dict[str, dict[str, Any]]:
    """The whole collection built in one pass, keyed by source identifier."""
    consulta = contexto.render("core.decisao", start=CEDO, end=TARDE).sql(
        dialect="postgres"
    )
    acervo.execute("DROP TABLE IF EXISTS core.decisao_stf_teste")
    acervo.execute(f"CREATE TABLE core.decisao_stf_teste AS {consulta}")
    with acervo.cursor(row_factory=psycopg.rows.dict_row) as cursor:
        cursor.execute(
            "SELECT * FROM core.decisao_stf_teste"
            " WHERE fonte_codigo = 'stf-jurisprudencia'"
        )
        return {
            linha["identificador_fonte"]: dict(linha) for linha in cursor.fetchall()
        }


class TestOQueEntra:
    def test_the_court_arrives_as_its_own_source(
        self, decisoes: dict[str, dict[str, Any]]
    ) -> None:
        assert decisoes, "nenhuma decisão do STF chegou à coleção"
        assert {d["tribunal_sigla"] for d in decisoes.values()} == {"STF"}

    def test_the_placeholder_ementa_is_not_a_decision(
        self, decisoes: dict[str, dict[str, Any]]
    ) -> None:
        """
        3.608 acórdãos do acervo carregado — 0,97% — trazem "Acórdão sem
        ementa." no lugar da ementa, e outros 16 vêm realmente vazios. O campo
        não está vazio, então `ementa_nao_vazia` aprova — e a decisão entraria
        no índice de busca para casar com quem procurasse a palavra "ementa".
        """
        assert "sjur-sem-ementa" not in decisoes
        for decisao in decisoes.values():
            assert "sem ementa" not in decisao["ementa"].lower()

    def test_a_judgement_from_before_the_old_start_is_reached(
        self, decisoes: dict[str, dict[str, Any]]
    ) -> None:
        """
        Metade do acervo do STF é anterior a 1989, que era onde o modelo
        começava. Com a data antiga essas decisões entrariam no `raw` e
        sumiriam aqui, sem erro e sem linha nenhuma a menos no log.
        """
        antigo = decisoes.get("sjur-antigo")

        assert antigo is not None, (
            "a decisão de 1961 não sobreviveu ao filtro de janela"
        )
        assert antigo["data_referencia"] == date(1961, 3, 14)


class TestClasse:
    def test_the_outermost_class_of_an_abbreviated_ladder_wins(
        self, decisoes: dict[str, dict[str, Any]]
    ) -> None:
        """
        "EMB.DECL.NO AG.REG.NO AGRAVO DE INSTRUMENTO" são embargos de
        declaração — não o agravo regimental, nem o agravo de instrumento em
        que ele foi interposto.
        """
        classe = decisoes["sjur-escada"]["classe_cnj"]

        assert classe == 1327, f"a escada resolveu para {classe}"

    def test_an_ordinal_does_not_hide_the_class(
        self, decisoes: dict[str, dict[str, Any]]
    ) -> None:
        """
        "SEGUNDO AGRAVO REGIMENTAL NO RECURSO EXTRAORDINÁRIO" continua sendo um
        agravo regimental. Sem tirar o ordinal ele fica sem classe, e com a
        regra inteira 369.273 dos 373.178 acórdãos — 98,95% — resolvem.
        """
        assert decisoes["sjur-ordinal"]["classe_cnj"] == 1321

    def test_the_class_comes_from_the_court_s_own_subtree(
        self, acervo: psycopg.Connection, decisoes: dict[str, dict[str, Any]]
    ) -> None:
        """
        "Agravo Regimental" existe em mais de uma raiz da tabela do CNJ. O do
        STF é o 1321, sob a raiz 1310; o 206 é o cível. Escolher pelo nome sem
        desempatar pela raiz dá a classe de outro tribunal, e a tela mostra um
        rótulo plausível e errado.
        """
        codigos = [d["classe_cnj"] for d in decisoes.values() if d["classe_cnj"]]
        assert codigos

        fora = acervo.execute(
            """
            WITH RECURSIVE arvore AS (
              SELECT codigo_cnj, codigo_cnj AS raiz
              FROM core.classe_processual WHERE codigo_pai IS NULL
              UNION ALL
              SELECT s.codigo_cnj, a.raiz
              FROM core.classe_processual s JOIN arvore a ON s.codigo_pai = a.codigo_cnj
            )
            SELECT codigo_cnj FROM arvore
            WHERE codigo_cnj = ANY(%s) AND raiz <> 1310
            """,
            (codigos,),
        ).fetchall()

        assert fora == [], f"classes fora da subárvore do STF: {fora}"


class TestDocumento:
    def test_the_token_is_the_whole_query_and_the_link_carries_it(
        self, decisoes: dict[str, dict[str, Any]]
    ) -> None:
        """
        O nome do parâmetro muda com a época — `numero` e `classe` nos antigos,
        `idDocumento` nos novos. Por isso o token é a query inteira, e é a
        auditoria `url_carrega_o_identificador` que o liga ao link publicado.
        """
        antigo = decisoes["sjur-antigo"]
        novo = decisoes["sjur-escada"]

        assert antigo["identificador_documento"] == "numero=41000&classe=HC"
        assert novo["identificador_documento"] == "idDocumento=800000"

        for decisao in (antigo, novo):
            assert decisao["identificador_documento"] in decisao["url_fonte"]
            assert decisao["url_fonte"].startswith("https://portal.stf.jus.br/")

    def test_the_token_is_never_the_record_s_own_key(
        self, decisoes: dict[str, dict[str, Any]]
    ) -> None:
        """A auditoria `token_do_documento_por_fonte` reprova a troca."""
        for chave, decisao in decisoes.items():
            assert decisao["identificador_documento"] != chave


class TestCampos:
    def test_the_reporting_judge_of_the_acordao_wins_over_the_one_of_the_case(
        self, decisoes: dict[str, dict[str, Any]]
    ) -> None:
        """
        Os dois campos existem e divergem quando o relator é vencido: quem
        assina o acórdão é o relator para o acórdão.
        """
        assert decisoes["sjur-escada"]["relator"] == "MIN. RELATOR DO ACORDAO"

    def test_absence_arrives_as_absence(
        self, decisoes: dict[str, dict[str, Any]]
    ) -> None:
        """
        6,8% dos acórdãos não trazem órgão julgador, 6,8% não trazem data de
        publicação e 0,1% não trazem relator — e a escassez se concentra nos
        mais antigos. Preencher qualquer um deles dataria ou atribuiria uma
        decisão por conveniência.
        """
        antigo = decisoes["sjur-antigo"]

        assert antigo["orgao_julgador"] is None
        assert antigo["data_publicacao"] is None
        assert antigo["relator"] is None
        assert antigo["data_julgamento"] == date(1961, 3, 14)
