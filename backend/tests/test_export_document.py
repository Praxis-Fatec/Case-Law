"""The PDF must identify the exact cut and preserve its references and order."""

from datetime import UTC, date, datetime
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from pypdf import PdfReader

from app.export import ExportDataset
from app.export_document import (
    DELIBERATION_LABELS,
    NOT_INFORMED,
    ORDER_LABELS,
    OUTCOME_LABELS,
    official_reference,
    render_export_html,
    render_export_pdf,
)

GENERATED = datetime(2026, 10, 23, 15, 30, 45, tzinfo=UTC)


def decision(n: int) -> dict[str, Any]:
    return {
        "fonte_codigo": "stj-espelhos",
        "identificador_fonte": f"id-{n:04d}",
        "processo": f"processo-{n:04d}",
        "tribunal_sigla": "STJ",
        "orgao_julgador": "CORTE ESPECIAL",
        "relator": "RELATOR A",
        "classe_cnj": 198,
        "data_julgamento": date(2024, 2, 29),
        "data_publicacao": date(2024, 3, 1),
        "data_referencia": date(2024, 2, 29),
        "deliberacao": "maioria",
        "resultado": "parcialmente_provido",
        "snippet": "CIVIL. Dano <mark>moral</mark> comprovado. Recurso provido em parte.",
        "url_fonte": f"https://example.test/oficial?documento={n}&origem=STJ",
        "link_valido": True,
    }


def dataset(count: int = 1) -> ExportDataset:
    return ExportDataset(
        total=count,
        order="relevance",
        decisions=[decision(n) for n in range(1, count + 1)],
        query='"dano moral" OR "indenização" -tributário',
        filters={
            "tribunais": ["STJ"],
            "orgao_julgador": ["CORTE ESPECIAL"],
            "relator": ["RELATOR A"],
            "classe_cnj": [198],
            "resultado": ["parcialmente_provido"],
            "date_from": date(2024, 1, 1),
            "date_to": date(2024, 12, 31),
            "published_from": date(2024, 2, 1),
            "published_to": date(2024, 3, 31),
        },
    )


class DocumentText(HTMLParser):
    def __init__(self, html: str) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.feed(html)

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    @property
    def text(self) -> str:
        return " ".join(self.parts)


def test_header_identifies_literal_expression_every_filter_count_order_and_timezone() -> (
    None
):
    data = dataset()
    text = DocumentText(render_export_html(data, generated_at=GENERATED)).text
    assert data.query in text
    for expected in (
        "Tribunais STJ",
        "Órgão julgador CORTE ESPECIAL",
        "Relator RELATOR A",
        "Classe CNJ 198",
        "Resultado Parcialmente provido",
        "Data do julgamento — de 01/01/2024",
        "Data do julgamento — até 31/12/2024",
        "Data de publicação — de 01/02/2024",
        "Data de publicação — até 31/03/2024",
        "Relevância",
        "Total de decisões do recorte:",
        "Decisões neste documento:",
        "23/10/2026 12:30:45",
        "America/Sao_Paulo",
        "2026-10-23T12:30:45-03:00",
    ):
        assert expected in text


def test_all_absent_metadata_is_explicit_without_inventing_a_judgment_date() -> None:
    data = dataset()
    row = data.decisions[0]
    for key in row:
        row[key] = None
    row["data_referencia"] = date(2024, 3, 1)
    text = DocumentText(render_export_html(data, generated_at=GENERATED)).text
    for label in (
        "Fonte",
        "Identificação da decisão",
        "Processo",
        "Tribunal",
        "Órgão julgador",
        "Relator",
        "Classe CNJ",
        "Data do julgamento",
        "Data de publicação",
        "Deliberação",
        "Resultado",
        "Trecho da ementa",
    ):
        assert f"{label} {NOT_INFORMED}" in text
    assert "Data de referência 01/03/2024" in text
    assert "Fonte oficial: Link indisponível no momento." in text


@pytest.mark.parametrize("vote", [None, "", "  "])
def test_missing_vote_is_not_inferred_from_an_outcome(vote: str | None) -> None:
    data = dataset()
    data.decisions[0]["deliberacao"] = vote
    text = DocumentText(render_export_html(data)).text
    assert "Deliberação Não informado" in text
    assert "Resultado Parcialmente provido" in text


