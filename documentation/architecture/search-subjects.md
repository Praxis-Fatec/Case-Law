# Searching by subject

What the reader chooses, how the two searches are combined, and what the
combination costs. This is the decision and the evidence for
**SCRUM-254 (G.6)**.

Measured on **2026-11-21** against the local collection of 1.360.708
decisions, with the vectors of [`corpus-vectors.md`](corpus-vectors.md) and
the index of [`vector-index.md`](vector-index.md).

---

## The reader chooses, and the words are not ours

The search box offers two options, and neither of them names a technology:

| On screen | `mode` | What it does |
|---|---|---|
| **Só as minhas palavras** | `exact` | Only decisions that contain what was written. |
| **Palavras e assuntos parecidos** | `subjects` | That same search, plus decisions about the same subject. |

The second is the default, because **SCRUM-250 (G.2)** measured the gain:
taking whichever of the two methods ranked a known-relevant decision better
lifts agreement with the court from 13,27% to 16,99% at ten, and recovers
11,78% of the pairs the word search never reaches at any depth. A reader who
changes nothing gets the better answer, and the exact search is one click away.

---

## One list, ordered by meaning

```
2.240 decisões
──────────────────────────────────────────────
  [ OVERBOOKING…       muito próximo • assunto parecido ]
  [ CANCELAMENTO…      muito próximo • assunto parecido ]
  [ INSCRIÇÃO INDEVIDA… muito próximo ]
  [ …                  próximo ]
```

In `mode=subjects` the word search and the subject search become **one list,
closest in meaning first**, whatever brought each decision there. A decision
the word search never returns carries `by_subject`, and that is the only thing
separating the two origins on screen.

**The first design kept them apart**, with the subject decisions in a block
below. It was replaced because a reader reads a page top to bottom: a block
underneath reads as "less relevant", and a `muito próximo` sitting below a
list that is not ordered by proximity at all invites exactly the wrong
inference.

### Two phases, and the second never repeats the first

```
1.  as mais próximas em sentido        ← ordered by distance, any origin
2.  o resto, pela palavra              ← skipping everything phase 1 served
```

**Phase one is every decision within the floor**, whether or not it carries
the words typed. A decision the word search also finds is not excluded from
it — it takes the place its distance earns, and simply carries no
`by_subject`. Phase two is the search as it always was, minus what phase one
already served.

The depth is `SEMANTIC_DEPTH = 500` neighbours before the two floors, which is
twenty-five screens and further than anyone pages; `hnsw.ef_search` caps at
1000 in any case.

**The boundary between the phases falls inside a page as often as not.** A
page that starts in phase one and runs out of close decisions is filled from
phase two rather than arriving short, and phase two's offset counts from the
first decision phase one did not serve. Without both, a page comes back with
two results and the next one starts crooked — which is exactly what the first
attempt did on `recurso`.

Measured over the whole collection:

| Query | By word | Widened | Phase one |
|---|---:|---:|---:|
| `recurso` | 967.143 | 967.143 | 2 |
| `dano moral` | 30.799 | 30.799 | 0 |
| `demora no voo` | 127 | 233 | 106 |
| `dano moral por inscrição indevida` | 2.230 | 2.351 | 121 |

**A short query is far from everything.** Two words against a whole ementa
produce a large distance whatever the result is, which is why `dano moral` has
not one decision within the floor and falls back to the word search entirely,
while `dano moral por inscrição indevida` has 6.215. The rule turns that into
a feature: the more the reader says, the more meaning has to work with, and
the less they say the more the search behaves exactly as it always did.

Four pages of each of those four searches were read back: eighty distinct
decisions every time, none repeated.

---

## Three things narrow what meaning may add, and each was measured

### It never repeats what the word search already found

A decision that matches the query is excluded outright. The block exists to
show what the other list cannot.

This produces a property nobody programmed: **the block appears only where it
is needed.** A search for `recurso` or `dano moral` comes back with an empty
block, because the decisions nearest in meaning to those words also contain
them. A search for `demora no voo` comes back with ten.

### A floor on distance, measured over queries and not over documents

The vector search always has a nearest neighbour. A question about something
the collection does not cover still gets ten decisions back, and they look
exactly like an answer. So anything past a distance is dropped.

**The first floor was wrong, and the way it was wrong is worth recording.**
It was taken from the pairs of **documents** in the G.1 evaluation set, where
the court's own similars sit at a median distance of 0,258 and a p90 of 0,378,
against 0,437 for random pairs — which suggested 0,35. Applied to the search
box it returned nothing at all. A six-token question is further from a full
ementa than two ementas are from each other, and the air-travel decisions that
the feature exists to find sat at 0,384 to 0,391 — just outside.

