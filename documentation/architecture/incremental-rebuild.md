# Why the transformation stopped rebuilding the whole collection

Every model was `kind FULL`. A weekend bringing three thousand decisions
rebuilt all 991,163 of them, and the number was about to grow: the STF source
takes the collection past 1.6 million.

This note is the measurement that came before the change and the measurement
that came after it, with the three decisions in between. Everything here was
measured on the development machine against the collection as it stood on
2026-11-05: 991,163 decisions, 876,996 from the TJDFT and 114,167 from the STJ.

## What it cost, model by model

`sqlmesh plan` says what it rebuilt; it does not say what each model cost. So
each one was built on its own into a scratch schema, from the same data a real
run reads, timed, counted and dropped. That is `medir_transformacao.py`, and it
is how both tables in this note were produced.

| model | build | indexes | total | rows |
|---|---:|---:|---:|---:|
| `core.busca_ampla` | 373.4 s | 0.7 s | **374.1 s** | 1,172,000 |
| `core.decisao` | 194.3 s | 41.7 s | **236.0 s** | 991,163 |
| `core.doutrina_termo` | 120.1 s | 0.0 s | **120.1 s** | 10,032 |
| `core.decisao_precedente` | 59.8 s | 0.7 s | **60.5 s** | 407,316 |
| `core.decisao_doutrina` | 25.3 s | 0.1 s | 25.4 s | 28,423 |
| `core.termo_frequente` | 17.7 s | 0.0 s | 17.7 s | 1,172 |
| `core.precedente` | 15.9 s | 0.0 s | 15.9 s | 1,513 |
| `core.carga` | 0.1 s | 0.0 s | 0.1 s | 23 |
| `core.doutrina` | 0.0 s | 0.0 s | 0.1 s | 797 |
| **total** | | | **849.9 s** | |

Fourteen minutes, of which almost none is work a week of new decisions needs
doing again.

## What kind of work each model does

The question that decides whether a model can be built by date range is whether
its work is per row or over the collection.

**Per row.** `core.decisao` parses the ementa, finds the dispositivo, reads the
verdict, extracts the thesis the court wrote, and builds the tsvector. Each
acórdão is read on its own and knows nothing of the others. `core.decisao_precedente`
is the same: each ementa is searched for the súmulas and temas it cites. A week
of decisions is a week of that work, and nothing more.

**Over the collection.** `core.doutrina_termo` counts, for every term in the
doctrine vocabulary, how many decisions in the whole collection contain it —
that count is the IDF weight. There is no date range that answers it.

**Over the collection, and hidden inside a per-row model.** `core.decisao` had
one column that was not per row:

```sql
COUNT(*) OVER (PARTITION BY m.url_fonte) > 1 AS url_compartilhada
```

Whether a decision's source link still reaches more than one of our decisions
is a property of the whole collection. Worse, it is one whose answer *changes
for rows nobody is rebuilding*: a decision from 2019 becomes shared the day a
2026 one arrives under the same link. A build restricted to 2026 cannot know
it, and would answer confidently and wrongly for both.

## The three decisions

**`url_compartilhada` moved out, into `core.url_compartilhada`.** It is rebuilt
whole on every run, and that is cheap because it reads the key and the address
and no text at all: 2.3 s for all 991,163 rows, against the 34 s the window
function was costing inside the model it was blocking. One model does the thing
that needs the whole collection so that the expensive one no longer has to.

**`core.decisao` and `core.decisao_precedente` are built by date range**, on
`data_referencia` — the same date they publish. The window is applied before
any of the per-row passes, so an ingestion pays for what it ingested. The
filter had to be on the published date and not on the judgement date: a
decision with no judgement date falls back to the publication date, and a
window that filtered on the first would silently drop it.

**The doctrine vocabulary runs monthly.** `core.doutrina_termo` cannot be built
by range without changing the method. But its weight is a logarithm of a ratio
over the whole collection, and a week adds about 0.1% to that collection. So it
is recalculated on a schedule of its own instead of with every ingestion, and
the date it last ran is published on the coverage screen beside the
collection's own — two dates that move at different speeds, said plainly,
because a reader who sees them differ with no explanation assumes one is broken.

## What it costs now

Measured over the last week the collection actually holds — 2,200 decisions,
which is the size of a real weekend's ingestion.

