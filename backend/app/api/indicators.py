"""
What the collection is, rather than what is in it.

These answer questions a reader asks before trusting a search: how recent the
data is, and later how it is distributed. They read the load record the pipeline
writes, never the courts themselves.
"""

from datetime import date, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from psycopg import Connection
from psycopg.rows import DictRow
from pydantic import BaseModel, Field

from app.api.decisions import MATCH, SEARCH_RESPONSES, _narrowing
from app.db import get_connection
from app.errors import NOT_PUBLISHED, UNAVAILABLE

router = APIRouter(tags=["indicators"])

# A load that failed left nothing behind, so it cannot be what the data is
# from. Ordering matters: without it PostgreSQL returns whichever row it reaches
# first, which is right on a small table and wrong on a real one.
LAST_LOAD_SQL = """
SELECT concluida_em, registros_gravados
FROM core.carga
WHERE status = 'concluida'
ORDER BY concluida_em DESC
LIMIT 1
"""

# Asked only when there is no successful load, to tell a collection that has
# never been loaded from one whose every load failed. The first is a new
# environment; the second is a broken pipeline, and they are not the same news.
ANY_LOAD_SQL = "SELECT COUNT(*) AS total FROM core.carga"

State = Literal["loaded", "all_loads_failed", "never_loaded"]

# One example per state. A single example would teach a reader that the other
# two do not exist, and they are exactly the cases worth handling.
ANSWERS: dict[str, dict[str, Any]] = {
    "loaded": {
        "summary": "The usual answer: a load finished here and left a date.",
        "value": {
            "state": "loaded",
            "updated_at": "2026-09-18T14:42:03Z",
            "records": 7,
        },
    },
    "all_loads_failed": {
        "summary": "The pipeline ran here and never finished.",
        "value": {"state": "all_loads_failed", "updated_at": None, "records": 0},
    },
    "never_loaded": {
        "summary": "Nothing has been collected here yet.",
        "value": {"state": "never_loaded", "updated_at": None, "records": 0},
    },
}

RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {"content": {"application/json": {"examples": ANSWERS}}},
    503: {
        "description": (
            "The load record has not been published to this environment yet, or "
            "the database is not answering. Neither means the request was wrong."
        ),
        "content": {
            "application/json": {
                "examples": {
                    "not published": {"value": {"detail": NOT_PUBLISHED}},
                    "database down": {"value": {"detail": UNAVAILABLE}},
                }
            }
        },
    },
}


class LastUpdate(BaseModel):
    state: State = Field(
        description=(
            "Which of three situations this is. `loaded` means `updated_at` "
            "holds a date. `all_loads_failed` means the pipeline ran here and "
            "never finished — the decisions on this server, if any, are from "
            "before that. `never_loaded` means nothing has been collected here "
            "at all. Read this rather than reading the absence of a date."
        ),
        examples=["loaded"],
    )
    updated_at: datetime | None = Field(
        description=(
            "When the most recent successful load finished, in UTC. `null` "
            "whenever `state` is not `loaded`."
        ),
        examples=["2026-09-18T14:42:03Z"],
    )
    records: int = Field(
        description="How many decisions that load wrote.",
        examples=[7],
    )


def _last_update(connection: Connection[DictRow]) -> LastUpdate:
    """
    Read the freshness once, so two answers cannot tell different stories.

    A failed load left nothing behind, so it cannot be what the data is from.
    Telling a collection never loaded from one whose every load failed costs a
    second question, and only when the first found nothing: one is a new
    environment, the other a broken pipeline.
    """
    with connection.cursor() as cursor:
        cursor.execute(LAST_LOAD_SQL)
        row = cursor.fetchone()

        if row is not None:
            return LastUpdate(
                state="loaded",
                updated_at=row["concluida_em"],
                records=row["registros_gravados"],
            )

        cursor.execute(ANY_LOAD_SQL)
        counted = cursor.fetchone()

    attempted = bool(counted and counted["total"])
    return LastUpdate(
        state="all_loads_failed" if attempted else "never_loaded",
        updated_at=None,
        records=0,
    )


