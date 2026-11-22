"""One filtered snapshot: descriptive panels and independent-process pairs."""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg import Connection
from psycopg.rows import DictRow
from pydantic import BaseModel, ValidationError

from app import divergence as rule
from app.api.decisions import MATCH, SEARCH_RESPONSES, _narrowing
from app.db import get_connection

router = APIRouter(tags=["indicators"])

# Do not ship all matching decisions into Python. Window selection and pairwise
# overlap exclusions run in PostgreSQL; only panel and pair aggregates leave it.
# Both result types share one statement/snapshot and the search's own WHERE.
SQL = """
WITH filtered AS MATERIALIZED (
    SELECT d.tribunal_sigla AS court, d.classe_cnj AS class_code,
           d.orgao_julgador AS panel, d.resultado AS outcome,
           d.data_referencia AS decided_on, d.fonte_codigo, d.identificador_fonte,
           CASE WHEN d.processo ~ '[0-9]' AND d.processo ~ '[1-9]'
                THEN NULLIF(REGEXP_REPLACE(UPPER(d.processo), '[^A-Z0-9]', '', 'g'), '')
                ELSE NULL END AS process
    FROM core.decisao d WHERE {match}{filters}
),
panels AS (
    SELECT court, class_code, panel, COUNT(*) AS documents,
           COUNT(*) FILTER (WHERE process IS NULL) AS missing,
           COUNT(DISTINCT process) AS processes,
           COUNT(*) FILTER (WHERE outcome = 'negado') AS denied,
           COUNT(*) FILTER (WHERE outcome = 'provido') AS granted,
           COUNT(*) FILTER (WHERE outcome = 'parcialmente_provido') AS partial,
           MIN(decided_on) AS first, MAX(decided_on) AS last
    FROM filtered GROUP BY court, class_code, panel
),
representatives AS MATERIALIZED (
    SELECT DISTINCT ON (court, class_code, panel, process) *
    FROM filtered WHERE process IS NOT NULL
    ORDER BY court, class_code, panel, process, decided_on DESC,
             fonte_codigo DESC, identificador_fonte DESC
),
pairs AS (
    SELECT a.court, a.class_code, a.panel AS left_panel, b.panel AS right_panel
    FROM panels a JOIN panels b ON a.court = b.court
      AND a.class_code = b.class_code AND a.panel < b.panel
    WHERE NULLIF(BTRIM(a.panel), '') IS NOT NULL
      AND NULLIF(BTRIM(b.panel), '') IS NOT NULL
),
paired AS (
    SELECT p.*, r.panel, r.process, r.outcome,
           COUNT(*) OVER (PARTITION BY p.court, p.class_code,
                          p.left_panel, p.right_panel, r.process) > 1 AS shared
    FROM pairs p JOIN representatives r ON r.court = p.court
      AND r.class_code = p.class_code AND r.panel IN (p.left_panel, p.right_panel)
),
samples AS (
    SELECT court, class_code, left_panel, right_panel, panel,
           COUNT(*) FILTER (WHERE NOT shared) AS processes,
           COUNT(*) FILTER (WHERE shared) AS shared,
           COUNT(*) FILTER (WHERE NOT shared AND outcome = 'negado') AS denied,
           COUNT(*) FILTER (WHERE NOT shared AND outcome = 'provido') AS granted,
           COUNT(*) FILTER (WHERE NOT shared AND outcome = 'parcialmente_provido') AS partial
    FROM paired GROUP BY court, class_code, left_panel, right_panel, panel
)
SELECT 'panel' AS kind, court, class_code, panel, NULL::TEXT AS other,
       documents, missing, processes, 0::BIGINT AS shared,
       denied, granted, partial, first, last
FROM panels
UNION ALL
SELECT 'sample', p.court, p.class_code, side.panel,
       CASE WHEN side.panel = p.left_panel THEN p.right_panel ELSE p.left_panel END,
       0, 0, COALESCE(s.processes, 0), COALESCE(s.shared, 0),
       COALESCE(s.denied, 0), COALESCE(s.granted, 0), COALESCE(s.partial, 0),
       NULL::DATE, NULL::DATE
FROM pairs p CROSS JOIN LATERAL (VALUES (p.left_panel), (p.right_panel)) side(panel)
LEFT JOIN samples s ON s.court = p.court AND s.class_code = p.class_code
  AND s.left_panel = p.left_panel AND s.right_panel = p.right_panel AND s.panel = side.panel
ORDER BY court, class_code NULLS LAST, panel NULLS LAST, kind, other
"""


class Thresholds(BaseModel):
    minimum_classified_processes: int = rule.MIN_CLASSIFIED
    minimum_classification_coverage: float = rule.MIN_COVERAGE
    minimum_expected_cell: int = rule.MIN_EXPECTED
    alpha: float = rule.ALPHA
    minimum_effect: float = rule.MIN_EFFECT
    test: str = "pearson_chi_square_without_yates"
    correction: str = "holm"


class Divergence(BaseModel):
    rule_version: str = "RF22-v1"
    outcome_order: tuple[str, str, str] = rule.OUTCOMES
    catalogue_version: str
    validated_groups: list[rule.ComparableGroup]
    thresholds: Thresholds
    cut: dict[str, Any]
    publication_reference: str | None = None
    documents: int
    panels: list[rule.PanelNumbers]
    pairs: list[rule.PanelPair]
    tested_pairs: int
    interpretation: str = (
        "Diferença estatística não comprova divergência jurídica nem prevê o resultado "
        "de um processo. Os percentuais usam resultados classificados automaticamente; "
        "confira as decisões e a competência das turmas."
    )
    evidence_scope: str = (
        "As contagens de documentos preservam o recorte aplicado. A amostra de cada par "
        "usa um representante por processo, exclui processos sem identidade e processos "
        "compartilhados pelo par. O acesso aos representantes deve aplicar a mesma seleção."
    )


