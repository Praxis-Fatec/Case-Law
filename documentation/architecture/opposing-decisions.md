# Decisions to the contrary

`RF23` asks for the decisions that may contradict the one being read. This
document is the subtask that comes before the feature: what counts as contrary,
and what that rule actually returns when run against the collection.

The story's own card says why the measurement comes first — *"without it the
story delivers noise with the face of analysis"*. The measurement below found
exactly that in the obvious rule, so the rule changed.

---

## The obvious rule does not work

Contrary is not *opposite outcome*. Two decisions can deny two different
appeals for opposite reasons, and two decisions can reach the same
understanding with opposite outcomes, because the outcome depends on which
party appealed — something the collection does not record.

That is an argument. Here is the measurement.

**Measured over 300 decisions drawn at random** from the 225.136 that cite a
resolved precedent and carry a published vector, taking up to 50 neighbours
each by the `RF20` method: **14.546 pairs** over 293 decisions (seven returned
no neighbour).

| | Share of similar pairs |
|---|---:|
| Opposite outcome (`provido` × `negado`) | **11,9 %** |
| Same, expected by chance | **25,7 %** |

The chance figure is `2 × P(provido) × P(negado)` over the decisions that carry
an outcome: 15,6 % and 75,9 %. Two decisions picked at random from the
collection disagree on the outcome a quarter of the time.

**Similar decisions disagree less than random ones.** Opposite outcome is not a
weak signal of contradiction; it points the other way. A feature built on it
would show, on a typical decision, around six "contrary" decisions that are
mostly pairs agreeing on the law and differing on who appealed.

It also cannot be repaired by excluding appeals that were never admitted:
`conhecimento` is NULL for all 991.163 decisions — the column exists and was
never implemented, as `etl.md` and the data dictionary already record.

---

## What does carry a signal

Adherence to precedent. `core.decisao_precedente` records, for each precedent a
decision cites, whether it **followed**, **departed from** (`afastou`),
**distinguished** or merely **mentioned** it. Two decisions citing *the same*
precedent, one following it and one departing from it, are in a disagreement
the court itself wrote down.

| | Pairs | Share |
|---|---:|---:|
| Opposed adherence on a shared precedent | 591 | 4,06 % |
| … disputing only an admissibility súmula | 374 | 63,3 % |
| … disputing at least one merits precedent | **217** | **36,7 %** |

Súmula 7/STJ alone — the re-examination of evidence — accounts for 263 of the
591, and it is cited 128.176 times across every subject in the base. A pair
"disputing" it is usually two unrelated cases where one could reach the facts
and the other could not. `related-decisions.md` measured the same bias from the
other side and warned about it; it shows up here in full force.

---

## The rule

A decision **B** is shown as contrary to **A** when all three hold:

1. **Same subject.** B is among A's neighbours by the `RF20` method — cosine
   over ementa terms weighed by rarity, rarity floor 4,5, at least two shared
   terms. No new similarity method is introduced here.
2. **Opposed adherence.** A and B cite the same precedent — same court, same
   type, same number — and one **followed** it while the other **departed from**
   or **distinguished** it.
3. **The precedent is not purely procedural.** A pair whose only disputed
   precedent is an admissibility súmula is not shown.

Opposite outcome is **not** a reason on its own. It is carried alongside, as
context the reader can see, because a pair that disagrees on both the precedent
and the outcome is a stronger case than one that disagrees on the precedent
alone — and 17,1 % of the merits pairs do.

### What the rule returns

| | |
|---|---:|
| Decisions with at least one contrary | **16,0 %** (47 of 293) |
| Contraries per decision, median | **0** |
| Contraries per decision, mean | 0,7 |
| Contraries per decision, most | 18 |
| Similarity of the pairs, median | 0,425 |

**The empty state is the common case, by design.** Five decisions in six have
no known contrary, which is why the story's acceptance criteria require the
screen to say so rather than show an empty block.

### Cost

Measured on the same 300: **797 ms** at the median, **2,07 s** at the
ninetieth percentile. That is the `RF20` neighbour query plus the adherence
lookup; subtask 23.2 moves it to a published model, so the endpoint reads a
table instead of computing this per request.

---

## What is not settled

**Which súmulas are procedural is a legal judgement, and it is currently mine.**
The list used in the measurement is ten admissibility súmulas — STJ 7, 83, 115,
182, 187, 211, 320 and STF 282, 283, 284. It was assembled by reading what the
súmulas are about, not by any property in the data, and it moves the headline
number a long way: without it, 40,6 % of decisions get a contrary instead of
16,0 %. It needs confirmation by someone with legal training, and the sample
beside this document asks for exactly that.

**Whether the pairs are really contrary has not been read yet.** Every number
here says the rule fires on a disagreement the court recorded. None of them
says a lawyer would call the two decisions contradictory.
`opposing-decisions-sample.csv` holds 40 cases drawn from this measurement —
20 caught by the merits rule, 10 by admissibility only, 10 by opposite outcome
alone — with four empty columns to be filled in by reading. The ten outcome-only
cases are there so the reading can confirm or overturn the finding that opens
this document, rather than taking it on the measurement alone.

Until that reading exists, the rate above is **the share of decisions the rule
fires on**, not the share of indications a lawyer would accept. The two are
different numbers and this document can only produce the first.