@router.get(
    "/indicators/last-update",
    summary="When the data was last refreshed",
    responses=RESPONSES,
)
def read_last_update(
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
) -> LastUpdate:
    """
    When this environment's decisions were last refreshed.

    A reader has to know how old the data is before drawing a conclusion from
    it, so this is read straight from the load record that travelled with the
    data rather than from the machine that answers.
    """
    return _last_update(connection)


# LEFT JOIN, not JOIN: a court the seed never registered would otherwise drop
# out and the sums would stop adding up to the search's total, which is the one
# thing this endpoint promises.
VOLUME_SQL = f"""
SELECT
    d.tribunal_sigla                     AS sigla,
    COALESCE(t.nome, d.tribunal_sigla)   AS nome,
    COUNT(*)                             AS decisoes
FROM core.decisao AS d
LEFT JOIN core.tribunal AS t ON t.sigla = d.tribunal_sigla
WHERE {MATCH}{{filters}}
GROUP BY d.tribunal_sigla, t.nome
ORDER BY COUNT(*) DESC, d.tribunal_sigla
"""


class CourtVolume(BaseModel):
    abbreviation: str = Field(description="The court's abbreviation.", examples=["STJ"])
    name: str = Field(
        description="The court's full name.",
        examples=["Superior Tribunal de Justiça"],
    )
    decisions: int = Field(
        description="How many of the search's decisions came from this court.",
        examples=[876996],
    )


class VolumeByCourt(BaseModel):
    total: int = Field(
        description=(
            "Every decision the same search matches. The courts' counts add up "
            "to it, so a chart drawn from this cannot disagree with the number "
            "beside the results."
        ),
        examples=[984824],
    )
    courts: list[CourtVolume] = Field(
        description="Busiest court first. Empty when the search matches nothing."
    )


@router.get(
    "/indicators/volume-by-court",
    summary="How the search's decisions divide between the courts",
    responses=SEARCH_RESPONSES,
)
def read_volume_by_court(
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
    q: Annotated[
        str,
        Query(
            min_length=2,
            description="The same expression the search takes.",
            examples=["dano moral"],
        ),
    ],
    tribunal: Annotated[
        list[str] | None,
        Query(description="The same court filter the search takes."),
    ] = None,
    date_from: Annotated[date | None, Query(description="Judged on or after.")] = None,
    date_to: Annotated[date | None, Query(description="Judged on or before.")] = None,
    published_from: Annotated[
        date | None, Query(description="Published on or after.")
    ] = None,
    published_to: Annotated[
        date | None, Query(description="Published on or before.")
    ] = None,
) -> VolumeByCourt:
    """
    The same decisions the search would return, counted by court.

    It takes the search's parameters and narrows the same way, from the same
    builder, so the chart and the results can never describe different sets. A
    search that matches nothing answers an empty list and a total of zero, not
    an error: no court is the honest answer to a question with no decisions.
    """
    filters, parameters = _narrowing(
        q, tribunal, date_from, date_to, published_from, published_to
    )

    with connection.cursor() as cursor:
        cursor.execute(VOLUME_SQL.format(filters=filters), parameters)
        rows = cursor.fetchall()

    courts = [
        CourtVolume(
            abbreviation=row["sigla"], name=row["nome"], decisions=row["decisoes"]
        )
        for row in rows
    ]
    return VolumeByCourt(total=sum(c.decisions for c in courts), courts=courts)


OUTCOME_SQL = f"""
SELECT
    d.resultado  AS resultado,
    COUNT(*)     AS decisoes
FROM core.decisao AS d
WHERE {MATCH}{{filters}}
GROUP BY d.resultado
"""

# Zeroed rather than dropped: a category missing from the cut would take its
# slice off the chart, and a reader cannot tell an absent slice from one nobody
# drew.
OUTCOMES = ("negado", "provido", "parcialmente_provido")


