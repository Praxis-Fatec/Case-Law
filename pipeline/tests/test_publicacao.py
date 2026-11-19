"""
That every table a model builds actually reaches dev and production.

`publish.TABLES` is written by hand, and the staging step copies those names and
nothing else: a table a model creates stays invisible in both environments until
somebody adds it to the list. `core.precedente` and `core.doutrina` were both
finished in the code and absent from the environments for exactly that reason,
which is the mistake this test exists to stop repeating.
"""

from __future__ import annotations

import re
from pathlib import Path

import publish

MODELOS = sorted(
    (Path(__file__).resolve().parents[1] / "transformations" / "models").glob("*.sql")
)


def nomes_dos_modelos() -> set[str]:
    nomes = set()
    for arquivo in MODELOS:
        achado = re.search(
            r"MODEL \(\s*name\s+core\.([a-z_]+)",
            arquivo.read_text(encoding="utf-8"),
        )
        if achado:
            nomes.add(achado.group(1))
    return nomes


def test_todo_modelo_do_core_e_publicado() -> None:
    faltando = sorted(nomes_dos_modelos() - set(publish.TABLES))

    assert not faltando, f"modelos que nunca chegam aos ambientes: {faltando}"


def test_nenhuma_tabela_publicada_deixou_de_existir() -> None:
    """
    O contrário derruba a publicação inteira: `CREATE TABLE ... AS SELECT * FROM
    core.x` falha se `core.x` não existe mais, e falha no meio do staging.
    """
    sobrando = sorted(set(publish.TABLES) - nomes_dos_modelos())

    assert not sobrando, f"tabelas publicadas sem modelo que as construa: {sobrando}"


def test_toda_tabela_publicada_tem_indice() -> None:
    """
    A cópia é um SELECT puro, então nenhum índice vem com ela. Uma tabela que a
    tela lê por chave e chega sem índice não dá erro: ela varre o acervo inteiro
    a cada decisão aberta, e a única pista é a demora.
    """
    indexadas = {
        achado
        for comando in publish.INDEXES
        for achado in re.findall(rf"{publish.STAGING_SCHEMA}\.([a-z_]+)", comando)
    }
    # As que a tela lê por chave da decisão. As de catálogo pequeno — tribunal,
    # fonte, classe processual, carga — são varridas de propósito.
    por_decisao = {
        "decisao",
        "decisao_precedente",
        "decisao_doutrina",
        "referencia_legislativa",
        "url_compartilhada",
    }

    assert por_decisao <= indexadas
