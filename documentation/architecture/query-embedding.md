# Embedding the reader's query

Where the query becomes a vector, what each path costs, and what one search is
expected to spend on it. This is the decision for **SCRUM-251 (G.3)**, and it
answers the question [`search-models.md`](search-models.md) handed forward.

Measured on **2026-11-21**. Two machines appear below and the difference
between them is the whole point, so both are named: the **development machine**
(Ryzen 7 9800X3D, 16 threads, RTX 5070) and the **server** (AMD EPYC 9354P,
**2 vCPU**, 7,9 GiB of RAM, São Paulo).

---

## The constraint that removes most of the freedom

A query vector is only comparable to the collection's vectors if the **same
model** produced both. **SCRUM-250 (G.2)** chose BGE-M3 and
**SCRUM-252 (G.4)** will spend 7,4 hours of GPU embedding the collection with
it. So this is not a free choice between models — it is a choice of *where*
BGE-M3 runs. Any path that implies a different model reopens G.2 and throws
away G.4.

That matters because the embedding APIs that are close to Brazil do not serve
BGE-M3, and the one that serves it is not close. The measurements below are
arranged around that fact.

---

## Where it would run, and why a dev measurement is not evidence

The production backend and its Postgres run **on the server itself**
(`case-law-prod-backend-1`, `case-law-prod-postgres-1`). The *development*
backend does not: nginx proxies dev to the development machine over Tailscale —
the machine with the RTX 5070.

So a latency measured in dev would be a latency measured on a gaming GPU and
reported as if it were production. Everything here is measured for the server's
shape: **2 threads**, no GPU, and RAM shared with Postgres.

| Server, as found | |
|---|---:|
| vCPU | 2 |
| RAM, total | 7,9 GiB |
| RAM, available | 3,9 GiB |
| Disk free | 48 GiB |
| Backend image today | **1,01 GB** |

`avx512_bf16` is present in `/proc/cpuinfo` on both machines — the hypervisor
does not mask it. That single fact is what makes the chosen path cheap, and it
was checked before it was relied on.

---

## The three paths

1. **BGE-M3 in the backend.** No external dependency, no per-query cost; the
   container grows and every search pays CPU inference on a machine with no GPU.
2. **An API that serves BGE-M3.** Small container, fast inference; a network hop
   per search, a paid account, and an outside service in the request path.
3. **An API-native model** (Jina, Gemini). Closest to Brazil, but a different
   model — which reopens G.2 and discards G.4.

---

## Path 1, measured: BGE-M3 on 2 CPU threads

### bf16 is 2,6× faster than fp32, and fp16 is worse than both

Median of nine runs, development machine, 2 threads, one query at a time:

| Query | Tokens | fp32 | **bf16** | fp16 |
|---|---:|---:|---:|---:|
| *demora no voo* | 6 | 57,6 ms | **22,7 ms** | 58,1 ms |
| *prescricao intercorrente execucao fiscal* | 12 | 71,2 ms | **25,6 ms** | 115,1 ms |
| a 35-token procedural question | 35 | 128,8 ms | **37,1 ms** | 309,6 ms |

**fp16 is a trap and the numbers say so loudly** — 309,6 ms against fp32's
128,8 at 35 tokens. There is no CPU hardware path for fp16 here, so every
matrix multiply converts up and back; the longer the query, the worse it gets.
bf16 has `avx512_bf16` and halves the weight bytes at the same time.

**int8 bought nothing.** `quantize_dynamic` over the Linear layers measured
58,9 ms against fp32's 58,4 at 6 tokens — no gain — while peak RSS during
quantization reached 5.079 MiB because both copies exist at once. At six
tokens the forward pass is not dominated by arithmetic, so cheaper arithmetic
buys nothing; the measurement is recorded so nobody pays for it twice.

### bf16 does not change the vector

| | Cosine against fp32 | Largest per-dimension error |
|---|---:|---:|
| bf16 | **0,999916** | 2,15 × 10⁻³ |
| fp16 | 0,999999 | 1,21 × 10⁻⁴ |

At 0,999916 the bf16 query vector is the fp32 query vector for any purpose a
ranking has. This is the check that licenses the speed: the corpus will be
embedded in G.4 at full precision, and a query embedded in bf16 is still
comparable to it.

