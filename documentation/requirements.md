# Requirement catalogue · JurisFonte

Single source for the definition of the 23 functional and 10 quality
requirements of the September 2026 solution proposal. The IDs are permanent and
the titles allow direct links. Acceptance criteria and evidence live in the Jira
user stories; delivery stages live in the Roadmap.

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

## Functional requirements

<a id="rf01"></a>

### RF01 · Search by term or exact phrase

**Objective.** Find decisions from the expression the user supplies.

**Expected behaviour.** Offer search by term and by exact phrase, with visible
syntax. Preserve the expression submitted and present total, results, loading,
error and guidance when there are no results.

**Verification.** Compare term and exact-phrase searches against known documents
and check the results.

<a id="rf02"></a>

### RF02 · Syllabus excerpt and official source

**Objective.** Assess a result and check its origin before citing it.

**Expected behaviour.** Show a contextualised excerpt of the syllabus,
highlighting the term found, and a link to the official document. Where there is
no highlightable occurrence, show the beginning of the syllabus. Links
identified as invalid must state the reason for the unavailability.

**Verification.** Check excerpts, highlights and the opening of the
corresponding document at the official source.

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

<a id="rf04"></a>

### RF04 · Decision detail

**Objective.** Read the decision and assess its application to the case.

**Expected behaviour.** Present the reporting judge, the judging body, the dates
and the complete syllabus. Do not truncate the syllabus; identify unavailable
metadata. Keep access to the origin and allow returning to the context of the
search.

**Verification.** Open decisions with long syllabuses and incomplete metadata
and compare the display with the source data.

<a id="rf05"></a>

### RF05 · Volume of decisions by court

**Objective.** Identify how the documents are distributed between courts.

**Expected behaviour.** Count the decisions of the whole searched scope, not
only of the page shown. Identify each court and allow consulting the documents
that make up its total. State that frequency does not represent legal
relevance.

**Verification.** Check the totals per court and their sum against the same
document query.

<a id="rf06"></a>

### RF06 · Ordering by relevance or date

**Objective.** Consult first the results most pertinent to the search, or the
most recent.

**Expected behaviour.** Offer ordering by relevance and by date, preserving the
expression and the filters. Document the relevance rule, the date field and the
tie-break. Search relevance does not represent legal importance.

**Verification.** Check the order with results of known dates and scores,
including ties.

<a id="rf07"></a>

### RF07 · Paging of the results

**Objective.** Go through an extensive set without losing the context.

**Expected behaviour.** Allow moving forward and back between pages, indicate
the current position and preserve expression, filters and ordering. Prevent
navigating beyond the first or the last page.

**Verification.** Go through several pages and return, checking position, scope
and stability of the results.

<a id="rf08"></a>

### RF08 · Coverage of the base

**Objective.** Know the reach of the available data before using it.

**Expected behaviour.** Show the number of documents, the number of courts and
the period available. Compute the values from the searchable base and state
partial coverage or unavailable information.

**Verification.** Compare counts and dates with the available records, including
an empty base and partial coverage.

<a id="rf09"></a>

### RF09 · Evolution of the volume over time

**Objective.** Observe how the number of decisions varies over the period.

**Expected behaviour.** Group the documents of the scope into identified time
intervals, stating the date used in the calculation. Allow opening the documents
of each interval and treat records without a date explicitly.

**Verification.** Compare each interval with its documents and check the sum of
the groups considered.

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

<a id="rf11"></a>

### RF11 · Additional legal filters

**Objective.** Narrow the search by judging body, reporting judge and procedural
class.

**Expected behaviour.** Offer filters fed by the data and combine them with
expression, court and period. Show the applied scope and update results and
total.

**Verification.** Apply each filter and their combinations and check that every
document matches the scope.

<a id="rf12"></a>

### RF12 · Documents behind the indicators

**Objective.** Check the evidence that supports each number.

**Expected behaviour.** Allow opening the list of documents corresponding to an
indicator, preserving the scope and the selected condition. Make limitations or
estimates explicit where they exist.

**Verification.** Compare the set opened with the rule of calculation and the
total of the indicator.

<a id="rf13"></a>

### RF13 · Unanimity or majority

**Objective.** Know the form of deliberation recorded in the decision.

**Expected behaviour.** State whether the decision was unanimous or by majority
when that information is available. Show a not-informed state in the remaining
cases, without deducing unanimity from the absence of dissent.

**Verification.** Check examples of unanimity, of majority and of absent
information against the origin.

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

<a id="rf15"></a>

### RF15 · Comparison between courts

**Objective.** Compare courts side by side on the same subject.

**Expected behaviour.** Apply the same expression, period and criteria to the
courts compared. Present equivalent metrics, supporting documents and
differences in coverage; distinguish absence of documents from unavailability of
the source.

**Verification.** Check each side against its equivalent search and test courts
with distinct coverage.

<a id="rf16"></a>

### RF16 · Status of the sources and last collection

**Objective.** Know where the data comes from and when it was collected.

**Expected behaviour.** Show the status of each source and the date of the last
collection, distinguishing a completed collection from a failed attempt. State
unavailable sources and do not replace unknown dates with estimated values.

**Verification.** Compare the interface with the collection records in cases of
success, of failure and of absence of collection.

<a id="rf17"></a>

### RF17 · Saved search

**Objective.** Resume a search with the filters already defined.

