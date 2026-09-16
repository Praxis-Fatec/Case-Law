import os
import time
from collections.abc import Iterator
from datetime import date
from typing import Any

import dlt
from dlt.sources.helpers import requests

SEARCH_URL = "https://jurisdf.tjdft.jus.br/api/v1/pesquisa"
COLLECTION = "acordaos"
PAGE_SIZE = 40
REQUEST_TIMEOUT = 90
REQUEST_INTERVAL = 0.5

DROPPED_FIELDS = ("marcadores",)
DROPPED_NESTED_FIELDS = {"jurisprudenciaEmFoco": ("conteudo",)}

dlt.config["schema.naming"] = "direct"


def _search_terms(start: date | None, end: date | None) -> list[dict[str, str]]:
    terms = [{"campo": "base", "valor": COLLECTION}]
    if start and end:
        terms.append({"campo": "dataJulgamento", "valor": f"entre {start} e {end}"})
    return terms


def _payload(
    terms: list[dict[str, str]],
    page: int,
    subject: str = "",
) -> dict[str, Any]:
    return {
        "query": subject,
        "termosAcessorios": terms,
        "pagina": page,
        "tamanho": PAGE_SIZE,
        "sinonimos": False,
        "espelho": False,
        "inteiroTeor": False,
        "retornaInteiroTeor": False,
        "retornaTotalizacao": False,
    }


def _clean(record: dict[str, Any]) -> dict[str, Any]:
    cleaned = {
        key: value for key, value in record.items() if key not in DROPPED_FIELDS
    }

    for field, inner_fields in DROPPED_NESTED_FIELDS.items():
        entries = cleaned.get(field)
        if not isinstance(entries, list):
            continue
        cleaned[field] = [
            {key: value for key, value in entry.items() if key not in inner_fields}
            for entry in entries
            if isinstance(entry, dict)
        ]

    return cleaned


class _Pacer:
    def __init__(self, interval: float) -> None:
        self.interval = interval
        self.last_call = 0.0

    def wait(self) -> None:
        elapsed = time.monotonic() - self.last_call
        if self.last_call and elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self.last_call = time.monotonic()


@dlt.resource(
    name="acordao_tjdft",
    write_disposition="merge",
    primary_key="identificador",
)
def acordaos(
    start: date | None = None,
    end: date | None = None,
    subject: str = "",
    max_pages: int | None = None,
    interval: float = REQUEST_INTERVAL,
) -> Iterator[list[dict[str, Any]]]:
    terms = _search_terms(start, end)
    pacer = _Pacer(interval)
    page = 0

    while max_pages is None or page < max_pages:
        pacer.wait()
        response = requests.post(
            SEARCH_URL,
            json=_payload(terms, page, subject),
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        records = response.json().get("registros") or []

        if not records:
            return

        yield [_clean(record) for record in records]
        page += 1


def total_available(
    start: date | None = None,
    end: date | None = None,
    subject: str = "",
) -> int:
    response = requests.post(
        SEARCH_URL,
        json={**_payload(_search_terms(start, end), 0, subject), "tamanho": 1},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return int(response.json()["hits"]["value"])


def _date_from_env(name: str) -> date | None:
    value = os.getenv(name, "").strip()
    return date.fromisoformat(value) if value else None


def _int_from_env(name: str) -> int | None:
    value = os.getenv(name, "").strip()
    return int(value) if value else None


def _float_from_env(name: str, default: float) -> float:
    value = os.getenv(name, "").strip()
    return float(value) if value else default


def run() -> None:
    start = _date_from_env("TJDFT_START_DATE")
    end = _date_from_env("TJDFT_END_DATE")
    subject = os.getenv("TJDFT_SUBJECT", "").strip()
    max_pages = _int_from_env("TJDFT_MAX_PAGES")
    interval = _float_from_env("TJDFT_REQUEST_INTERVAL", REQUEST_INTERVAL)

    pipeline = dlt.pipeline(
        pipeline_name="case_law",
        destination="postgres",
        dataset_name="raw",
    )

    print(f"available at the source: {total_available(start, end, subject)}")
    print(
        pipeline.run(
            acordaos(
                start=start,
                end=end,
                subject=subject,
                max_pages=max_pages,
                interval=interval,
            )
        )
    )


if __name__ == "__main__":
    run()