### The RSS trap: the model has to be *stored* in bf16

Loading BGE-M3 and then casting it to bf16 does **not** free the memory:

| How the model is loaded | Weights | Steady-state RSS |
|---|---:|---:|
| fp32 | 2.166 MiB | 2.283 MiB |
| fp32 from disk, cast to bf16 in memory | 1.083 MiB | **2.207 MiB** |
| **a bf16 copy, saved to disk and loaded directly** | 1.083 MiB | **1.701 MiB** |

`sentence-transformers` reads the fp32 safetensors and converts afterwards, and
the mapped fp32 pages stay resident — so the obvious way to ask for bf16 saves
76 MiB of 2.283, not half. A bf16 copy written to disk (1,1 GB) and loaded as
itself is what actually gives back 582 MiB. Whoever implements G.6 has to ship
that copy; asking for bf16 at load time is not the same thing.

### Two concurrent searches do not double the time

| Threads | 6 tokens | 35 tokens |
|---|---:|---:|
| 1 | 34,3 ms | 63,9 ms |
| **2** | **22,7 ms** | **37,1 ms** |
| 4 | 18,2 ms | 24,4 ms |

Halving the threads costs 1,5×, not 2×. On 2 vCPU that is the concurrency
answer: two searches at once get roughly one thread each and land near the
first row, not at twice the second.

### What it costs on the server: an estimate, and its honest width

The server cannot be measured directly without putting a 1,1 GB model and a
torch install on the host that serves production, so the number here is
transported from the development machine and the transport is stated.

Single-threaded memory bandwidth, measured on both with stock `python3` and no
installs — `bytearray[:] = bytes` for copy, `bytes.count` for a read-only scan,
at 32, 64 and 256 MiB:

| | Copy (r+w) | Scan (read) |
|---|---:|---:|
| Development machine | 9,7 – 12,1 GB/s | 5,2 GB/s |
| **Server** | **1,7 – 2,1 GB/s** | **0,9 – 1,2 GB/s** |
| Ratio | 4,6 – 5,8× | 4,3 – 5,8× |

The figures are consistent across all three sizes, so this is not a page-cache
artifact on a server with 408 MB free. The proxy understates absolute bandwidth
on both machines — torch's kernels stream weights far better than a libc
`memcpy` called from Python — so what transports is the **ratio**, not the
level.

A 6-token forward pass reads every one of BGE-M3's 1.083 MiB of bf16 weights
and does little arithmetic per byte, so it sits between two regimes. Both
bounds are reported rather than a single invented number:

| Query | On 2 threads here | If clock-bound (1,4×) | If bandwidth-bound (5,8×) |
|---|---:|---:|---:|
| 6 tokens | 22,7 ms | **32 ms** | **132 ms** |
| 35 tokens | 37,1 ms | **52 ms** | **215 ms** |

**The decision does not depend on which end is right.** The US A ceiling is
**2 s for the first page of `recurso`**, and after **SCRUM-210** that page costs
36,71 ms on the development machine. Even the pessimistic end of the range —
215 ms for a long query — spends **10,8% of the ceiling**, leaving 1,78 s for
the vector search of G.5 and the merge of G.6.

### What grows

| | Today | With BGE-M3 in bf16 |
|---|---:|---:|
| Inference stack (`torch` CPU + `sentence-transformers`) | — | 1,1 GB installed |
| Model on disk | — | 1,1 GB |
| **Backend image** | **1,01 GB** | **~3,2 GB** |
| **RSS at rest** | — | **1,70 GiB of the 3,9 available** |

The RAM is the binding constraint, not the latency — 1,70 GiB on a 7,9 GiB
host that also runs Postgres. The image can be kept near 2,1 GB by mounting
the model rather than baking it in, which is a G.5 decision and is noted there.

---

## Paths 2 and 3, measured: the network from São Paulo

The server is in São Paulo. Round trips measured from it, by `curl`, with no
API key and nothing sent:

