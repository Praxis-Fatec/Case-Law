# Doctrine sources

Which repositories of legal scholarship this project can harvest, what each one
answers today, and the rule that decides what may be collected at all.

Tested on **2026-10-24**, from a residential connection in Brazil, with an
identified `User-Agent` and one request at a time. The figures the sprint was
planned on came from a test on **2026-10-05**; three of them no longer hold,
which is why this document exists rather than a line in a card.

---

## The rule, before the sources

This is the scope of the story and it does not depend on which source answers.

1. **Only sets the repository itself declares to be open access.** Not our
   judgement about a work — the library's own classification of it.
2. **Only metadata and the link back.** Never the full text, never the PDF.
3. **`dc:rights` is respected** wherever the record carries it.

The tool points at scholarship; it does not redistribute it. That holds even
for open access, because open to read is not the same as open to redistribute.

**Which of the two carries the weight, measured.** Over a sample of 798 records
read on 25/10/2026, `dc:rights` is present in **5,8%**. Requiring it would leave
94% of the open collection out, so the collection is the guarantee and the field
is the exception — and where the two disagree, the field wins. One record filed
in Acesso Aberto declares `Restricted access` in its own `dc:rights`, and it
does not enter the core. The rule is an allow list: an unknown rights statement
excludes the work rather than including it.

What the same sample says about the fields, which is what decides how doctrine
can be matched to a decision at all:

| Field | Coverage |
|---|---:|
| title, author, date, type, identifier, format | 100% |
| `dc:language` | 99,4% |
| `dc:publisher` | 74,6% |
| `dc:subject` | 54,8% |
| `dc:description` — the abstract | 31,8% |
| `dc:relation` | 16,9% |
| `dc:rights` | 5,8% |

---

## BDJur — Biblioteca Digital do STJ

| | |
|---|---|
| Endpoint | `https://bdjur.stj.jus.br/server/oai/request` |
| 2026-10-05 | OAI-PMH 2.0 working, 13 formats, records since 2004 |
| **2026-10-24** | **HTTP 403 — automated access refused** |

The response is a JavaScript challenge page, and it names its author:

> Verificação automática em andamento. Enable JavaScript and cookies to continue
> — **Coordenadoria de Segurança e Defesa Cibernética (CSID/STJ)**

Three consecutive requests, 403 each time. The refusal covers the **whole
host**, not the harvesting path: `/`, `/server/api` and `/oai/request` all
answer 403.

This is a deliberate measure, not an outage, and it is not to be worked around.

**It lets a person through.** Opened in a browser on 2026-10-24, the endpoint
answers normally, which confirms the challenge is doing what it is for rather
than refusing the public. What a browser read that day:

| | |
|---|---|
| Repository | BDJur, protocol 2.0, DSpace |
| **Contact** | **`bdjur@stj.jus.br`** |
| Earliest record | 2004-04-06 13:40:01 |
| Granularity | `YYYY-MM-DD hh:mm:ss` — incremental harvesting by `from`/`until` |
| Sets | 57 |

That contact is published by the protocol itself and belongs to the library,
not to the security team. It is the address to ask for harvesting access.

**Sets the sprint was planned on**, recorded here so the request to the STJ can
name them:

```
com_2011_2   Doutrina                    83.374 registros
col_2011_8   Artigos de Acesso Aberto    20.597 registros   ← 20.504 em 05/10
col_2011_9   Artigos de Acesso Restrito  ← never collected
```

Confirmed in the browser on 2026-10-24: the three codes still name the same
sets, and the open-access one has grown by 93 records since the planning test.
Of the 57 sets the repository publishes, these are the ones this story needs.

That the STJ separates open from restricted into distinct collections is what
settles the copyright question the client asked about: collecting only the
first is the library's classification, not ours.

> **One trap worth keeping.** The endpoint is `/server/oai/request`, not
> `/oai/request`. In DSpace 7 the shorter path answers HTTP 200 with the
> Angular shell — success-shaped, and not OAI-PMH.

---

## BDTD — now Oasisbr, of the IBICT

| | |
|---|---|
| Old endpoint | `https://bdtd.ibict.br/vufind/OAI/Server` → **HTTP 503** |
| Current host | `https://oasisbr.ibict.br/vufind/OAI/Server` → **HTTP 200, and not OAI** |

The 200 is the same shape of trap as the DSpace one above. The body is 1.697
bytes of HTML titled **"Verificando conexão | Oasisbr"** — an anti-bot
challenge, served with a success code.

An identified `User-Agent` and a modest request rate do not get past it, which
the subtask asked to be measured. Two other addresses were tried and answer
404: `oasisbr.ibict.br/oai` and `bdtd.ibict.br/oai/request`.

**Verdict: does not enter this sprint.** Not because it was hard, but because
the protocol the client named is behind a challenge that only a browser
answers. An institutional harvesting channel at the IBICT would change this,
and is worth asking for — the content is theses and dissertations, which is
what the client wanted from it.

---

## SciELO

| | |
|---|---|
| Old OAI endpoint | `https://www.scielo.br/oai/scielo-oai.php` → **HTTP 404, gone** |
| **Current API** | `https://articlemeta.scielo.org/api/v1/` → **HTTP 200, JSON** |

ArticleMeta is the replacement, and it answers. It is not OAI-PMH — it is a
REST API over the same corpus, with identifiers, journals and articles.

**What it holds for this project:**

```
36 collections, Brazil among them (scl)
427 journals in the Brazilian collection
 6 of them are law journals by title
```

| ISSN | Journal | Articles |
|---|---|---:|
| 2179-8966 | Revista Direito e Práxis | 1.014 |
| 1808-2432 | Revista Direito GV | 660 |
| 2525-510X | Revista Brasileira de Direito Processual Penal | 211 |
| 1806-6445 | Sur. Revista Internacional de Direitos Humanos | 106 |
| 2179-8699 | Veredas do Direito | 88 |
| 2317-7721 | Revista de Direito da Cidade | 46 |
| | **Total** | **2.125** |

**Verdict: reachable, and small.** 2.125 articles against the 83.374 records of
the BDJur's Doutrina set is **2,5%**. SciELO is a complement to the BDJur, not
a replacement for it — a story built on it alone would match a thesis against a
corpus two orders of magnitude smaller than the one the client named.

Open access is not in question here: SciELO publishes under Creative Commons by
construction. The rule above still applies — metadata and the link, never the
article.

---

## Where this leaves the story

The subtask that recommended the BDJur for this sprint did so because it was
confirmed working. It is not working now, and the reason is a decision of the
STJ's, not a defect to fix.

Three ways forward, and the choice belongs with the client, not with the team:

| | What it costs |
|---|---|
| **Ask the STJ for harvesting access** | The right route, and it has a response time the sprint may not have |
| **Build on SciELO instead** | Reachable today, and 2,5% of the corpus the client named — a change of scope, not a substitution |
| **Re-test before deciding** | The STJ's open data portal answered HTTP 504 on the same day, so some of this may be transient |

What does not change either way is the rule at the top: open-access sets only,
metadata and the link only, `dc:rights` respected.
