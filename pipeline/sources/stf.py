"""
Acórdãos from the STF's jurisprudence search.

Unlike the STJ, the STF publishes no open-data product: there is no CKAN, no
licence and no documented interface. What exists is the Elasticsearch service
behind the Tribunal's own search page, and this module reads it. The survey that
reached that conclusion is in `documentation/architecture/stf-source.md`, and
the standing of the source is recorded on its row in `fonte.csv`.

Three consequences follow, and they shape the code below.

The contract is undocumented, so it can change without notice. Only the fields
this project actually reads are asked for, and every one of them is read
defensively: a renamed field has to surface as an absent value, not a crash
halfway through a load.

The service is a court's, not ours. Requests are paced, identify the client, and
stop on the first refusal. A 403 or a 429 ends the load with a message naming
the channel to ask through — it is never retried around, and the client is never
disguised.

The `from`/`size` paging the page itself uses is capped by Elasticsearch at ten
thousand documents, which the collection exceeds many times over. Paging here
walks `search_after` over a stable sort instead, so the whole base is reachable
and a record is never served twice.
"""

import os
import time
from collections.abc import Iterator
from datetime import date
from typing import Any

import dlt
from dlt.sources.helpers import requests

SEARCH_URL = "https://jurisprudencia.stf.jus.br/api/search/search"
INTEIRO_TEOR = "https://jurisprudencia.stf.jus.br/pages/search/{documento}"

USER_AGENT = "case-law-pipeline/1.0 (academic jurisprudence research)"

BASE = "acordaos"
PAGE_SIZE = 100
REQUEST_TIMEOUT = 120
REQUEST_INTERVAL = 1.0

REFUSAL_CODES = (401, 403, 429)

FIELDS = (
    "id",
    "dg_unique",
    "base",
    "titulo",
    "ementa_texto",
    "inteiro_teor_url",
    "julgamento_data",
    "publicacao_data",
    "orgao_julgador",
    "ministro_facet",
    "relator_processo_nome",
    "relator_acordao_nome",
    "processo_codigo_completo",
    "processo_numero",
    "processo_classe_processual_unificada_sigla",
    "processo_classe_processual_unificada_extenso",
    "acordao_ata",
    "documental_tese_texto",
    "documental_tese_tema_texto",
    "documental_indexacao_texto",
    "documental_legislacao_citada_texto",
    "documental_jurisprudencia_citada_texto",
    "documental_observacao_texto",
    "is_repercussao_geral",
    "is_questao_ordem",
    "acompanhamento_processual_url",
    "dje_url",
    "procedencia_geografica_uf_sigla",
    "dg_atualizado_em",
)

SORT = [{"julgamento_data": "asc"}, {"tiebreaker_sort": "asc"}]

dlt.config["schema.naming"] = "direct"


class SourceRefused(RuntimeError):
    """The STF declined to answer, and the load must stop rather than insist."""


class _Pacer:
    def __init__(self, interval: float) -> None:
        self.interval = interval
        self.last_call = 0.0

    def wait(self) -> None:
        elapsed = time.monotonic() - self.last_call
        if self.last_call and elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self.last_call = time.monotonic()


def _window(start: date | None, end: date | None) -> list[dict[str, Any]]:
    if not start and not end:
        return []
    bounds: dict[str, str] = {}
    if start:
        bounds["gte"] = start.isoformat()
    if end:
        bounds["lte"] = end.isoformat()
    return [{"range": {"julgamento_data": bounds}}]


def _payload(
    start: date | None,
    end: date | None,
    size: int,
    after: list[Any] | None,
    total: bool,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "query": {
            "bool": {
                "filter": [{"term": {"base": BASE}}, *_window(start, end)],
                "must": [],
                "should": [],
                "must_not": [],
            }
        },
        "_source": list(FIELDS),
        "size": size,
        "sort": SORT,
        "track_total_hits": total,
    }
    if after:
        body["search_after"] = after
    return body


