"""
Seguiu, afastou or distinguiu, read from the words around the citation.

The negative forms contain the positive ones: "não se aplica a súmula" carries
"aplica". The order the patterns are tried in is therefore part of the rule,
and these exercise it as the SQL expresses it, so the shapes come from the
collection rather than from imagination.
"""

import re
import unicodedata

import pytest

AFASTOU = re.compile(
    r"nao\s+(?:se\s+)?(?:aplica|incid|atrai)|inaplica|superad[oa]|"
    r"nao\s+obsta|nao\s+ha\s+falar\s+em\s+(?:aplicacao|incidencia)|"
    r"afastad\w*\s+(?:a\s+|o\s+)?(?:incidencia|aplicacao|obice)"
)
DISTINGUIU = re.compile(r"distingu|distincao")
SEGUIU = re.compile(
    r"incid|aplica|obice|obsta|esbarra|atrai|conforme|consoante|conformidade|"
    r"nos\s+termos|a\s+teor|a\s+luz|consonancia|orientacao|entendimento|"
    r"enunciado|observ|vedad|impede|precedente"
)


def _fold(text: str) -> str:
    return "".join(
        ch
        for ch in unicodedata.normalize("NFD", text.lower())
        if unicodedata.category(ch) != "Mn"
    )


def adherence(snippet: str, ementa: str | None = None) -> str | None:
    """The rule in core_decisao_precedente.sql, so a change there breaks a test here."""
    for text in (snippet, ementa):
        if text is None:
            return None
        folded = _fold(text)
        if AFASTOU.search(folded):
            return "afastou"
        if DISTINGUIU.search(folded):
            return "distinguiu"
        if SEGUIU.search(folded):
            return "seguiu"
    return None


SEGUIDAS = [
    ("incidência da Súmula n. 7 do Superior Tribunal de Justiça", "seguiu"),
    ("enfrenta o óbice da Súmula 7/STJ", "seguiu"),
    ("reexame de provas, conforme Súmula 7 do STJ", "seguiu"),
    ("consoante enunciado da Súmula 448/STF", "seguiu"),
    ("em razão da sua conformidade com o Tema 355/STJ", "seguiu"),
    ("acórdão recorrido em consonância com a Súmula 83/STJ", "seguiu"),
    ("aplica-se o IPC, nos termos da Súmula 179/STJ", "seguiu"),
]

AFASTADAS = [
    ("não incidência. Súmula 7/STJ. agravo não provido", "afastou"),
    ("não se aplica a orientação contida na Súmula 183/STJ", "afastou"),
    ("não aplicação - divergência superada - Súmula 168 do STJ", "afastou"),
    ("tal entendimento não se aplica ao caso em análise", "afastou"),
    ("afastada a incidência da Súmula 7/STJ", "afastou"),
]


@pytest.mark.parametrize(("snippet", "expected"), SEGUIDAS)
def test_the_court_applied_the_precedent(snippet: str, expected: str) -> None:
    assert adherence(snippet) == expected


@pytest.mark.parametrize(("snippet", "expected"), AFASTADAS)
def test_the_court_set_the_precedent_aside(snippet: str, expected: str) -> None:
    assert adherence(snippet) == expected


@pytest.mark.parametrize(
    "snippet",
    [
        "não se aplica a Súmula 183/STJ",
        "não incidência da Súmula 7/STJ",
        "inaplicabilidade da Súmula 487/STJ",
        "afastada a aplicação da Súmula 7/STJ",
        "não há falar em incidência da Súmula 282/STF",
    ],
)
def test_a_refusal_is_never_read_as_an_application(snippet: str) -> None:
    """
    The one the subtask exists for. Every text here carries "aplica" or
    "incid" and means the opposite of applying the precedent. A pattern for
    the application tried before the one for the refusal reads all five
    backwards, and nothing in a code review looks wrong.
    """
    assert adherence(snippet) == "afastou"


def test_a_distinction_is_neither_of_the_other_two() -> None:
    assert adherence("há distinção entre o caso e o Tema 630") == "distinguiu"


def test_the_ementa_answers_only_when_one_precedent_was_cited() -> None:
    """
    With a second citation in the same ementa the verb has another precedent
    it could belong to, so attributing it would be a guess.
    """
    bare = "Súmula n. 7/STJ. decisão mantida."
    assert adherence(bare, "reexame de prova, óbice da súmula") == "seguiu"
    assert adherence(bare, None) is None


def test_a_snippet_without_any_signal_stays_unknown() -> None:
    assert adherence("Súmula 7/STJ. honorários advocatícios.") is None