class OutcomeCount(BaseModel):
    outcome: str = Field(
        description="The reading, as the model records it.",
        examples=["negado"],
    )
    decisions: int = Field(
        description="How many of the search's decisions were read this way.",
        examples=[752293],
    )
    share: float = Field(
        description=(
            "Percentage over `classified`, not over `total`. Rounded to one "
            "decimal, so the counts are what add up, not these."
        ),
        examples=[75.9],
    )


class OutcomeShare(BaseModel):
    total: int = Field(
        description=(
            "Every decision the same search matches, read or not. The counts "
            "below never add up to it on their own."
        ),
        examples=[1788],
    )
    classified: int = Field(
        description=(
            "How many of them the dispositive stated an outcome for. This is "
            "the denominator of every `share`, and the reason it travels: "
            "a percentage of a part of the cut reads as a percentage of the "
            "cut unless the reader is told otherwise."
        ),
        examples=[1715],
    )
    unclassified: int = Field(
        description=(
            "The rest, which the court decided but not as an appeal on its "
            "merits — a conflict of competence, a prejudiced appeal, an "
            "extinction. `classified` and this add up to `total`."
        ),
        examples=[73],
    )
    outcomes: list[OutcomeCount] = Field(
        description=(
            "Commonest first, and always the three the model can record, zero "
            "included. Empty only when the search matches nothing."
        )
    )


@router.get(
    "/indicators/outcome-share",
    summary="How the search's decisions divide between the appeal outcomes",
    responses=SEARCH_RESPONSES,
)
def read_outcome_share(
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
    q: Annotated[
        str,
        Query(
            min_length=2,
            description="The same expression the search takes.",
            examples=["prescrição intercorrente"],
        ),
    ],
    tribunal: Annotated[
        list[str] | None,
        Query(description="The same court filter the search takes."),
    ] = None,
    date_from: Annotated[date | None, Query(description="Judged on or after.")] = None,
    date_to: Annotated[date | None, Query(description="Judged on or before.")] = None,
    published_from: Annotated[
        date | None, Query(description="Published on or after.")
    ] = None,
    published_to: Annotated[
        date | None, Query(description="Published on or before.")
    ] = None,
) -> OutcomeShare:
    """
    The same decisions the search would return, counted by what the court
    decided.

    It narrows from the builder the search itself uses, so the two can never
    describe different sets. A search that matches nothing answers an empty
    list and a total of zero, not an error.
    """
    filters, parameters = _narrowing(
        q, tribunal, date_from, date_to, published_from, published_to
    )

    with connection.cursor() as cursor:
        cursor.execute(OUTCOME_SQL.format(filters=filters), parameters)
        rows = cursor.fetchall()

    counted = {row["resultado"]: row["decisoes"] for row in rows}
    total = sum(counted.values())

    if total == 0:
        return OutcomeShare(total=0, classified=0, unclassified=0, outcomes=[])

    unclassified = counted.get(None, 0)
    classified = total - unclassified

    outcomes = [
        OutcomeCount(
            outcome=name,
            decisions=counted.get(name, 0),
            share=round(counted.get(name, 0) / classified * 100, 1)
            if classified
            else 0.0,
        )
        for name in OUTCOMES
    ]
    outcomes.sort(key=lambda item: (-item.decisions, item.outcome))
    return OutcomeShare(
        total=total,
        classified=classified,
        unclassified=unclassified,
        outcomes=outcomes,
    )


# One pass, grouped, so the courts and the base cannot disagree about a period
# the reader is deciding from. NULL dates sort out of MIN and MAX on their own.
COVERAGE_SQL = """
SELECT
    d.tribunal_sigla                     AS sigla,
    COALESCE(t.nome, d.tribunal_sigla)   AS nome,
    COUNT(*)                             AS documentos,
    MIN(d.data_referencia)               AS primeira,
    MAX(d.data_referencia)               AS ultima
FROM core.decisao AS d
LEFT JOIN core.tribunal AS t ON t.sigla = d.tribunal_sigla
GROUP BY d.tribunal_sigla, t.nome
ORDER BY COUNT(*) DESC, d.tribunal_sigla
"""


