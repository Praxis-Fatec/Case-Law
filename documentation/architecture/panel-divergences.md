# Statistical differences between panels of the same court

**Traceability:** SCRUM-204 / **SCRUM-281**, [RF22](../requirements.md#rf22),
with document access through [RF12](../requirements.md#rf12).

This records the rule to implement before the Panorama flags a difference.
It defines a statistical comparison of appeal outcomes, not a determination
that panels disagree on the law. The existing
[study of contrary decisions](opposing-decisions.md) explains why opposing
outcomes alone do not establish opposing legal understandings.

The thresholds below are explicit initial product choices. The mathematical
examples are synthetic checks, not measurements of the published collection,
empirical calibration, or evidence of approval by a legal specialist. The
endpoint and rule tests are implemented by SCRUM-282 as described below;
the Panorama panel is implemented by SCRUM-283. The document-opening flow
belongs to subsequent tasks.

## The comparison unit and its scope

Compare panels only inside the **same court, validated competence group and
exact CNJ procedural class**, over the same applied expression and filters.
Never pool different courts, competence groups or classes to meet a minimum.
Group membership must be recorded with its source and validation before a
pair is eligible. A shared word such as "Turma" in a name is insufficient.
This subtask does not approve a court's group catalogue.

For example, the STJ's official description places its First and Second
Panels in public law, Third and Fourth in private law, and Fifth and Sixth
in criminal law. This is a source for validating three separate groups; it
does not permit comparing all six indiscriminately. The catalogue must also
account for changes of competence over the selected period. An unvalidated
court, body or historical interval remains descriptive, without a signal.
[STJ: composition and areas of competence](https://www.stj.jus.br/sites/portalp/Institucional/Composicao).

`classe_cnj` is a procedural comparability control, not a guarantee of the
same underlying dispute or merits. A class that mixes incompatible procedural
situations must be split using available, validated metadata or withheld
from inference. Do not infer admissibility or collegiate judgment from
`tipo_texto`: its current value, `ementa_completa`, does not establish either.

The observation used by the test is **one process**, rather than every
document written in it. Several appeals or rulings in one process can be
dependent; counting them as independent would inflate the sample.

Within each fixed scope:

1. Use `(tribunal_sigla, processo)` as the process key, ignoring case-number
   formatting separators. An absent or unresolvable number cannot become an
   independent observation and is excluded from the inferential sample.
2. If the same process occurs in both panels of a proposed pair, exclude it
   from both inferential samples. Retain its documents in descriptive counts.
3. For a process confined to one panel, take its most recent decision in the
   scope, by `data_referencia DESC`, then `fonte_codigo DESC` and
   `identificador_fonte DESC`. Pick before inspecting its outcome; never
   prefer a classified or favourable decision over a later unknown one.
4. Run eligibility and the test on those representatives. Report how many
   documents and processes were excluded and why. A process number that
   identifies different underlying cases must be resolved or excluded.

This reduces known duplication; it does not establish random assignment or
independence between distinct, related proceedings. Repetitive litigation,
case mix, selection by search terms and changes over time remain limitations.
The signal is exploratory and cannot be described as a causal effect of
distribution to a panel or as a prediction for an individual case.

## Outcomes and denominators

Keep the three outcomes already used by the API:

| Stored value | Display meaning |
|---|---|
| `negado` | Denied |
| `provido` | Granted in full |
| `parcialmente_provido` | Partially granted |

For each panel in a pair, `T` is the number of eligible process
representatives **including unknown outcomes**. `C` is the number among them
whose outcome is one of those three values. Null, blank and unrecognised
outcomes contribute to `T - C`; they are never converted to denied outcomes.

Each category's inferential share is `count / C`, and classification coverage
is `C / T`. The test uses category counts, never rounded percentages. Partial
grant is a category of its own, not merged with full grant or denial. If
`C = 0` or `T = 0`, the corresponding percentage is unavailable, not zero.

The screen must distinguish document counts, representative-process counts,
classified processes and unknown processes. Both panels have their own
denominators. Counts shown for a statistical pair must come from that pair's
scope and exclusions; they cannot be reused unchanged for another pair.

An applied outcome filter makes the distribution conditional on the very
variable being tested. Preserve it in descriptive counts and document links,
but suppress inference with "Remova o filtro de resultado para comparar as
distribuições". Do not silently remove a filter to obtain a signal.

## The fixed initial rule

All gates apply together, in this order:

| Gate | Threshold | Reason |
|---|---|---|
| Comparable scope | Validated group, same court and exact class; at least two distinct panels | Different jurisdictions, competence or case types can explain the distribution |
| Independent-process floor | **`C >= 50` in each panel**, after the exclusions above | Five observations let one process move a category by 20 percentage points; at fifty it moves it by 2 points |
| Classification coverage | **`C / T >= 0.80` in each panel** | Withholds inference when more than one fifth of the eligible processes have unknown outcomes |
| Expected frequencies | **Every retained cell has expected count `>= 5`** | A conservative condition for the chi-square approximation; sample size alone is insufficient |
| Statistical evidence | **Holm-adjusted `p <= 0.05`** | Controls the family-wise error rate across the eligible pairwise tests in one response |
| Practical difference | **Maximum absolute category-share difference `>= 0.15`** | Avoids flagging a tiny change only because a large collection makes it statistically detectable |

Fifty is a floor, not a universal sufficient sample size. At the worst-case
binary share of 50%, `sqrt(0.5 * 0.5 / 50)` is about **7.1 percentage points**;
the 95% Wilson interval has a half-width of about **13.4 points**. At five,
that half-width is about **33.0 points**. The floor prevents especially
unstable conclusions; the test and expected-cell gate remain necessary.
For orientation, a worst-case two-proportion normal approximation needs about
**98 processes per panel** for 80% power to detect 20 percentage points at an
unadjusted two-sided 5% level: `2 * (1.96 + 0.84)^2 * 0.25 / 0.20^2`.
This is not a power calculation for the three-category, multiple-test rule.

The 80% and 15-point limits are conservative screening choices, not values
required by the reference methods or estimated from this collection. Twenty
percent unknown outcomes can still bias a comparison; passing coverage does
not establish that missingness is random. The 15-point floor means a change
of at least fifteen outcomes per hundred classified processes in one category.
Future calibration must version the rule and document the measured effect;
do not change limits per theme or after inspecting a pair's p-value.

### Pearson chi-square test of homogeneity

For every eligible pair, build a **2 × 3** table: rows are panels and columns
are denied, granted and partially granted. The null hypothesis is that both
panels have the same distribution of those outcomes in the defined scope.

Remove a category only when its pooled count is zero. Do not add pseudocounts
or merge categories to make a sparse table pass. If fewer than two columns
remain, report "Sem variação de resultado para testar", with no p-value.

For observed cell `O[i,j]`, use:

```text
E[i,j] = row_total[i] * column_total[j] / grand_total
X² = sum((O[i,j] - E[i,j])² / E[i,j])
degrees_of_freedom = retained_columns - 1
p = P(ChiSquare(degrees_of_freedom) >= X²)
```

Use Pearson's statistic **without Yates continuity correction**. There are
one or two degrees of freedom after removing empty columns. If any expected
cell is below five, do not compute a reportable p-value or switch methods
automatically: return the sparse-sample reason. A different exact test would
be a separately documented rule change. The gate concerns **expected** counts;
an observed zero can still be valid when its expected count is at least five.
The test and expected-count rationale follow
[NIST's chi-square independence reference](https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/chistest.htm).
The all-cells-at-least-five requirement here is stricter than the approximation
cautions described there.

### Multiple comparisons: Holm, not Holm–Šidák

A family contains **all pairs that passed the structural, sample,
classification and expected-cell gates in one response**, across the courts,
classes and competence groups included by that applied cut. Do not split it
by UI pagination, test outcome, effect magnitude or which pair looks most
interesting. Pairs below the 15-point effect floor still belong to the family
if their tests are eligible. Each unordered pair occurs once per scope.

For the `m` raw p-values sorted in ascending order, compute:

```text
adjusted_p[i] = min(1, max((m - j + 1) * p[j] for j in 1..i))
```

Map the adjusted values back to their pairs and compare to `0.05`. With one
pair, adjusted and raw p-values coincide. With no eligible pair, there is no
test or signal. For raw values `[0.001, 0.04, 0.06]`, the adjusted values are
`[0.003, 0.08, 0.08]`: only the first passes. Holm controls family-wise error
without requiring independent pairwise tests; this does not remove the
within-table observation assumptions. Implementation reference:
[`statsmodels.stats.multitest.multipletests`, method `holm`](https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html).

Keep full precision for gates, ordering and corrections. Round only display
values; `0.05004` must not pass because it displays as `0.05`.

## Below the threshold and other non-signalling states

Every panel remains visible with its counts, including a panel with five
decisions or no classified outcomes. Withhold the conclusion, not the panel.

| Situation | Required behaviour |
|---|---|
| `C < 50` in either panel | "Amostra insuficiente: mínimo de 50 processos distintos com resultado classificado por turma"; show actual `C`, `T` and document counts; no test or p-value |
| Classification coverage below 80% | Show classified and unknown counts and "Cobertura de classificação insuficiente"; no test |
| An expected count below 5 | "Categorias com poucos registros para o teste"; no inferential conclusion |
| Missing competence, class, process identity or comparable peer | Explain the unavailable comparison; retain descriptive counts and document access |
| One outcome category only, in both panels | "Sem variação de resultado para testar"; no p-value or difference signal |
| Valid test, adjusted `p > 0.05` | "Sem evidência estatística suficiente neste recorte"; do not say the panels are equivalent |
| Adjusted `p <= 0.05`, effect below 15 points | "Diferença abaixo do limiar prático de 15 pontos percentuais"; no signal |
| Every gate passes | "Diferença estatística na distribuição dos resultados"; show raw and adjusted p-values, effect, denominators and scope |
| No matching documents | Explain that the current cut is empty; invite changing the expression or period; no fabricated zero-percent analysis |
| Load or server failure | Loading/error state, separately from a successful empty or insufficient sample; allow retry |

Use this explanation beside any signal:

> Diferença estatística não comprova divergência jurídica nem prevê o resultado
> de um processo. Os percentuais usam resultados classificados automaticamente;
> confira as decisões e a competência das turmas.

Filtering repeatedly until a signal appears is not covered by one response's
multiple-test correction. Tell the reader that this is an exploratory view;
do not present the 5% level as the probability that a particular signal is
false or the probability that the panels agree.

## Evidence and reproducibility contract for subsequent tasks

The response and its evidence must identify the rule as **`RF22-v1`**, the
applied thematic cut, publication reference when available, court, validated
group, class, pair, category counts, `T`, `C`, unknown and excluded counts,
minimum expected count, raw/adjusted p, effect and non-signalling reason.
Do not invent a publication timestamp when none is available.

Each panel opens its documents with the original expression, inclusive date
ranges and every other applied filter, narrowed to that court, panel and
class. The counts must agree with that list. Also provide access to the exact
process representatives used by a tested pair, labelled as its statistical
sample, so a full-document count cannot be mistaken for `C` or `T`.
Exclusions and deterministic representative selection must be the same in
aggregation and evidence retrieval. The API shape is left to the endpoint
subtask; these are invariants, not an existing route contract.

## Numerical acceptance examples

The triples below are **(denied, granted, partially granted)** for distinct
classified processes. Except where stated, the competence and class match,
all processes have a known outcome, exclusions have already been applied,
and the response has only one eligible pair (`m = 1`). These are synthetic
fixtures, not claims about real panels.

| Scenario | Panel A | Panel B | Expected behaviour |
|---|---|---|---|
| Clear difference | `(80, 10, 10)` | `(20, 10, 70)` | `C = 100` each, smallest expected cell 10, `X² = 81`, df 2, `p ≈ 2.576757109e-18`, effect 60 points: signal |
| Similar distributions | `(60, 20, 20)` | `(55, 25, 20)` | `X² ≈ 0.772946860`, df 2, `p ≈ 0.6794487781`, effect 5 points: no signal |
| Only five processes each | `(4, 0, 1)` | `(1, 0, 4)` | A 60-point apparent gap cannot override the sample gate: counts only, no p-value |
| At the volume floor | `(30, 10, 10)` | `(20, 10, 20)` | Fifty classified each passes the sample floor; `p ≈ 0.06948345122` still fails despite a 20-point gap |
| Sparse expected cell | `(49, 1, 0)` | `(50, 0, 0)` | Remove the jointly empty third column; expected count 0.5 in the second column blocks the test |
| Classification too incomplete | `(40, 5, 5)` plus 20 unknown | `(10, 5, 35)` plus 20 unknown | `C = 50` each, but `C / T = 50 / 70 ≈ 71.43%`: no test |
| Exact coverage boundary | 50 classified of 62 representatives | 50 classified of 62 representatives | `80.645%` passes coverage; 50 of 63 (`79.365%`) fails |
| Same outcome in both | `(50, 0, 0)` | `(50, 0, 0)` | Only one pooled category; no test and no difference signal |

Additional regression cases must cover: 49 versus 50 classified processes;
effect exactly 15 points versus just below; raw p-values that pass while Holm
adjusted values fail; rounding near 0.05; a statistically significant but
smaller-than-15-point effect in a large sample; unknown outcome strings;
unresolved class or process identity; repeated documents in one process;
cross-panel processes; different competence groups; outcome-filtered cuts;
and identical filters/counts between the indicator and its evidence lists.

For the df-2 examples, `p = exp(-X² / 2)`. For df 1, the equivalent survival
function is `erfc(sqrt(X² / 2))`. These identities permit reproducing the
listed values independently of a future API implementation. Synthetic checks
validate the arithmetic and gates; they do not calibrate false signals or
power under real litigation dependence and classification error.

## SCRUM-282: HTTP contract and competence catalogue

`GET /indicators/divergence?q=...` is behind the same authentication gate as
the existing indicators. It accepts the search's court, judging-body, reporting
judge, CNJ class, outcome, judgment/reference-date and publication-date
filters, including judging-body and judge exclusions. It uses the search's
own narrowing builder and full-text expression. It aggregates the complete
matching cut, not one results page. Invalid or inverted dates are rejected.

The response contains:

- `rule_version: RF22-v1`, the thresholds and `catalogue_version`.
- `cut`, retaining the applied filters for subsequent evidence navigation.
- `documents` and `panels`, partitioned by court, exact class and original
  judging-body name. These are descriptive document counts, including
  unclassified outcomes, missing class/body fields and non-validated bodies.
  A body name does not by itself assert that the body is a comparable panel.
- `pairs`, comparing distinct named bodies only within the same court and
  non-null class. Each has its own process samples, unknown and excluded
  counts, classification coverage, reason code and `signal`.
- `outcome_order`, defining the order of each sample's `shares`: denied,
  granted, partially granted. These and `coverage` are fractions from 0 to 1,
  not percentages; `effect: 0.15` means 15 percentage points. Unknown
  percentages are `null`.
- Raw and adjusted p-values only for tests that passed every pre-test gate,
  and `tested_pairs` for the single Holm family. An insufficient sample does
  not carry a misleading p-value. `signal` is false unless every gate passes.
- `interpretation`, explaining the distinction from a legal finding, and
  `evidence_scope`, stating the representative-selection invariant.

`publication_reference` is currently `null`: this endpoint cannot identify a
specific publication from the available metadata and does not substitute the
request time or a collection-attempt timestamp. Single-statement SQL keeps
descriptive and inferential aggregates in the same database snapshot.

Process keys are normalised to uppercase ASCII letters/digits, removing
formatting separators. A missing number, a value without digits, or one
without any nonzero digit is excluded from the inferential sample. This is
a textual identity rule, not a CNJ check-digit validator. Known legacy
ambiguities still require resolution before approving the associated scope.
If any document in a pair's cut falls outside the group's approved interval,
the pair stays descriptive; the API never silently trims a historical cut to
make an approval fit.

The versioned, deployment-owned catalogue is
[`backend/app/panel_groups.json`](../../backend/app/panel_groups.json).
Each entry requires `id`, `court`, exact `panels`, allowed CNJ `classes`,
inclusive `valid_from` / `valid_to`, `evidence_url`, `validated_by` and
`validated_on`. Request parameters cannot approve a group or change the
thresholds. A missing/invalid catalogue returns 503, rather than an empty
successful analysis. Overlapping approvals for a pair produce
`ambiguous_group`, with no test.

**The initial catalogue is deliberately empty.** No competence scope has
been approved in this task; tests use explicitly fictional approvals.
Real responses provide counts and `unvalidated_group`, without a signal,
until a reviewed catalogue entry is committed. Populate it only after
validating the court, class and historical competence scope against the
recorded source. Installing the endpoint does not itself complete this
legal-validation prerequisite of SCRUM-204.

Tests cover the documented numeric examples, threshold boundaries, sparse
categories, unknown classifications, deterministic latest representatives,
cross-panel process exclusions, historical scopes, a global Holm family,
search-filter agreement and authentication. The document-list interface and
representative-sample retrieval remain the following RF12 tasks; no new
evidence-opening route is claimed here.

## SCRUM-283: Panorama panel

The Panorama dimension **Como as turmas do mesmo tribunal decidiram** reads
the authenticated endpoint only after a search has been applied and Panorama
is opened. It shares the applied cut and session cache with the existing
indicators; draft edits do not change its numbers, and a late response for
an older cut cannot replace the current one.

Panels appear side by side within their court and CNJ class, stacking on a
phone. Document outcome counts and identified processes are labelled
separately from each pair's classified-process sample. Pair details show its
own denominators, unknown outcomes and exclusions. A highlighted pair
requires the backend's confirmed signal and matching statistical reason;
insufficient or unvalidated comparisons remain visible with their counts
and explanation. The client rejects incomplete responses and inconsistent
signalling fields instead of displaying guessed zeros or conclusions.

Idle, loading, empty and failed states are distinct. Failed requests can be
retried. The panel repeats the distinction between a statistical difference
and a legal divergence. It does not yet expose representative-document links;
the RF12 flow must retain the sample-selection invariants described above.
