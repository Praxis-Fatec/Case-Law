"""Private bookmarks use source keys and survive collection publications."""

from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response
from psycopg import Connection
from psycopg.rows import DictRow
from pydantic import BaseModel, ConfigDict, Field

from app import sessions
from app.db import get_connection
from app.errors import DATABASE_RESPONSES

router = APIRouter(tags=["saved decisions"])
Person = Annotated[dict[str, Any], Depends(sessions.signed_in)]
Database = Annotated[Connection[DictRow], Depends(get_connection)]
NOT_FOUND = "Decisão salva não encontrada."


class NewBookmark(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str = Field(min_length=1, max_length=200, pattern=r"^[^\x00]+$")
    identifier: str = Field(min_length=1, max_length=1000, pattern=r"^[^\x00]+$")


class SavedDecision(BaseModel):
    source: str
    identifier: str
    court: str
    case_number: str | None
    summary: str
    decided_on: date | None
    created_at: datetime
    available: bool


class SavedDecisions(BaseModel):
    decisions: list[SavedDecision]


FIELDS = """
s.fonte_codigo AS source, s.identificador_fonte AS identifier,
s.tribunal AS court, s.processo AS case_number, s.resumo AS summary,
s.data_decisao AS decided_on, s.criado_em AS created_at
"""


@router.get("/saved-decisions", responses=DATABASE_RESPONSES)
def list_decisions(person: Person, connection: Database) -> SavedDecisions:
    rows = connection.execute(
        f"""SELECT {FIELDS}, d.fonte_codigo IS NOT NULL AS available
        FROM pesquisa.decisao_salva s
        LEFT JOIN core.decisao d ON d.fonte_codigo = s.fonte_codigo
          AND d.identificador_fonte = s.identificador_fonte
        WHERE s.usuario_id = %(person)s
        ORDER BY s.criado_em DESC, s.fonte_codigo, s.identificador_fonte""",
        {"person": person["id"]},
    ).fetchall()
    return SavedDecisions(decisions=[SavedDecision(**row) for row in rows])


@router.post("/saved-decisions", status_code=201, responses=DATABASE_RESPONSES)
def save_decision(
    new: NewBookmark, person: Person, connection: Database
) -> SavedDecision:
    row = connection.execute(
        f"""INSERT INTO pesquisa.decisao_salva AS s
        (usuario_id, fonte_codigo, identificador_fonte, tribunal, processo, resumo, data_decisao)
        SELECT %(person)s, fonte_codigo, identificador_fonte, tribunal_sigla,
          processo, LEFT(COALESCE(ementa, ''), 400), data_referencia
        FROM core.decisao
        WHERE fonte_codigo = %(source)s AND identificador_fonte = %(identifier)s
        ON CONFLICT (usuario_id, fonte_codigo, identificador_fonte)
          DO UPDATE SET fonte_codigo = EXCLUDED.fonte_codigo
        RETURNING {FIELDS}, TRUE AS available""",
        {"person": person["id"], **new.model_dump()},
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Esta decisão não está mais disponível no acervo.")
    return SavedDecision(**row)


@router.delete(
    "/saved-decisions/{source}/{identifier}",
    status_code=204,
    response_class=Response,
    responses=DATABASE_RESPONSES,
)
def delete_decision(
    source: str, identifier: str, person: Person, connection: Database
) -> Response:
    row = connection.execute(
        """DELETE FROM pesquisa.decisao_salva
        WHERE usuario_id = %(person)s AND fonte_codigo = %(source)s
          AND identificador_fonte = %(identifier)s RETURNING fonte_codigo""",
        {"person": person["id"], "source": source, "identifier": identifier},
    ).fetchone()
    if row is None:
        raise HTTPException(404, NOT_FOUND)
    return Response(status_code=204)
