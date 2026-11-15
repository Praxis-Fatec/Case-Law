"""
The legislation a decision applied.

The court writes each reference in a fixed layout its own system builds, so
what this endpoint answers is parsed, not inferred: act type, number, year,
article, and the paragraphs, items and letters inside it. Nothing here is a
suggestion — a reference is in the answer because the decision carried it.

Three things it refuses to do. It does not translate the sphere: `FED`, `EST`
and `DIS` have readings and `MUN`, `INT` and `IES` do not, and answering a
municipal statute as a state one is worse than answering a code. It does not
invent a name for an act code it cannot verify. And it does not drop what the
parser failed to read: 0,61% of the collection's references reach the reader as
the court's own text, marked, rather than disappearing.

A decision with no catalogued reference answers an empty list. Two thirds of the
STJ collection carry at least one and the TJDFT collection carries none at all,
so "none" is an ordinary answer and never an error.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path
from psycopg import Connection
from psycopg.rows import DictRow
from pydantic import BaseModel, Field

from app.db import get_connection
from app.errors import DATABASE_RESPONSES, NOT_FOUND_RESPONSE, two_examples

router = APIRouter(tags=["legislation"])

DECISION_EXISTS_SQL = """
SELECT 1
FROM core.decisao
WHERE fonte_codigo = %(source)s
  AND identificador_fonte = %(identifier)s
"""

# The court's own order: `ordem` is the position of the reference in the list it
# published, and `sequencia` the article inside it. Ordering on anything else
# would rearrange a list the court wrote.
LEGISLATION_SQL = """
SELECT
    esfera,
    tipo_ato,
    numero,
    ano,
    artigo,
    paragrafos,
    incisos,
    letras,
    reconhecida,
    texto_bruto