class CourtCoverage(BaseModel):
    abbreviation: str = Field(description="The court's abbreviation.", examples=["STJ"])
    name: str = Field(
        description="The court's full name.",
        examples=["Superior Tribunal de Justiça"],
    )
    documents: int = Field(
        description="How many decisions the base holds from this court.",
        examples=[876996],
    )
    first: date | None = Field(
        description="The oldest decision from this court. `null` if none is dated.",
        examples=["1989-02-19"],
    )
    last: date | None = Field(
        description="The most recent decision from this court.",
        examples=["2026-08-26"],
    )


class Coverage(BaseModel):
    documents: int = Field(
        description="Every decision the base holds. Zero before the first load.",
        examples=[984824],
    )
    first: date | None = Field(
        description=(
            "The oldest decision in the base. `null` when it holds none. Read it "
            "beside each court's own period: one court reaching back decades "
            "does not mean the base covers those decades for the others."
        ),
        examples=["1989-02-19"],
    )
    last: date | None = Field(
        description="The most recent decision in the base.",
        examples=["2026-09-17"],
    )
    courts: list[CourtCoverage] = Field(
        description="Every court present, largest first, each with its own period."
    )
    state: State = Field(
        description="Whether a load ever finished here. See `/indicators/last-update`.",
        examples=["loaded"],
    )
    updated_at: datetime | None = Field(
        description=(
            "When the data was last refreshed, so the scope above can be read "
            "with its age. `null` when no load ever finished."
        ),
        examples=["2026-09-25T17:12:44Z"],
    )


@router.get(
    "/indicators/coverage",
    summary="What the base covers as a whole",
    responses=RESPONSES,
)
def read_coverage(
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
) -> Coverage:
    """
    How far the base reaches, so a reader knows the scope before trusting it.

    This answers for the collection, not for a search: the volume endpoint
    answers for the set a query matched. An empty base answers zero documents
    and no courts, which is an answer rather than an error — a new environment
    is not a broken one.

    The freshness comes along because scope without age is half an answer, and
    it is read by the same function `/indicators/last-update` uses, so the two
    cannot disagree.
    """
    with connection.cursor() as cursor:
        cursor.execute(COVERAGE_SQL)
        rows = cursor.fetchall()

    courts = [
        CourtCoverage(
            abbreviation=row["sigla"],
            name=row["nome"],
            documents=row["documentos"],
            first=row["primeira"],
            last=row["ultima"],
        )
        for row in rows
    ]
    starts = [c.first for c in courts if c.first is not None]
    ends = [c.last for c in courts if c.last is not None]

    fresh = _last_update(connection)

    return Coverage(
        documents=sum(c.documents for c in courts),
        first=min(starts, default=None),
        last=max(ends, default=None),
        courts=courts,
        state=fresh.state,
        updated_at=fresh.updated_at,
    )


# `indeterminado` is not here: it travels as its own field, the way
# `unclassified` does above, so no share is ever computed over a guess.
DECIDED = ("seguiu", "afastou", "distinguiu", "mencionou")
UNDETERMINED = "indeterminado"

CUT_SIZE_SQL = f"""
SELECT COUNT(*) AS decisoes
FROM core.decisao AS d
WHERE {MATCH}{{filters}}
"""

# GROUPING SETS so one scan answers both levels: the per-category counts and,
# in the row where GROUPING is 1, how many distinct decisions cite anything.
# Summing the per-category decision counts would double a decision that cites
# two precedents it used differently.
ADHERENCE_SQL = f"""
WITH recorte AS (
    SELECT d.fonte_codigo, d.identificador_fonte
    FROM core.decisao AS d
    WHERE {MATCH}{{filters}}
),
ligada AS (
    SELECT dp.aderencia, dp.fonte_codigo, dp.identificador_fonte
    FROM recorte AS r
    JOIN core.decisao_precedente AS dp
        ON dp.fonte_codigo = r.fonte_codigo
       AND dp.identificador_fonte = r.identificador_fonte
)
SELECT
    GROUPING(aderencia) AS geral,
    aderencia           AS aderencia,
    COUNT(*)            AS ligacoes,
    COUNT(DISTINCT (fonte_codigo, identificador_fonte)) AS decisoes
FROM ligada
GROUP BY GROUPING SETS ((aderencia), ())
"""

