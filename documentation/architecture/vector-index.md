# The vector index, and what it costs to publish

Which index the collection's vectors get, what it costs to build and to carry,
and how much of the exact answer it gives back. This is the evidence for
**SCRUM-253 (G.5)**.

Measured on **2026-11-21** on the development machine against the 1.360.708
vectors of [`corpus-vectors.md`](corpus-vectors.md), pgvector 0.8.6.

---

## Why an index at all

The search without one is a sequential scan of every vector:

| | Median | p90 |
|---|---:|---:|
| Exact, no index, warm cache | **1.334 ms** | 1.394 ms |
| Exact, no index, cold | 3.150 ms | |

The US A ceiling is 2 s for a whole page of results, and the lexical half of
that page already costs 37 ms after **SCRUM-210**. A semantic half that costs
1,3 s warm — and 3,1 s cold, which is the state the server is actually in most
of the time — spends the entire budget on its own. On the server, whose
single-thread memory bandwidth is about five times worse and which cannot hold
3,6 GB of vectors in 3,9 GB of free RAM, it would be far worse than that.

**So the index is a requirement, not an optimisation.** Everything below is
about which one.

All timings below are medians over the same 50 query decisions, drawn
deterministically by `MD5` of the key. **53,7 ms of `docker exec` plus `psql`
startup were measured separately and subtracted**; the figures are the query,
not the shell.

---

## Recall is the number that decides it

Every index here is approximate: it answers faster by not looking at
everything. A latency without a recall beside it says nothing, so each
candidate is scored against the exact answer for the same 50 queries —
`recall@10` is how many of the exact ten nearest the index also returned.

---

## The candidates

| Index | Build | Size | Query | recall@10 |
|---|---:|---:|---:|---:|
| *(none — exact)* | — | — | 1.334 ms | *100%* |
| HNSW on `halfvec`, `ef_search` 40 | 8m43s | 3.460 MB | 19,3 ms | 91,8% |
| HNSW on `halfvec`, `ef_search` 100 | 8m43s | 3.460 MB | 19,3 ms | 97,0% |
| HNSW on `halfvec`, `ef_search` 200 | 8m43s | 3.460 MB | 32,2 ms | 97,2% |
| HNSW on **binary**, rerank 50 | 3m48s | 548 MB | 0,0 ms | 88,0% |
| HNSW on **binary**, rerank 100 | 3m48s | 548 MB | 3,1 ms | 94,4% |
| HNSW on **binary**, rerank 200 | 3m48s | 548 MB | 7,9 ms | 95,6% |
| **HNSW on binary, rerank 500** | **3m48s** | **548 MB** | **14,4 ms** | **97,8%** |
| IVFFlat on `halfvec`, 10 probes | 2m47s | 3.550 MB | 6,4 ms | 92,4% |
| IVFFlat on `halfvec`, 40 probes | 2m47s | 3.550 MB | 31,0 ms | 96,8% |
| IVFFlat on `halfvec`, 100 probes | 2m47s | 3.550 MB | 79,3 ms | 99,4% |

IVFFlat builds fastest of the three — k-means over a sample and one pass to
assign, against a graph built insertion by insertion — and it reaches the
highest recall of any candidate at 100 probes. It loses on the two things that
decide this: at a comparable 97% it answers in **31,0 ms against 14,4**, and
its index is **3.550 MB against 548**, because IVFFlat stores the vectors
themselves rather than a quantization of them.

> **A measurement trap worth recording.** The first IVFFlat run reported 91,8%
> recall at every probe count and *fell* from 164 ms to 52 ms as probes rose.
> Both are impossible, and the cause was that the `halfvec` HNSW index was
> still on the table: the planner was answering with HNSW at its default
> `ef_search`, whose recall is exactly 91,8%. Two indexes over the same
> operator class cannot be compared while both exist. The numbers above were
> taken after dropping the other one.

### What binary quantization is doing

`binary_quantize(vetor)::bit(1024)` keeps one bit per dimension — the sign —
and throws the magnitude away. The vector goes from **2.052 bytes to 136**, a
factor of 15, and the distance becomes a Hamming distance over machine words
instead of a dot product over 1024 half-floats.

That alone would lose too much, so the query is two stages: the index picks
500 candidates by Hamming distance, and those 500 are then re-ordered by the
**exact** cosine over the full `halfvec`. The quantization chooses who to look
at; the full vector decides the order. Confirmed by `EXPLAIN`, which reads
`Index Scan using decisao_hnsw_bit` and then sorts 500 rows.

**It wins on all four axes at once**, which is unusual enough to state plainly:
it builds in 44% of the time, occupies 16% of the space, answers in 75% of the
latency, and is *more* accurate — 97,8% against 97,0%. The reason it is also
faster is the same reason it is smaller: the graph it walks is a sixth of the
size, so the walk touches a sixth of the memory.

---

## The size is the part that matters on the server

| | Development machine | Server |
|---|---:|---:|
| RAM | 30 GiB | 7,9 GiB |
| RAM free | 19 GiB | 3,9 GiB |
| vCPU | 16 | 2 |