def counts(row: DictRow) -> rule.Counts:
    return rule.Counts(
        denied=row["denied"], granted=row["granted"], partially_granted=row["partial"]
    )


def aggregate(
    rows: list[DictRow],
    catalogue: rule.GroupCatalogue,
    cut: dict[str, Any],
    outcome_filtered: bool,
) -> Divergence:
    panels: dict[tuple[str, int | None, str | None], rule.PanelNumbers] = {}
    for row in rows:
        if row["kind"] != "panel":
            continue
        values = counts(row)
        panels[row["court"], row["class_code"], row["panel"]] = rule.PanelNumbers(
            court=row["court"],
            class_code=row["class_code"],
            panel=row["panel"],
            documents=row["documents"],
            classified_documents=values.total(),
            unknown_documents=row["documents"] - values.total(),
            outcomes=values,
            processes=row["processes"],
            missing_process_documents=row["missing"],
            repeated_documents=row["documents"] - row["missing"] - row["processes"],
            first=row["first"],
            last=row["last"],
            comparison_status="missing_panel"
            if not row["panel"]
            else "missing_class"
            if row["class_code"] is None
            else "no_peer",
        )
    samples: dict[tuple[str, int, str, str], list[rule.Sample]] = {}
    for row in rows:
        if row["kind"] != "sample":
            continue
        left, right = sorted((row["panel"], row["other"]))
        key = row["court"], row["class_code"], left, right
        panel = panels[row["court"], row["class_code"], row["panel"]]
        panel.comparison_status = "pair_available"
        values = counts(row)
        classified = values.total()
        samples.setdefault(key, []).append(
            rule.Sample(
                panel=row["panel"],
                processes=row["processes"],
                classified=classified,
                unknown=row["processes"] - classified,
                coverage=classified / row["processes"] if row["processes"] else None,
                outcomes=values,
                shares=[
                    n / classified if classified else None for n in values.values()
                ],
                shared_processes_excluded=row["shared"],
                missing_process_documents=panel.missing_process_documents,
                repeated_documents=panel.repeated_documents,
            )
        )
    pairs = []
    for (court, class_code, left, right), pair_samples in sorted(samples.items()):
        pair_samples.sort(key=lambda sample: sample.panel)
        pair = rule.PanelPair(
            court=court,
            class_code=class_code,
            left=pair_samples[0],
            right=pair_samples[1],
            reason="unvalidated_group",
        )
        dates = [panels[court, class_code, name] for name in (left, right)]
        starts = [panel.first for panel in dates if panel.first is not None]
        ends = [panel.last for panel in dates if panel.last is not None]
        if starts and ends:
            rule.evaluate(
                pair, catalogue.groups, min(starts), max(ends), outcome_filtered
            )
        pairs.append(pair)
    tested = rule.correct_family(pairs)
    return Divergence(
        catalogue_version=catalogue.version,
        validated_groups=catalogue.groups,
        thresholds=Thresholds(),
        cut=cut,
        documents=sum(p.documents for p in panels.values()),
        panels=list(panels.values()),
        pairs=pairs,
        tested_pairs=tested,
    )


@router.get(
    "/indicators/divergence",
    summary="Compare panel outcome distributions within a court and class",
    responses=SEARCH_RESPONSES,
)
def read_divergence(
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
    q: Annotated[
        str, Query(min_length=2, description="The applied thematic search expression.")
    ],
    tribunal: Annotated[list[str] | None, Query()] = None,
    orgao_julgador: Annotated[list[str] | None, Query()] = None,
    relator: Annotated[list[str] | None, Query()] = None,
    classe_cnj: Annotated[list[int] | None, Query()] = None,
    resultado: Annotated[list[str] | None, Query()] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    published_from: Annotated[date | None, Query()] = None,
    published_to: Annotated[date | None, Query()] = None,
    orgao_julgador_excluido: Annotated[list[str] | None, Query()] = None,
    relator_excluido: Annotated[list[str] | None, Query()] = None,
) -> Divergence:
    filters, parameters = _narrowing(
        q,
        tribunal,
        date_from,
        date_to,
        published_from,
        published_to,
        orgao_julgador,
        relator,
        classe_cnj,
        resultado,
        orgao_julgador_excluido,
        relator_excluido,
    )
    try:
        catalogue = rule.load_catalogue()
    except (OSError, ValidationError) as failure:
        raise HTTPException(
            503, "O catálogo de competências está indisponível."
        ) from failure
    cut = {
        "q": q,
        "tribunal": tribunal,
        "orgao_julgador": orgao_julgador,
        "relator": relator,
        "classe_cnj": classe_cnj,
        "resultado": resultado,
        "date_from": date_from,
        "date_to": date_to,
        "published_from": published_from,
        "published_to": published_to,
        "orgao_julgador_excluido": orgao_julgador_excluido,
        "relator_excluido": relator_excluido,
    }
    with connection.cursor() as cursor:
        cursor.execute(SQL.format(match=MATCH, filters=filters), parameters)
        rows = cursor.fetchall()
    return aggregate(
        rows,
        catalogue,
        {key: value for key, value in cut.items() if value is not None},
        bool(parameters.get("resultado")),
    )
