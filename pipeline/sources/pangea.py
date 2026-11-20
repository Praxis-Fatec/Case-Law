"""
Official precedents from the BNP, through the Pangea portal.

The collection reconstructs súmulas from how decisions transcribe them, which
gives a text and no standing: `core.precedente` leaves `situacao` null on
purpose, because showing a cancelled súmula as current is the error that story
exists to avoid. The BNP is the register that closes that gap. It is the CNJ's
national precedent base, fed by the courts themselves under Resolução CNJ
444/2022, and it carries a situação for every entry.

The documented BNP interface is behind the PDPJ's single sign-on and answers
401 to anyone without a certificate. What is reachable is the API the Pangea
portal's own pages call, and this module reads that. Three things about it
shape the code below.

The filter travels wrapped. The body is `{"filtro": {...}}`, and the whole
default object goes with it: a subset answers 400 with `Requisição inválida`
and no field name, so there is nothing to debug from the response.

`orgaos` and `tipos` must both carry a value. An empty list is the 400 above —
but a value outside the vocabulary is worse, because it answers 200 with
`total: 0`. Asking for `Súmula` instead of `SUM` reports an empty collection as
if the court had no súmulas. So the vocabulary is read from `/parametros` and
checked before the load, where a renamed sigla fails by name instead of
silently halving the base.

`cancelados` defaults to false on the portal, which hides exactly the rows this
is for. It is true here.
"""

import os
import time
from collections.abc import Iterator
from typing import Any

import dlt
from dlt.sources.helpers import requests

API = "https://pangeabnp.pdpj.jus.br/api/v1"
PRECEDENTES = f"{API}/precedentes"
PARAMETROS = f"{API}/parametros"

USER_AGENT = "case-law-pipeline/1.0 (academic jurisprudence research)"

PAGE_SIZE = 100
REQUEST_TIMEOUT = 120
REQUEST_INTERVAL = 1.0

REFUSAL_CODES = (401, 403, 429)

# Súmula, súmula vinculante, repercussão geral and the STJ's repetitive appeals,
# which is what the STJ numbers as a tema. The other species the BNP carries —
# notas técnicas, controvérsias, the concentrated-control actions — are not
# precedents the collection cites by number, and `core.precedente` has no shape
# for them.
RECORTE: tuple[tuple[str, str], ...] = (
    ("STF", "SUM"),
    ("STF", "SV"),
    ("STF", "RG"),
    ("STJ", "SUM"),
    ("STJ", "RR"),
)

dlt.config["schema.naming"] = "direct"


class SourceRefused(RuntimeError):
    """The portal declined to answer, and the load must stop rather than insist."""


class VocabularyChanged(RuntimeError):
    """A sigla this module asks for is no longer one the portal offers."""


class _Pacer:
    def __init__(self, interval: float) -> None:
        self.interval = interval
        self.last_call = 0.0

    def wait(self) -> None:
        elapsed = time.monotonic() - self.last_call
        if self.last_call and elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self.last_call = time.monotonic()


def _filtro(orgao: str, tipo: str, pagina: int, tamanho: int) -> dict[str, Any]:
    return {
        "filtro": {
            "buscaGeral": "",
            "todasPalavras": "",
            "quaisquerPalavras": "",
            "semPalavras": "",
            "trechoExato": "",
            "atualizacaoDesde": "",
            "atualizacaoAte": "",
            "cancelados": True,
            "ordenacao": "Text",
            "nr": "",
            "orgaos": [orgao],
            "tipos": [tipo],
            "pagina": pagina,
            "tamanhoPagina": tamanho,
        }
    }


def _refused(status: int) -> SourceRefused:
    return SourceRefused(
        f"the Pangea portal answered {status}. The load stops here. Access to "
        "the documented BNP interface is asked of the CNJ through the PDPJ, at "
        "https://docs.pdpj.jus.br; see "
        "documentation/architecture/pangea-source.md"
    )


def _ask(body: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        PRECEDENTES,
        json=body,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )

    if response.status_code in REFUSAL_CODES:
        raise _refused(response.status_code)

    response.raise_for_status()
    answer = response.json()
    return dict(answer) if isinstance(answer, dict) else {}