MOST_CITED_SQL = f"""
WITH recorte AS (
    SELECT d.fonte_codigo, d.identificador_fonte
    FROM core.decisao AS d
    WHERE {MATCH}{{filters}}
)
SELECT
    dp.corte     AS corte,
    dp.tipo      AS tipo,
    dp.numero    AS numero,
    p.enunciado  AS enunciado,
    COUNT(*)     AS citacoes,
    COUNT(DISTINCT (dp.fonte_codigo, dp.identificador_fonte)) AS decisoes
FROM recorte AS r
JOIN core.decisao_precedente AS dp
    ON dp.fonte_codigo = r.fonte_codigo
   AND dp.identificador_fonte = r.identificador_fonte
LEFT JOIN core.precedente AS p
    ON p.corte = dp.corte AND p.tipo = dp.tipo AND p.numero = dp.numero
-- A citation that never said which court settled it identifies no precedent,
-- so it cannot be ranked under one: counting a bare "Tema 793" among the
-- STJ's would inflate that row with citations of the STF's.
WHERE dp.corte_declarada
GROUP BY dp.corte, dp.tipo, dp.numero, p.enunciado
ORDER BY COUNT(*) DESC, dp.corte, dp.tipo, dp.numero
LIMIT %(limit)s
"""


class AdherenceCount(BaseModel):
    adherence: str = Field(
        description=(
            "`seguiu`, `afastou`, `distinguiu` or `mencionou`. The fifth the "
            "model records, `indeterminado`, travels as `undetermined` below."
        ),
        examples=["seguiu"],
    )
    links: int = Field(
        description="Citations in this state across the cut.", examples=[1204]
    )
    decisions: int = Field(
        description=(
            "Distinct decisions carrying at least one. These never add up to "
            "`citing`: a decision that followed one precedent and set another "
            "aside counts in both rows, which is why the sum is not offered."
        ),
        examples=[1102],
    )
    share: float = Field(
        description="Percentage of `determined`, to one decimal.", examples=[70.2]
    )


class AdherenceShare(BaseModel):
    decisions: int = Field(
        description=(
            "Every decision the same search matches. The first of three "
            "denominators, and the one a percentage is most often mistaken "
            "for."
        ),
        examples=[1788],
    )
    citing: int = Field(
        description=(
            "How many of them cite at least one precedent. The second "
            "denominator: most of the collection cites none, so a share of the "
            "citing decisions says nothing about the rest."
        ),
        examples=[497],
    )
    links: int = Field(
        description=(
            "Citations in the cut, counting a decision once per precedent it "
            "cites. `determined` plus `undetermined` equals this."
        ),
        examples=[1715],
    )
    determined: int = Field(
        description=(
            "Citations the wording settled. The third denominator, and the one "
            "every `share` is over."
        ),
        examples=[1301],
    )
    undetermined: int = Field(
        description=(
            "Citations whose wording decided nothing. Reported rather than "
            "hidden: a reader who cannot see this cannot tell a strong finding "
            "from a thin one."
        ),
        examples=[414],
    )
    adherences: list[AdherenceCount] = Field(
        description=(
            "Commonest first, and always the four the model can decide, zero "
            "included. Empty only when the cut carries no citation at all."
        )
    )


class MostCited(BaseModel):
    court: str = Field(description="`STJ` or `STF`.", examples=["STJ"])
    kind: str = Field(description="`sumula` or `tema`.", examples=["sumula"])
    number: int = Field(description="The precedent's number.", examples=[7])
    text: str | None = Field(
        default=None,
        description="What it settled, or `null` when the catalogue lacks it.",
        examples=[
            "A pretensão de simples reexame de prova não enseja recurso especial."
        ],
    )
    citations: int = Field(
        description="How many times the cut cites it.", examples=[612]
    )
    decisions: int = Field(
        description="Distinct decisions doing the citing.", examples=[598]
    )