| model | before, every run | a week, now |
|---|---:|---:|
| `core.decisao` | 236.0 s | **3.6 s** |
| `core.decisao_precedente` | 60.5 s | **0.3 s** |
| `core.url_compartilhada` | — (inside `core.decisao`) | 3.2 s |
| `core.doutrina_termo` | 120.1 s | 124.7 s, once a month |

The per-row work the story was opened for went from **296.5 s to 3.9 s**, and
`core.decisao` builds the same 991,163 rows as before when it is asked for the
whole range: 199.7 s against 236.0 s, the difference being the window function
that left.

A full rebuild still costs what a full rebuild costs: **827.3 s** against
849.9 s. That is the point — the rebuild did not get faster, it stopped
happening.

### But a weekly run is not 3.9 seconds

| | |
|---|---:|
| everything a weekly run builds | 448.0 s |
| of which `core.busca_ampla` | 381.1 s |
| everything else | 66.9 s |

(`core.doutrina_termo` is left out of that total: it has a monthly schedule
now, so a typical week does not pay its 124.7 s.)

`core.busca_ampla` is **85% of what a weekly run now costs**, and it was 44%
before. It did not get slower; everything around it got faster. Read the next
section before reading this one as a result.

## That it gives the same answer

Two proofs, because they fail differently.

**Against the collection that is published.** The converted model was built
over the whole range into a scratch table and compared with `core.decisao` as
it stands — 991,163 rows, all 24 columns it still carries, in both directions.
**Zero rows differ.** The conversion changed when the work happens, not what it
produces.

**Against itself, window by window.** `tests/test_incremental.py` builds the
model one week at a time and compares with the same model built in one go, over
a fixture written for the cases that can only go wrong incrementally: a
decision judged in one window and published in the next, one with no judgement
date at all, and two decisions six months apart that share a source link.

That second test was wrong when first written, and the way it was wrong is
worth keeping. It compared the windowed build with a "whole" build that was the
same model rendered over one large window — so both ran through the same
filter, and a filter on the wrong date made both skip the same rows and agree.
Changing the window to read `data_julgamento` instead of
`COALESCE(data_julgamento, data_publicacao)` left every test green while
silently dropping every decision the court never dated. The test now compares
against the source rather than against the other build, which is the only thing
that does not move when the filter is wrong, and it names the decision it lost.

## What the change broke, and what was done about it

Four of `core.decisao`'s audits and one of `core.decisao_precedente`'s are
coverage rules: they fail when an extraction stops matching and a column goes
quietly null. Each is guarded by a floor — `COUNT(*) > 100000` — because a
percentage cannot tell "the extraction broke" from "this is a sample", and
without the floor every development environment would fail them.

A model built by date range is audited by date range. A week holds a few
thousand rows, never a hundred thousand, so every one of those rules would have
passed without checking anything — no failure, no warning, exactly the silent
ending they were written to prevent.

They are now standalone audits, in `audits/acervo.sql`, reading the published
table whole. The floor means what it meant, and the rules run every day instead
of only on a full rebuild.

One audit was added rather than moved. `INCREMENTAL_BY_TIME_RANGE` deletes a
range before rewriting it, so a decision whose date changes between two runs —
which happens when the source fills in a judgement date for a record that only
had a publication date — is written into the new range while the old row stays
in the old one, which nobody deleted. Two rows, no window wrong, and only a
read of the whole table sees it. `decisao_unica_no_acervo` is that read.

## What this does not fix

**`core.busca_ampla` still rebuilds whole: 381.1 s, 85% of a weekly run.** It
is the materialised first page of a broad search (see
`broad-search-performance.md`), and it is global in the same way the vocabulary
is: the top thousand decisions for a frequent term are decided by comparing all
of them. New decisions can enter that top thousand, so it is not wrong to
rebuild it; it is only expensive.

The same argument that made the vocabulary monthly applies to it — a week adds
0.1% to the collection and moves the ranking of a term matching 765,840
decisions very little. Giving it a schedule of its own is the obvious next step
and is **not done here**, because it trades freshness of the search for speed
of the run, and that is a product decision rather than a pipeline one: a
decision collected on Saturday would not appear on the first page of a one-word
search until the ranking ran again.
