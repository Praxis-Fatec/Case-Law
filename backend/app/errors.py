from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from psycopg import OperationalError
from psycopg.errors import UndefinedObject, UndefinedTable
from psycopg_pool import PoolTimeout

NOT_PUBLISHED = (
    "The decisions have not been published to this environment yet. "
    "Nothing is wrong with your request."
)

UNAVAILABLE = "The database is not answering right now. Try again in a moment."


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
