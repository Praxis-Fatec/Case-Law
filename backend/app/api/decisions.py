from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from psycopg import Connection
from psycopg.rows import DictRow
from pydantic import BaseModel, Field

from app.config import settings
from app.db import get_connection

router = APIRouter(tags=["search"])

SEARCH_CONFIG = "portugues_sem_acento"

QUERY = f"websearch_to_tsquery('{SEARCH_CONFIG}', %(term)s)"
MATCH = f"ementa_busca @@ {QUERY}"

SNIPPET = f"""
ts_headline(
    '{SEARCH_CONFIG}', ementa, {QUERY},
    'StartSel=<mark>, StopSel=</mark>, MaxWords=38, MinWords=22,
     MaxFragments=2, FragmentDelimiter= … '
)
"""

FULL_HIGHLIGHT = f"""
ts_headline(
    '{SEARCH_CONFIG}', ementa, {QUERY},
    'StartSel=<mark>, StopSel=</mark>, HighlightAll=TRUE'
)
"""

COUNT_SQL = f"SELECT COUNT(*) AS total FROM core.decisao WHERE {MATCH}"

ORDERING = f"""
ORDER BY
    ts_rank(ementa_busca, {QUERY}) DESC,
    data_referencia DESC,
    identificador_fonte DESC
"""

PAGE_SQL = f"""
WITH pagina AS (
    SELECT fonte_codigo, identificador_fonte
    FROM core.decisao
    WHERE {MATCH}
    {ORDERING}
    LIMIT %(limit)s OFFSET %(offset)s
)
SELECT
    decisao.fonte_codigo,
    decisao.identificador_fonte,
    decisao.tribunal_sigla,
    decisao.processo,
    decisao.orgao_julgador,
    decisao.relator,
    decisao.data_referencia,
    decisao.turma_recursal,
    decisao.url_fonte,
    {SNIPPET} AS snippet
FROM pagina
JOIN core.decisao USING (fonte_codigo, identificador_fonte)
{ORDERING}
"""

DETAIL_SQL = """
SELECT
    fonte_codigo,
    identificador_fonte,
    tribunal_sigla,
    processo,
    orgao_julgador,
    relator,
    classe_cnj,
    data_julgamento,
    data_publicacao,
    data_referencia,
    ementa,
    decisao_texto,
    turma_recursal,
    possui_inteiro_teor,
    url_fonte
FROM core.decisao
WHERE fonte_codigo = %(source)s AND identificador_fonte = %(identifier)s
"""

HIGHLIGHT_SQL = f"""
SELECT {FULL_HIGHLIGHT} AS highlighted
FROM core.decisao
WHERE fonte_codigo = %(source)s AND identificador_fonte = %(identifier)s
"""


class DecisionBase(BaseModel):
    source: str = Field(
        description="Which collection the decision came from.",
        examples=["tjdft-jurisdf"],
    )
    identifier: str = Field(
        description="The identifier the court itself uses.",
        examples=["2084700"],
    )
    court: str = Field(description="Court abbreviation.", examples=["TJDFT"])
    case_number: str | None = Field(
        description="Case number in the national format.",
        examples=["0738852-37.2024.8.07.0003"],
    )
    judging_body: str | None = Field(
        description="The panel that decided.",
        examples=["1ª TURMA CÍVEL"],
    )
    reporting_judge: str | None = Field(
        description="The judge who wrote the opinion.",
        examples=["FABRÍCIO FONTOURA BEZERRA"],
    )
    decided_on: date = Field(
        description="Judgement date, or publication date when the first is absent.",
        examples=["2026-01-28"],
    )
    small_claims: bool = Field(
        description="Whether it comes from a small claims appellate panel.",
        examples=[False],
    )
    source_url: str = Field(
        description="The decision on the court's own site, which always prevails.",
        examples=["https://jurisdf.tjdft.jus.br/detalhes/2084700"],
    )


class DecisionMatch(DecisionBase):
    snippet: str = Field(
        description=(
            "The part of the ementa that matched, with every hit wrapped in "
            "`<mark>`. Accents survive: only the matching ignores them."
        ),
        examples=["Ilícito contratual. <mark>Dano</mark> <mark>moral</mark>."],
    )