Measured again, over queries:

| Query | Nearest | Tenth |
|---|---:|---:|
| `dano moral por inscricao indevida` | 0,238 | 0,260 |
| `prescricao intercorrente execucao fiscal` | 0,250 | 0,257 |
| `juros abusivos em contrato bancario` | 0,252 | 0,282 |
| `acidente de trabalho responsabilidade do empregador` | 0,257 | 0,296 |
| `guarda compartilhada de menor` | 0,298 | 0,329 |
| `demora no voo` | 0,375 | **0,391** |
| | | |
| *`como trocar o pneu do carro`* | **0,460** | 0,497 |
| *`flurbinator de quimbondo`* | 0,587 | 0,598 |
| *`qwertyuiop asdfghjkl`* | 0,618 | 0,664 |
| *`receita de bolo de cenoura com cobertura`* | 0,660 | 0,703 |

No legal question passed 0,391 and no question from outside the law started
below 0,460. **The floor is 0,42**, in the gap. It is a floor on an already
ranked list, not a selector: a cut that tried to be the selector would be
useless, because at 0,35 — measured on the document pairs — 12,7% of random
pairs pass, and 12,7% of 1,36 million decisions is 173 thousand.

### A floor on the ementa's length

The first run of this search answered `demora no voo` with these, ahead of
every real decision:

```
Demora. Pedido prejudicado.
Demora na instrução já sanada.
Demora provocada pela defesa.
```

When the ementa is three words long, the meaning it carries is the meaning of
one of them, and that one word outranks whole decisions about air transport.
The collection holds **6.426 ementas under 40 characters and 69.130 under
120**, 5,1% of it — the placeholders `stf-source.md` records. The floor is
120 characters.

---

## What it costs

Median of five, after a warm-up, over the whole local collection:

| Query | `exact` | `subjects` | The block | Results |
|---|---:|---:|---:|---:|
| `recurso` | 33,6 ms | 66,5 ms | **+32,9 ms** | 967.143 |
| `dano moral` | 158,3 ms | 197,8 ms | **+39,5 ms** | 30.799 |
| `demora no voo` | 8,7 ms | 48,3 ms | **+39,6 ms** | 127 |

**The US A ceiling is 2 s, and the broadest search spends 3,3% of it.** The
block costs a flat ~35 ms regardless of how many decisions the word search
found, because it is one query embedding plus one index read.

On the server the embedding is estimated at 32 to 215 ms rather than the ~20 ms
it costs here — the range and its method are in
[`query-embedding.md`](query-embedding.md) — so the worst case there is about
260 ms, or 13% of the ceiling.

---

## A capital letter decided whether the feature worked

The query is folded to lower case before it is embedded, and that is not
cosmetic:

| Typed | Cosine with the lower-case form | Nearest decision | |
|---|---:|---:|---|
| `demora no voo` | — | 0,375 | inside the floor |
| `demora no vôo` | 0,9511 | 0,354 | inside |
| **`Demora no voo`** | **0,7743** | **0,565** | **cut** |
| **`DEMORA NO VOO`** | **0,6891** | **0,471** | **cut** |

A capital letter is what anybody types, and without the fold it decided
whether a reader got the feature at all: 233 results against 127, fourteen
decisions against none. The longer query barely moves — 0,238, 0,240, 0,262
across the three forms — because this is the short-query problem again: a
three-word query sits so close to the floor that any perturbation tips it over.

Lower case also measured **closer to the collection in nine of twelve forms**,
which is backwards given the ementas are mostly upper case, and the reason it
is measured rather than assumed.

## Ordering by date turns meaning off

Meaning earns its place here by ordering. A reader who picks `date` has said
what the order is, so the semantic phase does not run and the list is the
search as it always was. Without this the screen answered `date` with
decisions in order of proximity — 2007, 2025, 2026, 2025 — while the control
said it was sorting by date.

## When it is off, the search is the old search

Four states return the plain word search, and none of them is an error:

| | |
|---|---|
| The reader chose **Palavras exatas** | the model is never loaded |
| This is not the first page | no vector search is run |
| `core.decisao_vetor` is not published yet | probed per request, like `core.busca_ampla` |
| `EMBEDDING_MODEL_PATH` is unset or will not load | logged once, then answered by word |

