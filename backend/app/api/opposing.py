"""
The decisions that may contradict the one being read — `RF23`.

Contrary is not opposite outcome. `opposing-decisions.md` measured it: over
14.546 similar pairs, decisions on the same subject disagree on the outcome
11,9% of the time against 25,7% expected by chance, so similar decisions
disagree *less* than random ones. An endpoint built on opposite outcomes would
answer about six contradictions per decision, nearly all of them pairs that
agree on the law and differ on which party appealed — the collection does not
record who appealed, and `conhecimento` is NULL for all 991.163 decisions, so
neither can be corrected for.

What is answered instead is a disagreement the court itself wrote down: two
decisions citing the same precedent, one following it and the other departing
from it or distinguishing it. The precedent travels in the answer, because the
reason is the point — a list of "contrary decisions" that does not say where
they diverge is noise with the face of analysis.

The opposite outcome still travels, as context beside each entry and never as
the reason an entry exists.

Nineteen decisions in twenty have no known contrary — 50.925 of the 991.163
carry one — so an empty list is the ordinary answer. It is not the same as not knowing: where the table is not published
this answers 503 rather than an empty list, because telling a lawyer there is
no contradiction when nobody looked is worse than telling them the screen is
unavailable.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from psycopg import Connection
from psycopg.rows import DictRow
from pydantic import BaseModel, ConfigDict, Field

from app.api.decisions import DecisionBase, _base_fields, _published, _shared
from app.db import get_connection
from app.errors import DATABASE_RESPONSES, NOT_FOUND_RESPONSE, two_examples

router = APIRouter(tags=["opposing"])

DECISION_EXISTS_SQL = """
SELECT 1
FROM core.decisao
WHERE fonte_codigo = %(source)s AND identificador_fonte = %(identifier)s
"""

# One row per disputed precedent, so a pair that disagrees over three
# precedents is three rows. The reader wants one entry per decision carrying
# all three reasons, which is what the aggregate does.
OPPOSING_SQL = """
WITH contraria AS (
  SELECT
    contraria_fonte,
    contraria_identificador,
    MAX(semelhanca)   AS semelhanca,
    MAX(termos_comuns) AS termos,
    BOOL_OR(resultado_oposto) AS resultado_oposto,
    JSON_AGG(
      JSON_BUILD_OBJECT(
        'corte', corte,
        'tipo', tipo,
        'numero', numero,
        'aderencia', aderencia,
        'contraria_aderencia', contraria_aderencia
      )
      ORDER BY corte, tipo, numero
    ) AS motivos
  FROM core.decisao_contraria
  WHERE fonte_codigo = %(source)s AND identificador_fonte = %(identifier)s
  GROUP BY contraria_fonte, contraria_identificador
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
  c.semelhanca,
  c.termos,
  c.resultado_oposto,
  c.motivos
FROM contraria AS c
JOIN core.decisao AS decisao
  ON decisao.fonte_codigo = c.contraria_fonte
 AND decisao.identificador_fonte = c.contraria_identificador{shared_join}
-- Closing on the unique key: without it PostgreSQL may return ties in any
-- order, and the same decision can appear twice across two reads.
ORDER BY c.semelhanca DESC, decisao.fonte_codigo, decisao.identificador_fonte
LIMIT %(limit)s
"""


def _sql(shared_published: bool) -> str:
    column, join = _shared(shared_published)
    return OPPOSING_SQL.format(shared=column, shared_join=join)


DISAGREEMENT_EXAMPLE: dict[str, Any] = {
    "court": "STJ",
    "kind": "sumula",
    "number": 85,
    "this_decision": "seguiu",
    "other_decision": "afastou",
}

OPPOSING_EXAMPLE: dict[str, Any] = {
    "source": "stj-espelhos",
    "identifier": "000226794",
    "court": "STJ",
    "case_number": "425432",
    "judging_body": "PRIMEIRA TURMA",
    "reporting_judge": "JOSE DELGADO",
    "decided_on": "2002-06-17",
    "small_claims": False,
    "source_url": "https://scon.stj.jus.br/SCON/pesquisar.jsp?num_registro=000226794",
    "source_url_reachable": True,
    "source_url_shared": False,
    "deliberation": "unanime",
    "similarity": 0.4612,
    "terms": 9,
    "opposite_outcome": True,
    "disagreements": [DISAGREEMENT_EXAMPLE],
}


class Disagreement(BaseModel):
    """One precedent the two decisions treated in opposite ways."""

    court: str = Field(
        description="Which court issued the precedent.", examples=["STJ"]
    )
    kind: str = Field(
        description="What kind of precedent it is, as the collection stores it.",
        examples=["sumula"],
    )
    number: int = Field(description="The precedent's number.", examples=[85])
    this_decision: str = Field(
        description=(
            "What the decision being read did with this precedent: `seguiu`, "
            "`afastou` or `distinguiu`."
        ),
        examples=["seguiu"],
    )
    other_decision: str = Field(
        description="What the other decision did with the same precedent.",
        examples=["afastou"],
    )


class Opposing(DecisionBase):
    """A decision that may contradict this one, and why."""

    similarity: float = Field(
        description=(
            "How close the two ementas are, from 0 to 1, by the same cosine "
            "`RF20` uses. It orders the list and is not itself a reason: a "
            "close pair that treats no precedent in opposite ways is not here."
        ),
        examples=[0.4612],
    )
    terms: int = Field(
        description="How many rare word stems the two ementas share.",
        examples=[9],
    )
    opposite_outcome: bool = Field(
        description=(
            "Whether one appeal was granted and the other denied. Context, "
            "never the reason: measured over the collection, similar decisions "
            "differ on the outcome less often than random pairs do, and the "
            "collection does not record which party appealed."
        ),
        examples=[True],
    )
    disagreements: list[Disagreement] = Field(
        default_factory=list,
        description=(
            "The precedents the two treated in opposite ways — the reason this "
            "entry exists. Never empty: an entry without one is not produced."
        ),
    )

    model_config = ConfigDict(json_schema_extra={"example": OPPOSING_EXAMPLE})


class OpposingDecisions(BaseModel):
    results: list[Opposing] = Field(
        default_factory=list,
        description=(
            "Ordered by similarity, closest first. Empty for nineteen "
            "decisions in twenty, which is the ordinary answer and never an "
            "error."
        ),
    )
    basis: str = Field(
        description=(
            "Where the indication comes from, which `RF23` requires to be told "
            "apart from a settled legal conclusion. Always this tool's reading "
            "of two decisions — never a statement by the court that they "
            "conflict."
        ),
        examples=["leitura desta ferramenta"],
    )


# `RF23` asks the indication to be distinguished from a definitive legal
# conclusion. This is the sentence that does it, and the screen shows it above
# the list rather than beside it.
BASIS = "leitura desta ferramenta"


@router.get(
    "/decisions/{source}/{identifier}/opposing",
    summary="Decisions that may contradict this one",
    responses={
        **DATABASE_RESPONSES,
        **NOT_FOUND_RESPONSE,
        200: two_examples(
            (
                "found",
                (
                    "Both decisions cite the same precedent and treat it in "
                    "opposite ways."
                ),
                {
                    "results": [OPPOSING_EXAMPLE],
                    "basis": "leitura desta ferramenta",
                },
            ),
            (
                "none known",
                (
                    "Five decisions in six answer this way. It is the ordinary "
                    "case, never a failure."
                ),
                {"results": [], "basis": "leitura desta ferramenta"},
            ),
        ),
    },
)
def opposing_decisions(
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
    source: Annotated[str, Path(description="Collection code.")],
    identifier: Annotated[str, Path(description="Identifier within the collection.")],
    limit: Annotated[
        int, Query(ge=1, le=20, description="How many decisions at most.")
    ] = 5,
) -> OpposingDecisions:
    """
    Decisions that treat the same subject and took the opposite view of a
    precedent both of them cite.

    Each entry names the precedent and what each decision did with it, so the
    reader can judge the indication before opening anything. The indication is
    this tool's reading, not a finding by the court.

    A decision with no known contrary answers an empty list, which is the
    common case. Only an identifier absent from the collection answers 404.
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

        # No probe for `core.decisao_contraria`. Where it is absent the query
        # raises and the handler answers 503: on this screen an empty list
        # reads as "no contradiction", and saying that when nobody looked is
        # the one wrong answer `RF23` cannot afford.
        cursor.execute(_sql(_published(cursor).shared), {**parameters, "limit": limit})
        rows = cursor.fetchall()

    return OpposingDecisions(
        results=[
            Opposing(
                **_base_fields(row),
                similarity=round(float(row["semelhanca"]), 4),
                terms=row["termos"],
                opposite_outcome=bool(row["resultado_oposto"]),
                disagreements=[
                    Disagreement(
                        court=motivo["corte"],
                        kind=motivo["tipo"],
                        number=motivo["numero"],
                        this_decision=motivo["aderencia"],
                        other_decision=motivo["contraria_aderencia"],
                    )
                    for motivo in row["motivos"]
                ],
            )
            for row in rows
        ],
        basis=BASIS,
    )
