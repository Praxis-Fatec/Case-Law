from collections.abc import Iterator
from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import ConnectionPool

from app.config import settings

pool: ConnectionPool[Connection[DictRow]] = ConnectionPool(
    conninfo=settings.database_url,
    min_size=1,
    max_size=settings.database_pool_size,
    kwargs={"row_factory": dict_row},
    open=False,
)


@contextmanager
def connection() -> Iterator[Connection[DictRow]]:
    with pool.connection() as conn:
        yield conn


def get_connection() -> Iterator[Connection[DictRow]]:
    with connection() as conn:
        yield conn


def get_own_connection() -> Iterator[Connection[DictRow]]:
    """
    A connection that nothing else in the same request has used.

    FastAPI resolves a dependency once per request, so every caller of
    `get_connection` shares one connection — the gate included, and the gate
    re-reads the account before any endpoint runs. Whoever asks for that
    shared connection therefore receives it already inside the gate's read
    committed transaction. Work that has to own its transaction asks for this
    one instead and holds a second connection for as long as the request
    lasts, which is why it is not the default.
    """
    with connection() as conn:
        yield conn
