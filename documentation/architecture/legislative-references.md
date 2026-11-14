# Legislative references

What the STJ writes in `referenciasLegislativas`, how much of it follows the
court's own fixed format, and the threshold the audit of RF19 is set at.

Measured on **2026-11-14** against the local collection
(`postgresql://postgres:postgres@127.0.0.1:5432/caselaw`), over the whole of
`raw."espelho_stj▶referenciasLegislativas"` — **1.243.281 rows**. Every figure
below comes from a query over that table and is reproducible against it. No
sampling.

This is the evidence for **SCRUM-238 (19.1)**, and the reason
`core.referencia_legislativa` is shaped the way it is.

---

## The format is the court's, not ours

A reference arrives as one text field written by the Secretaria de
Jurisprudência in a fixed layout:

```
LEG:FED DEL:003365 ANO:1941
        ART:00026 PAR:00002
```

Three parts, in this order:

1. **The header** — `LEG:<sphere> <act>:<number> ANO:<year>`. The sphere and the
   act type are three-letter codes; the number is six digits and the year four.
   The court writes `******` and `****` where there is no number or no year, as
   it does for the Constitution.
2. **An optional name block**, introduced by `*****`, carrying the act's
   shorthand and its full title: `***** CPC-15 CÓDIGO DE PROCESSO CIVIL DE
   2015`. Informative only — it holds no field the header does not.
3. **The components**, as repeated tokens: `ART:`, `PAR:`, `INC:`, `LET:`. They
   apply in sequence, so `ART:00105 INC:00003 LET:A LET:C` is article 105,
   item III, letters *a* and *c*.
4. **An optional issuing body** in brackets at the end: `(SENADO FEDERAL - SF)`.

Newlines fall inside the field, so every measurement here normalises whitespace
first (`BTRIM(REGEXP_REPLACE(value, '\s+', ' ', 'g'))`). 1.132.200 rows carry a
line feed and 16.513 carry a carriage return; none of that is structure.

**This is parsing, not extraction.** The layout is written by a machine at the
court, so there is nothing to infer and no model to run. What has to be measured
is how often the court's own machine departs from it.

---

## Conformance: 99,2910%

A reference counts as **recognised** when the header yields both a sphere and an
act type — the two fields without which the reference cannot be named at all.
Number, year and article are measured separately below, because the court leaves
them out legitimately.

| | Rows | Share |
|---|---:|---:|
| Recognised | 1.234.466 | **99,2910%** |
| Not recognised | 8.815 | **0,7090%** |

The deviations are a closed set of five shapes, and none of them is a new
format — each is a field the court's own export dropped:

| Shape | Rows |
|---|---:|
| Header stops at the sphere, then the `*****` name block | 3.823 |
| Act code missing, `ANO:` next (`LEG:FED ANO:1988`) | 3.060 |
| Act code missing, the colon kept (`LEG:FED :****** ANO:1988`) | 1.344 |
| Other | 321 |
| No sphere at all | 267 |

Two families account for almost all of it: STF súmulas, whose header names the
sphere and then goes straight to the name block, and the ADCT and the
Constitution, whose act code is simply absent. 8.548 of the 8.815 have a sphere
and no act type; 267 have neither.

**Nothing in this set is discarded.** An unrecognised reference is stored with
its raw text and `reconhecida = FALSE`, which is what the audit counts and what
the screen shows as a raw line.

---

## Spheres

Preserved as the court wrote them. The story named three — FED, EST, DIS — and
the collection has six, plus nine one-off typing slips:

| Sphere | Rows | Share | Read as |
|---|---:|---:|---|
| `FED` | 1.213.200 | 97,5805% | federal |
| `EST` | 23.073 | 1,8558% | state |
| `MUN` | 3.423 | 0,2753% | municipal |
| `INT` | 1.676 | 0,1348% | international |
| `DIS` | 1.435 | 0,1154% | districtal |
| *(absent)* | 267 | 0,0215% | — |
| `IES` | 198 | 0,0159% | — |
| nine others, one row each | 9 | 0,0007% | — |

`MUN`, `INT` and `IES` were not in the story and together are 0,426% of the
collection. They are kept as codes rather than folded into one of the three
named ones: a municipal statute presented as a state statute is a wrong answer,
and there is no reading of `IES` that is safe to guess. The nine others are
slips — `FE`, `DIST`, `LEI`, `FW` — and they travel raw as well.

---

## Act types

**106 distinct codes.** The head of the distribution is short and the tail is
long; the twenty most frequent are 99,6% of the recognised rows.

| Code | Rows | Share |
|---|---:|---:|
| `LEI` | 536.508 | 43,4607% |
| `SUM` | 282.938 | 22,9199% |
| `DEL` | 183.490 | 14,8639% |
| `CFB` | 63.011 | 5,1043% |
| `DEC` | 31.147 | 2,5231% |
| `RGI` | 29.452 | 2,3858% |
| `CFD` | 27.819 | 2,2535% |
| `LCP` | 18.882 | 1,5296% |
| `MPR` | 17.844 | 1,4455% |
| `RES` | 12.215 | 0,9895% |
| `EMC` | 7.771 | 0,6295% |
| `PRT` | 7.386 | 0,5983% |
| `ENU` | 2.847 | 0,2306% |
| `INT` | 2.205 | 0,1786% |
| `REC` | 1.561 | 0,1265% |
| `CNV` | 1.307 | 0,1059% |
| `CVC` | 1.236 | 0,1001% |
| `CES` | 923 | 0,0748% |
| `EMR` | 767 | 0,0621% |
| `CIR` | 694 | 0,0562% |

