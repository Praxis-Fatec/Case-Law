"""
The reader's query as a vector, when there is a model to make one.

An unset `EMBEDDING_MODEL_PATH` turns the search by subject off everywhere
rather than failing per request: without a model there is nothing to ask, and
the search answers by word alone, which is what it did before this existed.
The same is true when the model is set but cannot be loaded.

Which model, and why it is this one in bfloat16 on the CPU, is in
documentation/architecture/query-embedding.md.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from app.config import settings

DIM = 1024
MAX_TOKENS = 1024

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_model: Any | None = None
_loaded = False


def configured() -> bool:
    return bool(settings.embedding_model_path.strip())


def _load() -> Any | None:
    """Loaded once per process, and never retried after a failure."""
    global _model, _loaded

    with _lock:
        if _loaded:
            return _model
        _loaded = True

        caminho = Path(settings.embedding_model_path.strip())
        if not caminho.is_dir():
            logger.warning("embedding model not found at %s", caminho)
            return None

        try:
            import torch
            from sentence_transformers import SentenceTransformer

            torch.set_num_threads(settings.embedding_threads)
            rede = SentenceTransformer(str(caminho), device="cpu")
            rede.max_seq_length = MAX_TOKENS
        except Exception:
            logger.exception("the embedding model at %s did not load", caminho)
            return None

        _model = rede
        return _model


def warm() -> None:
    """Loads the model at startup, so no reader pays the first load."""
    if configured():
        _load()


def embed(consulta: str) -> str | None:
    """
    The query as a `halfvec` literal, or `None` when there is no model.

    A literal rather than a list because that is what the database takes, and
    building it here keeps the formatting in one place.
    """
    if not configured() or not consulta.strip():
        return None

    rede = _load()
    if rede is None:
        return None

    try:
        vetor = rede.encode([consulta], normalize_embeddings=True)[0]
    except Exception:
        logger.exception("the query could not be embedded")
        return None

    if len(vetor) != DIM:
        logger.error("the model produced %s dimensions, not %s", len(vetor), DIM)
        return None

    return "[" + ",".join(f"{valor:.6g}" for valor in vetor) + "]"
