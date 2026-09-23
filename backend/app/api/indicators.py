"""
What the collection is, rather than what is in it.

These answer questions a reader asks before trusting a search: how recent the
data is, and later how it is distributed. They read the load record the pipeline
writes, never the courts themselves.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from psycopg import Connection
from psycopg.rows import DictRow
from pydantic import BaseModel, Field

from app.db import get_connection

router = APIRouter(tags=["indicators"])

# A load that failed left nothing behind, so it cannot be what the data is from.
LAST_LOAD_SQL = """
SELECT concluida_em, registros_gravados
FROM core.carga
WHERE status = 'concluida'
ORDER BY concluida_em DESC
LIMIT 1
"""


class LastUpdate(BaseModel):
    updated_at: datetime | None = Field(
        description=(
            "When the most recent successful load finished, in UTC. `null` only "
            "when no load has ever succeeded here — read `state` rather than "
            "reading the absence."
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

    if row is None:
        return LastUpdate(updated_at=None, records=0)

    return LastUpdate(
        updated_at=row["concluida_em"],
        records=row["registros_gravados"],
    )
