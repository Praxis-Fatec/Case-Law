"""
How long each transformation model takes to build, measured one by one.

`sqlmesh plan` reports that it ran; it does not report what each model cost.
Without that number there is no way to say which model is worth converting to
incremental, nor to show afterwards that the conversion paid off.

Each model is built into a scratch schema from the same data the real run
reads, timed, counted and dropped. Index creation is timed apart from the
build, because on `core.decisao` the GIN index is a large share of the cost and
an incremental run pays it differently.

    uv run python medir_transformacao.py
    uv run python medir_transformacao.py --modelos core.decisao core.doutrina_termo
    uv run python medir_transformacao.py --janela 7 --saida medicao.json
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from sqlmesh.core.context import Context

SCRATCH = "medicao"
PROJECT = Path(__file__).resolve().parent / "transformations"


@dataclass
class Medida:
    modelo: str
    kind: str
    cron: str
    construcao_s: float
    indices_s: float
    linhas: int

    @property
    def total_s(self) -> float:
        return self.construcao_s + self.indices_s


def _ordem(context: Context, escolhidos: list[str] | None) -> list[str]:
    """Model names in dependency order, seeds left out: they are loaded, not built."""
    ordenados = [
        name
        for name in context.dag.sorted
        if name in context.models and context.models[name].kind.name != "SEED"
    ]
    if not escolhidos:
        return ordenados
    querido = {context.models[n].name: n for n in ordenados}
    faltando = [n for n in escolhidos if n not in querido]
    if faltando:
        raise SystemExit(f"modelo desconhecido: {', '.join(faltando)}")
    return [querido[n] for n in escolhidos]


def _janela(engine, dias: int | None) -> tuple[date, date] | None:
    """
    The last `dias` days the collection actually has, not the last `dias` days.

    Courts publish months behind, so a window ending today is usually empty and
    an empty window measures nothing. Ending it at the most recent decision
    gives the week a real ingestion would process.
    """
    if dias is None:
        return None
    fim = engine.fetchone("SELECT MAX(data_referencia) FROM core.decisao")[0]
    if fim is None:
        raise SystemExit("core.decisao está vazia: não há janela para medir")
    return fim - timedelta(days=dias - 1), fim


def _inicio_do_modelo(modelo) -> date:  # noqa: ANN001
    inicio = modelo.start
    if isinstance(inicio, date):
        return inicio
    return date.fromisoformat(str(inicio)[:10])


def _alvo(nome: str) -> str:
    return f'"{SCRATCH}"."{nome.replace(".", "__")}"'


def _posteriores(context: Context, chave: str, alvo: str) -> list[str]:
    modelo = context.models[chave]
    rendidos = modelo.render_post_statements(dialect="postgres")
    partes = '"."'.join(modelo.name.split("."))
    qualificado = f'"{context.default_catalog}"."{partes}"'
    comandos = []
    for statement in rendidos:
        sql = statement.sql(dialect="postgres")
        if not sql.lstrip().upper().startswith("CREATE"):
            continue
        comandos.append(sql.replace(qualificado, alvo))
    return comandos


def medir(
    context: Context, escolhidos: list[str] | None, dias: int | None
) -> list[Medida]:
    engine = context.engine_adapter
    engine.execute(f"CREATE SCHEMA IF NOT EXISTS {SCRATCH}")
    periodo = _janela(engine, dias)
    medidas: list[Medida] = []

    for chave in _ordem(context, escolhidos):
        modelo = context.models[chave]
        alvo = _alvo(modelo.name)
        if modelo.kind.is_incremental_by_time_range:
            # Rendered without a window, an incremental model falls back to the
            # default interval — a single recent day, which for a collection
            # that ends months ago is empty. An empty build measures nothing
            # and looks like a spectacular improvement.
            inicio, fim = periodo or (_inicio_do_modelo(modelo), date.today())
            consulta = context.render(chave, start=inicio, end=fim)
        else:
            consulta = context.render(chave)
        sql = consulta.sql(dialect="postgres")

        engine.execute(f"DROP TABLE IF EXISTS {alvo}")
        inicio = time.perf_counter()
        engine.execute(f"CREATE TABLE {alvo} AS {sql}")
        construcao = time.perf_counter() - inicio

        inicio = time.perf_counter()
        for comando in _posteriores(context, chave, alvo):
            engine.execute(comando)
        indices = time.perf_counter() - inicio

        linhas = engine.fetchone(f"SELECT COUNT(*) FROM {alvo}")[0]
        engine.execute(f"DROP TABLE IF EXISTS {alvo}")

        medidas.append(
            Medida(
                modelo.name,
                modelo.kind.name,
                str(modelo.cron),
                construcao,
                indices,
                int(linhas),
            )
        )
        print(
            f"  {modelo.name:32} {construcao:8.1f}s build "
            f"{indices:8.1f}s index  {linhas:>9} rows",
            flush=True,
        )

    engine.execute(f"DROP SCHEMA IF EXISTS {SCRATCH} CASCADE")
    return medidas


def _tabela(medidas: list[Medida]) -> str:
    largura = max((len(m.modelo) for m in medidas), default=10)
    linhas = [
        f"| {'model':<{largura}} | {'cron':>9} | {'build':>10} | {'indexes':>10} | {'total':>10} | {'rows':>10} |",
        f"|{'-' * (largura + 2)}|{'-' * 11}|{'-' * 12}|{'-' * 12}|{'-' * 12}|{'-' * 12}|",
    ]
    for m in medidas:
        linhas.append(
            f"| {m.modelo:<{largura}} | {m.cron:>9} | {m.construcao_s:9.1f}s "
            f"| {m.indices_s:9.1f}s | {m.total_s:9.1f}s | {m.linhas:>10,} |"
        )
    total = sum(m.total_s for m in medidas)
    linhas.append(
        f"| {'TOTAL':<{largura}} | {'':>9} | {'':>10} | {'':>10} | {total:9.1f}s | {'':>10} |"
    )
    return "\n".join(linhas)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelos", nargs="*", help="only these, by model name")
    parser.add_argument(
        "--janela",
        type=int,
        help="days of data to build for incremental models; full build without it",
    )
    parser.add_argument("--saida", type=Path, help="also write the numbers as JSON")
    args = parser.parse_args()

    context = Context(paths=PROJECT)
    janela = f"last {args.janela} days" if args.janela else "whole collection"
    print(f"measuring: {janela}\n")
    medidas = medir(context, args.modelos, args.janela)

    print("\n" + _tabela(medidas))

    if args.saida:
        args.saida.write_text(
            json.dumps(
                {
                    "medido_em": date.today().isoformat(),
                    "janela_dias": args.janela,
                    "modelos": [asdict(m) | {"total_s": m.total_s} for m in medidas],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nwritten to {args.saida}")


if __name__ == "__main__":
    main()
