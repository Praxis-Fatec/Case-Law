"""
The decisions that treat the same subject as the one being read.

Not the same words — the same subject. Searching a decision's own ementa for
other decisions returns whatever shares its procedural prose, and every
decision shares that: `doctrine-matching.md` measured a thesis about an oil
spill bringing back an article on limitation periods for workplace accidents.
So each term is weighed by how rare it is in judicial language, and the
procedural words weigh almost nothing.

Measured over the collection on 2026-11-11, against a sample of 3.000
decisions labelled by the precedents they cite: scoring by the summed weight
of the shared terms gives 0,426 precision at ten; dividing by the length of
both vectors gives 0,470; counting how often each term occurs in each ementa
gives 0,529. This endpoint does the third.

Similarity is not agreement. Two decisions about the same subject can settle
it in opposite directions, and the response says so by carrying the terms that
matched rather than a verdict about the relation. `RF20` requires the method
to be stated and calculated similarity told apart from an official link; these
suggestions are calculated, and nothing here is an official relation.

Enrichment, never the critical path. A decision opens without this; the detail
endpoint does not call it. Where the weights are not published, this answers an
empty list and the screen shows the decision anyway.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from psycopg import Connection
from psycopg.rows import DictRow
from pydantic import BaseModel, ConfigDict, Field

from app.api.decisions import DecisionBase, _base_fields, _published, _shared
from app.db import get_connection
from app.errors import DATABASE_RESPONSES, NOT_FOUND_RESPONSE, two_examples

router = APIRouter(tags=["related"])

DECISION_EXISTS_SQL = """
SELECT 1
FROM core.decisao
WHERE fonte_codigo = %(source)s AND identificador_fonte = %(identifier)s
"""

# Both tables arrive in the same publication and can still be absent one
# without the other, so the probe asks for both. It costs a tenth of a
# millisecond and lets a server that started before the weights were published
# begin using them the moment they appear, with nobody restarting anything —
# the same bargain `decisions.py` already makes for the broad-search ranking.
WEIGHTS_SQL = """
SELECT TO_REGCLASS('core.termo_judicial') IS NOT NULL AS vocabulario,
       TO_REGCLASS('core.decisao_norma')  IS NOT NULL AS normas
"""

# Only terms this rare are searched on. The floor is the one
# `doctrine-matching.md` arrived at by reading thirty suggestions one by one —
# a match needs at least one term that is rare in judicial prose — and using it
# to retrieve, rather than only to filter afterwards, is what makes the query
# affordable: without it the candidate set is most of the collection.
#
# It bounds the work per term and not per query. A term at this weight sits in
# at most 11.011 decisions, and up to twelve of them are searched with `OR`.
# Measured over 40 decisions drawn at random, asking for five: 674 ms at the
# median, 1,97 s at the ninetieth percentile, 4,68 s for the worst — whose
# candidate set is 72.811 decisions. Without the floor the same sample gives
# 1,42 s, 3,68 s and 10,08 s.
#
# The floor costs 16.370 decisions — 1,65% of the base — which carry no term
# this rare and so receive nothing, and 0,002 of precision at ten.
# `related-decisions.md` holds the rest, including the candidate budget that
# would halve the ninetieth percentile and was measured but not adopted.
RARITY_FLOOR = 4.5
SEARCH_TERMS = 12

# One term in common is a coincidence, which is why the project's method has
# always required two.
MINIMUM_TERMS = 2

RELATED_SQL = """
WITH origem AS (
  SELECT
    t.lexeme                                         AS termo,
    j.peso * (1 + LN(ARRAY_LENGTH(t.positions, 1)))  AS valor,
    j.peso                                           AS peso
  FROM core.decisao AS d
  CROSS JOIN LATERAL UNNEST(d.ementa_busca) AS t
  JOIN core.termo_judicial AS j ON j.termo = t.lexeme
  WHERE d.fonte_codigo = %(source)s AND d.identificador_fonte = %(identifier)s
),

raros AS (
  SELECT termo
  FROM origem
  WHERE peso >= {floor}
  ORDER BY peso DESC
  LIMIT {search_terms}
),

