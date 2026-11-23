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

    Uma tabela em `ORIGENS` é lida de outro esquema e não tem modelo; é por
    declarar a origem que ela escapa desta lista, não por exceção escrita aqui.
    """
    sobrando = sorted(set(publish.TABLES) - nomes_dos_modelos() - set(publish.ORIGENS))

    assert not sobrando, f"tabelas publicadas sem modelo que as construa: {sobrando}"


def test_toda_origem_declarada_e_publicada() -> None:
    """Declarar a origem de uma tabela que ninguém publica não faz nada."""
    orfas = sorted(set(publish.ORIGENS) - set(publish.TABLES))

    assert not orfas, f"origens declaradas para tabelas fora de TABLES: {orfas}"


def test_toda_coluna_escolhida_tem_origem_declarada() -> None:
    """
    Escolher colunas de uma tabela lida de `core` é o jeito de publicar metade
    dela sem perceber: o `SELECT *` some e ninguém nota qual campo ficou fora.
    """
    sem_origem = sorted(set(publish.COLUNAS) - set(publish.ORIGENS))

    assert not sem_origem, f"colunas escolhidas sem origem declarada: {sem_origem}"


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
        "decisao_vetor",
    }

    assert por_decisao <= indexadas


def test_o_indice_vetorial_nao_e_construido_duas_vezes() -> None:
    """
    Um índice em `INDEXES` é construído no staging e reconstruído pelo
    `pg_restore` no destino. Para o vetorial isso seria a construção mais cara
    da publicação paga duas vezes, então ele sai do staging e é criado uma vez
    só, na outra ponta, onde a memória de construção pode ser ajustada.
    """
    assert "hnsw" not in " ".join(publish.INDEXES).lower()
    assert "hnsw" in publish.VETOR_INDICE.lower()


def test_a_dimensao_do_indice_e_a_que_o_pipeline_gera() -> None:
    """Indexar 1024 bits de um vetor de outro tamanho não dá erro, dá ruído."""
    import embed_corpus

    assert publish.VETOR_DIMENSOES == embed_corpus.DIM
