"""Printable references from a validated, complete export dataset."""

from datetime import date, datetime
from html import escape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

from app.export import ExportDataset

# Match decisionFormat.ts, outcomeFormat.ts and ResultsSort.tsx. Contract tests
# guard the wording shared by the Python document and the TypeScript interface.
NOT_INFORMED = "Não informado"
DELIBERATION_LABELS = {
    "unanime": "Unânime",
    "maioria": "Por maioria",
    "nao-informado": NOT_INFORMED,
    "nao-aplicavel": "Não aplicável",
}
OUTCOME_LABELS = {
    "negado": "Negado",
    "provido": "Provido",
    "parcialmente_provido": "Parcialmente provido",
}
ORDER_LABELS = {"relevance": "Relevância", "date": "Mais recentes"}
FILTER_LABELS = {
    "tribunais": "Tribunais",
    "orgao_julgador": "Órgão julgador",
    "relator": "Relator",
    "classe_cnj": "Classe CNJ",
    "resultado": "Resultado",
    "date_from": "Data do julgamento — de",
    "date_to": "Data do julgamento — até",
    "published_from": "Data de publicação — de",
    "published_to": "Data de publicação — até",
}


def display(value: Any) -> str:
    if value is None or not str(value).strip():
        return NOT_INFORMED
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return str(value).strip()


