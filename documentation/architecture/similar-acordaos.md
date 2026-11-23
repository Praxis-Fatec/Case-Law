# The STJ's own similar acórdãos

Whether `acordaosSimilares` — the related-judgement list the STJ publishes with
every mirror — can point at documents this collection holds, and what that means
for RF20.

Measured on **2026-11-14** against the local collection
(`postgresql://postgres:postgres@127.0.0.1:5432/caselaw`), over the whole of
`raw."espelho_stj▶acordaosSimilares"` — **1.309.628 rows** — and
`core.decisao`, which held 991.163 decisions, 876.996 of them from the STJ.
Every figure is reproducible against those tables. No sampling.

This is the evidence for **SCRUM-240 (19.3)**.

---

## Why the measurement is retrospective

The sub-task was written in Sprint 2 to settle a design question for RF20: if
the court already publishes the related decisions, computing semantic
similarity would be work nobody needed. That question has since been answered
the other way — **US 20 (SCRUM-202) is implemented and pushed**, on
`feat/SCRUM-202-RF20-related-decisions`, with TF-IDF vectors and cosine
similarity. Nothing here changes it.

What is left is still worth knowing, and it is what this note answers: whether
the shortcut existed, and whether the court's own list is worth adding later as
a second, differently-sourced signal.

---

## The format, and that it parses

Each entry is one text field naming the judgement in the court's citation
style:

```
AgRg no AREsp   63163  RS  2011/0239289-4  Decisão:25/10/2011
 DJE        DATA:10/11/2011
```

The identity is the registry number, `2011/0239289-4`, which is the
`numeroRegistro` the mirrors carry with the slash and hyphen stripped
(`201102392894`).

| | Rows | Share |
|---|---:|---:|
| Entries in all | 1.309.628 | 100% |
| Carrying a readable registry number | 1.309.561 | **99,9949%** |
| Carrying a judgement date | 1.308.747 | 99,9327% |
| Carrying both | 1.308.684 | 99,9279% |

**Parsing is not the problem.** 248.322 of the 877.099 STJ mirrors — 28,32% —
carry at least one similar, and almost every entry can be read.

---

## Resolution: 0,4776%

The registry number names the **case**, not the judgement. One registry covers
the original acórdão, the embargos and the agravo alike — the figure the source
catalogue records is that 12,2% of decisions shared a source URL for exactly
this reason. So resolution has two steps, and they answer very differently.

| | Rows | Share of 1.309.628 |
|---|---:|---:|
| Registry is in the collection | 135.730 | **10,3640%** |
| Registry **and** judgement date are in the collection | 6.255 | **0,4776%** |
| …resolving to exactly one decision | 5.681 | 0,4338% |
| …resolving to more than one | 574 | 0,0438% |

By distinct registry rather than by entry: **1.113.223** distinct registries are
cited and **106.441** of them are in the collection — **9,5614%**.

The gap between the two steps is the whole finding. Of the 162.747
(entry, decision) pairs that share a registry, only **7.078 — 4,35%** agree on
the judgement date, and 6.679 on the publication date. In other words: where
the collection holds the case at all, it almost always holds a *different*
judgement of that case than the one the court named as similar.

Per citing decision, which is what a screen would show:

| | Decisions | Share of 248.322 |
|---|---:|---:|
| Carry at least one similar | 248.322 | 100% |
| At least one resolves by registry and date | 4.621 | **1,8609%** |
| At least one resolves by registry alone | 45.041 | 18,1378% |

**98,1% of the decisions that carry a similar would show an empty block.**

---

## It is a selection gap, not a coverage gap

The obvious explanation would be that the similars point outside the years this
project collected. They do not. The share of cited entries whose registry is in
the collection, by the lustrum of the cited judgement:

| Judged | Entries cited | Registry in the collection | Share |
|---|---:|---:|---:|
| 1985–1989 | 506 | 22 | 4,35% |
| 1990–1994 | 14.278 | 474 | 3,32% |
| 1995–1999 | 126.967 | 5.697 | 4,49% |
| 2000–2004 | 135.963 | 8.893 | 6,54% |
| 2005–2009 | 222.972 | 20.732 | 9,30% |
| 2010–2014 | 229.653 | 27.628 | 12,03% |
| 2015–2019 | 265.487 | 36.644 | **13,80%** |
| 2020–2024 | 266.041 | 32.774 | 12,32% |
| 2025–2026 | 29.456 | 2.134 | 7,24% |

The collection has between 1.761 and 174.878 decisions in each of those
lustrums, so there is no period it cannot answer for. The best period still
resolves 13,8% of the registries and, after the date, a fraction of that.

The reason is in the source catalogue already: the STJ's open data is
**jurisprudência selecionada pela Secretaria de Jurisprudência, não a base
inteira**. The similars are computed by the court over its whole base, and they
point into the part of it that is not published. Collecting more of what the
portal offers would not close this — there is nothing more to collect.

---

## Conclusion for RF20

**`acordaosSimilares` could not have served RF20.** A feature built on it would
answer 1,86% of the decisions that carry the field, and 0,53% of the STJ
collection — and the 98% that answered nothing would be indistinguishable, to a
reader, from a court that found nothing similar. RF20 asks to "present close
decisions and allow opening them"; a link that opens nothing is not a relation.
Computing similarity over the documents the project actually holds — which is
what SCRUM-202 does — was not an avoidable detour.

**Is it worth adding later as a complementary signal?** Narrowly, yes, and for
a reason that has nothing to do with volume. RF20 requires that the screen
"state the origin or the method of the relation and distinguish official
relations from computed similarity". For the 6.255 entries that resolve, the
relation is *the court's own*, not ours — it is the one kind of related decision
this tool could present without a disclaimer about method. 5.681 of them resolve
to exactly one decision, so they can be linked unambiguously.

So the shape it would take, if taken:

1. A second, clearly-labelled list beside the computed one — *indicada pelo
   próprio STJ* — never merged into the similarity ranking, whose scores would
   be meaningless beside it.
2. Resolution on registry **and** judgement date, never on registry alone.
   Registry alone would link 18,1% of decisions to a *different* judgement of
   the same case and present it as the one the court named: the 95,65%
   date-disagreement rate measured above is the size of that error.
3. The 574 entries that resolve to more than one decision get no link, for the
   same reason `core.url_compartilhada` exists.

That is a small story, not a sprint. It is recorded here rather than opened as a
card, because what makes it worth doing is provenance and what makes it easy to
get wrong is the registry — and both are measurements, not opinions.