| Endpoint | TCP handshake | One full request |
|---|---:|---:|
| `api.jina.ai` | 4,4 ms *(Cloudflare edge, São Paulo)* | 240 ms |
| `generativelanguage.googleapis.com` | 1,3 ms *(Google edge, São Paulo)* | 250 ms |
| `api.deepinfra.com` | **168 ms** *(no edge in Brazil)* | **521 ms** |

**The two that are 1 ms away do not serve BGE-M3, and the one that serves it is
168 ms away.** That is the whole shape of the API option. DeepInfra lists
`bge-m3` at **US$ 0,01 per million input tokens**, 200 concurrent requests per
account, on H100/A100, with **no free tier** — *"You have to add a card or
pre-pay or you won't be able to use our services."*

The money is not the problem: a 10-token query is **US$ 0,01 per 100.000
searches**. The problems are 521 ms measured against 32–215 ms estimated, an
outside service inside every search, and a card on a student project.

**Gemini's free tier is the ceiling the backlog already warned about.** The
figures reported for `gemini-embedding-001` are 100 requests per minute, 30k
tokens per minute and **1.000 requests per day**, with repeated reports of the
free embedding quota being issued as 0. A product whose search stops after a
thousand uses in a day is not a product. This is the same wall that bit thesis
reading, and it is a reason to keep inference off a free tier rather than an
argument about latency.

Path 3 also pays twice: switching to Jina v3 costs **0,63 points of union
recall@100** (33,77% → 33,14%, measured in G.2) *and* discards G.4's 7,4 hours.
It buys 240 ms instead of an estimated 32–215 ms — which is not a gain.

---

## The decision: BGE-M3 in the backend, stored and loaded in bf16

| | Latency per search | RAM on the server | Per search | Outside dependency | Reopens G.2 |
|---|---|---:|---:|---|---|
| **Backend, bf16** | **32 – 215 ms** *(est.)* | **1,70 GiB** | **0** | **none** | no |
| API, BGE-M3 (DeepInfra) | 521 ms *(measured)* | 0 | US$ 10⁻⁷ | yes, card required | no |
| API, another model | 240 – 250 ms *(measured)* | 0 | 0 – paid | yes, 1.000/day free | **yes** |

**The backend.** It is the fastest of the three even at the pessimistic end of
its range, it adds nothing to the request path that can fail outside this
project, it needs no payment method, and it is the only one that keeps G.2's
measured choice and G.4's GPU hours. What it costs is 1,70 GiB of server RAM
and an image three times larger.

And it closes the question G.2 left open. G.2 noted that Jina v3 requires a
frozen `transformers==4.49.0` + `sentence-transformers==3.4.1` stack, and that
the cost of the pin depended on this decision — in the pipeline it is cheap, in
the serving path it is expensive. **BGE-M3 runs on the current stack**, so
putting the model in the backend costs no pin at all. Had Jina won G.2, this
decision would have dragged two frozen libraries into the API container for as
long as the feature lived.

**The expected latency per search**, to be held to in G.6: **under 250 ms for
the embedding step**, against a US A ceiling of 2 s of which the lexical first
page now uses 36,71 ms.

### Triggers to revisit

- **If the measured server latency in G.6 exceeds 250 ms for a short query**,
  the estimate's bandwidth-bound end was right and the next lever is the
  ONNX Runtime backend, not a different model.
- **If 1,70 GiB cannot be spared beside Postgres**, the options in order are
  mounting the model instead of baking it into the image, raising the server's
  memory, and only then the API — accepting 521 ms and a card.
- **If a reader's query ever needs more than ~35 tokens**, re-measure: latency
  grows with query length and the table above stops at 35.

---

## What is still open

- **The model loads once, at startup, or the numbers above are fiction.** Every
  figure here is steady state with the weights already resident; a per-request
  load costs 0,9 s on top. G.6 has to hold the model in the process.
- **The measurement on the real server has not been made.** Everything about
  the server is either a direct observation of its hardware or a transported
  number with its ratio stated. The definitive figure comes from G.6, with the
  model in the container, and it should be written back here.
- **Query repetition is unknown.** Legal searches repeat heavily, and a cache
  of query vectors would make most searches free — but nothing in this
  collection records what readers typed. `pesquisa.salva` holds only searches a
  user chose to name. A cache is a legitimate mitigation and its hit rate
  cannot be claimed until there is a log to measure.
