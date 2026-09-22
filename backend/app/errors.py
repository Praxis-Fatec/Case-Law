from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from psycopg import DataError, OperationalError
from psycopg.errors import UndefinedObject, UndefinedTable
from psycopg_pool import PoolTimeout

NOT_PUBLISHED = (
    "The decisions have not been published to this environment yet. "
    "Nothing is wrong with your request."
)

UNAVAILABLE = "The database is not answering right now. Try again in a moment."

MALFORMED = (
    "Part of the request is not text the database can read. Check for stray "
    "control characters, such as %00, in the query or the identifier."
)


def _unavailable(detail: str) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": detail})


def register(app: FastAPI) -> None:
    @app.exception_handler(UndefinedTable)
    @app.exception_handler(UndefinedObject)
    async def _missing_dataset(_: Request, __: Exception) -> JSONResponse:
        return _unavailable(NOT_PUBLISHED)

    @app.exception_handler(OperationalError)
    @app.exception_handler(PoolTimeout)
    async def _database_down(_: Request, __: Exception) -> JSONResponse:
        return _unavailable(UNAVAILABLE)

    # A caller controls every parameter, so a value PostgreSQL refuses to read
    # is a bad request, not a broken server. Registered centrally because the
    # next endpoint would otherwise have to remember this on its own.
    @app.exception_handler(DataError)
    async def _malformed_input(_: Request, __: Exception) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": MALFORMED})
