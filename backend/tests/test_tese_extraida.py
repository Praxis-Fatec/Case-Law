"""
The thesis the court wrote, split into what it numbered.

The split is the part that breaks quietly: a loose number inside a sentence
matches the item pattern, and one thesis becomes two fragments that read as
nonsense on screen.
"""

from app.ementa import theses


def test_a_numbered_block_becomes_one_entry_per_item() -> None:
    found = theses(
        "1. A palavra da vítima possui especial relevância em crimes de "
        "violência doméstica. 2. A ausência de testemunhas presenciais não "
        "inviabiliza a condenação."
    )

    assert len(found) == 2
    assert found[0].startswith("A palavra da vítima")
    assert found[1].startswith("A ausência de testemunhas")


def test_a_single_thesis_is_a_list_of_one() -> None:
    """A quarter of the blocks carry one thesis and no numbering."""
    found = theses(
        "A ausência de impugnação concreta de todos os fundamentos impede o "
        "conhecimento do agravo em recurso especial."
    )

    assert len(found) == 1
    assert found[0].startswith("A ausência")


def test_letters_count_as_items_too() -> None:
    found = theses(
        "a) o habeas corpus não é cabível como substitutivo de recurso "
        "próprio; b) a suspensão do livramento condicional exige contraditório."
    )

    assert len(found) == 2


def test_a_precedent_number_does_not_open_an_item() -> None:
    """
    "Incide a Súmula n. 7 do STJ" carries a number followed by a stop, which is
    the item pattern. Splitting there turns four theses into eleven fragments —
    measured on two decisions of a hundred-decision sample.
    """
    found = theses(
        "1. Incide a Súmula n. 7 do STJ para obstar o reexame do conjunto "
        "fático-probatório. 2. Aplica-se, por analogia, a Súmula n. 284 do "
        "STF diante da deficiência de fundamentação."
    )

    assert len(found) == 2
    assert "Súmula n. 7 do STJ" in found[0]
    assert "Súmula n. 284 do STF" in found[1]


def test_a_law_number_does_not_open_an_item_either() -> None:
    found = theses(
        "1. Aplica-se a Súmula n. 83 do STJ quando o acórdão se harmoniza com "
        "a jurisprudência que resguarda, pelo art. 39 da Lei n. 4.886/1965, o "
        "foro do domicílio do representante comercial."
    )

    assert len(found) == 1


def test_a_lone_item_number_is_dropped_from_the_text() -> None:
    found = theses("1. Diante da ausência de elementos, não cabe a tutela.")

    assert found == ["Diante da ausência de elementos, não cabe a tutela."]


def test_nothing_in_nothing_out() -> None:
    assert theses(None) == []
    assert theses("") == []
    assert theses("   ") == []
