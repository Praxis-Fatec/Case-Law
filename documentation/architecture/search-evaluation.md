# The evaluation set for search

What a search model is scored against, how the score is computed, and what the
search in production scores today. This is the evidence for **SCRUM-249 (G.1)**
and the baseline every candidate in **SCRUM-250 (G.2)** has to beat.

Measured on **2026-11-21** against the local collection
(`postgresql://postgres:postgres@127.0.0.1:5432/caselaw`), which held
**1.360.708 decisions**, 876.996 of them from the STJ. The source is the whole
of `raw."espelho_stj▶acordaosSimilares"` — **1.309.628 entries**. No sampling:
every figure below is a count over those tables, reproducible with
`pipeline/evaluate_search.py`.

---

## Why this set and not a judgement of our own

US G asks for a search that finds *atraso de aeronave* when the reader typed
*demora no voo*. Whether a model does that cannot be settled by reading its
name or by looking at a handful of results and liking them. It needs pairs of
documents that somebody other than this project has already called similar.

The collection holds exactly one such judgement: `acordaosSimilares`, the
related-judgement list the STJ publishes beside each mirror. It is computed by
the court over its own base, by a method we do not control and did not tune.
That is its whole value — it is the one similarity signal here that cannot be
accused of agreeing with us because we built both sides.

---

## The entries parse; the trouble is resolving them

Each entry is one text field in the court's citation style:

```
AgRg no AREsp   63163  RS  2011/0239289-4  Decisão:25/10/2011
 DJE        DATA:10/11/2011
```

| | Entries | Share |
|---|---:|---:|
| All | 1.309.628 | 100% |
| Carrying a readable registry number | 1.309.561 | 99,9949% |
| Carrying a judgement date | 1.308.747 | 99,9327% |
| Carrying both | 1.308.684 | 99,9279% |

248.322 of the 877.099 mirrors — 28,32% — carry at least one similar.

**The date is read case-insensitively, and that is not cosmetic.** The older
mirrors write `DECISÃO:`, the newer ones `Decisão:`. A case-sensitive read
returns 1.014.754 dates instead of 1.308.747 — it silently drops **293.993
entries**. The loss is not spread evenly: the uppercase form stops in **2010**,
so a case-sensitive read removes the court's own view of its older case law and
keeps all of the recent. `test_avaliacao_busca.py` pins this.

---

## Resolution needs the registry *and* the date

The registry number names the **case**, not the judgement: one registry covers
the original acórdão, the embargos and the agravo alike.
[`similar-acordaos.md`](similar-acordaos.md) measured the consequence — of the
entry/decision pairs that share a registry, only **4,35%** agree on the
judgement date. Resolving on the registry alone would, 95,65% of the time,
link to a *different* judgement of the case than the one the court named.

So both are required. Over the 1.304.120 distinct (citing decision, registry,
date) triples:

| | Triples |
|---|---:|
| Resolve to at least one decision in the collection | 5.701 |
| …to exactly one | **5.108** |
| …to more than one | 593 |

The 593 ambiguous ones are dropped. A pair whose "correct answer" is two
different documents cannot score a ranking.

---

## Three exclusions, and what each costs

Of the 5.108 that resolve unambiguously:

| Excluded | Pairs | Why |
|---|---:|---|
| The decision cites **itself** as similar | 1.184 | Retrieving itself is not agreement with the court |
| Another **judgement of the same case** | 80 | Near-identical text, trivially retrieved by any method |
| | | |
| **Kept** | **3.844** | |

The self-citations are the surprise: **23,2%** of everything that resolves is a
decision the court lists as similar to itself. Left in, they would be ranked
first by every method that exists, lexical or semantic, and would lift every
score by the same large amount while distinguishing nothing.

The 80 same-case pairs are fewer but worse. Two judgements of one case share
most of their text, so they are found by exact word matching alone — which is
precisely the capability this story is *not* trying to measure.

---

## The set

| | |
|---|---:|
| Pairs | **3.844** |
| Query decisions | **2.920** |
| Relevant per query, mean | 1,32 |
| Relevant per query, most | 97 |
| Queries with exactly one relevant | 2.554 |

Versioned as `search-evaluation-pairs.csv`, two columns of
`core.decisao.identificador_fonte` within `stj-espelhos`. It is written down
rather than recomputed so that a score measured in G.2 and a score measured in
G.6 are scores on the same thing: the collection grows every week, and a set
rebuilt after a load is a different set.

---

## The metric

**Recall@1, Recall@10, Recall@100, and MRR** — all over pairs, not over
queries.

*Recall at a cut* is the share of pairs whose target the method placed within
the first *k* results. Ten is one screen; a hundred is as far as anyone pages
before rephrasing. One is reported because it is the only cut that cannot be
reached by luck.

*MRR* is the mean of 1/rank, counting a target never reached as zero. Recall
says whether the court's answer was on the page; MRR says where on it.