def parametros() -> dict[str, Any]:
    response = requests.get(
        PARAMETROS,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )

    if response.status_code in REFUSAL_CODES:
        raise _refused(response.status_code)

    response.raise_for_status()
    answer = response.json()
    return dict(answer) if isinstance(answer, dict) else {}


def _siglas(entries: Any) -> set[str]:
    if not isinstance(entries, list):
        return set()
    return {
        str(entry["sigla"]).strip()
        for entry in entries
        if isinstance(entry, dict) and str(entry.get("sigla") or "").strip()
    }


def confirmar_vocabulario(recorte: tuple[tuple[str, str], ...] = RECORTE) -> None:
    """
    That every sigla asked for is still one the portal publishes.

    This is the guard against the silent empty answer. Without it a renamed
    species reaches the collection as a tribunal that stopped having súmulas.
    """
    publicados = parametros()
    orgaos = _siglas(publicados.get("orgaos"))
    tipos = _siglas(publicados.get("especies"))

    ausentes = sorted(
        {f"orgao {orgao}" for orgao, _ in recorte if orgao not in orgaos}
        | {f"tipo {tipo}" for _, tipo in recorte if tipo not in tipos}
    )
    if ausentes:
        raise VocabularyChanged(
            "the Pangea vocabulary no longer offers " + ", ".join(ausentes)
        )


def _records(answer: dict[str, Any]) -> list[dict[str, Any]]:
    found = answer.get("resultados")
    if not isinstance(found, list):
        return []
    return [record for record in found if isinstance(record, dict)]


def _total(answer: dict[str, Any]) -> int:
    try:
        return int(answer.get("total") or 0)
    except (TypeError, ValueError):
        return 0


def _identifier(record: dict[str, Any]) -> str:
    return str(record.get("id") or "").strip()


def _collect(
    orgao: str,
    tipo: str,
    pacer: _Pacer,
    page_size: int,
    max_pages: int | None,
) -> Iterator[list[dict[str, Any]]]:
    pagina = 1
    vistos = 0
    total: int | None = None

    while max_pages is None or pagina <= max_pages:
        pacer.wait()
        answer = _ask(_filtro(orgao, tipo, pagina, page_size))
        records = _records(answer)

        if total is None:
            total = _total(answer)
            print(f"  {orgao}/{tipo}: {total} published", flush=True)

        if not records:
            break

        useful = [record for record in records if _identifier(record)]
        if useful:
            yield useful
        vistos += len(records)

        if len(records) < page_size or (total and vistos >= total):
            break
        pagina += 1

    if total and vistos < total:
        print(f"  {orgao}/{tipo}: stopped at {vistos} of {total}", flush=True)


@dlt.resource(
    name="precedente_pangea",
    write_disposition="merge",
    primary_key="id",
)
def precedentes(
    recorte: tuple[tuple[str, str], ...] = RECORTE,
    interval: float = REQUEST_INTERVAL,
    page_size: int = PAGE_SIZE,
    max_pages: int | None = None,
    check_vocabulary: bool = True,
) -> Iterator[list[dict[str, Any]]]:
    if check_vocabulary:
        confirmar_vocabulario(recorte)

    pacer = _Pacer(interval)
    for orgao, tipo in recorte:
        yield from _collect(orgao, tipo, pacer, page_size, max_pages)


def main() -> None:
    limite = os.getenv("PANGEA_MAX_PAGES", "").strip()
    ritmo = os.getenv("PANGEA_REQUEST_INTERVAL", "").strip()
    pagina = os.getenv("PANGEA_PAGE_SIZE", "").strip()

    pipeline = dlt.pipeline(
        pipeline_name="case_law",
        destination="postgres",
        dataset_name="raw",
    )
    print("loading official precedents from the BNP", flush=True)
    print(
        pipeline.run(
            precedentes(
                interval=float(ritmo) if ritmo else REQUEST_INTERVAL,
                page_size=int(pagina) if pagina else PAGE_SIZE,
                max_pages=int(limite) if limite else None,
            )
        )
    )


if __name__ == "__main__":
    main()