def _ask(body: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        SEARCH_URL,
        json=body,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )

    if response.status_code in REFUSAL_CODES:
        raise SourceRefused(
            f"the STF answered {response.status_code}. The load stops here. "
            "Collection access is asked of the Coordenadoria de Pesquisas "
            "Judiciarias, copj@stf.jus.br; see "
            "documentation/architecture/stf-source.md"
        )

    response.raise_for_status()
    return dict(response.json())


def _result(answer: dict[str, Any]) -> dict[str, Any]:
    """The service wraps the Elasticsearch answer in `result`, beside a search id."""
    inner = answer.get("result")
    return dict(inner) if isinstance(inner, dict) else answer


def _hits(answer: dict[str, Any]) -> list[dict[str, Any]]:
    hits = _result(answer).get("hits")
    if not isinstance(hits, dict):
        return []
    found = hits.get("hits")
    if not isinstance(found, list):
        return []
    return [hit for hit in found if isinstance(hit, dict)]


def _record(hit: dict[str, Any]) -> dict[str, Any]:
    source = hit.get("_source")
    fields = dict(source) if isinstance(source, dict) else {}
    fields["_id"] = str(hit.get("_id") or "")
    return fields


def _identifier(record: dict[str, Any]) -> str:
    for key in ("_id", "id", "dg_unique"):
        value = str(record.get(key) or "").strip()
        if value:
            return value
    return ""


@dlt.resource(
    name="acordao_stf",
    write_disposition="merge",
    primary_key="_id",
)
def acordaos(
    start: date | None = None,
    end: date | None = None,
    max_pages: int | None = None,
    interval: float = REQUEST_INTERVAL,
    page_size: int = PAGE_SIZE,
) -> Iterator[list[dict[str, Any]]]:
    pacer = _Pacer(interval)
    after: list[Any] | None = None
    pages = 0
    sem_chave = 0

    while max_pages is None or pages < max_pages:
        pacer.wait()
        answer = _ask(_payload(start, end, page_size, after, pages == 0))
        hits = _hits(answer)

        if not hits:
            break

        records = [_record(hit) for hit in hits]
        useful = [r for r in records if _identifier(r)]
        sem_chave += len(records) - len(useful)

        if useful:
            yield useful

        last = hits[-1].get("sort")
        if not isinstance(last, list) or not last:
            break
        after = last
        pages += 1

        if len(hits) < page_size:
            break

    if sem_chave:
        print(f"  {sem_chave} records without an id, skipped", flush=True)


def total_available(start: date | None = None, end: date | None = None) -> int:
    answer = _ask(_payload(start, end, 0, None, True))
    hits = _result(answer).get("hits")
    if not isinstance(hits, dict):
        return 0
    total = hits.get("total")
    if isinstance(total, dict):
        return int(total.get("value") or 0)
    return int(total or 0)


def document_opens(identificador: str, documento: str | None = None) -> bool:
    """
    Whether the search still holds the record a link was built from.

    The portal is a single-page application and answers the same bytes for a
    real document, an invented one and none at all, so the page cannot be asked.
    The search can: a record that is still indexed answers one hit for its own
    id.

    Raises whatever the request raised, which is not an answer of "invalid".
    """
    chave = (documento or identificador or "").strip()
    if not chave:
        return False

    answer = _ask(
        {
            "query": {
                "bool": {
                    "filter": [{"term": {"base": BASE}}, {"ids": {"values": [chave]}}]
                }
            },
            "_source": ["id"],
            "size": 1,
            "track_total_hits": False,
        }
    )
    return bool(_hits(answer))


def main() -> None:
    inicio = os.getenv("STF_START", "").strip()
    fim = os.getenv("STF_END", "").strip()
    limite = os.getenv("STF_MAX_PAGES", "").strip()

    pipeline = dlt.pipeline(
        pipeline_name="case_law",
        destination="postgres",
        dataset_name="raw",
    )
    print(
        pipeline.run(
            acordaos(
                start=date.fromisoformat(inicio) if inicio else None,
                end=date.fromisoformat(fim) if fim else None,
                max_pages=int(limite) if limite else None,
            )
        )
    )


if __name__ == "__main__":
    main()
