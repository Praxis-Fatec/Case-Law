# Vectors for the collection

How the collection's ementas become vectors, what the run costs, and what makes
it safe to interrupt. This is the evidence for **SCRUM-252 (G.4)**.

Measured on **2026-11-21** on the development machine — RTX 5070, 12 GiB,
driver 580.126.09 — against the local collection of **1.360.708 decisions**,
embedded with the model chosen in [`search-models.md`](search-models.md).

---

## What a row records, and why

```
vetor.decisao (fonte_codigo, identificador_fonte, modelo,
               revisao, ementa_digest, vetor halfvec(1024), gerado_em)
```

Three of those columns exist only to stop a silent failure.

**`modelo`** because two models' vectors in one index produce an ordering that
means nothing while looking perfectly healthy. **`revisao`** — the model's
commit on the Hub — because `BAAI/bge-m3` is a moving name: the weights behind
it can change, and a vector produced by yesterday's weights is not comparable
to one produced by today's. **`ementa_digest`**, the SHA-256 of the exact text
embedded, because a decision can be re-collected: the key stays, the ementa
changes, and the vector now describes text the collection no longer holds.

The vectors live **outside the SQLMesh-managed schemas** on purpose.
`core.decisao` is `INCREMENTAL_BY_TIME_RANGE` and gets rebuilt; two hours of
GPU cannot be part of a rebuild. `vetor.decisao` is keyed by
`(fonte_codigo, identificador_fonte)`, which survives every rebuild, so the
vectors outlive the model that joins them.

---

## Resumability without a checkpoint file

The work left to do is a query, not a stored position:

```sql
LEFT JOIN vetor.decisao AS v
  ON  v.fonte_codigo        = d.fonte_codigo
  AND v.identificador_fonte = d.identificador_fonte
  AND v.modelo              = :modelo
  AND v.revisao             = :revisao
  AND v.ementa_digest       = SHA256(CONVERT_TO(d.ementa, 'UTF8'))
WHERE v.fonte_codigo IS NULL
```

One join covers all four reasons a decision needs embedding: never embedded,
embedded by a different model, embedded by an older revision of this one, and
an ementa that changed since. A checkpoint file would catch only the first.

It costs **7,3 s** to answer over the whole collection, so asking is cheaper
than remembering.

**Proven by interrupting it.** The run was killed mid-flight after 43.008
vectors. The log's last line was 43.008 — the kill landed between chunks, so no
partial write existed — and the pending count then read **1.317.700**, which is
1.360.708 − 43.008 exactly. Restarting embedded the remainder and nothing
twice.

The one invariant this rests on is that `hashlib.sha256(ementa.encode("utf-8"))`
in Python and `SHA256(CONVERT_TO(ementa, 'UTF8'))` in PostgreSQL agree, over
accented text. Two implementations of one idea in two languages, and nothing in
the run would notice them drifting apart — so `test_vetores_acervo.py` pins it,
along with each of the four pending cases.

---

## fp16, and the sorting that mattered more

Two independent levers were measured, each on 8.192 real ementas of
`stj-espelhos`:

| | Ementas/s | Whole collection |
|---|---:|---:|
| fp32, batches of 16 in key order | 24,3 | 15,6 h |
| fp16, batches of 16 in key order | 82,0 | 4,6 h |
| fp32, chunks of 2.048 sorted by length | 50,3 | 7,5 h |
| **fp16, chunks of 2.048 sorted by length** | **174,4** | **2,2 h** |

**fp16 is 3,5× faster than fp32 and costs nothing.** The column is `halfvec`,
which is fp16 — so precision beyond fp16 is discarded at write time anyway.
Embedding in fp32 would buy accuracy the storage immediately throws away.
`bfloat16` measured 81,9/s against fp16's 82,0 in the unsorted arrangement, an
identical tie, so fp16 was kept as the one the storage already matches.

**Letting the library sort by length is worth 2,1× on its own**, and it is easy
to lose. `SentenceTransformer.encode` sorts its input by length, batches the
sorted order, and restores the original order before returning — so feeding it
sixteen rows at a time, in key order, defeats it and pays for padding on every
batch. Handing it a chunk of 2.048 and letting it choose its own batches of 16
measured 174,4/s against 82,0 for the same work and the same VRAM.

The two levers compose: 24,3 → 174,4 ementas/s, **7,2× in total**, which is why
the 7,4 h that G.2 projected for this run is not the number it cost.

### Throughput follows ementa length, and the sources differ sharply

