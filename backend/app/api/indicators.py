"""
What the collection is, rather than what is in it.

These answer questions a reader asks before trusting a search: how recent the
data is, and later how it is distributed. They read the load record the pipeline
writes, never the courts themselves.
"""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from psycopg import Connection
from psycopg.rows import DictRow
from pydantic import BaseModel, Field

from app.db import get_connection

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


@router.get("/indicators/last-update", summary="When the data was last refreshed")
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
