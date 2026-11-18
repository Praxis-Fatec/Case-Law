"""
What the STF collector reads, and what it refuses to do.

The source is an undocumented service, which moves the weight of these tests.
With the STJ the question is whether a published file was parsed correctly;
here it is whether a contract that nobody promised to keep can change without
the load either crashing or quietly inventing data.

The fixture is a real answer, captured on 18/11/2026, with the traps the
collection actually carries: the `result` envelope the service wraps the
Elasticsearch answer in, the two shapes of inteiro teor address that the eras
use, an acordao from 1892 with no publication date and no reporting judge, one
from 2026 with both, and a record whose key is empty.

The refusal tests are the ones that matter for conduct. A court that answers
401, 403 or 429 has declined, and the collector has to stop on the spot instead
of retrying around it.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from sources import stf

FIXTURES = Path(__file__).parent / "fixtures"
RESPOSTA: dict[str, Any] = json.loads(
    (FIXTURES / "stf_resposta.json").read_text(encoding="utf-8")
)

ANTIGO = "sjur364972"
RECENTE = "sjur559244"


class _Resposta:
    def __init__(self, status: int, payload: Any = None) -> None:
        self.status_code = status
        self._payload = payload if payload is not None else {}

    def json(self) -> Any:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise AssertionError(f"raise_for_status reached with {self.status_code}")


def _responde(
    monkeypatch: pytest.MonkeyPatch, *respostas: _Resposta
) -> list[dict[str, Any]]:
    enviados: list[dict[str, Any]] = []
    fila = list(respostas)

    def _post(url: str, **kwargs: Any) -> _Resposta:
        enviados.append({"url": url, **kwargs})
        return (
            fila.pop(0) if fila else _Resposta(200, {"result": {"hits": {"hits": []}}})
        )

    monkeypatch.setattr(stf.requests, "post", _post)
    return enviados


def _registros(monkeypatch: pytest.MonkeyPatch, **kwargs: Any) -> list[dict[str, Any]]:
    _responde(monkeypatch, _Resposta(200, RESPOSTA))
    saida: list[dict[str, Any]] = []
    for item in stf.acordaos(interval=0.0, **kwargs):
        saida.extend(item if isinstance(item, list) else [item])
    return saida


def _falha(acao: Callable[[], object]) -> BaseException | None:
    """Whatever the action raised, or None when it did not raise."""
    try:
        acao()
    except BaseException as erro:  # noqa: BLE001 - the type is what is under test
        return erro
    return None


def _na_cadeia(
    erro: BaseException | None, tipo: type[BaseException]
) -> BaseException | None:
    """
    The refusal travels inside whatever the extraction wrapped it in.

    dlt reports a resource's failure as its own error with the original as the
    cause, so a test that waits for the bare exception would pass only by
    accident of how the library reports today.
    """
    atual: BaseException | None = erro
    while atual is not None:
        if isinstance(atual, tipo):
            return atual
        atual = atual.__cause__ or atual.__context__
    return None


def _por_id(linhas: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {linha["_id"]: linha for linha in linhas}


class TestLeitura:
    def test_the_answer_is_unwrapped_from_its_envelope(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        The service does not answer Elasticsearch directly: it nests the answer
        under `result`, beside a search id of its own. Read as if it were plain
        Elasticsearch, every load would report zero documents and succeed.
        """
        assert "result" in RESPOSTA
        assert "hits" not in RESPOSTA

        registros = _registros(monkeypatch, max_pages=1)

        assert registros, "the envelope was not unwrapped"
        assert ANTIGO in _por_id(registros)

    def test_a_record_without_a_key_is_dropped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        A record with no id cannot be merged: the next load would write it
        again. The fixture carries one, and it must not reach the destination.
        """
        registros = _registros(monkeypatch, max_pages=1)

        assert all(linha["_id"] for linha in registros)
        assert len(registros) == len(RESPOSTA["result"]["hits"]["hits"]) - 1

    def test_the_fields_the_project_reads_survive_the_reading(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        por_id = _por_id(_registros(monkeypatch, max_pages=1))
        recente = por_id[RECENTE]

        assert recente["ementa_texto"].startswith("Ementa:")
        assert recente["julgamento_data"] == "2026-02-05"
        assert recente["orgao_julgador"] == "Tribunal Pleno"
        assert recente["inteiro_teor_url"].startswith("https://portal.stf.jus.br/")

    def test_an_old_acordao_keeps_the_fields_it_has_and_no_others(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        The collection starts in 1892 and the old records are sparse: no
        publication date, no reporting judge. Absence has to arrive as absence,
        because a load that invents a date would date a decision by when it was
        collected.
        """
        antigo = _por_id(_registros(monkeypatch, max_pages=1))[ANTIGO]

        assert antigo["julgamento_data"] == "1892-04-27"
        assert antigo.get("publicacao_data") is None
        assert antigo.get("relator_acordao_nome") is None
        assert antigo["ementa_texto"]

    def test_both_shapes_of_document_address_are_kept(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        The address of the inteiro teor changes form with the era: the older
        acordaos open by `numero` and `classe`, the newer ones by `idDocumento`.
        The parameter's own name varies, so the record has to carry its address
        rather than the seed rebuilding one.
        """
        por_id = _por_id(_registros(monkeypatch, max_pages=1))

        assert "numero=" in por_id[ANTIGO]["inteiro_teor_url"]
        assert "idDocumento=" in por_id[RECENTE]["inteiro_teor_url"]


class TestPaginacao:
    def test_the_walk_asks_for_what_comes_after_the_last_record(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        `from` and `size` stop at ten thousand documents and the base holds
        373.191, so the walk is by `search_after` over a stable sort. The second
        request has to carry the last record's sort, or the walk reads the first
        page forever.
        """
        enviados = _responde(
            monkeypatch, _Resposta(200, RESPOSTA), _Resposta(200, RESPOSTA)
        )
        list(stf.acordaos(max_pages=2, page_size=5, interval=0.0))

        assert len(enviados) == 2
        assert "search_after" not in enviados[0]["json"]

        ultimo = RESPOSTA["result"]["hits"]["hits"][-1]["sort"]
        assert enviados[1]["json"]["search_after"] == ultimo

    def test_the_tiebreaker_is_unique_per_document(self) -> None:
        """
        The index advertises a `tiebreaker_sort` and the court's own page sorts
        by it, but the field does not exist: Elasticsearch answers Long.MAX for
        every document. The sort tuple is then unique only in its date, and
        `search_after` reads as "after this date" — every other decision judged
        that day is skipped.

        It fails silently, which is why this is a test and not a comment. The
        walk ends early, reports no error, and loads a third of the base:
        measured over 2026, 3.593 of 11.568.
        """
        assert len(stf.SORT) == 2
        assert stf.SORT[0] == {"julgamento_data": "asc"}
        assert stf.SORT[1] == {"id": "asc"}, (
            "the second sort key has to be unique per document"
        )

    def test_a_short_page_ends_the_walk(self, monkeypatch: pytest.MonkeyPatch) -> None:
        enviados = _responde(monkeypatch, _Resposta(200, RESPOSTA))
        list(stf.acordaos(page_size=500, interval=0.0))

        assert len(enviados) == 1

    def test_only_the_first_request_counts_the_whole_base(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        `track_total_hits` makes the service count every match. Asking for it on
        every page would charge the court for a number the load already has.
        """
        enviados = _responde(
            monkeypatch, _Resposta(200, RESPOSTA), _Resposta(200, RESPOSTA)
        )
        list(stf.acordaos(max_pages=2, page_size=5, interval=0.0))

        assert enviados[0]["json"]["track_total_hits"] is True
        assert enviados[1]["json"]["track_total_hits"] is False


class TestConduta:
    @pytest.mark.parametrize("status", [401, 403, 429])
    def test_a_refusal_stops_the_load(
        self, monkeypatch: pytest.MonkeyPatch, status: int
    ) -> None:
        """
        A court answering 401, 403 or 429 has declined. The BDJur is the
        precedent: it answered automated access until the STJ's cyber-security
        coordination stopped it, and the collector's duty then is to stop too.
        """
        _responde(monkeypatch, _Resposta(status))

        erro = _falha(lambda: list(stf.acordaos(interval=0.0)))
        recusa = _na_cadeia(erro, stf.SourceRefused)

        assert recusa is not None, f"the refusal did not survive: {erro!r}"
        assert str(status) in str(recusa)
        assert "copj@stf.jus.br" in str(recusa)

    def test_a_refusal_is_not_retried(self, monkeypatch: pytest.MonkeyPatch) -> None:
        enviados = _responde(monkeypatch, _Resposta(429), _Resposta(200, RESPOSTA))

        assert _falha(lambda: list(stf.acordaos(interval=0.0))) is not None
        assert len(enviados) == 1

    def test_the_client_says_what_it_is(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        The request identifies the client. Disguising it as a browser would be
        the one thing this collector must never do.
        """
        enviados = _responde(monkeypatch, _Resposta(200, RESPOSTA))
        list(stf.acordaos(max_pages=1, interval=0.0))

        agente = enviados[0]["headers"]["User-Agent"]
        assert agente == stf.USER_AGENT
        assert "Mozilla" not in agente

    def test_only_the_acordaos_are_asked_for(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        The same index also serves 762.031 monocratic decisions, 799 sumulas and
        the informativos. The project collects acordaos, and asking for more
        than that would read what it has no model for.
        """
        enviados = _responde(monkeypatch, _Resposta(200, RESPOSTA))
        list(stf.acordaos(max_pages=1, interval=0.0))

        filtros = enviados[0]["json"]["query"]["bool"]["filter"]
        assert {"term": {"base": "acordaos"}} in filtros

    def test_a_window_narrows_the_request_at_the_source(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from datetime import date

        enviados = _responde(monkeypatch, _Resposta(200, RESPOSTA))
        list(
            stf.acordaos(
                start=date(2026, 1, 1),
                end=date(2026, 12, 31),
                max_pages=1,
                interval=0.0,
            )
        )

        filtros = enviados[0]["json"]["query"]["bool"]["filter"]
        assert {
            "range": {"julgamento_data": {"gte": "2026-01-01", "lte": "2026-12-31"}}
        } in filtros


class TestTotal:
    def test_the_total_is_read_through_the_envelope(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _responde(monkeypatch, _Resposta(200, RESPOSTA))

        assert stf.total_available() == len(RESPOSTA["result"]["hits"]["hits"])

    def test_an_answer_without_a_total_is_zero_and_not_a_crash(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _responde(monkeypatch, _Resposta(200, {"result": {}}))

        assert stf.total_available() == 0
