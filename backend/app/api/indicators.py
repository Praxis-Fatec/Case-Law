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