The five the story named are all here: `LEI`, `DEL`, `LCP`, `RES` and `CIR` —
and `CIR`, at 0,0562%, is 694 rows. What the story did not anticipate is that
**`SUM` is the second most frequent code**: 282.938 references are súmulas filed
in the legislation field. Those are already the subject of SCRUM-112, which
reads them out of the ementa with the excerpt and the adherence that RF19 asks
for. They stay in this model as references, because they were cited and because
losing a fifth of the collection to tidiness would be a worse answer, but the
screen's legislation block is not where a reader goes to read a súmula.

**Only a code that can be verified gets expanded into words.** The expansion
catalogue carries the codes whose meaning is settled — `LEI`, `DEL`, `LCP`,
`DEC`, `DLG`, `MPR`, `EMC`, `CFB`, `RES`, `PRT`, `CIR`, `SUM`, `RGI` — and every
other code reaches the screen as the code. Guessing that `CVC` means *convenção*
would be the same class of error as guessing a link to the wrong law: an
invented name on a legal citation reads as fact.

---

## What a reference actually carries

Of the 1.243.281 rows:

| Field | Rows | Share |
|---|---:|---:|
| Act number (not `******`) | 866.647 | 69,71% |
| Year (not `****`) | 952.410 | 76,60% |
| At least one article | 787.177 | 63,31% |
| A paragraph | 239.835 | 19,29% |
| An item (`INC`) | 235.132 | 18,91% |
| A letter (`LET`) | 49.055 | 3,95% |

A missing number or year is not a defect: `CFB:****** ANO:1988` is how the court
writes the Constitution, and 36,69% of the references name an act without
pointing at an article inside it. The model keeps all four nullable, and the
screen says *act, year* where there is no article rather than inventing one.

**Token shapes**, which is what the parser has to accept:

- `ART:` — 1.134.985 tokens. 1.110.682 are five digits (`ART:00026` → art. 26);
  **24.222 are four digits and a letter** (`ART:0543B` → art. 543-B), which a
  parser that expects five digits would read as article 5.434; 81 are neither.
- `PAR:` — 300.502 tokens, numeric except for `ÚNICO` (29.666) and `UNICO`
  (8.042). Both spellings mean *parágrafo único* and both have to be accepted.
- `INC:` — 324.454 tokens, 324.306 of them five digits. Numbered in arabic in
  the source and read in roman numerals in Brazilian practice, so the number is
  what is stored and the numeral is what the screen writes.
- `LET:` — 64.223 tokens, single letters A to O.

---

## One row per article, which is why the model is not one row per reference

Articles per reference:

| Articles | References | Share |
|---|---:|---:|
| none | 456.104 | 36,68% |
| one | 564.819 | 45,43% |
| two or more | 222.358 | 17,88% |

The most any single reference names is **24**. A model with one row per source
row would keep the first article and silently lose the rest — 17,88% of the
collection, which is the shape of a bug that nobody sees. So the grain is
**(decision, reference, article)**: a reference with no article contributes one
row with a null article, and a reference with six contributes six, each carrying
the paragraph, item and letter that follow its own `ART:` token.

**1.591.078 rows** come out of 1.243.281 source rows this way, and every source
row is represented by at least one of them.

---

## Reach into the collection

| | |
|---|---:|
| STJ mirrors in `raw` | 877.099 |
| mirrors carrying at least one reference | 585.237 — **66,73%** |
| decisions in `core.decisao` | 991.163 |
| decisions carrying at least one reference | 585.235 — **59,05%** |
| references whose decision is not in `core.decisao` | **6** |

The six are mirrors with an empty ementa, which `core.decisao` refuses. The
TJDFT collection carries no legislative reference field at all, which is why the
share over the whole core is lower than over the STJ's own.

Two thirds of the STJ collection gaining a legislation block is the measure that
makes RF19 worth the work: the comparable figure for cited precedents is 30,2%.

---

## The threshold: 1%

The audit of SCRUM-241 measures the share of rows in
`core.referencia_legislativa` with `reconhecida = FALSE`. Over the model's own
grain — after exploding by article — that share today is:

| | |
|---|---:|
| Rows in the model | 1.591.078 |
| Unrecognised | 9.664 |
| **Share** | **0,6074%** |

It is lower than the 0,7090% over source rows because the unrecognised families
name fewer articles each than the collection's average.

**The audit fails above 1%.** That is 65% headroom over today, which is enough
that a month of new collection cannot trip it on volume alone, and tight enough
that a real change at the court cannot hide under it: the smallest single
deviating family already measured is 267 rows, and the largest is 3.823 — a
format change would move the rate by whole percentage points at once, not by
tenths. A threshold at 0,7% would fail on the next load for no reason, and one
at 5% would let the court stop writing act codes entirely without a word.

The rate is also the thing to watch rather than the count: the collection grows
every week, and a ceiling on the count of unrecognised rows would have to be
raised by hand each time, which is how a guard stops guarding.
