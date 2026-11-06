# Requirement catalogue · JurisFonte

Single source for the definition of the 23 functional and 10 quality
requirements of the September 2026 solution proposal. The IDs are permanent and
the titles allow direct links. Acceptance criteria and evidence live in the Jira
user stories; delivery stages live in the Roadmap. Implementation links are
recorded under each requirement below.

The IDs keep the Portuguese prefixes **RF** (*requisito funcional*) and **RNF**
(*requisito não funcional*). They are not translated: they are the identifiers
used in Jira, in Confluence and in the repository's autolink configuration, and
renaming them would break every link already written in a branch, a commit or a
pull request.

Each requirement carries its own anchor, so that
`documentation/requirements.md#RF18` opens the matching section. That is the
destination used by the commits and pull requests described in the
contribution guide, `CONTRIBUTING.md`.

| | | | |
|---|---|---|---|
| [RF01](#rf01) Search by term or exact phrase | [RF07](#rf07) Paging of the results | [RF13](#rf13) Unanimity or majority | [RF19](#rf19) Laws, articles and precedents cited |
| [RF02](#rf02) Syllabus excerpt and official source | [RF08](#rf08) Coverage of the base | [RF14](#rf14) Export of the scope | [RF20](#rf20) Semantically close decisions |
| [RF03](#rf03) Filters by court and period | [RF09](#rf09) Evolution of the volume over time | [RF15](#rf15) Comparison between courts | [RF21](#rf21) Report of an incorrect classification |
| [RF04](#rf04) Decision detail | [RF10](#rf10) Proportion of appeal outcomes | [RF16](#rf16) Status of the sources and last collection | [RF22](#rf22) Divergences between panels |
| [RF05](#rf05) Volume of decisions by court | [RF11](#rf11) Additional legal filters | [RF17](#rf17) Saved search | [RF23](#rf23) Decisions to the contrary |
| [RF06](#rf06) Ordering by relevance or date | [RF12](#rf12) Documents behind the indicators | [RF18](#rf18) Concentration by judging body and reporting judge | |

| | | | |
|---|---|---|---|
| [RNF01](#rnf01) Traceability | [RNF04](#rnf04) Performance | [RNF07](#rnf07) Data quality | [RNF10](#rnf10) Maintainability |
| [RNF02](#rnf02) Security | [RNF05](#rnf05) Scalability | [RNF08](#rnf08) Observability | |
| [RNF03](#rnf03) Privacy | [RNF06](#rnf06) Availability | [RNF09](#rnf09) Accessibility | |

---

## Delivery traceability

Reviewed against `dev` at
[`189c0b7`](https://github.com/Praxis-Fatec/Case-Law/commit/189c0b72ed3281a1049ee29a6d899639c92be7ee)
on **2026-11-05**. Each requirement below lists its implementation and verification
deliverables as clickable pull requests. PRs are preferred to individual commits
because they group the change and expose its constituent commits and diff.

- Only PRs whose merge commits are reachable from this snapshot are listed.
  Environment-promotion and branch-synchronisation PRs are omitted.
- A PR can contribute to more than one requirement; each link states its scope.
- A merged delivery is not a declaration of complete acceptance, successful
  deployment or passing checks. Acceptance evidence remains in the Jira story.
- Coverage notes identify partial evidence and limits. “Not identified” means
  absent from this review, not proof that no work exists on other branches or PRs.
- Keep these lists updated when a delivery is integrated. Add a direct commit
  link only when the change has no corresponding PR; do not duplicate every
  commit already contained in a linked PR.

## Functional requirements

<a id="rf01"></a>

### RF01 · Search by term or exact phrase

**Objective.** Find decisions from the expression the user supplies.

**Expected behaviour.** Offer search by term and by exact phrase, with visible
syntax. Preserve the expression submitted and present total, results, loading,
error and guidance when there are no results.

**Verification.** Compare term and exact-phrase searches against known documents
and check the results.

**Deliverables.**

- [PR #15](https://github.com/Praxis-Fatec/Case-Law/pull/15) — Search endpoint.
- [PR #20](https://github.com/Praxis-Fatec/Case-Law/pull/20) — Term and exact-phrase search behaviour.
- [PR #27](https://github.com/Praxis-Fatec/Case-Law/pull/27) — Search screen and response states.
- [PR #31](https://github.com/Praxis-Fatec/Case-Law/pull/31) — Search contract regression tests.
- [PR #125](https://github.com/Praxis-Fatec/Case-Law/pull/125) — Optimised frequent single-lexeme searches while preserving the existing search path for other queries.

<a id="rf02"></a>

### RF02 · Syllabus excerpt and official source

**Objective.** Assess a result and check its origin before citing it.

**Expected behaviour.** Show a contextualised excerpt of the syllabus,
highlighting the term found, and a link to the official document. Where there is
no highlightable occurrence, show the beginning of the syllabus. Links
identified as invalid must state the reason for the unavailability.

**Verification.** Check excerpts, highlights and the opening of the
corresponding document at the official source.

**Deliverables.**

- [PR #36](https://github.com/Praxis-Fatec/Case-Law/pull/36) — Contextual syllabus snippets and highlights.
- [PR #37](https://github.com/Praxis-Fatec/Case-Law/pull/37) — Official-document URL construction.
- [PR #38](https://github.com/Praxis-Fatec/Case-Law/pull/38) — Link validity and unavailability information.
- [PR #44](https://github.com/Praxis-Fatec/Case-Law/pull/44) — Result cards with metadata, excerpt and source link.
- [PR #48](https://github.com/Praxis-Fatec/Case-Law/pull/48) — Highlight and link regression tests.
- [PR #66](https://github.com/Praxis-Fatec/Case-Law/pull/66) — Correct TJDFT document destination.
- [PR #69](https://github.com/Praxis-Fatec/Case-Law/pull/69) — Source-specific link verification.
- [PR #110](https://github.com/Praxis-Fatec/Case-Law/pull/110) — Evidence excerpts for classification-based indicator navigation.

<a id="rf03"></a>

### RF03 · Filters by court and period

**Objective.** Narrow the search to the scope of interest.

**Expected behaviour.** Allow selecting one or several courts and supplying a
start and an end date. Selected courts form a union; the period and the search
expression narrow that set. Include the boundary dates, prevent an inverted
interval and recalculate the total. The date field used must be identified in
the interface.

**Verification.** Test filters in isolation and combined, the boundaries of the
interval, and a search with no filters.

**Deliverables.**

- [PR #50](https://github.com/Praxis-Fatec/Case-Law/pull/50) — Court and date parameters in the search endpoint.
- [PR #56](https://github.com/Praxis-Fatec/Case-Law/pull/56) — Available courts read from the database.
- [PR #57](https://github.com/Praxis-Fatec/Case-Law/pull/57) — Court/date filter panel and active-filter interactions.
- [PR #75](https://github.com/Praxis-Fatec/Case-Law/pull/75) — Combined filters and boundary regression tests.

<a id="rf04"></a>

### RF04 · Decision detail

**Objective.** Read the decision and assess its application to the case.

**Expected behaviour.** Present the reporting judge, the judging body, the dates
and the complete syllabus. Do not truncate the syllabus; identify unavailable
metadata. Keep access to the origin and allow returning to the context of the
search.

**Verification.** Open decisions with long syllabuses and incomplete metadata
and compare the display with the source data.

**Deliverables.**

- [PR #41](https://github.com/Praxis-Fatec/Case-Law/pull/41) — Decision detail endpoint with the complete syllabus and metadata.
- [PR #46](https://github.com/Praxis-Fatec/Case-Law/pull/46) — Structured syllabus sections.
- [PR #58](https://github.com/Praxis-Fatec/Case-Law/pull/58) — Detail reading interface.
- [PR #64](https://github.com/Praxis-Fatec/Case-Law/pull/64) — Navigation between results and detail.
- [PR #76](https://github.com/Praxis-Fatec/Case-Law/pull/76) — Detail endpoint regression tests.
- [PR #110](https://github.com/Praxis-Fatec/Case-Law/pull/110) — The court's thesis and its supporting passage in the detail.

<a id="rf05"></a>

### RF05 · Volume of decisions by court

**Objective.** Identify how the documents are distributed between courts.

**Expected behaviour.** Count the decisions of the whole searched scope, not
only of the page shown. Identify each court and allow consulting the documents
that make up its total. State that frequency does not represent legal
relevance.

**Verification.** Check the totals per court and their sum against the same
document query.

**Deliverables.**

- [PR #70](https://github.com/Praxis-Fatec/Case-Law/pull/70) — Volume-by-court endpoint over the searched scope.
- [PR #82](https://github.com/Praxis-Fatec/Case-Law/pull/82) — Court-volume interface.
- [PR #83](https://github.com/Praxis-Fatec/Case-Law/pull/83) — Agreement tests between chart counts and search results.
- [PR #106](https://github.com/Praxis-Fatec/Case-Law/pull/106) — Open the documents behind each court total.

<a id="rf06"></a>

### RF06 · Ordering by relevance or date

**Objective.** Consult first the results most pertinent to the search, or the
most recent.

**Expected behaviour.** Offer ordering by relevance and by date, preserving the
expression and the filters. Document the relevance rule, the date field and the
tie-break. Search relevance does not represent legal importance.

**Verification.** Check the order with results of known dates and scores,
including ties.

**Deliverables.**

- [PR #55](https://github.com/Praxis-Fatec/Case-Law/pull/55) — Relevance/date ordering in the search endpoint.
- [PR #62](https://github.com/Praxis-Fatec/Case-Law/pull/62) — Ordering selector.
- [PR #77](https://github.com/Praxis-Fatec/Case-Law/pull/77) — Ordering with filters regression tests.
- [PR #125](https://github.com/Praxis-Fatec/Case-Law/pull/125) — Stored ranking for eligible broad searches, with equivalence tests.

<a id="rf07"></a>

### RF07 · Paging of the results

**Objective.** Go through an extensive set without losing the context.

**Expected behaviour.** Allow moving forward and back between pages, indicate
the current position and preserve expression, filters and ordering. Prevent
navigating beyond the first or the last page.

**Verification.** Go through several pages and return, checking position, scope
and stability of the results.

**Deliverables.**

- [PR #67](https://github.com/Praxis-Fatec/Case-Law/pull/67) — Stable backend pagination.
- [PR #74](https://github.com/Praxis-Fatec/Case-Law/pull/74) — Results pagination controls.
- [PR #78](https://github.com/Praxis-Fatec/Case-Law/pull/78) — Preservation of the results position.
- [PR #79](https://github.com/Praxis-Fatec/Case-Law/pull/79) — Pagination boundary and traversal tests.

<a id="rf08"></a>

### RF08 · Coverage of the base

**Objective.** Know the reach of the available data before using it.

**Expected behaviour.** Show the number of documents, the number of courts and
the period available. Compute the values from the searchable base and state
partial coverage or unavailable information.

**Verification.** Compare counts and dates with the available records, including
an empty base and partial coverage.

**Deliverables.**

- [PR #71](https://github.com/Praxis-Fatec/Case-Law/pull/71) — Coverage endpoint with document, court and date information.
- [PR #80](https://github.com/Praxis-Fatec/Case-Law/pull/80) — Database coverage interface.
- [PR #81](https://github.com/Praxis-Fatec/Case-Law/pull/81) — Coverage totals and exclusion of sealed records tests.

<a id="rf09"></a>

### RF09 · Evolution of the volume over time

**Objective.** Observe how the number of decisions varies over the period.

**Expected behaviour.** Group the documents of the scope into identified time
intervals, stating the date used in the calculation. Allow opening the documents
of each interval and treat records without a date explicitly.

**Verification.** Compare each interval with its documents and check the sum of
the groups considered.

**Deliverables.**

- [PR #105](https://github.com/Praxis-Fatec/Case-Law/pull/105) — Time-series aggregation, chart and tests.
- [PR #106](https://github.com/Praxis-Fatec/Case-Law/pull/106) — Navigation from a time interval to its documents.

<a id="rf10"></a>

### RF10 · Proportion of appeal outcomes

**Objective.** Observe the distribution between appeals granted, partially
granted and denied.

**Expected behaviour.** Present the categories and their proportions within the
scope, with an explicit basis of calculation. Identify records without a
classification, without presuming them denied. Allow opening the documents of
each category.

**Verification.** Check classifications, numerators and denominator against a
sample and against the totals of the scope.

**Deliverables.**

- [PR #101](https://github.com/Praxis-Fatec/Case-Law/pull/101) — Outcome classification, explicit calculation base, unclassified records, API, interface and tests.
- [PR #106](https://github.com/Praxis-Fatec/Case-Law/pull/106) — Navigation from an outcome category to its documents.

<a id="rf11"></a>

### RF11 · Additional legal filters

**Objective.** Narrow the search by judging body, reporting judge and procedural
class.

**Expected behaviour.** Offer filters fed by the data and combine them with
expression, court and period. Show the applied scope and update results and
total.

**Verification.** Apply each filter and their combinations and check that every
document matches the scope.

**Deliverables.**

- [PR #104](https://github.com/Praxis-Fatec/Case-Law/pull/104) — Data-driven judging-body, reporting-judge and procedural-class filters across API, interface and tests.

<a id="rf12"></a>

### RF12 · Documents behind the indicators

**Objective.** Check the evidence that supports each number.

**Expected behaviour.** Allow opening the list of documents corresponding to an
indicator, preserving the scope and the selected condition. Make limitations or
estimates explicit where they exist.

**Verification.** Compare the set opened with the rule of calculation and the
total of the indicator.

**Deliverables.**

- [PR #106](https://github.com/Praxis-Fatec/Case-Law/pull/106) — Indicator document drawer, scope preservation, return navigation and count-agreement tests.
- [PR #110](https://github.com/Praxis-Fatec/Case-Law/pull/110) — Supporting excerpts explaining classification-based indicator results.

<a id="rf13"></a>

### RF13 · Unanimity or majority

**Objective.** Know the form of deliberation recorded in the decision.

**Expected behaviour.** State whether the decision was unanimous or by majority
when that information is available. Show a not-informed state in the remaining
cases, without deducing unanimity from the absence of dissent.

**Verification.** Check examples of unanimity, of majority and of absent
information against the origin.

**Deliverables.**

- [PR #97](https://github.com/Praxis-Fatec/Case-Law/pull/97) — Deliberation extraction, audits, API fields, interface labels and tests, including missing information.

<a id="rf14"></a>

### RF14 · Export of the scope

**Objective.** Take the search to an external analysis with verifiable
references.

**Expected behaviour.** Export the scope with the filters applied and the
references of the documents. State the date of the export and the collection
dates available. The format and the limits of the export must be stated in the
criteria of the user story.

**Verification.** Open the file generated and check scope, references, dates and
the limits stated.

**Deliverables.**

- [PR #112](https://github.com/Praxis-Fatec/Case-Law/pull/112) — PDF export of the scope, filters, references, indicators, download states and tests.
- [PR #114](https://github.com/Praxis-Fatec/Case-Law/pull/114) — Removal of the configured decision-count limit from PDF exports.

**Coverage note.** PR #114 changes the earlier export limit; the accepted limit and operational constraints must reflect the current implementation.

<a id="rf15"></a>

### RF15 · Comparison between courts

**Objective.** Compare courts side by side on the same subject.

**Expected behaviour.** Apply the same expression, period and criteria to the
courts compared. Present equivalent metrics, supporting documents and
differences in coverage; distinguish absence of documents from unavailability of
the source.

**Verification.** Check each side against its equivalent search and test courts
with distinct coverage.

**Deliverables.** No directly matching implementation was identified in the reviewed `dev` history.

**Coverage note.** Court totals (RF05) are not evidence of the complete side-by-side comparison, common scope and source-unavailability behaviour required here.

<a id="rf16"></a>

### RF16 · Status of the sources and last collection

**Objective.** Know where the data comes from and when it was collected.

**Expected behaviour.** Show the status of each source and the date of the last
collection, distinguishing a completed collection from a failed attempt. State
unavailable sources and do not replace unknown dates with estimated values.

**Verification.** Compare the interface with the collection records in cases of
success, of failure and of absence of collection.

**Deliverables.**

- [PR #43](https://github.com/Praxis-Fatec/Case-Law/pull/43) — Last successful load endpoint, with distinct never-loaded and all-loads-failed states.
- [PR #80](https://github.com/Praxis-Fatec/Case-Law/pull/80) — Coverage interface with dataset update information.

**Coverage note.** Partial: the inspected endpoint reads the environment-wide load record. This does not establish individual source status and last collection for every source.

<a id="rf17"></a>

### RF17 · Saved search

**Objective.** Resume a search with the filters already defined.

**Expected behaviour.** Keep the expression and the filters and allow reapplying
them. Saving a search does not imply freezing the documents found. Ownership,
sharing and persistence must be defined in the user story before
implementation.

**Verification.** Save and reopen a search, checking the restoration of the
expression and of the filters.

**Deliverables.** No directly matching implementation was identified in the reviewed `dev` history.

**Coverage note.** Preserving the current search during navigation is not a persisted saved-search feature with defined ownership and sharing.

<a id="rf18"></a>

### RF18 · Concentration by judging body and reporting judge

**Objective.** Identify where the searched set is concentrated.

**Expected behaviour.** Group the volume of the scope by judging body and by
reporting judge. Preserve the identification of the groups, treat absent values
and allow opening their documents. State the grouping rule when there is an
Other category.

**Verification.** Check groups and totals against the documents of the scope,
including records without metadata.

**Deliverables.** No directly matching implementation was identified in the reviewed `dev` history.

**Coverage note.** PR #104 provides filters by judging body and reporting judge, not the grouped concentration indicator and its document navigation.

<a id="rf19"></a>

### RF19 · Laws, articles and precedents cited

**Objective.** Consult the grounds referenced in the decision.

**Expected behaviour.** Show the references identified in the document, with
context that allows verifying the citation. Offer access to the origin where
available and identify unresolved references. Do not present a suggested
reference as if it had been cited.

**Verification.** Compare the references shown with the text of the decision and
check the destinations of the links.

**Deliverables.**

- [PR #109](https://github.com/Praxis-Fatec/Case-Law/pull/109) — Precedent catalogue, extraction of cited precedents, document links, context, interface and tests.

**Coverage note.** Partial: this delivery covers cited precedents. A complete implementation for cited laws and articles was not identified.

<a id="rf20"></a>

### RF20 · Semantically close decisions

**Objective.** Find other documents with content related to a decision.

**Expected behaviour.** Present close decisions and allow opening them. State
the origin or the method of the relation and distinguish official relations from
computed similarity. Semantic proximity does not prove identity of legal
understanding.

**Verification.** Validate a sample of relations, their documents and the
identification of the method used.

**Deliverables.** No directly matching implementation was identified in the reviewed `dev` history.

**Coverage note.** PR #111 links decisions to related legal scholarship. It does not deliver semantically close decisions and is therefore not counted as an implementation of RF20.

<a id="rf21"></a>

### RF21 · Report of an incorrect classification

**Objective.** Report errors found during the search.

**Expected behaviour.** Allow reporting an incorrect classification, linking the
report to the document and to the information contested. Confirm receipt; the
report does not automatically change the classification published.

**Verification.** Send a report and check its record and the preservation of the
classification until review.

**Deliverables.** No directly matching implementation was identified in the reviewed `dev` history.

**Coverage note.** No report submission, receipt confirmation and review-preserving classification workflow was identified.

<a id="rf22"></a>

### RF22 · Divergences between panels

**Objective.** Investigate differences of understanding within the same court.

**Expected behaviour.** Present indications of divergence with subject, panels,
period and the decisions that support the comparison. The criteria for
identifying divergence must be defined and validated in the user story; a
difference in volume alone does not prove legal divergence.

**Verification.** Check the cases identified against the decisions that support
them and against the rule approved for the comparison.

**Deliverables.** No directly matching implementation was identified in the reviewed `dev` history.

**Coverage note.** Volume or outcome differences alone are not an implementation of legal divergence between panels. No matching comparison workflow was identified.

<a id="rf23"></a>

### RF23 · Decisions to the contrary

**Objective.** Find documents that may contradict the understanding searched
for.

**Expected behaviour.** Show potentially contrary decisions, explaining the
context compared and the reason for the indication. Allow checking the
documents; the indication must be distinguished from a definitive legal
conclusion.

**Verification.** Validate a sample of results and their justification according
to the criteria defined in the user story.

**Deliverables.** No directly matching implementation was identified in the reviewed `dev` history.

**Coverage note.** Precedent adherence in PR #109 does not establish the contrary-decision retrieval and explanation required here.

---

## Quality requirements

They apply to the features affected. Numeric targets not defined in the proposal
must be agreed and recorded before being used as a condition of acceptance.

<a id="rnf01"></a>

### RNF01 · Traceability

**Objective.** Preserve the relation between results, indicators and source
documents.

**Expected behaviour.** Each result keeps its source; indicators allow reaching
the documents and the scope used.

**Verification.** Walk from a result and from an indicator to the origin and
check filters and references.

**Deliverables.**

- [PR #37](https://github.com/Praxis-Fatec/Case-Law/pull/37) — Source-based official-document references.
- [PR #66](https://github.com/Praxis-Fatec/Case-Law/pull/66) — Correct document-level TJDFT links.
- [PR #69](https://github.com/Praxis-Fatec/Case-Law/pull/69) — Source-aware link verification.
- [PR #106](https://github.com/Praxis-Fatec/Case-Law/pull/106) — Traceability from indicators to their underlying documents and scope.
- [PR #112](https://github.com/Praxis-Fatec/Case-Law/pull/112) — Exported document references and search context.

**Coverage note.** This requirement concerns product-to-source traceability. The requirement catalogue in PRs #123 and #126 supports development traceability, but does not by itself satisfy this requirement.

<a id="rnf02"></a>

### RNF02 · Security

**Objective.** Protect data, access and credentials.

**Expected behaviour.** Control the operations according to the permissions
foreseen; do not expose credentials in the code, in the interface or in the
execution records.

**Verification.** Review permissions, exposure of secrets and access to the
protected operations.

**Deliverables.**

- [PR #117](https://github.com/Praxis-Fatec/Case-Law/pull/117) — Accounts, authentication, access levels and protected operations with tests.
- [PR #119](https://github.com/Praxis-Fatec/Case-Law/pull/119) — Deployment correction for account administration and separate session secrets per environment.

**Coverage note.** Security-related deliveries; these links are not a comprehensive security assessment or proof that every credential exposure and permission path has been audited.

<a id="rnf03"></a>

### RNF03 · Privacy

**Objective.** Treat judicial data according to the applicable rules.

**Expected behaviour.** Restrict the exposure of protected information and block
pre-emptively, for review, records suspected of judicial secrecy.

**Verification.** Test the block and check that restricted content does not
appear in results, details or exports.

**Deliverables.**

- [PR #11](https://github.com/Praxis-Fatec/Case-Law/pull/11) — Core transformation layer with judicial-secrecy filtering.
- [PR #30](https://github.com/Praxis-Fatec/Case-Law/pull/30) — Tests of the model's secrecy filter.
- [PR #32](https://github.com/Praxis-Fatec/Case-Law/pull/32) — Regression for a decision sealed after publication.
- [PR #76](https://github.com/Praxis-Fatec/Case-Law/pull/76) — Tests preventing direct detail access to sealed decisions.
- [PR #81](https://github.com/Praxis-Fatec/Case-Law/pull/81) — Tests excluding sealed decisions from coverage totals.

**Coverage note.** Evidence covers secrecy flags and exclusion from the published base. Preventive review of suspected secrecy and a dedicated export privacy verification were not established by this review.

<a id="rnf04"></a>

### RNF04 · Performance

**Objective.** Answer the queries in a time adequate to interactive use.

**Expected behaviour.** Measure response time with the volume of data, the
queries and the environment identified. The proposal does not establish a
general numeric limit; specific targets belong to the corresponding user story.

**Verification.** Run reproducible measurements and compare them with the target
recorded for the feature.

**Deliverables.**

- [PR #125](https://github.com/Praxis-Fatec/Case-Law/pull/125) — Broad-search diagnosis, stored ranking, equivalence tests and reproducible measurements.

**Coverage note.** The documented improvement applies to eligible unfiltered, single-lexeme searches ordered by relevance within the stored depth. The after-change timings were measured locally using a restored production dataset; they are not a production-wide latency guarantee.

<a id="rnf05"></a>

### RNF05 · Scalability

**Objective.** Support the growth of the volume searched.

**Expected behaviour.** Evaluate search and processing as the base grows,
recording the limits of capacity and the resources used.

**Verification.** Run scenarios with growing volumes and record time,
consumption and the limits found.

**Deliverables.**

- [PR #16](https://github.com/Praxis-Fatec/Case-Law/pull/16) — Windowed, reloadable TJDFT ingestion.
- [PR #65](https://github.com/Praxis-Fatec/Case-Law/pull/65) — Integration of the STJ as another source.
- [PR #125](https://github.com/Praxis-Fatec/Case-Law/pull/125) — Recorded dataset size, ranking storage cost and build/query measurements.

**Coverage note.** Supporting work only: a capacity study with progressively growing volumes and measured resource limits was not identified. These PRs do not establish acceptance of RNF05.

<a id="rnf06"></a>

### RNF06 · Availability

**Objective.** Prevent the unavailability of one source from interrupting the
whole application.

**Expected behaviour.** Isolate failures per source and state the
unavailability, keeping accessible the features and the data not affected.

**Verification.** Simulate the failure of one source and check the continuity of
the rest of the application.

**Deliverables.**

- [PR #22](https://github.com/Praxis-Fatec/Case-Law/pull/22) — Separate publication of treated data and handling of unavailable database states.
- [PR #69](https://github.com/Praxis-Fatec/Case-Law/pull/69) — Source-aware link checks that distinguish unavailable sources from invalid documents.

**Coverage note.** Supporting work only: continued access to published data reduces dependence on live portals, but a complete source-failure isolation simulation was not identified.

<a id="rnf07"></a>

### RNF07 · Data quality

**Objective.** Monitor completeness, uniqueness, validity and currency.

**Expected behaviour.** Identify absent fields, duplicates, invalid data and
staleness of the collections; record the treatment and the limitations relevant
to the user.

**Verification.** Apply checks over samples and totals and review the records of
the problems found.

**Deliverables.**

- [PR #11](https://github.com/Praxis-Fatec/Case-Law/pull/11) — Core data model and initial data audits.
- [PR #16](https://github.com/Praxis-Fatec/Case-Law/pull/16) — Reloadable ingestion using source identifiers.
- [PR #38](https://github.com/Praxis-Fatec/Case-Law/pull/38) — Official-link validity checks.
- [PR #65](https://github.com/Praxis-Fatec/Case-Law/pull/65) — STJ integration and source-specific audits.
- [PR #97](https://github.com/Praxis-Fatec/Case-Law/pull/97) — Deliberation validity and coverage audits.
- [PR #101](https://github.com/Praxis-Fatec/Case-Law/pull/101) — Appeal-outcome classification audits.
- [PR #109](https://github.com/Praxis-Fatec/Case-Law/pull/109) — Precedent extraction and relation audits.
- [PR #108](https://github.com/Praxis-Fatec/Case-Law/pull/108) — Data dictionary documenting fields and completeness.

**Coverage note.** These deliveries cover specific quality checks. They do not establish that every field, source and collection-freshness rule has been validated.

<a id="rnf08"></a>

### RNF08 · Observability

**Objective.** Record evidence of execution and of failure.

**Expected behaviour.** Keep records that allow identifying the operation, the
time, the outcome and the error, preserving credentials and restricted content.

**Verification.** Locate a successful execution and a failure in the records and
follow their diagnosis.

**Deliverables.**

- [PR #16](https://github.com/Praxis-Fatec/Case-Law/pull/16) — Collection-window progress, failure reporting and retry information.
- [PR #43](https://github.com/Praxis-Fatec/Case-Law/pull/43) — Observable load outcomes and last successful publication information.
- [PR #112](https://github.com/Praxis-Fatec/Case-Law/pull/112) — PDF-rendering error logging and failed-download handling.

**Coverage note.** Partial: end-to-end correlation, retention and a review of logs for credentials/restricted content were not established by the inspected deliveries.

<a id="rnf09"></a>

### RNF09 · Accessibility

**Objective.** Follow good practice in digital accessibility.

**Expected behaviour.** Offer keyboard navigation, visible focus,
understandable labels, contrast and messages that do not depend on colour
alone.

**Verification.** Check the main flows by keyboard and run checks of labels, of
contrast and of assistive reading.

**Deliverables.**

- [PR #57](https://github.com/Praxis-Fatec/Case-Law/pull/57) — Labelled filter controls and visible focus styles.
- [PR #106](https://github.com/Praxis-Fatec/Case-Law/pull/106) — Indicator document navigation with focus handling, labelled controls and textual context.
- [PR #116](https://github.com/Praxis-Fatec/Case-Law/pull/116) — Motion behaviours respecting reduced-motion preferences.

**Coverage note.** Partial accessibility evidence only. A complete keyboard, contrast and assistive-reading audit was not identified.

<a id="rnf10"></a>

### RNF10 · Maintainability

**Objective.** Keep the code tested, documented and organised.

**Expected behaviour.** Keep the instructions for running the project up to
date, the organisation consistent and the rules changed covered by tests, with
code review.

**Verification.** Run the checks of the project and review the documentation and
the review of the change.

**Deliverables.**

- [PR #5](https://github.com/Praxis-Fatec/Case-Law/pull/5) — Continuous-integration workflow.
- [PR #6](https://github.com/Praxis-Fatec/Case-Law/pull/6) — Reproducible development environment.
- [PR #13](https://github.com/Praxis-Fatec/Case-Law/pull/13) — Code-quality tooling.
- [PR #18](https://github.com/Praxis-Fatec/Case-Law/pull/18) — PostgreSQL-backed CI test infrastructure.
- [PR #107](https://github.com/Praxis-Fatec/Case-Law/pull/107) — ETL architecture documentation.
- [PR #108](https://github.com/Praxis-Fatec/Case-Law/pull/108) — Data dictionary.
- [PR #125](https://github.com/Praxis-Fatec/Case-Law/pull/125) — Performance regression tests and explanation of the search design.

**Coverage note.** Links identify concrete maintainability work. Merge history alone does not prove that each PR received reviewer approval or that its checks remain green.

---

## Change control

Record changes of definition in the requirement affected, with reason, date and
related user story. Preserve the ID and the history of the page.

Source: solution proposal, pages 2–3; the detail guides the refinement of the
user stories.