**Expected behaviour.** Keep the expression and the filters and allow reapplying
them. Saving a search does not imply freezing the documents found. Ownership,
sharing and persistence must be defined in the user story before
implementation.

**Verification.** Save and reopen a search, checking the restoration of the
expression and of the filters.

<a id="rf18"></a>

### RF18 · Concentration by judging body and reporting judge

**Objective.** Identify where the searched set is concentrated.

**Expected behaviour.** Group the volume of the scope by judging body and by
reporting judge. Preserve the identification of the groups, treat absent values
and allow opening their documents. State the grouping rule when there is an
Other category.

**Verification.** Check groups and totals against the documents of the scope,
including records without metadata.

<a id="rf19"></a>

### RF19 · Laws, articles and precedents cited

**Objective.** Consult the grounds referenced in the decision.

**Expected behaviour.** Show the references identified in the document, with
context that allows verifying the citation. Offer access to the origin where
available and identify unresolved references. Do not present a suggested
reference as if it had been cited.

**Verification.** Compare the references shown with the text of the decision and
check the destinations of the links.

<a id="rf20"></a>

### RF20 · Semantically close decisions

**Objective.** Find other documents with content related to a decision.

**Expected behaviour.** Present close decisions and allow opening them. State
the origin or the method of the relation and distinguish official relations from
computed similarity. Semantic proximity does not prove identity of legal
understanding.

**Verification.** Validate a sample of relations, their documents and the
identification of the method used.

<a id="rf21"></a>

### RF21 · Report of an incorrect classification

**Objective.** Report errors found during the search.

**Expected behaviour.** Allow reporting an incorrect classification, linking the
report to the document and to the information contested. Confirm receipt; the
report does not automatically change the classification published.

**Verification.** Send a report and check its record and the preservation of the
classification until review.

<a id="rf22"></a>

### RF22 · Divergences between panels

**Objective.** Investigate differences of understanding within the same court.

**Expected behaviour.** Present indications of divergence with subject, panels,
period and the decisions that support the comparison. The criteria for
identifying divergence must be defined and validated in the user story; a
difference in volume alone does not prove legal divergence.

**Verification.** Check the cases identified against the decisions that support
them and against the rule approved for the comparison.

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

<a id="rnf02"></a>

### RNF02 · Security

**Objective.** Protect data, access and credentials.

**Expected behaviour.** Control the operations according to the permissions
foreseen; do not expose credentials in the code, in the interface or in the
execution records.

**Verification.** Review permissions, exposure of secrets and access to the
protected operations.

<a id="rnf03"></a>

### RNF03 · Privacy

**Objective.** Treat judicial data according to the applicable rules.

**Expected behaviour.** Restrict the exposure of protected information and block
pre-emptively, for review, records suspected of judicial secrecy.

**Verification.** Test the block and check that restricted content does not
appear in results, details or exports.

<a id="rnf04"></a>

### RNF04 · Performance

**Objective.** Answer the queries in a time adequate to interactive use.

**Expected behaviour.** Measure response time with the volume of data, the
queries and the environment identified. The proposal does not establish a
general numeric limit; specific targets belong to the corresponding user story.

**Verification.** Run reproducible measurements and compare them with the target
recorded for the feature.

<a id="rnf05"></a>

### RNF05 · Scalability

**Objective.** Support the growth of the volume searched.

**Expected behaviour.** Evaluate search and processing as the base grows,
recording the limits of capacity and the resources used.

**Verification.** Run scenarios with growing volumes and record time,
consumption and the limits found.

<a id="rnf06"></a>

### RNF06 · Availability

**Objective.** Prevent the unavailability of one source from interrupting the
whole application.

**Expected behaviour.** Isolate failures per source and state the
unavailability, keeping accessible the features and the data not affected.

**Verification.** Simulate the failure of one source and check the continuity of
the rest of the application.

<a id="rnf07"></a>

### RNF07 · Data quality

**Objective.** Monitor completeness, uniqueness, validity and currency.

**Expected behaviour.** Identify absent fields, duplicates, invalid data and
staleness of the collections; record the treatment and the limitations relevant
to the user.

**Verification.** Apply checks over samples and totals and review the records of
the problems found.

<a id="rnf08"></a>

### RNF08 · Observability

**Objective.** Record evidence of execution and of failure.

**Expected behaviour.** Keep records that allow identifying the operation, the
time, the outcome and the error, preserving credentials and restricted content.

**Verification.** Locate a successful execution and a failure in the records and
follow their diagnosis.

<a id="rnf09"></a>

### RNF09 · Accessibility

**Objective.** Follow good practice in digital accessibility.

**Expected behaviour.** Offer keyboard navigation, visible focus,
understandable labels, contrast and messages that do not depend on colour
alone.

**Verification.** Check the main flows by keyboard and run checks of labels, of
contrast and of assistive reading.

<a id="rnf10"></a>

### RNF10 · Maintainability

**Objective.** Keep the code tested, documented and organised.

**Expected behaviour.** Keep the instructions for running the project up to
date, the organisation consistent and the rules changed covered by tests, with
code review.

**Verification.** Run the checks of the project and review the documentation and
the review of the change.

---

## Change control

Record changes of definition in the requirement affected, with reason, date and
related user story. Preserve the ID and the history of the page.

Source: solution proposal, pages 2–3; the detail guides the refinement of the
user stories.