candidatos AS (
  SELECT d.fonte_codigo, d.identificador_fonte, d.ementa_busca
  FROM core.decisao AS d
  WHERE d.ementa_busca @@ TO_TSQUERY(
          'portugues_sem_acento', (SELECT STRING_AGG(termo, ' | ') FROM raros))
    AND NOT (d.fonte_codigo = %(source)s
             AND d.identificador_fonte = %(identifier)s)
),

casamento AS (
  SELECT
    c.fonte_codigo,
    c.identificador_fonte,
    SUM(o.valor * (j.peso * (1 + LN(ARRAY_LENGTH(t.positions, 1))))) AS produto,
    COUNT(*)                                                         AS termos,
    ARRAY_AGG(o.termo ORDER BY o.peso DESC)                          AS casou_em
  FROM candidatos AS c
  CROSS JOIN LATERAL UNNEST(c.ementa_busca) AS t
  JOIN origem AS o ON o.termo = t.lexeme
  JOIN core.termo_judicial AS j ON j.termo = t.lexeme
  GROUP BY c.fonte_codigo, c.identificador_fonte
),

proximas AS (
  SELECT
    m.fonte_codigo,
    m.identificador_fonte,
    m.produto / (nc.norma * no.norma) AS semelhanca,
    m.termos,
    m.casou_em
  FROM casamento AS m
  JOIN core.decisao_norma AS nc
    ON nc.fonte_codigo = m.fonte_codigo
   AND nc.identificador_fonte = m.identificador_fonte
  CROSS JOIN (
    SELECT norma FROM core.decisao_norma
    WHERE fonte_codigo = %(source)s AND identificador_fonte = %(identifier)s
  ) AS no
  WHERE m.termos >= {minimum}
)

SELECT
  decisao.fonte_codigo,
  decisao.identificador_fonte,
  decisao.tribunal_sigla,
  decisao.processo,
  decisao.orgao_julgador,
  decisao.relator,
  decisao.data_referencia,
  decisao.turma_recursal,
  decisao.url_fonte,
  decisao.link_valido,
  decisao.deliberacao,
  {shared} AS url_compartilhada,
  p.semelhanca,
  p.termos,
  p.casou_em
FROM proximas AS p
-- Aliased `decisao` because `SHARED_JOIN` names that alias: the join is
-- written once in `decisions.py` and read here, so a search result and a
-- suggestion warn about a shared link by the same rule. Calling it `d` here
-- made the query fail with "missing FROM-clause entry for table decisao".
JOIN core.decisao AS decisao
  ON decisao.fonte_codigo = p.fonte_codigo
 AND decisao.identificador_fonte = p.identificador_fonte{shared_join}