@router.get(
    "/indicators/adherence",
    summary="How the search's decisions used the precedents they cite",
    responses=SEARCH_RESPONSES,
)
def read_adherence(
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
    q: Annotated[
        str,
        Query(
            min_length=2,
            description="The same expression the search takes.",
            examples=["prescrição intercorrente"],
        ),
    ],
    tribunal: Annotated[
        list[str] | None,
        Query(description="The same court filter the search takes."),
    ] = None,
    date_from: Annotated[date | None, Query(description="Judged on or after.")] = None,
    date_to: Annotated[date | None, Query(description="Judged on or before.")] = None,
    published_from: Annotated[
        date | None, Query(description="Published on or after.")
    ] = None,
    published_to: Annotated[
        date | None, Query(description="Published on or before.")
    ] = None,
) -> AdherenceShare:
    """
    Whether the courts followed the precedents they cited, over the cut.

    Three denominators travel, because confusing them produces a false
    percentage: every decision the search matches, the ones citing a precedent
    at all, and the citations whose wording settled the question. "70%
    followed" is only ever true of the third.
    """
    filters, parameters = _narrowing(
        q, tribunal, date_from, date_to, published_from, published_to
    )

    with connection.cursor() as cursor:
        cursor.execute(CUT_SIZE_SQL.format(filters=filters), parameters)
        size = cursor.fetchone()
        decisions = size["decisoes"] if size else 0

        cursor.execute(ADHERENCE_SQL.format(filters=filters), parameters)
        rows = cursor.fetchall()

    overall = next((row for row in rows if row["geral"] == 1), None)
    counted = {row["aderencia"]: row for row in rows if row["geral"] == 0}

    links = overall["ligacoes"] if overall else 0
    citing = overall["decisoes"] if overall else 0
    undetermined = counted[UNDETERMINED]["ligacoes"] if UNDETERMINED in counted else 0
    determined = links - undetermined

    adherences = [
        AdherenceCount(
            adherence=name,
            links=counted[name]["ligacoes"] if name in counted else 0,
            decisions=counted[name]["decisoes"] if name in counted else 0,
            share=round(counted[name]["ligacoes"] / determined * 100, 1)
            if determined and name in counted
            else 0.0,
        )
        for name in DECIDED
    ]
    adherences.sort(key=lambda item: (-item.links, item.adherence))

    return AdherenceShare(
        decisions=decisions,
        citing=citing,
        links=links,
        determined=determined,
        undetermined=undetermined,
        adherences=adherences if links else [],
    )


@router.get(
    "/indicators/most-cited-precedents",
    summary="Which precedents the search's decisions cite most",
    responses=SEARCH_RESPONSES,
)
def read_most_cited(
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
    q: Annotated[
        str,
        Query(
            min_length=2,
            description="The same expression the search takes.",
            examples=["prescrição intercorrente"],
        ),
    ],
    tribunal: Annotated[
        list[str] | None,
        Query(description="The same court filter the search takes."),
    ] = None,
    date_from: Annotated[date | None, Query(description="Judged on or after.")] = None,
    date_to: Annotated[date | None, Query(description="Judged on or before.")] = None,
    published_from: Annotated[
        date | None, Query(description="Published on or after.")
    ] = None,
    published_to: Annotated[
        date | None, Query(description="Published on or before.")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=50, description="How many to return.")] = 10,
) -> list[MostCited]:
    """
    The precedents the cut leans on, commonest first.

    A precedent the catalogue has no entry for still ranks, with `text` null:
    how often a court invokes something is worth knowing even when the wording
    of it is not on hand.
    """
    filters, parameters = _narrowing(
        q, tribunal, date_from, date_to, published_from, published_to
    )

    with connection.cursor() as cursor:
        cursor.execute(
            MOST_CITED_SQL.format(filters=filters), {**parameters, "limit": limit}
        )
        rows = cursor.fetchall()

    return [
        MostCited(
            court=row["corte"],
            kind=row["tipo"],
            number=row["numero"],
            text=row["enunciado"],
            citations=row["citacoes"],
            decisions=row["decisoes"],
        )
        for row in rows
    ]