**Why per pair and not per query.** A query the court gave two similars to is
two chances to agree with it. Averaging per query would weigh a query with one
relevant the same as the query with ninety-seven, and the set has both.

**A target the method never reached counts as a miss**, not as a missing
measurement. Every method under comparison narrows the collection to candidates
before it ranks them, and failing to consider the right document is a failure
of the method, not a gap in the data.

---

## The protocol is document-to-document, and that is a limitation

The method is given the query decision's ementa and asked to rank the
collection; the score is where the court's named similar landed. Candidates are
drawn from the whole collection — all 1.360.708 decisions, not only the STJ —
because that is what the product searches.

**This is not the search box.** The box takes a short phrase a reader typed;
the set is pairs of documents. The gap is real and nothing in this collection
closes it: there is no record anywhere of what a reader typed and which
decision satisfied them.

A simulated short query was tried and rejected. Taking each decision's most
distinctive terms — the rule RF20 already uses — and offering them as if typed
produces this:

| Decision | "Query" |
|---|---|
| 000000620 | `mingu` |
| 000001181 | `surj rejeitam-s atribuica` |
| 000003431 | `1.200.850 958.428 1.360.737 408.618 735.745` |
| 000000406 | `telecom primit unirrecorribil certificaca dissoc` |

The rarest words in a legal ementa are case numbers, typos and oddities, not
the subject. Restricting to letters-only terms in a narrower rarity band
improves some and empties others: two of the six decisions above produce no
query at all. Scoring a model against *that* would measure the term-picking
rule, not the model.

So the choice is deliberate: **compare the methods on the input the gold
standard actually supports.** A model that cannot tell which documents are
about the same thing will not do it from five words either, and how the
reader's own words reach the model is a separate decision — taken in
**SCRUM-251 (G.3)** and measured end to end in **SCRUM-254 (G.6)**.

---

## The baseline

The search in production today, measured on the set above.

The ranking is the one `backend/app/api/related.py` serves RF20 with, unchanged
and with its own constants: the 12 rarest terms of the query decision above a
rarity of 4,5, candidates that carry at least two of them, ordered by the
cosine of the TF-IDF vectors. It is used because it is the strongest lexical
method the project already has — a baseline a new model should be made to beat
at its best, not at its weakest.

| | Pairs | Share of 3.844 |
|---|---:|---:|
| Target ranked **first** | 108 | **2,81%** |
| …within the first **ten** | 266 | **6,92%** |
| …within the first **hundred** | 580 | **15,09%** |
| Target reached at all | 1.305 | 33,95% |
| **Target never became a candidate** | **2.539** | **66,05%** |

**MRR 0,0427.** Median position, among the targets it reached at all: **147**.

Two numbers carry the story.

**The search puts the court's own answer on the first screen 6,92% of the
time.** That is the bar. It is not a failure of the ranking — ranking by TF-IDF
cosine is a reasonable thing to do — it is what lexical matching can do when
two decisions are about the same question in different words.

**Two thirds of the targets are never even considered.** 2.539 of 3.844 fall
outside the candidate step entirely: the cited decision shares fewer than two
of the citing decision's twelve rarest terms, so no ordering could have
rescued it. This is the part a better ranking cannot fix and the part US G
exists for — a reader who types the wrong synonym is in exactly this position,
and the tool today has nothing to offer them.

**How it was run.** 3.844 pairs, each ranked against the whole collection.
About 110 minutes on the development machine. The per-pair form was used for
this run; the committed script ranks once per query, which is the same answer
for about 85 minutes — verified by re-measuring 81 pairs with the committed
`MEASURE` and comparing position by position: 81 identical, 0 divergent. The
cost sits in the candidate step: a query reaches a mean of 26.559 candidates
and each of their ementas is unnested term by term.

**This baseline is over the whole collection, and a model cannot be compared
against it on a smaller one.** Scoring embeddings at `recall@100` needs every
candidate vectorised, which for three candidate models is three full passes of
**SCRUM-252 (G.4)** before the model is even chosen. **SCRUM-250 (G.2)** will
therefore score on a reduced, versioned corpus — and must re-measure this same
lexical ranking on that corpus too. The two arenas are never compared across.

---

## What a score here does not say

- **It does not say the model is good at the search box.** See the protocol
  above. It says the model agrees, or does not, with the only outside judgement
  of similarity this collection contains.
- **It does not make the STJ's list correct.** It is one court's computation,
  over a base larger than ours, by a method it does not publish. Agreeing with
  it is evidence; it is not proof.
- **It says nothing about the 98,1%.** Only 1,86% of the decisions carrying a
  similar resolve at all, and `similar-acordaos.md` shows the gap is a
  selection gap in the court's open data, not a coverage gap here. The set is
  drawn from the part that resolves, and nothing establishes that it looks like
  the part that does not.
