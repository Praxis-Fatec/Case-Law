"""
A ordem entre os três registros de precedente, e o que ela conserta.

A reconstrução acertou 87,1% dos enunciados e errou calada no resto: decisão
cita súmulas em bloco, e o par número-texto mais próximo não é o par certo. A
Súmula 70 do STF vinha com o enunciado da 323. É esse o defeito que a
precedência existe para corrigir, e o fixture o reproduz — três decisões
transcrevendo o texto errado sob o número certo, que é exatamente o que passa
pelo piso de três transcrições.

O que estes testes seguram é o que não falharia sozinho: o oficial deixar de
vencer, um precedente desaparecer na troca, a súmula vinculante colidir com a
súmula de mesmo número, e a data de julgamento — que só o catálogo publica —
sumir junto com o texto que ela acompanhava.
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

ALVO = "core.precedente_fusao_teste"

# O enunciado verdadeiro da Súmula 323, que a reconstrução prende na 70.
TEXTO_DA_323 = (
    "e inadmissivel a apreensao de mercadorias como meio coercitivo "
    "para pagamento de tributos"
)
TEXTO_OFICIAL_DA_70 = (
    "É inadmissível a interdição de estabelecimento como meio coercitivo "
    "para cobrança de tributo."
)


@pytest.fixture(scope="session")
def contexto(banco: str) -> Context:
    partes = psycopg.conninfo.conninfo_to_dict(TEST_DATABASE_URL)
    os.environ["POSTGRES_DB"] = str(partes.get("dbname"))
    os.environ["POSTGRES_HOST"] = str(partes.get("host", "localhost"))
    os.environ["POSTGRES_PORT"] = str(partes.get("port", "5432"))
    os.environ["POSTGRES_USER"] = str(partes.get("user", "postgres"))
    os.environ["POSTGRES_PASSWORD"] = str(partes.get("password", "postgres"))
    return Context(paths=PROJETO)


def _decisoes(conn: psycopg.Connection) -> None:
    """Três acórdãos transcrevendo o texto da 323 sob o número da 70."""
    conn.execute("DROP TABLE IF EXISTS core.decisao CASCADE")
    conn.execute("CREATE TABLE core.decisao (identificador_fonte TEXT, ementa TEXT)")
    ementa = (
        "TRIBUTARIO. EXECUCAO FISCAL. Sumula 70 do STF: "
        f'"{TEXTO_DA_323}". Recurso conhecido e provido.'
    )
    for i in range(3):
        conn.execute(
            "INSERT INTO core.decisao VALUES (%s, %s)", (f"d-{i}", ementa)
        )


def _catalogo(conn: psycopg.Connection) -> None:
    """
    O catálogo do STJ: um tema que o BNP também tem, e um que ele não firmou.

    O 100 prova a precedência; o 999 prova que nada desaparece quando o
    oficial chega sem tese.
    """
    conn.execute("DROP TABLE IF EXISTS raw.precedente_stj")
    conn.execute(
        'CREATE TABLE raw.precedente_stj ("numeroPrecedente" TEXT,'
        ' "tipoPrecedente" TEXT, "teseFirmada" TEXT, situacao TEXT,'
        ' "dataJulgamento" TEXT)'
    )
    conn.execute(
        'INSERT INTO raw.precedente_stj ("numeroPrecedente", "tipoPrecedente",'
        ' "teseFirmada", situacao, "dataJulgamento") VALUES'
        " ('100', 'Tema', %s, 'Trânsito em julgado', '2017-03-15'),"
        " ('999', 'Tema', %s, 'Trânsito em julgado', '2019-05-20')",
        (
            "Tese antiga do catalogo, com mais de quarenta caracteres de texto.",
            "Tese que so o catalogo publica, com mais de quarenta caracteres.",
        ),
    )


def _bnp(conn: psycopg.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS raw.precedente_pangea")
    conn.execute(
        "CREATE TABLE raw.precedente_pangea (id TEXT, orgao TEXT, tipo TEXT,"
        ' nr BIGINT, tese TEXT, questao TEXT, situacao TEXT,'
        ' "ultimaAtualizacao" TEXT)'
    )
    linhas = [
        # Súmula do STF: o texto está em `questao` e `tese` é a string literal.
        ("stf-sum-70", "STF", "SUM", 70, "não informado", TEXTO_OFICIAL_DA_70,
         "APROVADO", "22/05/2025"),
        ("stf-sum-1", "STF", "SUM", 1, "não informado",
         "É vedada a expulsão de estrangeiro casado com Brasileira.",
         "APROVADO", "22/05/2025"),
        ("stf-sum-619", "STF", "SUM", 619, "não informado",
         "Enunciado cancelado, com mais de quarenta caracteres de texto.",
         "Cancelado", "15/10/2026"),
        # Vinculante 1 divide o número com a Súmula 1 e diz outra coisa.
        ("stf-sv-1", "STF", "SV", 1, "não informado",
         "Ofende a garantia constitucional do ato jurídico perfeito a decisão.",
         "APROVADO", "22/05/2025"),
        # Súmula do STJ: o texto está em `tese`, com marcação.
        ("stj-sum-1", "STJ", "SUM", 1,
         "<p>O foro do domicílio ou da residência do alimentando é o "
         "competente.</p><br>", "", "Vigente", "01/04/2025"),
        # O tema que o catálogo também tem, com texto diferente.
        ("stj-rr-100", "STJ", "RR", 100,
         "<p>Tese oficial do BNP, com mais de quarenta caracteres de "
         "texto.</p>", "A questão que foi posta.", "Transitado em julgado",
         "09/06/2026"),
        # O tema sem tese firmada: pergunta, não precedente.
        ("stj-rr-999", "STJ", "RR", 999, "não informado",
         "A questão ainda em julgamento.", "Afetado", "09/06/2026"),
        # Situação que é uma frase inteira, como o registro faz para tema.
        ("stf-rg-1", "STF", "RG", 1,
         "Tese de repercussão geral, com mais de quarenta caracteres.",
         "Base de cálculo do PIS.",
         "Há repercussão geral. Leading case: transitado em julgado",
         "15/10/2026"),
        # Tema cuja marcação chega escapada, como o registro manda em três.
        ("stj-rr-986", "STJ", "RR", 986,
         "&lt;span style=\"font-size:14px\"&gt;A Tarifa de Uso do Sistema de "
         "Transmissão compõe a base de cálculo do ICMS.&lt;/span&gt;",
         "A questão que foi posta.", "Transitado em julgado", "09/06/2026"),
    ]
    for linha in linhas:
        conn.execute(
            "INSERT INTO raw.precedente_pangea (id, orgao, tipo, nr, tese,"
            ' questao, situacao, "ultimaAtualizacao")'
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            linha,
        )


@pytest.fixture
def precedentes(
    acervo: psycopg.Connection, contexto: Context
) -> list[dict[str, Any]]:
    _decisoes(acervo)
    _catalogo(acervo)
    _bnp(acervo)

    consulta = contexto.render("core.precedente").sql(dialect="postgres")
    acervo.execute(f"DROP TABLE IF EXISTS {ALVO}")
    acervo.execute(f"CREATE TABLE {ALVO} AS {consulta}")

    with acervo.cursor(row_factory=psycopg.rows.dict_row) as cursor:
        cursor.execute(f"SELECT * FROM {ALVO} ORDER BY corte, tipo, numero")
        return cursor.fetchall()


def _chave(
    linhas: list[dict[str, Any]],
) -> dict[tuple[str, str, int], dict[str, Any]]:
    return {(l["corte"], l["tipo"], l["numero"]): l for l in linhas}


def test_o_oficial_corrige_o_enunciado_reconstruido(
    precedentes: list[dict[str, Any]],
) -> None:
    """
    O defeito que a história existe para consertar.

    A reconstrução prendeu na Súmula 70 do STF o enunciado da 323, e passou
    pelo piso de três transcrições porque as três decisões transcrevem igual.
    Repetição confirma que o texto foi transcrito, nunca que foi transcrito
    para aquele número.
    """
    linha = _chave(precedentes)[("STF", "sumula", 70)]

    assert linha["enunciado"] == TEXTO_OFICIAL_DA_70
    assert linha["origem"] == "oficial"
    assert "apreensao de mercadorias" not in linha["enunciado"]


def test_o_oficial_vence_o_catalogo(precedentes: list[dict[str, Any]]) -> None:
    linha = _chave(precedentes)[("STJ", "tema", 100)]

    assert linha["origem"] == "oficial"
    assert linha["enunciado"].startswith("Tese oficial do BNP")


def test_a_data_do_catalogo_atravessa_a_fusao(
    precedentes: list[dict[str, Any]],
) -> None:
    """
    Só o catálogo publica data de julgamento; o BNP não traz nenhuma. Tomar a
    data pela mesma regra do texto esvaziaria a coluna para substituí-la por
    nada, então o texto vem de quem venceu e a data vem de quem a tem.
    """
    linha = _chave(precedentes)[("STJ", "tema", 100)]

    assert linha["origem"] == "oficial"
    assert linha["data"] == date(2017, 3, 15)


def test_nenhum_precedente_desaparece_na_troca(
    precedentes: list[dict[str, Any]],
) -> None:
    """
    Tema que o BNP tem sem tese firmada não some: o oficial só entra com
    enunciado, e quem fica sem ele cede a vez para o registro anterior.
    """
    linha = _chave(precedentes)[("STJ", "tema", 999)]

    assert linha["origem"] == "catalogo"
    assert linha["enunciado"].startswith("Tese que so o catalogo publica")


def test_tema_sem_tese_firmada_nao_entra_sozinho(
    precedentes: list[dict[str, Any]],
) -> None:
    """Tema sem tese é pergunta, não precedente — a mesma regra do catálogo."""
    assert ("STF", "tema", 999) not in _chave(precedentes)


def test_a_vinculante_nao_colide_com_a_sumula(
    precedentes: list[dict[str, Any]],
) -> None:
    """
    Os 62 números de vinculante já existem como súmula do STF, e a Súmula
    Vinculante 1 não é a Súmula 1. Na mesma chave, uma sobrescreveria a outra.
    """
    por_chave = _chave(precedentes)
    sumula = por_chave[("STF", "sumula", 1)]
    vinculante = por_chave[("STF", "sumula_vinculante", 1)]

    assert sumula["enunciado"] != vinculante["enunciado"]
    assert "expulsão de estrangeiro" in sumula["enunciado"]
    assert "ato jurídico perfeito" in vinculante["enunciado"]


def test_a_marcacao_do_stj_sai_do_enunciado(
    precedentes: list[dict[str, Any]],
) -> None:
    """A tela lê o enunciado como texto dentro de uma citação."""
    linha = _chave(precedentes)[("STJ", "sumula", 1)]

    assert "<p>" not in linha["enunciado"]
    assert "<br>" not in linha["enunciado"]
    assert linha["enunciado"].endswith("é o competente.")


def test_a_marcacao_escapada_tambem_sai(
    precedentes: list[dict[str, Any]],
) -> None:
    """
    Três temas trazem a tag escapada. Limpar antes de desescapar devolvia
    `<span style="font-size:14px">` à tela em 71 citações.
    """
    linha = _chave(precedentes)[("STJ", "tema", 986)]

    assert "<" not in linha["enunciado"]
    assert "span" not in linha["enunciado"]
    assert linha["enunciado"].startswith("A Tarifa de Uso")


def test_o_texto_da_sumula_do_stf_vem_de_questao(
    precedentes: list[dict[str, Any]],
) -> None:
    """
    A súmula do STF tem `tese` igual à string literal "não informado" nas 734,
    e o enunciado em `questao`. Ler só `tese` daria 29,2% do registro vazio.
    """
    linha = _chave(precedentes)[("STF", "sumula", 1)]

    assert linha["enunciado"] != "não informado"
    assert "expulsão de estrangeiro" in linha["enunciado"]


def test_a_situacao_chega_e_marca_o_cancelado(
    precedentes: list[dict[str, Any]],
) -> None:
    por_chave = _chave(precedentes)

    assert por_chave[("STF", "sumula", 619)]["situacao"] == "Cancelado"
    assert por_chave[("STF", "sumula", 1)]["situacao"] == "APROVADO"
    assert por_chave[("STJ", "sumula", 1)]["situacao"] == "Vigente"


def test_a_situacao_de_tema_pode_ser_uma_frase(
    precedentes: list[dict[str, Any]],
) -> None:
    """`situacao` é texto livre: 26 valores no registro, e frase para tema."""
    linha = _chave(precedentes)[("STF", "tema", 1)]

    assert linha["situacao"] == (
        "Há repercussão geral. Leading case: transitado em julgado"
    )


def test_a_data_da_ultima_atualizacao_e_lida(
    precedentes: list[dict[str, Any]],
) -> None:
    """A única data que o BNP publica, e o que diz há quanto tempo a situação
    não se move."""
    por_chave = _chave(precedentes)

    assert por_chave[("STF", "sumula", 619)]["atualizado_em"] == date(2026, 10, 15)
    assert por_chave[("STJ", "tema", 999)]["atualizado_em"] is None


def test_todo_tipo_escrito_e_conhecido(
    precedentes: list[dict[str, Any]],
) -> None:
    tipos = {linha["tipo"] for linha in precedentes}

    assert tipos <= {"sumula", "sumula_vinculante", "tema"}
