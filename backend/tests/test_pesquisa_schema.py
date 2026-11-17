"""Saved searches belong to an account and survive collection publication."""

from contextlib import nullcontext
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb

from app import owner
from tests.conftest import needs_database
from tests.test_contas import manager

pytestmark = needs_database

FILTERS = {
    "q": '"dano moral"',
    "tribunal": ["STJ", "TJDFT"],
    "orgao_julgador": ["CORTE ESPECIAL"],
    "relator": ["ANA CANTARINO"],
    "classe_cnj": [198, 213],
    "date_from": "2026-01-01",
    "date_to": "2026-12-31",
}


def save(db: psycopg.Connection[DictRow], usuario: UUID) -> DictRow:
    saved = db.execute(
        "INSERT INTO pesquisa.salva (usuario_id, nome, filtros) VALUES (%s, %s, %s) "
        "RETURNING id, usuario_id, nome, filtros, criado_em",
        (usuario, "Dano moral nos tribunais", Jsonb(FILTERS)),
    ).fetchone()
    assert saved is not None
    return saved


def test_saved_searches_live_outside_core(
    db_rolled_back: psycopg.Connection[DictRow],
) -> None:
    schemas = db_rolled_back.execute(
        "SELECT table_schema FROM information_schema.tables WHERE table_name = 'salva'"
    ).fetchall()
    assert {row["table_schema"] for row in schemas} == {"pesquisa"}


def test_migrar_creates_the_table_and_preserves_saved_rows_when_repeated(
    db_rolled_back: psycopg.Connection[DictRow], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Only the test database, inside the transaction the fixture rolls back.
    db_rolled_back.execute("DROP SCHEMA pesquisa CASCADE")
    monkeypatch.setattr(owner, "connection", lambda: nullcontext(db_rolled_back))
    owner.run("migrar", [])
    saved = save(db_rolled_back, manager(db_rolled_back)["id"])
    owner.run("migrar", [])
    assert (
        db_rolled_back.execute(
            "SELECT id, usuario_id, nome, filtros, criado_em FROM pesquisa.salva WHERE id = %s",
            (saved["id"],),
        ).fetchone()
        == saved
    )


def test_owner_name_filters_and_creation_time_are_kept(
    db_rolled_back: psycopg.Connection[DictRow],
) -> None:
    usuario = manager(db_rolled_back)["id"]
    saved = save(db_rolled_back, usuario)
    assert isinstance(saved["id"], UUID)
    assert saved["usuario_id"] == usuario
    assert saved["nome"] == "Dano moral nos tribunais"
    assert saved["filtros"] == FILTERS
    assert isinstance(saved["criado_em"], datetime)
    assert saved["criado_em"].tzinfo is not None


def test_publication_preserves_the_saved_search_and_its_owner(
    db_rolled_back: psycopg.Connection[DictRow],
) -> None:
    saved = save(db_rolled_back, manager(db_rolled_back)["id"])
    # Same drop-and-rename as pipeline/publish.py, without committing it: the
    # fixture rollback restores the published tables after the assertion.
    db_rolled_back.execute("CREATE SCHEMA core_publicacao")
    db_rolled_back.execute(
        "CREATE TABLE core_publicacao.publication_probe (id INTEGER)"
    )
    db_rolled_back.execute("INSERT INTO core_publicacao.publication_probe VALUES (1)")
    db_rolled_back.execute("DROP SCHEMA core CASCADE")
    db_rolled_back.execute("ALTER SCHEMA core_publicacao RENAME TO core")
    assert db_rolled_back.execute(
        "SELECT id FROM core.publication_probe"
    ).fetchone() == {"id": 1}
    assert (
        db_rolled_back.execute(
            "SELECT id, usuario_id, nome, filtros, criado_em FROM pesquisa.salva WHERE id = %s",
            (saved["id"],),
        ).fetchone()
        == saved
    )
    assert db_rolled_back.execute(
        "SELECT id FROM identidade.usuario WHERE id = %s", (saved["usuario_id"],)
    ).fetchone() == {"id": saved["usuario_id"]}


def test_an_owner_must_be_a_registered_account(
    db_rolled_back: psycopg.Connection[DictRow],
) -> None:
    with (
        pytest.raises(psycopg.errors.ForeignKeyViolation),
        db_rolled_back.transaction(),
    ):
        save(db_rolled_back, uuid4())


@pytest.mark.parametrize("nome", [None, "", "   "])
def test_a_saved_search_requires_a_nonblank_name(
    db_rolled_back: psycopg.Connection[DictRow], nome: str | None
) -> None:
    usuario = manager(db_rolled_back)["id"]
    with pytest.raises(psycopg.IntegrityError), db_rolled_back.transaction():
        db_rolled_back.execute(
            "INSERT INTO pesquisa.salva (usuario_id, nome, filtros) VALUES (%s, %s, %s)",
            (usuario, nome, Jsonb(FILTERS)),
        )


@pytest.mark.parametrize("filtros", [None, [], "dano moral", 1, True])
def test_filters_are_a_json_object_not_a_scalar_or_array(
    db_rolled_back: psycopg.Connection[DictRow], filtros: Any
) -> None:
    usuario = manager(db_rolled_back)["id"]
    with pytest.raises(psycopg.errors.CheckViolation), db_rolled_back.transaction():
        db_rolled_back.execute(
            "INSERT INTO pesquisa.salva (usuario_id, nome, filtros) VALUES (%s, 'Busca', %s)",
            (usuario, Jsonb(filtros)),
        )
