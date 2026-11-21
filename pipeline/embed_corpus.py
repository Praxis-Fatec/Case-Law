"""
Vectors for the collection's ementas, generated on the local GPU.

Every row records which model, which revision of it, and a digest of the exact
text embedded, which is also what makes the run resumable without a checkpoint
file. Why BGE-M3 and what the alternatives scored is in
documentation/architecture/search-models.md; how the run behaves is in
corpus-vectors.md.

    uv run --group embeddings python embed_corpus.py --create
    uv run --group embeddings python embed_corpus.py --embed
    uv run --group embeddings python embed_corpus.py --report
    uv run --group embeddings python embed_corpus.py --serving-model ./modelo
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import io
import os
import sys
import time
from pathlib import Path
from typing import Any, Iterator

import psycopg2

MODEL = "BAAI/bge-m3"
DIM = 1024
MAX_TOKENS = 1024

SCHEMA = "vetor"
TABLE = f"{SCHEMA}.decisao"

BATCH = 16
CHUNK = 2048

CREATE = f"""
CREATE SCHEMA IF NOT EXISTS {SCHEMA};

CREATE TABLE IF NOT EXISTS {TABLE} (
  fonte_codigo        TEXT         NOT NULL,
  identificador_fonte VARCHAR      NOT NULL,
  modelo              TEXT         NOT NULL,
  revisao             TEXT         NOT NULL,
  ementa_digest       BYTEA        NOT NULL,
  vetor               halfvec({DIM}) NOT NULL,
  gerado_em           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  PRIMARY KEY (fonte_codigo, identificador_fonte, modelo)
);

CREATE INDEX IF NOT EXISTS decisao_revisao_digest_idx
  ON {TABLE} (modelo, revisao, ementa_digest);
"""

PENDING = f"""
SELECT d.fonte_codigo, d.identificador_fonte, d.ementa
FROM core.decisao AS d
LEFT JOIN {TABLE} AS v
  ON  v.fonte_codigo        = d.fonte_codigo
  AND v.identificador_fonte = d.identificador_fonte
  AND v.modelo              = %(modelo)s
  AND v.revisao             = %(revisao)s
  AND v.ementa_digest       = SHA256(CONVERT_TO(d.ementa, 'UTF8'))
WHERE v.fonte_codigo IS NULL
  AND d.ementa IS NOT NULL
  AND BTRIM(d.ementa) <> ''
  AND (%(fonte)s = '' OR d.fonte_codigo = %(fonte)s)
ORDER BY d.fonte_codigo, d.identificador_fonte
"""

COUNT_PENDING = f"SELECT COUNT(*) FROM ({PENDING}) AS pendente"

REPORT = f"""
SELECT modelo, revisao, COUNT(*) AS vetores,
       MIN(gerado_em) AS primeiro, MAX(gerado_em) AS ultimo
FROM {TABLE}
GROUP BY modelo, revisao
ORDER BY ultimo DESC
"""


def digest(ementa: str) -> bytes:
    return hashlib.sha256(ementa.encode("utf-8")).digest()


def _connect(url: str) -> Any:
    conexao = psycopg2.connect(url)
    conexao.autocommit = True
    return conexao


def create(conexao: Any) -> None:
    with conexao.cursor() as cursor:
        cursor.execute(CREATE)


def revision(nome: str) -> str:
    """The model's commit on the Hub, which is what `version` has to mean."""
    from huggingface_hub import HfApi

    return HfApi().model_info(nome).sha


def pending(conexao: Any, modelo: str, revisao: str, fonte: str = "") -> int:
    with conexao.cursor() as cursor:
        cursor.execute(
            COUNT_PENDING,
            {"modelo": modelo, "revisao": revisao, "fonte": fonte},
        )
        return int(cursor.fetchone()[0])


def _lotes(linhas: Iterator[tuple], tamanho: int) -> Iterator[list[tuple]]:
    lote: list[tuple] = []
    for linha in linhas:
        lote.append(linha)
        if len(lote) == tamanho:
            yield lote
            lote = []
    if lote:
        yield lote


def _escrever(conexao: Any, modelo: str, revisao: str, prontas: list[tuple]) -> None:
    """CSV and not COPY's text format, where `\\x` is eaten as an escape."""
    buffer = io.StringIO()
    escritor = csv.writer(buffer)
    for fonte, identificador, ementa, vetor in prontas:
        escritor.writerow((
            fonte,
            identificador,
            modelo,
            revisao,
            "\\x" + digest(ementa).hex(),
            "[" + ",".join(f"{v:.6g}" for v in vetor) + "]",
        ))
    buffer.seek(0)
    with conexao.cursor() as cursor:
        cursor.copy_expert(
            f"COPY {TABLE} "
            "(fonte_codigo, identificador_fonte, modelo, revisao, "
            "ementa_digest, vetor) FROM STDIN WITH (FORMAT csv)",
            buffer,
        )


