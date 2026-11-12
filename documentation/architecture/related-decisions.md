# Suggesting the decisions that treat the same subject

How this project decides which other decisions to offer beside the one being
read, why sentence embeddings were measured and then not used, and what the
suggestion costs to produce.

Measured on **2026-11-11** against the whole collection: 991.163 decisions,
540.198 distinct word stems of four letters or more, and 299.502 decisions
(30,2%) citing at least one súmula or tema — the labels the method was scored
against.

> **RF20, and the sentence it insists on.** The requirement asks for close
> decisions to be presented and opened, for the origin or the method of the
> relation to be stated, and for official relations to be told apart from
> computed similarity. Then it says the thing the rest of this document is
> careful about: *semantic proximity does not prove identity of legal
> understanding*. Nothing here claims that two decisions agree.

---

## The rule that comes before the method

**A bad suggestion is worse than no suggestion** — the same posture
`doctrine-matching.md` takes, and for the same reason: a decision about another
subject, offered as related, costs the reader time and costs the tool its
credibility.

So the method stays silent rather than guesses. **1,7% of the collection
receives nothing at all** because its ementa carries no term rare enough to
search on, and a decision sharing only one rare term receives nothing either.
Both are the correct answer, not a failure.

---

## Why the search already in the project does not answer this

`doctrine-matching.md` measured this for thesis → work, and the finding carries
over unchanged: a thesis turned into a query is 103 terms of procedural prose,
and the works that win are the ones sharing those words — which is all of them.
The first result for a thesis about an oil spill was an article on the
limitation period of workplace-accident claims.

Decision → decision is the same problem one size worse. The input is not a
thesis but the whole ementa, and both sides of the comparison are written in
the same procedural register. *Recurso*, *indenização*, *responsabilidade*,
*dano* are in practically every decision in the base; a match built on them is
a match on the fact that both documents are decisions.

---

## What the quality was measured against

There is a free gabarito in the base, and it costs nobody's time to produce:
**two decisions citing the same súmula or tema are treating the same subject.**
`core.decisao_precedente` already holds those citations for 299.502 decisions.

The measure is **precision@10**: of the ten decisions suggested for one being
read, how many cite a precedent it also cites. Measured over a sample of
**3.000** decisions drawn from the 299.502.

**What this proxy is not.** It is a label nobody checked, and it is biased in a
knowable direction: a procedural súmula is cited across every subject in the
base — Súmula 7/STJ, on the re-examination of evidence, is the clearest case —
so two decisions can share a cited precedent while having nothing in common but
the procedural posture that brought them to the court. The proxy therefore
rewards procedural matches that a reader would call useless. **Treat every
number below as an ordering between methods, not as the share of suggestions a
lawyer would accept.** That share has not been measured, and this document
cannot settle it.

---

## The method

Each term of the ementa is weighed by how rare it is in the collection, and two
decisions are compared by the weighted overlap of their terms.

```
weight(t)        = LN(decisions / decisions containing t)
value(t, d)      = weight(t) * (1 + LN(times t occurs in d))
similarity(a, b) = SUM(value(t,a) * value(t,b)) / (norm(a) * norm(b))
```

`weight` is `core.termo_judicial`, `norm` is `core.decisao_norma`, and the
product is the only part computed while someone waits.

Three decisions, measured one at a time. Each line adds one change to the line
above it:

| Scoring | precision@10 |
|---|---:|
| sum of the weights of the shared terms — what `doctrine-matching.md` stores | 0,426 |
| divided by the length of both vectors, i.e. the cosine | 0,470 |
| each term counted by how often it occurs in the ementa | **0,529** |

Both additions earn their keep, and neither is free: the cosine is what forces
the length of *the candidate's* vector to be known, which is why
`core.decisao_norma` exists at all.

The rarity floor and the two-term minimum are **not re-derived here**. They are
`doctrine-matching.md`'s, reused: `forte >= 4,5` for at least one rare term in
common, and `termos >= 2` because one term in common is a coincidence.