FROM core.referencia_legislativa
WHERE fonte_codigo = %(source)s AND identificador_fonte = %(identifier)s
ORDER BY ordem, sequencia
"""

REFERENCE_EXAMPLE: dict[str, Any] = {
    "sphere": "FED",
    "act_type": "DEL",
    "number": 3365,
    "year": 1941,
    "article": "26",
    "paragraphs": ["2"],
    "items": [],
    "letters": [],
    "recognised": True,
    "raw": "LEG:FED DEL:003365 ANO:1941 ART:00026 PAR:00002",
}

UNRECOGNISED_EXAMPLE: dict[str, Any] = {
    "sphere": "FED",
    "act_type": None,
    "number": None,
    "year": None,
    "article": None,
    "paragraphs": [],
    "items": [],
    "letters": [],
    "recognised": False,
    "raw": ("LEG:FED ***** SUM(STF) SUMULA DO SUPREMO TRIBUNAL FEDERAL SUM:000282"),
}


class CitedLegislation(BaseModel):
    sphere: str | None = Field(
        description=(
            "Which legislator, as the court's own three-letter code: `FED`, "
            "`EST`, `DIS`, and also `MUN`, `INT` and `IES`, which are 0,426% "
            "of the collection. Never translated here — a reading that folded "
            "the last three into one of the first three would answer a "
            "municipal statute as a state one. `null` on the 0,02% whose "
            "header carries no sphere at all."
        ),
        examples=["FED"],
    )
    act_type: str | None = Field(
        description=(
            "Which kind of act, as the court's three-letter code — `LEI`, "
            "`DEL`, `LCP`, `CFB`, `SUM` and 101 others. `null` means the "
            "header carried none, which is 0,69% of the collection: STF "
            "súmulas and the ADCT, above all. Expanding the code into words is "
            "the screen's job, and only for the codes whose meaning is settled."
        ),
        examples=["DEL"],
    )
    number: int | None = Field(
        description=(
            "The act's number. `null` where the court wrote `******`, which is "
            "how it writes an act identified by name — the Constitution, a "
            "súmula — and is 30,29% of the references. Not an absent field: an "
            "absent number."
        ),
        examples=[3365],
    )
    year: int | None = Field(
        description=(
            "The act's year, as the court wrote it, including when the court "
            "wrote it wrong: the field runs from 1002 to 8906 in the "
            "collection. `null` where it wrote `****`, 23,40% of the time."
        ),
        examples=[1941],
    )
    article: str | None = Field(
        description=(
            "One article per entry, so a reference naming six articles comes "
            "back as six entries. Text, not a number, because `543-B` is an "
            "article and 5.434 is not: 24.222 tokens carry the lettered form. "
            "`null` when the decision cited the act without pointing inside it, "
            "which is 36,68% of the references."
        ),
        examples=["26"],
    )
    paragraphs: list[str] = Field(
        default_factory=list,
        description=(
            "The paragraphs of this article, in the order the court wrote them. "
            "`único` is a value like any other. A list because 2,16% of the "
            "entries name more than one, and showing one of two narrows the "
            "citation while looking complete."
        ),
        examples=[["2"]],
    )
    items: list[str] = Field(
        default_factory=list,
        description=(
            "The items — `incisos` — of this article, as the arabic numbers the "
            "source carries. Brazilian practice reads them in roman numerals, "
            "which is a rendering and belongs to the screen."
        ),
        examples=[["3"]],
    )
    letters: list[str] = Field(
        default_factory=list,
        description="The letters — `alíneas` — of this article.",
        examples=[["A"]],
    )
    recognised: bool = Field(
        description=(
            "Whether the fixed-format parser read a sphere and an act type out "
            "of the header. False for 0,61% of the collection, and those "
            "entries still answer: the decision cited something, and `raw` is "
            "what it cited. A reference dropped for being unreadable would be a "
            "decision that looks like it applied less law than it did."
        )
    )
    raw: str | None = Field(
        description=(
            "The court's own text for the whole reference, whitespace "
            "collapsed. Always present, because it is the only thing a reader "
            "can check an unrecognised entry against, and because the article "
            "split does not carry the name block or the issuing body. `null` "
            "for the 12 references the source publishes empty."
        ),
        examples=["LEG:FED DEL:003365 ANO:1941 ART:00026 PAR:00002"],
    )


class CitedLegislationList(BaseModel):
    results: list[CitedLegislation] = Field(
        default_factory=list,
        description=(
            "The references this decision carried, in the court's own order. "
            "Empty for a decision with none catalogued — which is every TJDFT "
            "decision and a third of the STJ's — and that is an answer, not an "
            "error."
        ),
    )


@router.get(
    "/decisions/{source}/{identifier}/legislation",
    summary="Laws and articles this decision applied",
    responses={
        **DATABASE_RESPONSES,
        **NOT_FOUND_RESPONSE,
        200: two_examples(
            (
                "parsed",
                "The court's fixed format, read into fields.",
                {"results": [REFERENCE_EXAMPLE, UNRECOGNISED_EXAMPLE]},
            ),
            (
                "nothing catalogued",
                (
                    "A third of the STJ collection and all of the TJDFT's "
                    "answer this way. It is the normal case, never a failure."
                ),
                {"results": []},
            ),
        ),
    },
)
def cited_legislation(
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
    source: Annotated[str, Path(description="Collection code.")],
    identifier: Annotated[str, Path(description="Identifier within the collection.")],
) -> CitedLegislationList:
    """
    The laws, articles and paragraphs this decision applied.

    Parsed from the fixed layout the court publishes, one entry per article, in
    the order the court listed them. The sphere and the act type come back as
    the court's own codes; what the parser could not read comes back raw and
    marked, never dropped.

    A decision that cites no legislation answers an empty list. Only an
    identifier that is not in the collection answers 404.
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

        cursor.execute(LEGISLATION_SQL, parameters)
        rows = cursor.fetchall()

    return CitedLegislationList(
        results=[
            CitedLegislation(
                sphere=row["esfera"],
                act_type=row["tipo_ato"],
                number=row["numero"],
                year=row["ano"],
                article=row["artigo"],
                paragraphs=row["paragrafos"] or [],
                items=row["incisos"] or [],
                letters=row["letras"] or [],
                recognised=row["reconhecida"],
                raw=row["texto_bruto"],
            )
            for row in rows
        ]
    )
