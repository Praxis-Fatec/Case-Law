"""Named searches are private to the account that saved them."""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Response
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from app import sessions
from app.db import get_connection
from app.errors import DATABASE_RESPONSES, ErrorResponse

router = APIRouter(tags=["saved searches"])

NOT_FOUND = "Pesquisa salva não encontrada."
FIELDS = "id, nome, filtros, criado_em"

INSERT_SQL = f"""
INSERT INTO pesquisa.salva (usuario_id, nome, filtros)
VALUES (%(person)s, %(name)s, %(filters)s)
RETURNING {FIELDS}
"""

LIST_SQL = f"""
SELECT {FIELDS} FROM pesquisa.salva
WHERE usuario_id = %(person)s
ORDER BY criado_em DESC, id DESC
"""

# Ownership belongs in both statements, not in a check made before them.
# In particular, DELETE never has a moment between checking and deleting in
# which another account's search could be affected. Managers have no bypass.
READ_SQL = f"""
SELECT {FIELDS} FROM pesquisa.salva
WHERE id = %(identifier)s AND usuario_id = %(person)s
"""

DELETE_SQL = """
DELETE FROM pesquisa.salva
WHERE id = %(identifier)s AND usuario_id = %(person)s
RETURNING id
"""

RESPONSES: dict[int | str, dict[str, Any]] = {
    **DATABASE_RESPONSES,
    401: {
        "model": ErrorResponse,
        "description": "Sign in with an active account before saving or reading searches.",
        "content": {
            "application/json": {"example": {"detail": sessions.NOT_SIGNED_IN}}
        },
    },
}
NOT_FOUND_RESPONSE: dict[int | str, dict[str, Any]] = {
    404: {
        "model": ErrorResponse,
        "description": "No search with this identifier belongs to the signed-in account. Other people's searches answer identically to missing ones.",
        "content": {"application/json": {"example": {"detail": NOT_FOUND}}},
    },
}


class NewSearch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120, examples=["Dano moral no STJ"])
    filters: dict[str, JsonValue] = Field(
        description=(
            "The applied expression in `q` (at least two nonblank characters) "
            "and its filters. Arrays, dates and additional JSON fields are "
            "kept as supplied. Saving does not execute the search or freeze "
            "its documents."
        ),
        examples=[
            {"q": '"dano moral"', "tribunal": ["STJ"], "date_from": "2026-01-01"}
        ],
    )

    @field_validator("name")
    @classmethod
    def has_content(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Informe um nome para a pesquisa.")
        if "\x00" in stripped:
            raise ValueError("O nome contém um caractere inválido.")
        return stripped

    @field_validator("filters")
    @classmethod
    def has_expression(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        expression = value.get("q")
        if not isinstance(expression, str) or len(expression.strip()) < 2:
            raise ValueError(
                "Informe a expressão da pesquisa em q, com pelo menos dois caracteres."
            )
        if "\x00" in expression:
            raise ValueError("A expressão contém um caractere inválido.")
        return value


class SavedSearch(BaseModel):
    id: str = Field(description="Identifier of the saved search.")
    name: str
    filters: dict[str, JsonValue]
    created_at: datetime = Field(
        description="When this search was saved, with time zone."
    )


class SavedSearches(BaseModel):
    searches: list[SavedSearch] = Field(
        description="Only this account's searches, newest first. Empty when none were saved."
    )


def _saved(row: DictRow) -> SavedSearch:
    return SavedSearch(
        id=str(row["id"]),
        name=row["nome"],
        filters=row["filtros"],
        created_at=row["criado_em"],
    )


@router.post(
    "/searches",
    status_code=201,
    summary="Save a named search for this account",
    responses=RESPONSES,
)
def save_search(
    new: NewSearch,
    person: Annotated[dict[str, Any], Depends(sessions.signed_in)],
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
) -> SavedSearch:
    """Keep the expression and filters, owned by the authenticated account.

    The owner and creation date are never taken from the request. A search is
    stored in `pesquisa`, so publishing a new collection leaves it intact.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            INSERT_SQL,
            {"person": person["id"], "name": new.name, "filters": Jsonb(new.filters)},
        )
        row = cursor.fetchone()
    assert row is not None
    return _saved(row)


@router.get(
    "/searches", summary="List this account's saved searches", responses=RESPONSES
)
def list_searches(
    person: Annotated[dict[str, Any], Depends(sessions.signed_in)],
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
) -> SavedSearches:
    with connection.cursor() as cursor:
        cursor.execute(LIST_SQL, {"person": person["id"]})
        rows = cursor.fetchall()
    return SavedSearches(searches=[_saved(row) for row in rows])


@router.get(
    "/searches/{identifier}",
    summary="Read one of this account's saved searches",
    responses={**RESPONSES, **NOT_FOUND_RESPONSE},
)
def read_search(
    identifier: Annotated[UUID, Path(description="Identifier of the saved search.")],
    person: Annotated[dict[str, Any], Depends(sessions.signed_in)],
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
) -> SavedSearch:
    with connection.cursor() as cursor:
        cursor.execute(READ_SQL, {"identifier": identifier, "person": person["id"]})
        row = cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return _saved(row)


@router.delete(
    "/searches/{identifier}",
    status_code=204,
    response_class=Response,
    summary="Delete one of this account's saved searches",
    responses={**RESPONSES, **NOT_FOUND_RESPONSE},
)
def delete_search(
    identifier: Annotated[UUID, Path(description="Identifier of the saved search.")],
    person: Annotated[dict[str, Any], Depends(sessions.signed_in)],
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
) -> Response:
    with connection.cursor() as cursor:
        cursor.execute(DELETE_SQL, {"identifier": identifier, "person": person["id"]})
        deleted = cursor.fetchone()
    if deleted is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return Response(status_code=204)