An index of 3.460 MB does not fit in what the server has free beside
PostgreSQL, so every query would read it from disk. An index of **548 MB**
fits with room to spare, and stays in the page cache between searches. On this
machine the difference between the two is 5 ms; on the server it is the
difference between an index and a file.

---

## The index is built on the server, and that is not obvious

`publish.py` dumps the staged schema with `pg_dump --format custom` and pipes
it into `pg_restore`. **A custom-format dump carries index definitions, not
index pages** — so every index in the staged schema is *rebuilt* on the target
during the restore. The HNSW is not shipped; it is constructed on 2 vCPU.

That has two consequences, and the second is a bug this note is here to stop.

**The build time lands on the server.** Scaled by the ~5× single-thread factor
measured in [`query-embedding.md`](query-embedding.md), the binary index's
3m48s here is roughly **19 minutes** there, against roughly 44 minutes for the
`halfvec` one — and the `halfvec` graph does not fit in the memory the server
can give a build, which turns it into a disk-backed build and makes that
estimate a floor rather than a figure.

**Built in `INDEXES`, it would be paid twice.** Everything in `INDEXES` is
created on the local staging schema so that `pg_dump` finds the definition, and
then created again by `pg_restore`. For the cheap b-trees that is seconds. For
a 3m48s HNSW it is 3m48s of the publish spent building an index that is thrown
away with the staging schema. So the vector index is **not** in `INDEXES`: it
is created once, on the target, by `_remote_psql` between the transfer and the
swap — before the swap, so the published schema never exists without it.
`test_publicacao.py` pins that it stays out of `INDEXES`.

### `/dev/shm` stops the parallel build

The first attempt failed in 0,05 s:

```
ERROR: could not resize shared memory segment to 8586907168 bytes:
       No space left on device
```

pgvector's parallel build puts the graph in dynamic shared memory, and the
container's `/dev/shm` is Docker's default **64 MB**. Every build above is
therefore serial — `max_parallel_maintenance_workers = 0` — which uses the
backend's own memory instead. The same wall is waiting on the server, so the
statement that builds the index sets it explicitly rather than hoping.

---

## What the publish carries now

Measured by running `publish.stage()` locally and dumping the staged schema
exactly as `transfer()` does, with and without the vector table.

| | Before | After |
|---|---:|---:|
| Staged schema | 8,2 GB | **12 GB** |
| Dump, `gzip:6` | 1,55 GiB in **2m05s** | 7,01 GiB in **11m31s** |
| Dump, **`zstd:6`** | — | **4,88 GiB in 2m52s** |
| Staging step | — | 4m06s |

**The vectors do not travel as vectors.** A custom-format dump writes table
data as `COPY` text, so each `halfvec(1024)` leaves as a string of about nine
thousand characters — `[0.0123,-0.4567,…]` a thousand times — instead of the
2.050 bytes it occupies on disk. That is why the dump grows by 5,46 GiB when
the staged table is 3.824 MB: the text is larger than the table before it is
compressed, and random floating point does not compress.

**So the compressor was changed from gzip to zstd**, which PostgreSQL 17
supports and both ends already run:

| | Size | Time |
|---|---:|---:|
| `gzip:6` | 7,01 GiB | 11m31s |
| **`zstd:6`** | **4,88 GiB** | **2m52s** |

**30% smaller and four times faster**, for one flag. The publish still costs
more than it did — 2m52s against 2m05s to dump, 4,88 GiB against 1,55 — but
the growth is 2,4× rather than 5,5×.

---

## The decision

**HNSW over `binary_quantize(vetor)::bit(1024)`, with the top 500 re-ordered by
the exact `halfvec` cosine.**

It is the fastest, the smallest, the quickest to build and the most accurate of
the candidates measured, and the only one whose index fits in the memory the
server has free. The accuracy it gives up against an exact scan is **2,2% of
the first ten**, on a feature whose purpose is to surface decisions the lexical
search returns none of.

`SCRUM-253` asks for an HNSW index and this is one: the quantization is in the
indexed expression, not in a different index type.

### The trigger to revisit

- **If recall@10 below 97% ever matters**, the rerank depth is the dial and it
  is cheap: 500 costs 14,4 ms against 7,9 ms at 200. Nothing has to be rebuilt.
- **If the build on the server exceeds the publish window**, the next lever is
  building the index once and leaving it — restoring only the data on later
  publishes — which the current swap-the-schema design does not allow and would
  have to be redesigned for.

---

## What is still open

- **Nothing here measures retrieval quality against the court.** `recall@10`
  above is agreement with the *exact vector search*, not with the STJ. How much
  of G.2's measured gain survives the index is measured in **SCRUM-254 (G.6)**,
  on the evaluation set of G.1.
- **The real publish has not been run.** Everything here is local: the staging,
  the dump and the index build were measured on this machine, and the server
  figures are transported with their factor stated. Publishing to dev and
  production is a separate, deliberate act.