-- Ordering closes on the unique key: without it PostgreSQL may return ties in
-- any order, and the same decision can show up twice across two reads.
ORDER BY p.semelhanca DESC, decisao.fonte_codigo, decisao.identificador_fonte
LIMIT %(limit)s
"""


def _sql(shared_published: bool) -> str:
    """
    The query, with the shared-link join only where that table is published.

    `_base_fields` reads `url_compartilhada` to decide whether to warn that a
    link opens a list of decisions rather than one. Leaving it out would not
    fail — it would quietly read as False, and the reader of a suggestion
    would get no warning where the reader of a search result does.
    """
    column, join = _shared(shared_published)
    return RELATED_SQL.format(
        floor=RARITY_FLOOR,
        search_terms=SEARCH_TERMS,
        minimum=MINIMUM_TERMS,
        shared=column,
        shared_join=join,
    )


NEIGHBOUR_EXAMPLE: dict[str, Any] = {
    "source": "stj-espelhos",
    "identifier": "000525506",
    "court": "STJ",
    "case_number": None,
    "judging_body": "SEGUNDA SEÇÃO",
    "reporting_judge": "SIDNEI BENETI",
    "decided_on": "2026-02-10",
    "small_claims": False,
    "source_url": "https://scon.stj.jus.br/SCON/pesquisar.jsp?num_registro=000525506",
    "source_url_reachable": True,
    "source_url_shared": False,
    "deliberation": "unanime",
    "similarity": 0.3841,
    "terms": 31,
    "matched_on": ["poluidor-pag", "poluidor", "pescador", "artesanal"],
}


class Neighbour(DecisionBase):
    """A decision found to treat the same subject, and the evidence for it."""

    similarity: float = Field(
        description=(
            "How close the two ementas are, from 0 to 1: the cosine between "
            "them, with every word weighed by how rare it is in judicial "
            "language. It orders the list. It does not measure whether the two "
            "decisions agree — two decisions on one subject can settle it in "
            "opposite directions and still score high."
        ),
        examples=[0.3841],
    )
    terms: int = Field(
        description="How many distinct word stems the two ementas share.",
        examples=[31],
    )
    matched_on: list[str] = Field(
        description=(
            "The rarest shared stems, strongest first, so a reader can judge "
            "the suggestion without opening it. Stems, not words: "
            "`poluidor-pag` is *poluidor-pagador*."
        ),
        examples=[["poluidor-pag", "pescador"]],
    )

    model_config = ConfigDict(json_schema_extra={"example": NEIGHBOUR_EXAMPLE})


class RelatedDecisions(BaseModel):
    results: list[Neighbour] = Field(
        default_factory=list,
        description=(
            "Ordered by similarity, closest first. Empty is a normal answer: "
            "1,7% of the collection carries no term rare enough to search on, "
            "and a decision can simply have nothing like it."
        ),
    )
    method: str = Field(
        description=(
            "How the relation was arrived at, which `RF20` requires to be "
            "stated. Always calculated similarity here — never an official "
            "link between the two decisions, which this endpoint does not know."
        ),
        examples=["similaridade calculada"],
    )


# `RF20` asks for the method to be stated and for a calculated relation to be
# told apart from an official one. This is the sentence that does it.
METHOD = "similaridade calculada"

MATCHED_ON_SHOWN = 6


@router.get(
    "/decisions/{source}/{identifier}/related",
    summary="Decisions on the same subject as this one",
    responses={
        **DATABASE_RESPONSES,
        **NOT_FOUND_RESPONSE,
        200: two_examples(
            (
                "found",
                "The ementa carries rare terms other decisions also carry.",
                {
                    "results": [NEIGHBOUR_EXAMPLE],
                    "method": "similaridade calculada",
                },
            ),
            (
                "nothing close",
                (
                    "No term rare enough to search on, or nothing sharing two "
                    "of them. A normal answer, never an error."
                ),
                {"results": [], "method": "similaridade calculada"},
            ),
        ),
    },
)
def related_decisions(
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
    source: Annotated[str, Path(description="Collection code.")],
    identifier: Annotated[str, Path(description="Identifier within the collection.")],
    limit: Annotated[
        int, Query(ge=1, le=20, description="How many decisions at most.")
    ] = 5,
) -> RelatedDecisions:
    """
    Other decisions whose ementa treats the same subject, closest first.

    Each one carries the stems that matched, so the reader can judge the
    suggestion before opening it. Proximity is not agreement: a decision listed
    here may well have decided the other way.

    A decision with nothing close answers an empty list, not an error. Only an
    identifier absent from the collection answers 404.
    """
    # A NUL byte cannot be sent to PostgreSQL as text, and both parts arrive
    # from the URL. Refusing it here is the difference between "no such
    # decision" and a stack trace.
    if "\x00" in source or "\x00" in identifier:
        raise HTTPException(status_code=404, detail="Decision not found.")

    parameters = {"source": source, "identifier": identifier}

    with connection.cursor() as cursor:
        cursor.execute(DECISION_EXISTS_SQL, parameters)
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Decision not found.")

        cursor.execute(WEIGHTS_SQL)
        weights = cursor.fetchone() or {}
        if not (weights.get("vocabulario") and weights.get("normas")):
            # An environment whose base predates the weights. Answering an
            # empty list keeps the screen whole; answering 500 would take the
            # decision down with it.
            return RelatedDecisions(results=[], method=METHOD)

        cursor.execute(_sql(_published(cursor).shared), {**parameters, "limit": limit})
        rows = cursor.fetchall()

    return RelatedDecisions(
        results=[
            Neighbour(
                **_base_fields(row),
                similarity=round(float(row["semelhanca"]), 4),
                terms=row["termos"],
                matched_on=row["casou_em"][:MATCHED_ON_SHOWN],
            )
            for row in rows
        ],
        method=METHOD,
    )