class Decision(DecisionBase):
    class_code: int | None = Field(
        description="Case class, as the national court council codes it.",
        examples=[12394],
    )
    judged_on: date | None = Field(description="When the panel decided.")
    published_on: date | None = Field(description="When it reached the gazette.")
    summary: str = Field(
        description="The ementa in full: the legal thesis, as the court wrote it."
    )
    outcome: str | None = Field(
        description="The operative part, when the court records it separately.",
        examples=["ADMITIR. JULGAR IMPROCEDENTE A REVISÃO CRIMINAL. UNÂNIME."],
    )
    full_text_available: bool = Field(
        description="Whether the court offers the complete document."
    )


class SearchResults(BaseModel):
    total: int = Field(
        description="How many decisions match, beyond the current page.",
        examples=[1847],
    )
    page: int = Field(description="Which page this is, starting at 1.", examples=[1])
    page_size: int = Field(description="How many results per page.", examples=[20])
    results: list[DecisionMatch]


def _base_fields(row: DictRow) -> dict[str, Any]:
    return {
        "source": row["fonte_codigo"],
        "identifier": row["identificador_fonte"],
        "court": row["tribunal_sigla"],
        "case_number": row["processo"],
        "judging_body": row["orgao_julgador"],
        "reporting_judge": row["relator"],
        "decided_on": row["data_referencia"],
        "small_claims": row["turma_recursal"],
        "source_url": row["url_fonte"],
    }


@router.get("/decisions", summary="Search decisions by term")
def search_decisions(
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
    q: Annotated[
        str,
        Query(
            min_length=2,
            description=(
                'What to look for. `termo` matches every word, `"frase exata"` '
                "matches the sequence, `um OR outro` matches either, and `-termo` "
                "excludes. Accents are ignored."
            ),
            examples=["dano moral"],
        ),
    ],
    page: Annotated[int, Query(ge=1, description="Page number.")] = 1,
    page_size: Annotated[int, Query(ge=1, description="Results per page.")] = 20,
) -> SearchResults:
    """
    Search the ementa of every collected decision.

    Each result carries the passage that matched rather than the whole ementa,
    which runs to several thousand characters. Open a decision to read it whole.

    The total counts every match, not only this page, so a screen can say how
    many decisions exist before paging through them.
    """
    page_size = min(page_size, settings.search_max_page_size)
    parameters = {
        "term": q,
        "limit": page_size,
        "offset": (page - 1) * page_size,
    }

    with connection.cursor() as cursor:
        cursor.execute(COUNT_SQL, parameters)
        total = int((cursor.fetchone() or {"total": 0})["total"])

        rows: list[DictRow] = []
        if total:
            cursor.execute(PAGE_SQL, parameters)
            rows = cursor.fetchall()

    return SearchResults(
        total=total,
        page=page,
        page_size=page_size,
        results=[
            DecisionMatch(**_base_fields(row), snippet=row["snippet"]) for row in rows
        ],
    )


@router.get("/decisions/{source}/{identifier}", summary="Read one decision in full")
def read_decision(
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
    source: Annotated[str, Path(description="Collection code.")],
    identifier: Annotated[str, Path(description="Identifier within the collection.")],
    q: Annotated[
        str | None,
        Query(
            min_length=2,
            description="The search that led here, to highlight it in the ementa.",
        ),
    ] = None,
) -> Decision:
    """
    Read a single decision, ementa included.

    Pass the search term that led here and the ementa comes back with every hit
    wrapped in `<mark>`, so the reader lands on what they were looking for.
    """
    parameters = {"source": source, "identifier": identifier}

    with connection.cursor() as cursor:
        cursor.execute(DETAIL_SQL, parameters)
        row = cursor.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Decision not found.")

        summary = row["ementa"]
        if q:
            cursor.execute(HIGHLIGHT_SQL, {**parameters, "term": q})
            highlighted = cursor.fetchone()
            if highlighted:
                summary = highlighted["highlighted"]

    return Decision(
        **_base_fields(row),
        class_code=row["classe_cnj"],
        judged_on=row["data_julgamento"],
        published_on=row["data_publicacao"],
        summary=summary,
        outcome=row["decisao_texto"],
        full_text_available=row["possui_inteiro_teor"],
    )