---

## Sentence embeddings were measured, and lost

This is the part of the subtask worth recording, because the result contradicts
the obvious design and `pgvector` is installed and inviting.

Measured on the same sample, with the multilingual `e5` family:

| Method | precision@10 |
|---|---:|
| lexical, as above | **0,563** |
| best `e5` configuration | 0,480 |
| `e5` over chunks of the ementa, overlapping, max-pooled | 0,417 |
| lexical and `e5` combined, several weightings | no gain over lexical alone |

The chunking row was run specifically to test the excuse for the row above it —
that an ementa is longer than the model's 512-token window, so the comparison
was being made on a truncated document. Removing the truncation made it
**worse**.

> **The two runs are not the same quantity.** The 0,563 above is the lexical
> baseline of the embedding comparison, measured before the retrieval floor and
> the twelve-term restriction below were adopted; the 0,529 in the previous
> table is the configuration actually shipped. The conclusion does not depend
> on reconciling them: both lexical numbers beat every embedding number.

**Why this is not surprising, in hindsight.** A general-purpose sentence model
is trained to place documents by what they are about in ordinary language. The
discriminating words here are legal terms of art, and what separates two
decisions is the presence of a rare one — exactly the signal an embedding
averages away. A legal-domain model is a different experiment; this was not it.

**What would change the answer**, in the order it should be tried:

1. **An evaluation set of real queries judged by someone with legal training.**
   Query → document is a different problem from document → document, and it is
   the one embeddings are usually bought for. 30 to 50 queries is enough to
   tell. Until that exists, there is nothing to tune against and no way to know
   a change helped. This is the gate in front of SCRUM-198.
2. **A model trained on Portuguese legal text**, measured against the same
   sample as everything above.
3. **Not a hybrid.** Several weightings were tried and none beat the lexical
   method alone. Recorded here so it is not tried again as a first step.

---

## Making it affordable

The method above is a product over two sparse vectors, and the expensive half
is the candidate's: scoring one means reading its whole vector.

Measured against the collection with the indexes `publish.py` creates, asking
for five suggestions, over **40 decisions drawn at random** — 15 for the two
comparisons, which are slow enough to measure on fewer:

| Query | Median | p90 | Worst |
|---|---:|---:|---:|
| **what is shipped** | **674 ms** | **1.973 ms** | **4.684 ms** |
| without the precomputed norm | 4.763 ms | 13.978 ms | 23.369 ms |
| without the rarity floor on retrieval | 1.420 ms | 3.675 ms | 10.076 ms |

Both decisions earn their place, and the norm earns more than the floor. The
cosine divides by the length of both vectors, and the candidate's length is a
second pass over the vector that was just read — which is why
`core.decisao_norma` exists.

**The floor does the retrieval, not only the filtering.** `doctrine-matching.md`
uses `forte >= 4,5` to discard a match after the fact; the same number deciding
*which terms to search on* is what keeps the candidate set from being most of
the collection.

**It bounds the work per term, not per query.** A term at that weight sits in at
most 11.011 decisions, but up to twelve of them are searched with `OR`. For the
slowest decision in the sample that is **72.811 candidates**, of which 41.262
share two terms or more — and that is the p90 and the worst case above, not an
outlier of the measurement.

What the floor costs is **16.370 decisions — 1,65% of the base** — which carry
no term that rare and so receive nothing, and **0,002 of precision@10** over
the 3.000-decision sample.

**A candidate budget cuts the body of the distribution and not the tail.**
Taking the terms rarest-first until their document frequencies add up to a
budget, instead of twelve regardless of how many decisions they reach:

| Budget | Median | p90 | Worst | Suggestions kept |
|---|---:|---:|---:|---|
| 20.000 | 636 ms | 1.078 ms | 4.334 ms | 196 of 200; 2 of 40 lists changed |
| 10.000 | 435 ms | 717 ms | 3.024 ms | 187 of 200; 6 of 40 lists changed |

