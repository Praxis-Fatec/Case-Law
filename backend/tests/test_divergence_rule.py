"""RF22-v1 arithmetic and gates, independent of the HTTP/database layer."""

from datetime import date

import pytest
from pydantic import HttpUrl, ValidationError

from app.divergence import (
    ComparableGroup,
    Counts,
    PanelPair,
    Sample,
    chi_square,
    correct_family,
    evaluate,
    holm,
)


def group() -> ComparableGroup:
    return ComparableGroup(
        id="fixture-only",
        court="STJ",
        panels=["A", "B", "C"],
        classes=[198],
        valid_from=date(2020, 1, 1),
        valid_to=date(2030, 12, 31),
        evidence_url=HttpUrl("https://example.test/fixture"),
        validated_by="Test fixture, not legal approval",
        validated_on=date(2026, 1, 1),
    )


def sample(panel: str, values: tuple[int, int, int], unknown: int = 0) -> Sample:
    classified = sum(values)
    total = classified + unknown
    return Sample(
        panel=panel,
        processes=total,
        classified=classified,
        unknown=unknown,
        coverage=classified / total if total else None,
        outcomes=Counts(
            denied=values[0], granted=values[1], partially_granted=values[2]
        ),
        shares=[n / classified if classified else None for n in values],
        shared_processes_excluded=0,
        missing_process_documents=0,
        repeated_documents=0,
    )


def pair(
    a: tuple[int, int, int], b: tuple[int, int, int], unknown: int = 0
) -> PanelPair:
    return PanelPair(
        court="STJ",
        class_code=198,
        left=sample("A", a, unknown),
        right=sample("B", b, unknown),
        reason="unvalidated_group",
    )


def run(
    item: PanelPair,
    groups: list[ComparableGroup] | None = None,
    outcome_filtered: bool = False,
) -> PanelPair:
    evaluate(
        item,
        [group()] if groups is None else groups,
        date(2026, 1, 1),
        date(2026, 12, 31),
        outcome_filtered,
    )
    correct_family([item])
    return item


@pytest.mark.parametrize(
    "a,b,reason",
    [
        ((80, 10, 10), (20, 10, 70), "difference"),
        ((60, 20, 20), (55, 25, 20), "not_significant"),
        ((4, 0, 1), (1, 0, 4), "insufficient_sample"),
        ((30, 10, 10), (20, 10, 20), "not_significant"),
        ((49, 1, 0), (50, 0, 0), "sparse_categories"),
        ((50, 0, 0), (50, 0, 0), "no_variation"),
        ((6000, 2000, 2000), (5500, 2500, 2000), "small_effect"),
    ],
)
def test_documented_examples(
    a: tuple[int, int, int], b: tuple[int, int, int], reason: str
) -> None:
    item = run(pair(a, b))
    assert item.reason == reason
    assert item.signal == (reason == "difference")
    if reason in {"insufficient_sample", "sparse_categories", "no_variation"}:
        assert item.raw_p is None and item.adjusted_p is None


def test_numerical_reference_and_two_degrees_of_freedom() -> None:
    statistic, df, minimum, p = chi_square((80, 10, 10), (20, 10, 70))
    assert statistic == 81 and df == 2 and minimum == 10
    assert p == pytest.approx(2.576757109154981e-18)


def test_empty_category_is_removed_and_observed_zero_is_allowed() -> None:
    statistic, df, minimum, p = chi_square((50, 0, 0), (0, 50, 0))
    assert statistic == 100 and df == 1 and minimum == 25
    assert p == pytest.approx(1.523970604832105e-23)
    assert run(pair((50, 0, 0), (0, 50, 0))).signal


def test_no_group_or_overlapping_approvals_cannot_signal() -> None:
    assert (
        run(pair((80, 10, 10), (20, 10, 70)), groups=[]).reason == "unvalidated_group"
    )
    assert (
        run(pair((80, 10, 10), (20, 10, 70)), groups=[group(), group()]).reason
        == "ambiguous_group"
    )


def test_wrong_court_class_or_historical_interval_cannot_signal() -> None:
    for field, value in (("court", "TJDFT"), ("class_code", 213)):
        item = pair((80, 10, 10), (20, 10, 70))
        setattr(item, field, value)
        assert run(item).reason == "unvalidated_group"
    item = pair((80, 10, 10), (20, 10, 70))
    evaluate(item, [group()], date(1989, 1, 1), date(2026, 1, 1), False)
    assert item.reason == "unvalidated_group"


@pytest.mark.parametrize(
    "unknown,reason",
    [(12, "difference"), (13, "insufficient_coverage"), (20, "insufficient_coverage")],
)
def test_coverage_gate(unknown: int, reason: str) -> None:
    assert run(pair((40, 5, 5), (5, 5, 40), unknown)).reason == reason


def test_sample_floor_49_versus_50() -> None:
    assert run(pair((49, 0, 0), (0, 50, 0))).reason == "insufficient_sample"
    assert run(pair((50, 0, 0), (0, 50, 0))).signal


def test_outcome_filter_blocks_inference() -> None:
    item = run(pair((80, 10, 10), (20, 10, 70)), outcome_filtered=True)
    assert item.reason == "outcome_filter" and item.raw_p is None


def test_holm_corrects_the_whole_family_without_sorting_the_output() -> None:
    assert holm([0.04, 0.001, 0.06]) == pytest.approx([0.08, 0.003, 0.08])
    assert holm([]) == []
    assert holm([0.03]) == [0.03]


def test_effect_does_not_remove_a_test_from_the_family_and_rounding_does_not_pass() -> (
    None
):
    items = [pair((80, 10, 10), (20, 10, 70)) for _ in range(3)]
    for item, p, effect in zip(items, [0.001, 0.04, 0.06], [0.01, 0.2, 0.2]):
        item.raw_p, item.effect = p, effect
    assert correct_family(items) == 3
    assert [item.reason for item in items] == [
        "small_effect",
        "not_significant",
        "not_significant",
    ]
    item = items[0]
    item.raw_p, item.effect, item.signal = 0.05004, 0.5, False
    correct_family([item])
    assert not item.signal


def test_effect_boundary_and_alpha_boundary_are_inclusive() -> None:
    for effect, expected in ((0.15, True), (0.149999, False)):
        item = pair((80, 10, 10), (20, 10, 70))
        item.raw_p, item.effect = 0.05, effect
        correct_family([item])
        assert item.signal == expected


@pytest.mark.parametrize(
    "missing",
    [
        "evidence_url",
        "validated_by",
        "validated_on",
        "classes",
        "valid_from",
        "valid_to",
    ],
)
def test_catalogue_requires_explicit_approval_and_its_scope(missing: str) -> None:
    values = group().model_dump()
    del values[missing]
    with pytest.raises(ValidationError):
        ComparableGroup.model_validate(values)


def test_computed_effect_at_fifteen_points_does_not_fail_from_float_subtraction() -> (
    None
):
    item = run(pair((500, 250, 250), (350, 400, 250)))
    assert item.effect == 0.15
    assert item.signal
