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

**Measured over 300 decisions drawn at random** from the 225.136 that cited a
resolved precedent and carried a published vector, taking up to 50 neighbours
each by the `RF20` method: **14.546 pairs** over 293 decisions (seven returned
no neighbour). Measured in the collection as it stood before the STF entered it
— 991.163 decisions — and left as measured: it is a study of how the rule
behaves, not a figure the collection moves. The counts further down, which the
collection does move, were measured again after the rebuild.

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
`conhecimento` is NULL for all 1.360.708 decisions — the column exists and was
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
591, and it is cited 128.237 times across every subject in the base. A pair
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

Re-measured after the STF entered the collection, which moved every weight:
the weight is `ln(N / citations)` and `N` went from 991.163 to 1.360.708.

| Precedent | Decisions citing it | Weight | |
|---|---:|---:|---|
| Súmula 7/STJ | 128.237 | 2,36 | dropped |
| Súmula 284/STF | 31.170 | 3,78 | dropped |
| Súmula 83/STJ | 29.230 | 3,84 | dropped |
| Súmula 182/STJ | 22.001 | 4,12 | dropped |
| Súmula 279/STF | 17.576 | 4,35 | dropped |
| Súmula 211/STJ | 17.265 | 4,37 | dropped |
| Súmula 283/STF | 13.776 | 4,59 | dropped |
| Súmula 280/STF | 12.485 | 4,69 | dropped |
| Súmula 282/STF | 9.951 | 4,92 | dropped |
| Súmula 691/STF | 4.494 | 5,71 | dropped |
| Súmula 568/STJ | 3.797 | 5,88 | dropped |
| Súmula 126/STJ | 3.577 | 5,94 | dropped |
| *the floor* | *3.373* | *6,00* | |
| Súmula 115/STJ | 3.201 | 6,05 | **kept** |
| Súmula 85/STJ | 2.899 | 6,15 | **kept** |
| Súmula 5/STJ | 2.692 | 6,23 | **kept** |
| Súmula 168/STJ | 2.331 | 6,37 | **kept** |
| Súmula 343/STF | 2.141 | 6,45 | **kept** |

**The floor moved with the collection, and that is the property that matters.**
Twelve precedents fall below it now rather than fourteen, and the three that
crossed over — STJ 115, 85 and 5 — did not become less procedural. They are
cited the same number of times against a collection a third larger, so a
proportional floor stops calling them collection-wide. Súmula 279/STF appears
because the STF's own acordaos cite it, which the STJ's mirrors never did.

**The floor is not a better version of the list. It is a different criterion.**
It keeps 1.004 of the 1.016 resolved precedents that carry a weight, and the
rows just below the floor line are where the two methods disagree the other way:
they are as procedural as the ones above, and the floor keeps them because they
are rarely cited. Rarity is a proxy for "narrows the subject", and a rarely cited
procedural súmula defeats the proxy.

What the floor does guarantee is a bound, and the bound is the same share it
always was: no precedent cited by more than **3.373** decisions — **0,25 % of
the collection** — can produce a pair. That the number moved from 2.457 to 3.373
while the share did not is the whole case for expressing it as a weight rather
than a count. Without it the rule generated 666 million pairs on the smaller
collection, almost all of them two unrelated cases that both reached for
Súmula 7.

---

## What the rule returns

Measured over the whole collection by subtask 23.2, not over a sample, and
re-measured on 18/11/2026 after the STF entered it.

| | before the STF | with the STF |
|---|---:|---:|
| Pairs | 3.325.818 | **6.323.556** |
| Decisions with at least one contrary | 50.925 | **61.644** |
| … as a share of the collection | 5,1 % | **4,5 %** |
| … as a share of those that cite a resolved precedent and carry a vector | 22,6 % | **20,8 %** (296.926) |
| Similarity of the pairs, median | 0,193 | **0,198** |
| Similarity of the pairs, ninetieth percentile | 0,353 | **0,357** |
| Pairs whose two decisions had opposite outcomes | 17,2 % | **15,0 %** |

The pairs nearly doubled while the **share of decisions the rule fires on
fell**, from 5,1 % to 4,5 %. Both move for the same reason: the STF's acordaos
cite a precedent in 11,2 % of cases against the STJ's 30,9 %, so they add far
more decisions than they add pairable ones — but the ones they do add pair
against the whole collection. A bigger base does not make the rule fire more
often per decision; it makes each firing carry more.

The opposite-outcome share fell too, from 17,2 % to 15,0 %, which is the finding
at the top of this document holding up on a third more data.

**The empty state is the common case, by design.** More than nineteen decisions
in twenty have no known contrary, which is why the story's acceptance criteria
require the screen to say so rather than show an empty block.

### The volume per decision is the open question

| Contraries on a decision that has any | before the STF | with the STF |
|---|---:|---:|
| Median | 21 | **27** |
| Mean | 65,3 | **102,6** |
| Ninetieth percentile | 160 | **291** |
| Most | 1.266 | **2.732** |

The sampled measurement in this document reported a median of 0 and a maximum of
18. It was not wrong about a different thing: it drew candidates from each
decision's top fifty `RF20` neighbours, and the published model has no such cut —
it pairs every two decisions that share a precedent above the floor and two rare
terms.

So the endpoint's `limit` is doing more work than the sample implied, and more
of it with every court added. It answers five by default and twenty at most,
ordered by similarity, which means that on the worst decision in the collection
the reader now sees five of **2.732** rather than five of 1.266 — the truncation
more than doubled without a line of code changing. That is defensible —
similarity ordering is exactly how `RF20` already decides what is worth showing,
and the same cosine is used here — but it is a cut, not an absence of one, and
it is a cut that grows with the collection.

Half of that is settled. Subtask 23.4 makes the screen say it was cut: where the
list comes back full, the block says so and offers the twenty, and the sentence
claims no total because the answer carries none. A screen that shows five of
2.732 in silence is asserting something it never measured; one that says "pode
haver outras" is not — and the sentence stayed true when the number behind it
doubled, which is what not claiming a total buys.

What is still open is whether a similarity floor belongs in the model. No
threshold was invented here, because inventing one would be a number with no
measurement behind it, and the measurement that would justify it is the legal
reading below.

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

**Where 6,0 came from.** It is the value at which the heaviest precedents fall
away and the pair count drops from 666 million to a few million. It was not
tuned against an outcome, because there is no labelled outcome to tune against
until the reading exists. It has since survived a test it was not designed for:
the collection grew by a third and the floor's bound stayed at 0,25 % of it
without anyone touching the number.

Until that reading exists, the share above is **the share of decisions the rule
fires on**, not the share of indications a lawyer would accept. The two are
different numbers and this document can only produce the first.
