"""
What the BNP collector reads, and what it refuses to do.

The source is an undocumented API behind a court council's portal, so these
tests carry the same weight as the STF's: the question is not whether a
published file was parsed, it is whether a contract nobody promised to keep can
change without the load either crashing or quietly inventing data.

Two of its failures are silent, and both are tested here rather than trusted.

A sigla outside the vocabulary answers 200 with `total: 0`. Asking for `Súmula`
instead of `SUM` reports an empty register as if the court had no súmulas, and
every guard downstream approves it — an empty source is not an invalid one. So
the vocabulary is confirmed against `/parametros` before the first page, and the
test that matters is the one where a sigla disappears.

`cancelados` defaults to false on the portal, which hides the 257 cancelled
precedents. A collector that copied the portal's defaults would load the whole
register and still be unable to say that a súmula was cancelled, which is the
only reason this source is read at all.

The fixtures are real answers, captured on 20/11/2026, with the traps the
register actually carries: a STF súmula whose `tese` is the literal string `não
informado` and whose text is in `questao`, a STJ súmula whose text is in `tese`
and arrives as HTML, a cancelled súmula, an altered one, a tema with a sentence
for a situação, and a record whose key is empty.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from sources import pangea

FIXTURES = Path(__file__).parent / "fixtures"
RESPOSTAS: dict[str, Any] = json.loads(
    (FIXTURES / "pangea_resposta.json").read_text(encoding="utf-8")
)
PARAMETROS: dict[str, Any] = json.loads(
    (FIXTURES / "pangea_parametros.json").read_text(encoding="utf-8")
)

VAZIA = {"total": 0, "resultados": []}


class _Resposta:
    def __init__(self, status: int, payload: Any = None) -> None:
        self.status_code = status
        self._payload = payload if payload is not None else {}

    def json(self) -> Any:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise AssertionError(f"raise_for_status reached with {self.status_code}")


def _par(body: dict[str, Any]) -> str:
    filtro = body["filtro"]
    return f"{filtro['orgaos'][0]}/{filtro['tipos'][0]}"


def _responde(
    monkeypatch: pytest.MonkeyPatch,
    *,
    parametros: Any = None,
    post: Callable[[dict[str, Any], int], _Resposta] | None = None,
    get_status: int = 200,
) -> list[dict[str, Any]]:
    """
    The portal, answered from the fixtures. Returns what was asked of it.

    `post` receives the body and the page already read for that pair, so a test
    can answer a refusal, an empty page or a second page without restating the
    paging.
    """
    enviados: list[dict[str, Any]] = []
    paginas: dict[str, int] = {}

    def _get(url: str, **kwargs: Any) -> _Resposta:
        enviados.append({"metodo": "get", "url": url, **kwargs})
        payload = PARAMETROS if parametros is None else parametros
        return _Resposta(get_status, payload)

    def _post(url: str, **kwargs: Any) -> _Resposta:
        body = kwargs["json"]
        enviados.append({"metodo": "post", "url": url, **kwargs})
        par = _par(body)
        paginas[par] = paginas.get(par, 0) + 1
        if post is not None:
            return post(body, paginas[par])
        return _Resposta(200, RESPOSTAS.get(par, VAZIA))

    monkeypatch.setattr(pangea.requests, "get", _get)
    monkeypatch.setattr(pangea.requests, "post", _post)
    return enviados


def _registros(monkeypatch: pytest.MonkeyPatch, **kwargs: Any) -> list[dict[str, Any]]:
    _responde(monkeypatch)
    return _ler(pangea.precedentes(interval=0.0, **kwargs))


def _ler(recurso: Any) -> list[dict[str, Any]]:
    saida: list[dict[str, Any]] = []
    for item in recurso:
        saida.extend(item if isinstance(item, list) else [item])
    return saida


def _falha(acao: Callable[[], object]) -> BaseException | None:
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
    return {linha["id"]: linha for linha in linhas}


class TestPedido:
    def test_the_filter_travels_wrapped_and_whole(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        A bare filter answers 400, and so does one carrying only the fields
        that matter. The portal sends its whole default object on every search,
        and the 400 names no field — there is nothing to debug from it.
        """
        enviados = _responde(monkeypatch)
        _ler(pangea.precedentes(interval=0.0, recorte=(("STF", "SUM"),)))

        corpo = next(e["json"] for e in enviados if e["metodo"] == "post")

        assert set(corpo) == {"filtro"}
        assert set(corpo["filtro"]) == {
            "buscaGeral",
            "todasPalavras",
            "quaisquerPalavras",
            "semPalavras",
            "trechoExato",
            "atualizacaoDesde",
            "atualizacaoAte",
            "cancelados",
            "ordenacao",
            "nr",
            "orgaos",
            "tipos",
            "pagina",
            "tamanhoPagina",
        }

    def test_cancelled_precedents_are_asked_for(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        The whole point of the source. Left at the portal's own default this
        load would collect the register and still show a cancelled súmula as
        current.
        """
        enviados = _responde(monkeypatch)
        _ler(pangea.precedentes(interval=0.0, recorte=(("STF", "SUM"),)))

        corpo = next(e["json"] for e in enviados if e["metodo"] == "post")

        assert corpo["filtro"]["cancelados"] is True

    def test_each_pair_is_asked_for_on_its_own(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        There is no way to ask for everything: an empty `orgaos` or `tipos` is
        a 400, so the register is reachable only by iterating the pairs.
        """
        enviados = _responde(monkeypatch)
        _ler(pangea.precedentes(interval=0.0))

        pedidos = [_par(e["json"]) for e in enviados if e["metodo"] == "post"]

        assert pedidos == [f"{orgao}/{tipo}" for orgao, tipo in pangea.RECORTE]
        for e in enviados:
            if e["metodo"] == "post":
                assert len(e["json"]["filtro"]["orgaos"]) == 1
                assert len(e["json"]["filtro"]["tipos"]) == 1

    def test_the_client_identifies_itself(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        enviados = _responde(monkeypatch)
        _ler(pangea.precedentes(interval=0.0, recorte=(("STF", "SUM"),)))

        for e in enviados:
            assert "case-law-pipeline" in e["headers"]["User-Agent"]


class TestVocabulario:
    def test_the_vocabulary_is_confirmed_before_the_first_page(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        enviados = _responde(monkeypatch)
        _ler(pangea.precedentes(interval=0.0, recorte=(("STF", "SUM"),)))

        assert enviados[0]["metodo"] == "get"
        assert enviados[0]["url"] == pangea.PARAMETROS

    def test_a_species_that_disappeared_fails_by_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        The silent failure this guard exists for. Without it the load reads a
        200 with `total: 0` and reports a court that stopped having súmulas.
        """
        sem_sumula = {
            "orgaos": PARAMETROS["orgaos"],
            "especies": [e for e in PARAMETROS["especies"] if e["sigla"] != "SUM"],
        }
        enviados = _responde(monkeypatch, parametros=sem_sumula)

        erro = _falha(lambda: _ler(pangea.precedentes(interval=0.0)))
        mudou = _na_cadeia(erro, pangea.VocabularyChanged)

        assert mudou is not None
        assert "SUM" in str(mudou)
        assert not [e for e in enviados if e["metodo"] == "post"], (
            "the load asked for pages although the vocabulary had moved"
        )

    def test_a_court_that_disappeared_fails_by_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sem_stj = {
            "orgaos": [o for o in PARAMETROS["orgaos"] if o["sigla"] != "STJ"],
            "especies": PARAMETROS["especies"],
        }
        _responde(monkeypatch, parametros=sem_stj)

        erro = _falha(lambda: _ler(pangea.precedentes(interval=0.0)))
        mudou = _na_cadeia(erro, pangea.VocabularyChanged)

        assert mudou is not None
        assert "STJ" in str(mudou)


class TestLeitura:
    def test_a_record_without_a_key_is_dropped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        A record with no id cannot be merged: the next load would write it
        again. The fixture carries one, and it must not reach the destination.
        """
        registros = _registros(monkeypatch, recorte=(("STF", "SUM"),))
        esperados = RESPOSTAS["STF/SUM"]["resultados"]

        assert all(linha["id"] for linha in registros)
        assert len(registros) == len(esperados) - 1

    def test_the_fields_the_transformation_reads_survive(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        por_id = _por_id(_registros(monkeypatch))

        sumula = por_id["stf-sum-1"]
        assert sumula["orgao"] == "STF"
        assert sumula["tipo"] == "SUM"
        assert sumula["nr"] == 1
        assert sumula["situacao"] == "APROVADO"
        assert sumula["ultimaAtualizacao"] == "22/05/2025"

    def test_the_two_courts_carry_their_text_in_different_fields(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        The finding the survey turned on. The STF's súmula text is in
        `questao` and its `tese` is the literal `não informado`; the STJ's is in
        `tese`, as HTML. A reader of `tese` alone would call 29,2% of the
        register empty.
        """
        por_id = _por_id(_registros(monkeypatch))

        assert por_id["stf-sum-1"]["tese"] == "não informado"
        assert "expulsão de estrangeiro" in por_id["stf-sum-1"]["questao"]

        assert "<p>" in por_id["stj-sum-1"]["tese"]
        assert not por_id["stj-sum-1"].get("questao")

    def test_a_cancelled_precedent_arrives_marked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        por_id = _por_id(_registros(monkeypatch))

        assert por_id["stf-sum-619"]["situacao"] == "Cancelado"
        assert por_id["stf-sum-359"]["situacao"] == "ALTERADO"
        assert por_id["stj-sum-68"]["situacao"] == "Cancelado"

    def test_a_status_may_be_a_whole_sentence(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        `situacao` is free text, not an enumeration: 26 values over the
        register, and for temas a sentence. Anything that reads it has to treat
        it as prose.
        """
        por_id = _por_id(_registros(monkeypatch))

        assert "repercussão geral" in por_id["stf-rg-1"]["situacao"]


class TestPaginacao:
    def test_the_walk_stops_when_the_page_is_short(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        enviados = _responde(monkeypatch)
        _ler(pangea.precedentes(interval=0.0, recorte=(("STF", "SUM"),)))

        assert len([e for e in enviados if e["metodo"] == "post"]) == 1

    def test_the_walk_reads_a_second_page(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        primeira = RESPOSTAS["STF/SUM"]["resultados"][:2]
        segunda = RESPOSTAS["STF/SUM"]["resultados"][2:3]

        def responder(body: dict[str, Any], pagina: int) -> _Resposta:
            cheia = primeira if pagina == 1 else segunda
            return _Resposta(200, {"total": 3, "resultados": cheia})

        enviados = _responde(monkeypatch, post=responder)
        registros = _ler(
            pangea.precedentes(interval=0.0, recorte=(("STF", "SUM"),), page_size=2)
        )

        paginas = [
            e["json"]["filtro"]["pagina"] for e in enviados if e["metodo"] == "post"
        ]
        assert paginas == [1, 2]
        assert len(registros) == 3

    def test_the_first_page_is_page_one(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`pagina` is 1-based; asking for page 0 is a 400."""
        enviados = _responde(monkeypatch)
        _ler(pangea.precedentes(interval=0.0, recorte=(("STF", "SUM"),)))

        corpo = next(e["json"] for e in enviados if e["metodo"] == "post")
        assert corpo["filtro"]["pagina"] == 1


class TestConduta:
    @pytest.mark.parametrize("status", pangea.REFUSAL_CODES)
    def test_a_refusal_ends_the_load(
        self, monkeypatch: pytest.MonkeyPatch, status: int
    ) -> None:
        """
        A portal that answers 401, 403 or 429 has declined. The load stops on
        the spot instead of retrying around it, and the message names the
        channel to ask through.
        """
        enviados = _responde(monkeypatch, post=lambda body, pagina: _Resposta(status))

        erro = _falha(lambda: _ler(pangea.precedentes(interval=0.0)))
        recusa = _na_cadeia(erro, pangea.SourceRefused)

        assert recusa is not None
        assert str(status) in str(recusa)
        assert "docs.pdpj.jus.br" in str(recusa)
        assert len([e for e in enviados if e["metodo"] == "post"]) == 1

    @pytest.mark.parametrize("status", pangea.REFUSAL_CODES)
    def test_a_refusal_on_the_vocabulary_ends_the_load(
        self, monkeypatch: pytest.MonkeyPatch, status: int
    ) -> None:
        enviados = _responde(monkeypatch, get_status=status)

        erro = _falha(lambda: _ler(pangea.precedentes(interval=0.0)))

        assert _na_cadeia(erro, pangea.SourceRefused) is not None
        assert not [e for e in enviados if e["metodo"] == "post"]


class TestContrato:
    def test_a_renamed_container_arrives_as_absence(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        A renamed field has to surface as an absent value, not a crash halfway
        through a load. The guard against reading nothing is the vocabulary
        check, not an exception here.
        """
        _responde(
            monkeypatch,
            post=lambda body, pagina: _Resposta(200, {"total": 3, "linhas": []}),
        )

        registros = _ler(pangea.precedentes(interval=0.0))

        assert registros == []

    def test_an_unreadable_total_does_not_stop_the_reading(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def responder(body: dict[str, Any], pagina: int) -> _Resposta:
            return _Resposta(
                200,
                {
                    "total": "muitos",
                    "resultados": RESPOSTAS["STF/SV"]["resultados"],
                },
            )

        _responde(monkeypatch, post=responder)

        registros = _ler(pangea.precedentes(interval=0.0, recorte=(("STF", "SV"),)))

        assert _por_id(registros)["stf-sv-1"]["nr"] == 1
