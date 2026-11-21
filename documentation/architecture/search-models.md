# Choosing an embedding model

Which of three candidates earns the cost of vectorising the collection, and
what adding one buys over the search that exists. This is the evidence for
**SCRUM-250 (G.2)**.

Measured on **2026-11-21** on the development machine — RTX 5070, 12 GiB,
driver 580.126.09, CUDA 13.0 — against the evaluation set of
[`search-evaluation.md`](search-evaluation.md): 3.844 pairs over 2.920 query
decisions.

---

## The reduced corpus

Scoring `recall@100` for an embedding model needs every candidate vectorised.
Over the whole collection that is 1,36 million ementas **per model**, which is
three full runs of **SCRUM-252 (G.4)** before the model is chosen. So the
comparison runs on a fixed, reduced corpus:

| | Decisions |
|---|---:|
| Query decisions and their targets | 6.572 |
| Random distractors from the STJ | 41.546 |
| **Total** | **48.118** |

Built by `avaliacao.corpus`. Only 2% of it exceeds ~1024 tokens, so truncation
at that length is not a confound.

**The lexical baseline is re-measured on this same corpus.** Comparing a model
on 48.118 documents against TF-IDF on 1.360.708 would credit the model for the
smaller haystack. The two arenas are never compared across.

---

## What the lexical search scores, in both arenas

| | Whole collection | Reduced corpus |
|---|---:|---:|
| recall@1 | 2,81% | 5,52% |
| recall@10 | 6,92% | 13,27% |
| recall@100 | 15,09% | 24,84% |
| MRR | 0,0427 | 0,0805 |
| **Targets reachable at all** | **1.305** | **1.305** |

The scores roughly double in the smaller haystack, and **the ceiling does not
move**. 1.305 of 3.844 — 33,95% — in both. The binding constraint is the
candidate step, not the ordering: a target that shares fewer than two of the
query's twelve rarest terms never enters the list, and shrinking the collection
27-fold recovered **not one** of the 2.539 it loses. An embedding model has no
candidate step, so its ceiling is 100%.

---

## The candidates

### Cost, measured on 2.000 real ementas

Measured over the 48.118 of the reduced corpus, which is the mix the real run
would meet:

| Model | Dim | Ementas/s | Peak VRAM | Whole collection |
|---|---:|---:|---:|---:|
| jinaai/jina-embeddings-v3 | 1024 | **123,0** | 2.449 MiB | **3,1 h** |
| BAAI/bge-m3 | 1024 | 51,3 | 2.960 MiB | 7,4 h |
| rufimelo/Legal-BERTimbau-sts-large | 1024 | 51,9 | 1.673 MiB | 7,3 h |

Batch size was swept and **bigger is worse**: 59,6/s at 16, 56,9 at 32, 55,3 at
64, 54,4 at 128, while peak VRAM climbs from 3,0 to 7,9 GiB. Sequences are
padded to the longest in the batch, so a larger batch buys only padding. Batch
16 is both the fastest and the lightest.

**Jina v3 runs only on a frozen stack, and that is part of its price.** Its
remote code (`XLMRobertaLoRA`) expects an older `transformers` API —
`_tied_weights_keys` rather than `all_tied_weights_keys` — and pinning
`transformers` alone then breaks `sentence-transformers`, which wants
`is_kernels_available` from the newer one. The pair that works is
`transformers==4.49.0` with `sentence-transformers==3.4.1`, both already old,
in an environment of their own. The other two load on the current stack. Where
that lands depends on **SCRUM-251 (G.3)**: if the reader's query is embedded in
the backend, the frozen stack moves into the serving path; if an embedding API
is chosen, it stays in the pipeline and costs little.

### Agreement with the court, on the reduced corpus

| | Lexical | BGE-M3 | Jina v3 | Jina v3 @256 | Legal-BERTimbau |
|---|---:|---:|---:|---:|---:|
| recall@1 | **5,52%** | 5,28% | 4,92% | 4,89% | 4,84% |
| recall@10 | **13,27%** | 12,85% | 12,07% | 11,78% | 9,42% |
| recall@100 | 24,84% | **27,47%** | 26,46% | 26,20% | 20,45% |
| MRR | **0,0805** | 0,0792 | 0,0745 | 0,0733 | 0,0658 |

**Jina's Matryoshka dimensions are nearly free.** Truncating 1024 to 256 costs
0,26 points at a hundred — under 1% relative — for a quarter of the storage.
That is the only lever measured here that moves cost by a factor and recall by
a rounding error.

**The Portuguese legal model loses on every measure**, including the one it
would be chosen for. It is a sentence-similarity model with a 512-token ceiling
rather than a retrieval model, and being trained on Portuguese legal text did
not make up for that. Where it matters most — the pairs the lexical search
cannot reach — it recovers 6,46% at a hundred against BGE-M3's 11,78%, roughly
half.

**BGE-M3 does not beat the search it was meant to replace.** It is level at one
and ten — slightly below — and ahead only at a hundred. And it scores that
while ranking the entire corpus, with no candidate step to lose targets in,
against a lexical method that discards two thirds of them before ordering
begins.

### The tie hides two opposite populations

Split the same 3.844 pairs by whether the lexical candidate step can reach the
target at all, and the averages come apart:

