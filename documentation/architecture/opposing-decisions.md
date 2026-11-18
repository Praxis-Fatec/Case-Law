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

1. **Same subject.** A and B share at least two rare ementa terms, and the pair
   is scored by the `RF20` cosine over terms weighed by rarity, rarity floor
   4,5. No new similarity method is introduced here.
2. **Opposed adherence.** A and B cite the same precedent — same court, same
   type, same number — and one **followed** it while the other **departed from**
   or **distinguished** it.
3. **The disputed precedent narrows the subject.** The precedent's own rarity is
   at least 6,0, measured as `LN(decisions / decisions citing it)` — the same
   IDF `core.termo_judicial` already applies to terms, now applied to
   precedents and published as `core.precedente_judicial`.

Opposite outcome is **not** a reason. It is carried alongside, as context the
reader can see: 17,2 % of the pairs have it, which the measurement at the top of
this document shows is *below* chance.

---

## The floor, and why it replaced a list of súmulas

The first version of rule 3 was a hand-written list of ten admissibility
súmulas — STJ 7, 83, 115, 182, 187, 211, 320 and STF 282, 283, 284 — assembled
by reading what the súmulas are about. The list was wrong by omission: STF 280,
STJ 568 and STJ 126 are cited the same way and accounted for 2,8 million pairs
on their own.

The floor needs no reading. A precedent cited by a large share of the collection
cannot be telling us what a decision is *about*, and that is measurable. The
ordering it produces is the argument for it: the fourteen precedents below the
floor are the fourteen most cited in the collection.

| Precedent | Decisions citing it | Weight | |
|---|---:|---:|---|
| Súmula 7/STJ | 128.176 | 2,05 | dropped |
| Súmula 284/STF | 29.971 | 3,50 | dropped |
| Súmula 83/STJ | 29.226 | 3,52 | dropped |
| Súmula 182/STJ | 21.970 | 3,81 | dropped |
| Súmula 211/STJ | 17.259 | 4,05 | dropped |
| Súmula 283/STF | 12.766 | 4,35 | dropped |
| Súmula 282/STF | 9.062 | 4,69 | dropped |
| Súmula 280/STF | 9.060 | 4,70 | dropped |
| Súmula 568/STJ | 3.795 | 5,57 | dropped |
| Súmula 126/STJ | 3.574 | 5,63 | dropped |
| Súmula 691/STF | 3.426 | 5,67 | dropped |
| Súmula 115/STJ | 3.200 | 5,74 | dropped |
| Súmula 85/STJ | 2.894 | 5,84 | dropped |
| Súmula 5/STJ | 2.691 | 5,91 | dropped |
| *the floor* | *2.457* | *6,00* | |
| Súmula 187/STJ | 1.665 | 6,39 | **kept** |
| Súmula 320/STJ | 181 | 8,61 | **kept** |

**The floor is not a better version of the list. It is a different criterion.**
It keeps 988 of the 1.002 resolved precedents, and the two rows at the bottom of
the table are where the two methods disagree the other way: Súmula 187/STJ and
Súmula 320/STJ are as procedural as the ones above them, and the floor keeps
them because they are rarely cited. Rarity is a proxy for "narrows the subject",
and a rarely cited procedural súmula defeats the proxy.

What the floor does guarantee is a bound: no precedent cited by more than 2.457
decisions — 0,25 % of the collection — can produce a pair. Without it the rule
generates 666 million pairs, almost all of them two unrelated cases that both
reached for Súmula 7.

---

## What the rule returns

Measured over the whole collection by subtask 23.2, not over a sample.

| | |
|---|---:|
| Pairs | **3.325.818** |
| Decisions with at least one contrary | **50.925** |
| … as a share of the collection | **5,1 %** |
| … as a share of the 225.136 that cite a resolved precedent and carry a vector | 22,6 % |
| Similarity of the pairs, median | 0,193 |
| Similarity of the pairs, ninetieth percentile | 0,353 |
| Pairs whose two decisions had opposite outcomes | 17,2 % |

**The empty state is the common case, by design.** Nineteen decisions in twenty
have no known contrary, which is why the story's acceptance criteria require the
screen to say so rather than show an empty block.

### The volume per decision is the open question

| Contraries on a decision that has any | |
|---|---:|
| Median | **21** |
| Mean | 65,3 |
| Ninetieth percentile | 160 |
| Most | **1.266** |

The sampled measurement in this document reported a median of 0 and a maximum of
18. It was not wrong about a different thing: it drew candidates from each
decision's top fifty `RF20` neighbours, and the published model has no such cut —
it pairs every two decisions that share a precedent above the floor and two rare
terms.

So the endpoint's `limit` is doing more work than the sample implied. It answers
five by default and twenty at most, ordered by similarity, which means that on
the worst decision in the collection the reader sees five of 1.266. That is
defensible — similarity ordering is exactly how `RF20` already decides what is
worth showing, and the same cosine is used here — but it is a cut, not an
absence of one, and the reader is not told the list was truncated. Whether the
screen should say so, and whether a similarity floor belongs in the model after
all, is the first thing to settle after the legal reading below. No threshold was
invented here, because inventing one would be a number with no measurement
behind it.

---

## What is not settled

**Whether the pairs are really contrary has not been read yet.** Every number
here says the rule fires on a disagreement the court recorded. None of them says
a lawyer would call the two decisions contradictory.
`opposing-decisions-sample.csv` holds 40 pairs drawn from the published table,
with four empty columns to be filled in by reading: whether the two decisions
are contrary, whether the stated reason is the right one, whether the disputed
precedent is procedural, and a free note. Each row carries both ementas, both
adherences, the precedent and its weight, so the question can be answered
without opening the tool.

The 40 are not a random sample. They are drawn in six strata, each aimed at a
way the rule could be wrong:

| Stratum | Pairs | The question it asks |
|---|---:|---|
| `semelhanca_alta` | 5 | does a high cosine mean the two really treat the same question? |
| `semelhanca_mediana` | 5 | is the median pair — cosine near 0,19 — worth showing at all? |
| `semelhanca_baixa` | 5 | where does the tail stop being useful? |
| `precedente_perto_do_piso` | 10 | the floor's known failure: precedents just above 6,0 |
| `resultado_oposto` | 10 | confirm or overturn the finding that opens this document |
| `decisao_com_muitas_contrarias` | 5 | from decisions with 500 or more, where truncation bites |

Drawn with a fixed hash order rather than `RANDOM()`, so re-running the query
returns the same 40 and a second reader sees what the first one read.

**Whether rarity is the right stand-in for "narrows the subject".** The floor is
derived from the data and needs no opinion, which is its advantage over the list
it replaced. It is still a proxy, and the table above shows it failing in the
direction nobody will notice: a procedural súmula that is rarely cited stays in,
and the pairs it produces look exactly like the ones the floor was meant to
remove. The sample includes pairs drawn from just above the floor so the reading
can say whether that failure matters in practice.

**Where 6,0 came from.** It is the value at which the fourteen heaviest
precedents fall away and the pair count drops from 666 million to 3,3 million.
It was not tuned against an outcome, because there is no labelled outcome to tune
against until the reading exists.

Until that reading exists, the share above is **the share of decisions the rule
fires on**, not the share of indications a lawyer would accept. The two are
different numbers and this document can only produce the first.