def test_text_is_escaped_and_highlight_tags_do_not_leak_into_the_document() -> None:
    data = dataset()
    data = data._replace(
        query='<script src="https://attack.test/a.js">expressão</script>'
    )
    data.decisions[0]["relator"] = '<img src="https://attack.test/image">'
    html = render_export_html(data, generated_at=GENERATED)
    assert "<script" not in html and "<img" not in html and "<mark>" not in html
    assert data.query in DocumentText(html).text
    assert "Dano moral comprovado" in DocumentText(html).text


@pytest.mark.parametrize(
    "url",
    [
        None,
        "",
        "javascript:alert(1)",
        "file:///etc/passwd",
        "https://",
        "http://[bad",
        "https://bad host/",
    ],
)
def test_invalid_or_missing_url_never_becomes_an_invented_link(url: str | None) -> None:
    row = decision(1)
    row["url_fonte"] = url
    result = official_reference(row)
    assert "Link indisponível no momento." in result
    assert "href=" not in result


def test_audited_url_is_kept_exactly_and_broken_links_are_not_followable() -> None:
    row = decision(1)
    row["url_fonte"] = "https://oficial.test/path/123?inteiro=sim&formato=pdf#documento"
    row["identificador_fonte"] = "different-id-must-not-be-interpolated"
    html = official_reference(row)
    assert (
        'href="https://oficial.test/path/123?inteiro=sim&amp;formato=pdf#documento"'
        in html
    )
    assert "different-id" not in html
    row["link_valido"] = False
    assert "href=" not in official_reference(row)


def test_document_labels_match_the_existing_interface() -> None:
    components = Path(__file__).resolve().parents[2] / "frontend/src/components"
    formats = (components / "decisionFormat.ts").read_text(encoding="utf-8")
    outcomes = (components / "outcomeFormat.ts").read_text(encoding="utf-8")
    orders = (components / "ResultsSort.tsx").read_text(encoding="utf-8")
    assert f"'{NOT_INFORMED}'" in formats
    for key, label in DELIBERATION_LABELS.items():
        assert key in formats
        assert f"'{label}'" in formats
    for key, label in OUTCOME_LABELS.items():
        assert f"{key}: '{label}'" in outcomes
    for key, label in ORDER_LABELS.items():
        assert f"value: '{key}', label: '{label}'" in orders


@pytest.mark.parametrize("data", [dataset(0), dataset(2)._replace(total=3)])
def test_refuses_empty_or_incomplete_datasets(data: ExportDataset) -> None:
    with pytest.raises(ValueError, match="complete, nonempty"):
        render_export_pdf(data)


def test_generation_time_cannot_silently_assume_the_machine_timezone() -> None:
    with pytest.raises(ValueError, match="timezone"):
        render_export_html(dataset(), generated_at=GENERATED.replace(tzinfo=None))


def test_one_hundred_decisions_have_pagination_order_and_exact_clickable_references() -> (
    None
):
    data = dataset(100)
    # Deliberately keep a nonnumeric input order. The renderer must not sort again.
    data.decisions.reverse()
    data = data._replace(order="date")
    pdf = render_export_pdf(data, generated_at=GENERATED)
    assert pdf.startswith(b"%PDF-")
    reader = PdfReader(BytesIO(pdf))
    assert len(reader.pages) > 1
    texts = [page.extract_text() for page in reader.pages]
    text = "\n".join(texts)
    assert "Mais recentes" in text
    assert "Total de decisões do recorte: 100" in text
    assert "Decisões neste documento: 100" in text
    assert "Unânime" not in text
    positions = [text.index(row["processo"]) for row in data.decisions]
    assert positions == sorted(positions)
    for index, page_text in enumerate(texts, 1):
        assert f"Página {index} de {len(reader.pages)}" in page_text
    links = [
        annotation.get_object()["/A"]["/URI"]
        for page in reader.pages
        for annotation in page.get("/Annots", [])
        if annotation.get_object().get("/A", {}).get("/S") == "/URI"
    ]
    assert links == [row["url_fonte"] for row in data.decisions]


def test_very_long_excerpt_can_continue_on_multiple_pages_without_losing_its_end() -> (
    None
):
    data = dataset()
    data.decisions[0]["snippet"] = (
        "Fundamentação jurídica extensa. " * 1500
    ) + "FIM-DA-EMENTA"
    pdf = render_export_pdf(data, generated_at=GENERATED)
    reader = PdfReader(BytesIO(pdf))
    assert len(reader.pages) > 1
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert "FIM-DA-EMENTA" in text
    assert "Link indisponível" not in text
