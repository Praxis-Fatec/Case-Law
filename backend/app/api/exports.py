"""Download a complete PDF only after collection and rendering succeed."""

import hashlib
import json
import logging
import re
import unicodedata
from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from psycopg import Connection
from psycopg.rows import DictRow
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from app.api.decisions import DEFAULT_ORDER, SEARCH_RESPONSES, Order
from app.config import settings
from app.db import get_connection
from app.export import ExportRefused, collect_export
from app.export_document import render_export_pdf

router = APIRouter(prefix="/exports", tags=["search"])
logger = logging.getLogger(__name__)


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q: str = Field(min_length=2)
    tribunal: list[str] | None = None
    orgao_julgador: list[str] | None = None
    relator: list[str] | None = None
    classe_cnj: list[int] | None = None
    resultado: list[str] | None = None
    date_from: date | None = None
    date_to: date | None = None
    published_from: date | None = None
    published_to: date | None = None
    order: Order = DEFAULT_ORDER


class ExportOptions(BaseModel):
    max_decisions: int


@router.get("/options", summary="Current maximum number of decisions in a PDF export")
def export_options() -> ExportOptions:
    return ExportOptions(max_decisions=settings.export_max_decisions)


def export_filename(params: ExportRequest, generated_at: datetime) -> str:
    normalized = (
        unicodedata.normalize("NFKD", params.q).encode("ascii", "ignore").decode()
    )
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")[:50] or "pesquisa"
    identity = hashlib.sha256(
        json.dumps(params.model_dump(mode="json"), sort_keys=True).encode()
    ).hexdigest()[:8]
    return f"case-law-recorte-{slug}-{identity}-{generated_at:%Y-%m-%d-%H%M%S}.pdf"


@router.post(
    "/pdf",
    summary="Generate a PDF for the entire applied search",
    response_class=Response,
    responses={
        **SEARCH_RESPONSES,
        200: {
            "content": {
                "application/pdf": {"schema": {"type": "string", "format": "binary"}}
            }
        },
        409: {"description": "The cut has no decisions to export."},
        413: {
            "description": "The entire cut exceeds the configured export limit; no PDF is generated."
        },
    },
)
async def export_pdf(
    params: ExportRequest,
    request: Request,
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
) -> Response:
    try:
        data = await run_in_threadpool(
            collect_export, connection, **params.model_dump()
        )
    except ExportRefused as error:
        detail = (
            "Não há decisões neste recorte para exportar."
            if error.code == "empty"
            else f"O recorte tem {error.total} decisões e o limite é {error.limit}. "
            "Aplique mais filtros para reduzir o recorte."
        )
        return JSONResponse(
            status_code=409 if error.code == "empty" else 413,
            content={
                "detail": detail,
                "code": error.code,
                "total": error.total,
                "limit": error.limit,
            },
        )
    if await request.is_disconnected():
        return Response(status_code=499)
    generated_at = datetime.now(ZoneInfo("America/Sao_Paulo"))
    try:
        pdf = await run_in_threadpool(
            render_export_pdf, data, generated_at=generated_at
        )
    except Exception:
        logger.exception("PDF export rendering failed")
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Não foi possível gerar o PDF. Tente novamente.",
            },
        )
    if await request.is_disconnected():
        return Response(status_code=499)
    # No streaming: a failure never commits a PDF header or partial document.
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{export_filename(params, generated_at)}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