class ExcerptText(HTMLParser):
    """Strip ts_headline's mark tags before escaping the excerpt as plain text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def official_reference(row: dict[str, Any]) -> str:
    # Keep the audited url_fonte exactly; never interpolate identifiers into it.
    raw = row.get("url_fonte")
    url = raw.strip() if isinstance(raw, str) else ""
    try:
        parsed = urlsplit(url)
        valid = parsed.scheme in {"http", "https"} and bool(parsed.hostname)
        valid = valid and not any(c.isspace() or ord(c) < 32 for c in url)
    except ValueError:
        valid = False
    if not valid or row.get("link_valido") is False:
        return '<p class="source">Fonte oficial: Link indisponível no momento.</p>'
    return (
        f'<p class="source">Fonte oficial: <a href="{escape(url, quote=True)}">'
        f'Abrir fonte oficial</a><br><span class="url">{escape(url)}</span></p>'
    )


def decision_entry(index: int, row: dict[str, Any]) -> str:
    vote = display(row.get("deliberacao"))
    outcome = display(row.get("resultado"))
    fields = [
        ("Fonte", row.get("fonte_codigo")),
        ("Identificação da decisão", row.get("identificador_fonte")),
        ("Processo", row.get("processo")),
        ("Tribunal", row.get("tribunal_sigla")),
        ("Órgão julgador", row.get("orgao_julgador")),
        ("Relator", row.get("relator")),
        ("Classe CNJ", row.get("classe_cnj")),
        ("Data do julgamento", row.get("data_julgamento")),
        ("Data de publicação", row.get("data_publicacao")),
        ("Data de referência", row.get("data_referencia")),
        ("Deliberação", DELIBERATION_LABELS.get(vote, vote)),
        ("Resultado", OUTCOME_LABELS.get(outcome, outcome)),
    ]
    metadata = "".join(
        f"<div><dt>{escape(label)}</dt><dd>{escape(display(value))}</dd></div>"
        for label, value in fields
    )
    excerpt = ExcerptText()
    excerpt.feed(row.get("snippet") or "")
    excerpt.close()
    return (
        f'<article class="decision"><h2>{index}. '
        f"{escape(display(row.get('tribunal_sigla')))} — "
        f"{escape(display(row.get('identificador_fonte')))}</h2>"
        f'<dl class="metadata">{metadata}</dl>'
        "<h3>Trecho da ementa</h3>"
        f'<p class="excerpt">{escape(display("".join(excerpt.parts)))}</p>'
        f"{official_reference(row)}</article>"
    )


def render_export_html(
    dataset: ExportDataset, *, generated_at: datetime | None = None
) -> str:
    if dataset.total < 1 or dataset.total != len(dataset.decisions):
        raise ValueError("A document requires a complete, nonempty export dataset.")
    zone = ZoneInfo("America/Sao_Paulo")
    instant = generated_at if generated_at is not None else datetime.now(zone)
    if instant.utcoffset() is None:
        raise ValueError("Generation time must include a timezone.")
    instant = instant.astimezone(zone)
    timestamp = instant.strftime("%d/%m/%Y %H:%M:%S")
    timestamp += f" · America/Sao_Paulo · {instant.isoformat(timespec='seconds')}"
    filters = []
    for key, label in FILTER_LABELS.items():
        value = dataset.filters.get(key)
        if isinstance(value, list):
            values = [
                OUTCOME_LABELS.get(str(v), v) if key == "resultado" else v
                for v in value
            ]
            rendered = "; ".join(display(v) for v in values) or "Sem restrição"
        else:
            rendered = display(value) if value is not None else "Sem restrição"
        filters.append(
            f"<div><dt>{escape(label)}</dt><dd>{escape(rendered)}</dd></div>"
        )
    count = f"{dataset.total:,}".replace(",", ".")
    entries = "".join(
        decision_entry(i, row) for i, row in enumerate(dataset.decisions, 1)
    )
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>Case Law — Referências do recorte</title><style>
@page {{ size:A4; margin:18mm 16mm 20mm; }}
* {{ box-sizing:border-box; }}
body {{ font:12px/1.5 Arial,sans-serif; color:#30242a; }}
h1,h2 {{ font-family:Georgia,serif; color:#421523; }}
h1 {{ font-size:28px; margin:8px 0 16px; }}
h2 {{ font-size:18px; margin:0 0 12px; break-after:avoid; }}
h3 {{ font-size:12px; margin:12px 0 4px; break-after:avoid; }}
.eyebrow {{ text-transform:uppercase; letter-spacing:2px; color:#79636b; }}
.query,.excerpt {{ white-space:pre-wrap; overflow-wrap:anywhere; }}
.query {{ padding:12px; background:#fff1eb; border-left:3px solid #6b1730; }}
.filters,.metadata {{ display:grid; grid-template-columns:1fr 1fr; gap:8px 18px; }}
dl {{ margin:12px 0; }} dl div {{ min-width:0; overflow-wrap:anywhere; }}
dt {{ font-weight:bold; }} dd {{ margin:0; }}
.metadata {{ gap:5px 18px; }}
.metadata dt,.metadata dd {{ display:inline; }}
.metadata dt::after {{ content:': '; }}
.summary {{ border-bottom:1px solid #d9c8cd; padding-bottom:18px; margin-bottom:22px; }}
.decision {{ border-bottom:1px solid #d9c8cd; padding:18px 0; break-inside:avoid; }}
.source {{ font-size:11px; overflow-wrap:anywhere; }}
.url {{ color:#79636b; }} a {{ color:#6b1730; }}
.note {{ font-size:11px; color:#79636b; }}
</style></head><body><header class="summary">
<p class="eyebrow">Case Law · Exportação do recorte</p>
<h1>Referências da pesquisa</h1>
<h3>Expressão pesquisada</h3><p class="query">{escape(dataset.query)}</p>
<h3>Filtros aplicados</h3><dl class="filters">{"".join(filters)}</dl>
<p><b>Ordenação:</b> {ORDER_LABELS[dataset.order]}<br>
<b>Total de decisões do recorte:</b> {count}<br>
<b>Decisões neste documento:</b> {count}<br>
<b>Gerado em:</b> {escape(timestamp)}</p>
<p class="note">A ordem preserva a pesquisa aplicada. Os trechos de ementa
reproduzem a seleção textual da busca. A data de referência utiliza a data do
julgamento ou, quando ausente na origem, a de publicação; isso não preenche
uma data de julgamento ausente. Consulte a fonte oficial para o conteúdo integral.</p>
</header><main>{entries}</main>
<p class="note">Frequência não representa relevância jurídica.</p></body></html>"""


def render_export_pdf(
    dataset: ExportDataset, *, generated_at: datetime | None = None
) -> bytes:
    # Validate and build before starting a browser. This function owns no files,
    # connection or pagination state; the collector already fixed the snapshot.
    document = render_export_html(dataset, generated_at=generated_at)
    with (
        sync_playwright() as playwright,
        playwright.chromium.launch() as browser,
    ):
        page = browser.new_page(java_script_enabled=False)
        page.route("**/*", lambda route: route.abort())
        page.set_content(document, wait_until="load")
        return page.pdf(
            print_background=True,
            prefer_css_page_size=True,
            display_header_footer=True,
            header_template="<span></span>",
            footer_template=(
                '<div style="font:9px Arial;width:100%;text-align:center;color:#79636b">'
                'Case Law · Página <span class="pageNumber"></span> de '
                '<span class="totalPages"></span></div>'
            ),
        )