Measured and **not done**: it changes which terms are searched, so it belongs
to a story with a target of its own, and `RNF04` leaves that target to the
story rather than fixing a number for the whole product.

**Two explanations of the cost were tested and are wrong**, recorded so they
are not tried again. The ordered `ARRAY_AGG` that builds the matched-term list
is not the cost — removing the ordering moves the median from 685 ms to
659 ms — and neither is aggregating every shared term instead of only the rare
ones, at 690 ms. The cost is unnesting each candidate's vector, and only a
stored inverted index avoids that.

**Enrichment, never the critical path.** The decision detail endpoint does not
call this one; the screen asks for it separately, and a failure becomes a line
inside that block. Where the two tables are not published, the endpoint answers
an empty list rather than an error — an environment whose base predates them
keeps working, and starts using them the moment they arrive, with nobody
restarting anything.

---

## What is stored

| Table | Grain | Rows | Size | Cadence |
|---|---|---:|---:|---|
| `core.termo_judicial` | one term | 540.103 | 34 MB + 14 MB index | monthly |
| `core.decisao_norma` | one decision | 991.128 | 71 MB + 66 MB index | by date range |

`core.termo_judicial` holds 540.103 of the 540.198 stems of four letters or
more. The 2,0 weight floor drops 95 of them — it corresponds to appearing in
more than 134.133 decisions, which almost no word does. It stays because it
costs nothing and guards the extreme case, not because it is filtering much.

> The wording in `core_doutrina_termo.sql` and in `doctrine-matching.md` — *"a
> minimum weight of 2,0 drops any term present in more than 13% of
> decisions"* — is arithmetically right and misleading about its effect. Both
> frame it as one of two cuts that keep the vocabulary honest; measured, it
> removes 0,018% of the vocabulary and the stem-length cut does the work.

`core.termo_judicial` is monthly because the IDF has to read the whole
collection and does not fit in a date range, and because a week adds 0,1% to
the base and barely moves the number. `core.decisao_norma` is **by date range
anyway**: a decision with no norm is never suggested, so a monthly table would
leave the week's load invisible until the month turned. The price is that norms
from different rebuilds use different vintages of the weights, and that
difference lands in a denominator, which is where it matters least.

**35 decisions have no norm** and are therefore never suggested: no term of
their ementa survives the vocabulary's cuts, so there is nothing to match and
they would never have been a candidate for anyone.

---

## What the reader is told, and the two deliberate silences

| RF20 asks for | The screen |
|---|---|
| present close decisions, allow opening them | each suggestion is a link to that decision's own address |
| state the origin or the method | the sentence above the first card, built from the answer's `method` field, never written into the screen |
| tell an official relation from a computed one | the block sits immediately below the precedents the court itself cited; its lead says the court pointed at no link between them |
| proximity is not identity of understanding | *"tratar do mesmo assunto não é decidir no mesmo sentido: uma destas pode ter decidido o contrário"* |

**The score is not shown.** It orders the list and nothing else. A number
beside two decisions reads as *"they agree 38%"*, which is exactly what it does
not mean. The ordering is the signal, and the list is ordered.

**The stems are not shown either.** The answer carries `poluidor-pag`, because
that is what actually matched and the record belongs in the data. The reader is
shown *poluidor-pagador* — the stems are spelled out from the ementa already on
screen, which costs no extra request.

---

## Where the next gain is

Ranked by what was measured, not by what is interesting to build.

1. **A sample judged by someone with legal training.** Every number in this
   document rests on a proxy with a known bias (above). This is the only item
   that can tell whether the suggestions are good, as opposed to better than
   the alternative.
2. **A gabarito that is not the cited precedent.** The same measurement run
   against decisions that share a *subject-matter* súmula, excluding the
   procedural ones, would say how much of the 0,529 is the proxy flattering
   procedural matches.
3. **Query → document**, with the evaluation set from item 1. That is where a
   semantic method is worth re-measuring, and it is a different requirement
   from this one.