The last two matter operationally. A deploy can land before the base that goes
with it — it happened once this sprint — and a server without the model is a
server that answers the way it did before the feature existed. That is the
same bargain `google_api_key` already makes for reading a thesis, and the
reason `test_busca_por_assunto.py` pins both.

---

## Running it locally

The publish creates `core.decisao_vetor` on the environments. On a development
machine the vectors live in `vetor.decisao`, so the view that stands in for it
is one statement:

```sql
CREATE OR REPLACE VIEW core.decisao_vetor AS
  SELECT fonte_codigo, identificador_fonte, modelo, revisao, vetor
  FROM vetor.decisao;
```

And the model the API loads is produced by the pipeline, not by hand:

```bash
uv run --group embeddings python embed_corpus.py --serving-model ./modelo
export EMBEDDING_MODEL_PATH=$PWD/modelo
```

---

## What is still open

- **Nothing here measures agreement with the court.** The cost is measured and
  the behaviour is pinned, but whether the block actually surfaces decisions a
  reader wanted is the G.1 measurement re-run end to end, which belongs to
  **SCRUM-256 (G.8)** along with the proof that the word search did not change.
- **The block respects the screen's filters**, and the candidate step reads
  500 before applying them. A narrow filter can therefore return fewer than
  ten — or none — while matching decisions exist further down. Measuring how
  often that happens needs a filter the readers actually use, and there is no
  log of that yet.
- **Query repetition is unknown.** Legal searches repeat, and a cache of query
  vectors would make most of them free — but nothing records what readers
  typed, so the hit rate cannot be claimed.

---

## On screen — SCRUM-255 (G.7)

The choice sits beside the filters, in the words the reader uses:

```
[ Só as minhas palavras | Palavras e assuntos parecidos ]  [ Filtros ]  [ Pesquisar ]
```

Nothing names a technology. "Semântico", "vetorial" and "léxico" are words for
the people who built it, and the people who use it are lawyers.

### How close, in words rather than in a number

Every decision answered in `mode=subjects` carries a proximity label — **muito
próximo**, **próximo** or **relacionado** — and the labels are the thirds of
the range the floor keeps, measured over ten real legal queries: the 100
results they returned split at **0,272** and **0,326**.

**It is deliberately not a percentage.** The cosine the search ranks by does
not read as one: the air-travel decisions that answer *demora no voo*
perfectly sit at a distance of 0,384, which as a "similarity" would print as
**61%** — a number a reader would take for a poor match. Three named bands say
what the figure means; a percentage would say something false.

**The spread is between queries, not within one.** Over those ten queries,
*dano moral por inscrição indevida* returned everything between 0,238 and
0,260 while *demora no voo* returned everything between 0,375 and 0,391. So
the label rarely separates one result from its neighbour; what it separates is
one search from another. That is the useful reading: it says how well the
collection covers the question, decision by decision.

**Only the block carries it, and the first attempt did not.** A decision found
by its words can sit any distance away, because nothing filtered it by
distance: measured on the first page of three searches, `recurso` ranges from
0,483 to 0,640 and `dano moral` from 0,540 to 0,632 — every one of the twelve
past the 0,42 floor. Labelling them `relacionado` claimed a kinship the
measurement denies. The deeper reason is that a short query is far from
everything: two words against a whole ementa produce a large distance whatever
the result is, so on that list the label would report how short the question
was rather than how close the answer is. Past the floor `_band` returns
nothing, and `test_busca_por_assunto.py` pins the boundary.

Each decision in the block also carries a **`assunto parecido`** tag in its header,
and the block itself carries the one-line explanation the story asks for:
*estas decisões não aparecem na busca pelas palavras que você escreveu, mas
tratam do mesmo tema.* A decision in the main list never carries the tag, so
the two kinds of result are told apart by the card and not only by where it
sits.

**The indicator drawer always asks for `exact`.** It lists the documents behind
a number and never renders the block, so asking for it would spend a query
embedding and a vector search per opening to throw the answer away.

### Two things the frontend had to learn

**The results buffer fetches two screens at once.** `PAGES_PER_BLOCK` is 2, so
the API is asked for page 1 at `page_size` 40 and the answer is sliced into
screens 1 and 2. The subject block belongs to the request, not to the slice,
so `sliceFor` hands it to the first screen and an empty list to the second —
otherwise the same ten decisions would appear again under page 2.

**A tag beside the date is not free naming.** The first version wrapped the
date in `decision-result-card__meta`, which already exists on the card and
already holds the deliberation; `querySelector` returned the new one and a
test about reporting a classification started reading the wrong element. The
wrapper is `__flags`.