| Source | Decisions | Mean ementa | Ementas/s | Estimated |
|---|---:|---:|---:|---:|
| `stf-jurisprudencia` | 369.545 | 597 chars | **833,0** | 7 min |
| `stj-espelhos` | 876.996 | 1.291 chars | 174,4 | 1 h 24 min |
| `tjdft-jurisdf` | 114.167 | 3.171 chars | 92,0 | 21 min |
| **Whole collection** | **1.360.708** | | | **~1 h 52 min** |

A 9× spread in throughput across three sources, tracking ementa length almost
exactly. The STF is fast partly because 6.374 of its ementas are shorter than
40 characters — the placeholders recorded in
[`stf-source.md`](stf-source.md) — and every decision with a blank or
whitespace ementa is excluded from the run entirely, because a vector for
whitespace would rank against real ones.

This is also why a throughput figure measured on one source does not transport:
the reduced corpus of G.2 was STJ-heavy, and the collection is not.

---

## The run

| | |
|---|---:|
| Vectors written | **1.360.708** |
| Still pending afterwards | **0** |
| Wall clock | **2 h 04 min** |
| Throughput | 183 ementas/s |
| Model | `BAAI/bge-m3` |
| Revision | `5617a9f61b028005a4858fdac845db406aefb181` |
| Precision | `float16` |

The estimate above was 1 h 52 min and the run took 2 h 04 — **11% optimistic**.
The per-source rates were measured on the first few thousand rows of each
source, which are not a random sample of it.

### Where the 4 GB went

| | |
|---|---:|
| Table | 220 MB |
| **TOAST** | **3.603 MB** |
| Indexes (primary key, digest) | 268 MB |
| **Total** | **4.090 MB** |

**A `halfvec(1024)` is 2.050 bytes and the row limit before out-of-line
storage is about 2 KB, so every single vector is TOASTed.** The vectors are
not in the table; they are in its TOAST relation, one trip away. G.2 budgeted
2,6 GiB for the column from the raw arithmetic — the stored cost is 4,0 GB,
**54% more**, and the difference is TOAST overhead and the two indexes.

### The vectors agree with the subject

Nearest neighbours of a decision whose ementa reads *"AGRAVO REGIMENTAL.
AGRAVO DE INSTRUMENTO. ADMINISTRATIVO E PROCESSUAL CIVIL. EXECUÇÃO. COISA
JULGADA. [...] SÚMULA 280/STF"*:

| Cosine | Neighbour |
|---:|---|
| 0,8568 | PROCESSUAL CIVIL. AGRAVO REGIMENTAL. AGRAVO DE INSTRUMENTO. SÚMULA 280/STF… |
| 0,8559 | PROCESSUAL CIVIL. AGRAVO REGIMENTAL NO AGRAVO DE INSTRUMENTO. VIABILIZAÇÃO… |
| 0,8523 | ADMINISTRATIVO. PROCESSUAL CIVIL. AGRAVO REGIMENTAL NO AGRAVO DE INSTRUMENTO… |

This is a smoke test, not a measurement — the measurement is G.6. It is here
because a run that silently wrote 1,36 million wrong vectors would look exactly
like a run that worked.

### The exact search is already over the ceiling

That query — one vector against all 1.360.708, no index — took **3,2 s**. The
US A ceiling is 2 s for a whole page of results. So **the HNSW index of
SCRUM-253 (G.5) is a requirement and not an optimisation**, and this 3,2 s is
the figure it has to beat.

---

## What G.5 inherits

- **`vetor` is not in `publish.py`'s `TABLES`**, and that tuple is written by
  hand — the comment at the top of the file records that `core.precedente` and
  `core.doutrina` were both ready in code and absent from the environments for
  exactly this reason. The vectors reach dev and production only when
  **SCRUM-253 (G.5)** adds them.
- **The test fixtures replace `raw`, `core` and `verificacao`, and `vetor` is
  none of those.** A test that writes vectors has to drop the schema itself or
  it reads the last test's rows; `test_vetores_acervo.py` does.
- **The HNSW index does not exist yet.** Nothing here builds one: this is the
  table of vectors, and the index, the published column and the publish cost
  are G.5's.

## What is still open

- **The weekly load has no hook into this.** A new decision arrives with no
  vector and the pending query will find it, but nothing runs the script
  automatically. Where that belongs — beside the load, or inside the publish —
  is a question for G.5 and for `SCRUM-192`.
- **Nothing here measures retrieval.** These are the vectors G.2's measurement
  said to produce, over the whole collection rather than its reduced corpus.
  Whether the collection-wide numbers match the reduced ones is measured end to
  end in **SCRUM-254 (G.6)**.