def embed(
    url: str,
    modelo: str,
    revisao: str,
    precisao: str = "float16",
    limite: int = 0,
    fonte: str = "",
) -> dict[str, Any]:
    """
    A chunk at a time, so `encode` can sort it by length before batching.

    The reader stays inside a transaction: a named cursor needs one, and its
    snapshot is what fixes the work list for the whole run.
    """
    import torch
    from sentence_transformers import SentenceTransformer

    dtype = getattr(torch, precisao)
    rede = SentenceTransformer(modelo, device="cuda", model_kwargs={"torch_dtype": dtype})
    rede.max_seq_length = MAX_TOKENS

    leitura = psycopg2.connect(url)
    escrita = _connect(url)
    gravadas = 0
    inicio = time.time()

    try:
        with leitura.cursor(name="pendente") as cursor:
            cursor.itersize = CHUNK
            cursor.execute(
                PENDING,
                {"modelo": modelo, "revisao": revisao, "fonte": fonte},
            )
            for bloco in _lotes(cursor, CHUNK):
                vetores = rede.encode(
                    [linha[2] for linha in bloco],
                    batch_size=BATCH,
                    show_progress_bar=False,
                    normalize_embeddings=True,
                )
                if vetores.shape[1] != DIM:
                    raise RuntimeError(
                        f"{modelo} produced {vetores.shape[1]} dimensions, "
                        f"and {TABLE} holds {DIM}"
                    )
                _escrever(
                    escrita, modelo, revisao,
                    [(f, i, e, v) for (f, i, e), v in zip(bloco, vetores)],
                )
                gravadas += len(bloco)
                decorrido = time.time() - inicio
                print(
                    f"{gravadas} em {decorrido / 60:.1f} min "
                    f"({gravadas / decorrido:.1f}/s)",
                    flush=True,
                )
                if limite and gravadas >= limite:
                    break
    finally:
        leitura.close()
        escrita.close()

    decorrido = time.time() - inicio
    return {
        "modelo": modelo,
        "revisao": revisao,
        "precisao": precisao,
        "fonte": fonte or "todas",
        "gravadas": gravadas,
        "minutos": round(decorrido / 60, 1),
        "por_segundo": round(gravadas / decorrido, 1) if decorrido else 0.0,
    }


def save_serving_model(nome: str, destino: str) -> dict[str, Any]:
    """
    A bfloat16 copy of the model, which is what the API loads.

    Asking for bfloat16 at load time does not give the memory back: the
    weights are read from the float32 safetensors and cast afterwards, and the
    mapped float32 pages stay resident. Only a copy stored as bfloat16 and
    loaded as itself does, and it is 582 MiB of the server's RAM.
    """
    import torch
    from sentence_transformers import SentenceTransformer

    rede = SentenceTransformer(
        nome, device="cpu", model_kwargs={"torch_dtype": torch.bfloat16}
    )
    rede.max_seq_length = MAX_TOKENS
    rede.save(destino)

    return {
        "modelo": nome,
        "revisao": revision(nome),
        "precisao": "bfloat16",
        "destino": destino,
    }


def report(conexao: Any) -> list[tuple]:
    with conexao.cursor() as cursor:
        cursor.execute(REPORT)
        return cursor.fetchall()


def main(argv: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--create", action="store_true")
    analisador.add_argument("--embed", action="store_true")
    analisador.add_argument("--report", action="store_true")
    analisador.add_argument("--pending", action="store_true")
    analisador.add_argument("--model", default=MODEL)
    analisador.add_argument("--revision", default="")
    analisador.add_argument("--precision", default="float16",
                            choices=("float16", "bfloat16", "float32"))
    analisador.add_argument("--limit", type=int, default=0)
    analisador.add_argument("--source", default="")
    analisador.add_argument("--serving-model", type=Path)
    argumentos = analisador.parse_args(argv)

    if argumentos.serving_model:
        for chave, valor in save_serving_model(
            argumentos.model, str(argumentos.serving_model)
        ).items():
            print(f"{chave}: {valor}")
        return 0

    url = os.getenv("DATABASE_URL", "")
    if not url:
        print("set DATABASE_URL", file=sys.stderr)
        return 2

    with contextlib.closing(_connect(url)) as conexao:
        if argumentos.create:
            create(conexao)
            print(f"ready: {TABLE}")

        revisao = argumentos.revision
        if (argumentos.embed or argumentos.pending) and not revisao:
            revisao = revision(argumentos.model)

        if argumentos.pending:
            print(
                f"pending: "
                f"{pending(conexao, argumentos.model, revisao, argumentos.source)}"
            )

        if argumentos.embed:
            medida = embed(
                url, argumentos.model, revisao, argumentos.precision,
                argumentos.limit, argumentos.source,
            )
            for chave, valor in medida.items():
                print(f"{chave}: {valor}")

        if argumentos.report:
            for linha in report(conexao):
                print(" | ".join(str(c) for c in linha))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
