"""
Que toda auditoria citada por um modelo exista de verdade.

O SQLMesh não reclama de um nome que não resolve: a auditoria simplesmente não
roda. Um erro de digitação na lista do bloco MODEL desliga a regra em silêncio,
e a carga continua passando — que é o pior jeito de perder uma garantia.
"""

import re
from pathlib import Path

TRANSFORMACOES = Path(__file__).resolve().parents[1] / "transformations"
MODELOS = sorted((TRANSFORMACOES / "models").glob("*.sql"))
REGRAS = sorted((TRANSFORMACOES / "audits").glob("*.sql"))

# As que o SQLMesh traz prontas; não estão em regras.sql e não precisam estar.
EMBUTIDAS = {
    "not_null",
    "unique_values",
    "unique_combination_of_columns",
    "accepted_values",
}


def declaradas() -> set[str]:
    nomes: set[str] = set()
    for arquivo in REGRAS:
        nomes |= set(
            re.findall(
                r"AUDIT \(\s*name\s+([a-z_]+)\s*,",
                arquivo.read_text(encoding="utf-8"),
            )
        )
    return nomes


def avulsas() -> set[str]:
    """
    As que rodam sozinhas, sem modelo que as cite.

    Uma auditoria de cobertura presa a um modelo construído por faixa de data
    confere só a janela recém-escrita, onde o piso de cem mil linhas nunca é
    alcançado — ela passa sem olhar nada. Fora do modelo, lê a tabela inteira.
    Não aparecer na lista de nenhum modelo é o ponto, não um esquecimento.
    """
    nomes: set[str] = set()
    for arquivo in REGRAS:
        nomes |= set(
            re.findall(
                r"AUDIT \(\s*name\s+([a-z_]+)\s*,\s*standalone\s+true",
                arquivo.read_text(encoding="utf-8"),
            )
        )
    return nomes


def citadas(modelo: Path) -> set[str]:
    texto = modelo.read_text(encoding="utf-8")
    bloco = re.search(r"audits\s*\((.*?)\n\s*\)\s*\n\);", texto, re.DOTALL)

    if not bloco:
        return set()

    # Os argumentos saem antes: `not_null(columns := (a, b))` traz nomes de
    # coluna que não são auditoria nenhuma.
    lista = re.sub(r"\([^()]*(?:\([^()]*\)[^()]*)*\)", "", bloco.group(1))
    nomes = re.findall(r"[a-z_]+", lista)
    return {nome for nome in nomes if nome not in EMBUTIDAS}


def test_toda_auditoria_citada_existe() -> None:
    existentes = declaradas()
    faltando = {
        modelo.name: sorted(citadas(modelo) - existentes)
        for modelo in MODELOS
        if citadas(modelo) - existentes
    }

    assert not faltando, f"auditorias citadas e inexistentes: {faltando}"


def test_nenhuma_auditoria_fica_sem_uso() -> None:
    """
    O contrário também engana: uma regra escrita e nunca citada parece proteger
    e não protege nada.
    """
    usadas = set().union(*(citadas(modelo) for modelo in MODELOS)) | avulsas()

    assert not declaradas() - usadas


def test_o_link_oficial_tem_auditoria() -> None:
    """
    A regra da SCRUM-180, presa ao modelo que ela guarda.

    Mudou de modelo quando `url_compartilhada` saiu de `core.decisao`: é lá que
    a coluna mora agora, e uma auditoria que ficasse para trás apontaria para
    uma coluna que o modelo não tem mais.
    """
    modelo = TRANSFORMACOES / "models" / "core_url_compartilhada.sql"

    assert "url_aponta_para_um_acordao" in citadas(modelo)
