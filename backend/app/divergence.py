"""RF22-v1: descriptive outcomes are never a legal finding of divergence."""

from datetime import date
from fractions import Fraction
from math import erfc, exp, fsum, sqrt
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

OUTCOMES = ("negado", "provido", "parcialmente_provido")
MIN_CLASSIFIED = 50
MIN_COVERAGE = 0.8
MIN_EXPECTED = 5
ALPHA = 0.05
MIN_EFFECT = 0.15


class ComparableGroup(BaseModel):
    """Deployment-owned approval, never supplied by a request."""

    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    court: str = Field(min_length=1)
    panels: list[str] = Field(min_length=2)
    classes: list[int] = Field(min_length=1)
    valid_from: date
    valid_to: date
    evidence_url: HttpUrl
    validated_by: str = Field(min_length=1)
    validated_on: date

    @model_validator(mode="after")
    def valid_scope(self) -> "ComparableGroup":
        if self.valid_from > self.valid_to:
            raise ValueError("Inverted competence interval")
        if any(not panel.strip() for panel in self.panels):
            raise ValueError("A panel must have an exact nonblank name")
        if len(set(self.panels)) != len(self.panels):
            raise ValueError("Duplicate panel names")
        if any(code <= 0 for code in self.classes):
            raise ValueError("Invalid CNJ class")
        if not self.validated_by.strip():
            raise ValueError("Approval must name its validator")
        return self


class GroupCatalogue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str = Field(min_length=1)
    groups: list[ComparableGroup]

    @model_validator(mode="after")
    def unique_ids(self) -> "GroupCatalogue":
        if len({group.id for group in self.groups}) != len(self.groups):
            raise ValueError("Duplicate competence-group identifiers")
        return self


def load_catalogue() -> GroupCatalogue:
    return GroupCatalogue.model_validate_json(
        Path(__file__).with_name("panel_groups.json").read_text(encoding="utf-8")
    )


class Counts(BaseModel):
    denied: int
    granted: int
    partially_granted: int

    def values(self) -> tuple[int, int, int]:
        return self.denied, self.granted, self.partially_granted

    def total(self) -> int:
        return sum(self.values())


class PanelNumbers(BaseModel):
    court: str
    class_code: int | None
    panel: str | None
    documents: int
    classified_documents: int
    unknown_documents: int
    outcomes: Counts
    processes: int
    missing_process_documents: int
    repeated_documents: int
    first: date | None
    last: date | None
    # A name is descriptive; it does not establish legal comparability.
    comparison_status: Literal[
        "pair_available", "no_peer", "missing_class", "missing_panel"
    ]


class Sample(BaseModel):
    panel: str
    processes: int
    classified: int
    unknown: int
    coverage: float | None
    outcomes: Counts
    shares: list[float | None]
    shared_processes_excluded: int
    missing_process_documents: int
    repeated_documents: int


Reason = Literal[
    "unvalidated_group",
    "ambiguous_group",
    "outcome_filter",
    "insufficient_sample",
    "insufficient_coverage",
    "no_variation",
    "sparse_categories",
    "not_significant",
    "small_effect",
    "difference",
]


class PanelPair(BaseModel):
    court: str
    class_code: int
    group_id: str | None = None
    left: Sample
    right: Sample
    reason: Reason
    signal: bool = False
    statistic: float | None = None
    degrees_of_freedom: int | None = None
    minimum_expected: float | None = None
    raw_p: float | None = None
    adjusted_p: float | None = None
    effect: float | None = None


def chi_square(
    left: tuple[int, int, int], right: tuple[int, int, int]
) -> tuple[float, int, float, float | None]:
    """Pearson, no Yates correction; retain pooled nonempty categories."""
    columns = [i for i in range(3) if left[i] + right[i] > 0]
    if len(columns) < 2:
        return 0.0, 0, 0.0, None
    sizes = (sum(left), sum(right))
    total = sum(sizes)
    if not all(sizes):
        raise ValueError("Both samples must be nonempty")
    expected = [
        [size * (left[j] + right[j]) / total for j in columns] for size in sizes
    ]
    minimum = min(min(row) for row in expected)
    if minimum < MIN_EXPECTED:
        return 0.0, len(columns) - 1, minimum, None
    statistic = fsum(
        (row[j] - expected[i][k]) ** 2 / expected[i][k]
        for i, row in enumerate((left, right))
        for k, j in enumerate(columns)
    )
    df = len(columns) - 1
    p = exp(-statistic / 2) if df == 2 else erfc(sqrt(statistic / 2))
    return statistic, df, minimum, p


def holm(p_values: list[float]) -> list[float]:
    adjusted = [0.0] * len(p_values)
    previous = 0.0
    for rank, index in enumerate(
        sorted(range(len(p_values)), key=p_values.__getitem__)
    ):
        previous = min(1.0, max(previous, (len(p_values) - rank) * p_values[index]))
        adjusted[index] = previous
    return adjusted


def evaluate(
    pair: PanelPair,
    groups: list[ComparableGroup],
    first: date,
    last: date,
    outcome_filtered: bool,
) -> None:
    matches = [
        group
        for group in groups
        if group.court == pair.court
        and pair.class_code in group.classes
        and pair.left.panel in group.panels
        and pair.right.panel in group.panels
        and group.valid_from <= first
        and last <= group.valid_to
    ]
    if not matches:
        pair.reason = "unvalidated_group"
        return
    if len(matches) != 1:
        pair.reason = "ambiguous_group"
        return
    pair.group_id = matches[0].id
    if outcome_filtered:
        pair.reason = "outcome_filter"
        return
    if min(pair.left.classified, pair.right.classified) < MIN_CLASSIFIED:
        pair.reason = "insufficient_sample"
        return
    if any(
        sample.coverage is None or sample.coverage < MIN_COVERAGE
        for sample in (pair.left, pair.right)
    ):
        pair.reason = "insufficient_coverage"
        return
    statistic, df, minimum, p = chi_square(
        pair.left.outcomes.values(), pair.right.outcomes.values()
    )
    pair.degrees_of_freedom = df
    if df == 0:
        pair.reason = "no_variation"
        return
    pair.minimum_expected = minimum
    if p is None:
        pair.reason = "sparse_categories"
        return
    pair.statistic, pair.raw_p = statistic, p
    pair.effect = float(
        max(
            abs(Fraction(a, pair.left.classified) - Fraction(b, pair.right.classified))
            for a, b in zip(pair.left.outcomes.values(), pair.right.outcomes.values())
        )
    )
    pair.reason = "not_significant"


def correct_family(pairs: list[PanelPair]) -> int:
    for pair in pairs:
        pair.signal = False
    tested = [pair for pair in pairs if pair.raw_p is not None]
    for pair, adjusted in zip(
        tested, holm([pair.raw_p for pair in tested if pair.raw_p is not None])
    ):
        pair.adjusted_p = adjusted
        if adjusted > ALPHA:
            pair.reason = "not_significant"
        elif pair.effect is not None and pair.effect < MIN_EFFECT:
            pair.reason = "small_effect"
        else:
            pair.reason, pair.signal = "difference", True
    return len(tested)