| | Pairs | Lexical @10 | BGE-M3 @10 | Lexical @100 | BGE-M3 @100 |
|---|---:|---:|---:|---:|---:|
| Lexical **never reaches** | 2.539 | 0,00% | **3,07%** | 0,00% | **11,78%** |
| Lexical **reaches** | 1.305 | **39,08%** | 31,88% | **73,18%** | 58,01% |

Legal-BERTimbau splits the same way and lower throughout: 1,50% and 6,46% on
the pairs the lexical search never reaches, 24,83% and 47,66% on the ones it
does.

The model recovers 299 pairs at a hundred that the lexical search cannot see at
any depth — and it is plainly **worse** wherever both can see, 31,88% against
39,08% on the first screen. The overall tie was these two cancelling.

### Together they beat either one

Taking, for each pair, whichever of the two ranked it better:

| Paired with the lexical search | recall@10 | recall@100 | Recovers, of the 2.539 |
|---|---:|---:|---:|
| **BGE-M3** | **16,99%** | **33,77%** | **11,78%** |
| Jina v3 @1024 | 16,65% | 33,14% | 10,59% |
| Jina v3 @256 | 16,52% | 32,83% | 10,12% |
| Legal-BERTimbau | 15,09% | 29,86% | 6,46% |
| *(lexical alone)* | *13,27%* | *24,84%* | *0,00%* |

**+28% relative at ten and +23% at a hundred over the better of the two.** The
methods are complementary, not competing, and the comparison that matters is
not "which model replaces the search" but "what does adding one buy". This is
measured support for what **SCRUM-254 (G.6)** already asks for — *combinando
com o resultado léxico* — and it says the lexical ranking must stay in the
answer rather than be ranked alongside: it is the better of the two on its own
ground by a wide margin.

---

## The gold standard is not lexically biased

The obvious objection is that the court computes `acordaosSimilares` by some
lexical method of its own, in which case the measurement rewards whoever
resembles it. Tested directly, as the TF-IDF cosine of the pairs:

| Pairs | Mean | Median | p90 |
|---|---:|---:|---:|
| Named similar by the court | 0,1891 | **0,0944** | 0,4644 |
| Random | 0,0204 | 0,0127 | 0,0493 |

Nine times a random pair, which any true notion of similarity would produce —
but the median is the answer. At **0,0944**, half the pairs the court calls
similar share almost no distinctive vocabulary. A lexical judge would have
produced pairs with high cosine. It did not, so the objection does not hold:
the court is pointing at kinship the words do not carry, which is exactly what
US G promises and exactly why the lexical search loses two thirds of them.

---

## The choice: BGE-M3, stored as `halfvec`

What each candidate costs to carry 1.360.708 decisions, beside what it buys:

| | Union recall@100 | Of the 2.539 | Embed once | Column, `halfvec` |
|---|---:|---:|---:|---:|
| **BGE-M3, 1024** | **33,77%** | **11,78%** | 7,4 h | 2,6 GiB |
| Jina v3, 1024 | 33,14% | 10,59% | **3,1 h** | 2,6 GiB |
| Jina v3, 256 | 32,83% | 10,12% | **3,1 h** | **0,65 GiB** |
| Legal-BERTimbau, 1024 | 29,86% | 6,46% | 7,3 h | 2,6 GiB |

**BGE-M3.** It wins every recall figure, and it wins by most on the only
population that justifies the feature at all: 11,78% of the pairs the lexical
search cannot reach, against 10,12% for the cheapest alternative. That is a
16% relative difference in the thing being bought.

The case against it is real and was weighed. Jina v3 at 256 dimensions embeds
in 3,1 hours instead of 7,4 and stores 0,65 GiB instead of 2,6 — four times
less, carried over the network on every publish. Three things decided it the
other way:

1. **The embedding cost is paid once.** After the first pass only new decisions
   are embedded, and the weekly load adds thousands, not millions. Four hours
   of a one-off is not worth 1,66 points of the feature's whole purpose.
2. **2,6 GiB is affordable where it lands.** The development host has 1,7 TiB
   free and its database is 5.241 MB. Publication time grows and must be
   measured in **SCRUM-253 (G.5)** — but it is a measurable operational cost,
   not a wall.
3. **Jina costs a frozen stack.** `transformers==4.49.0` with
   `sentence-transformers==3.4.1`, both already old, pinned for as long as the
   feature lives. BGE-M3 runs on the current one.

**The trigger to revisit.** If G.5 measures the publish and the vector column
adds more than it is worth, Jina v3 at 256 dimensions is the fallback, and this
note already holds the number it would cost: 0,94 points of union recall at a
hundred.

---

## What is still open

- **How the two orderings are merged.** The hybrid is justified above; the rule
  is not chosen, and **SCRUM-254 (G.6)** requires it to be explicable to a
  reader. Whatever it is, it has to respect the measured asymmetry: on its own
  ground the lexical ranking is far better — 39,08% against 31,88% at ten — so
  a merge treating the two as equals would lose ground where most answers come
  from.
- **Whether 11,78% is worth building.** That is a judgement about the product
  rather than a measurement, and it belongs to whoever owns the backlog. What
  the measurement can say: the gain falls entirely on searches that today
  return nothing the reader wanted, and nothing cheaper reaches them.
- **The query side is untouched.** Everything here is document against
  document. How the reader's own words become a vector is **SCRUM-251 (G.3)**,
  and the frozen-stack question above lands there.
