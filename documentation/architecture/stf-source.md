# The STF as a source

`SCRUM-193` asks for the STF's decisions in the base. The STJ arrived through a
published open-data product, and the story assumes the STF has one too. This
document is the subtask that comes before the connector: what the STF actually
publishes, what each endpoint answers, and which of them can carry a collection.

Surveyed on 18/11/2026. Every status code below was read from the service, not
from documentation about it.

---

## The short answer

The STF has a working jurisprudence API. It is not an open-data product.

Everything the Tribunal publishes openly is either statistics without the text
of the decisions, or a service restricted to the courts of the country by a
signed accession term. The search that holds the acórdãos is served by a private
backend built for the Tribunal's own web page, with no documentation, no licence
and no terms of use.

That is the asymmetry with the STJ, and it is the whole of the problem: the
STJ's CKAN declares Creative Commons Attribution over files meant to be
downloaded. The STF declares nothing, because it never offered the data.

---

## Hosts

| Host | Answer |
|---|---|
| `api.stf.jus.br` | does not resolve |
| `dadosabertos.stf.jus.br` | does not resolve |
| `opendata.stf.jus.br` | does not resolve |
| `servicos.stf.jus.br` | does not resolve |
| `api-publica.stf.jus.br` | does not resolve |
| `estatisticas.stf.jus.br` | does not resolve |
| `precedentes.stf.jus.br` | does not resolve |
| `dados.stf.jus.br` | resolves · 403 nginx, every path |
| `ws.stf.jus.br` | resolves · 403 nginx, every path |
| `transparencia.stf.jus.br` | 403 to a client that is not a browser |
| `portal.stf.jus.br/dadosabertos` | 200, and the body is the portal's own error page |

`dados.stf.jus.br` and `ws.stf.jus.br` exist and refuse everyone. `ws` is where
the integration described below is served; the refusal is the accession rule
enforced at the door.

## The jurisprudence API

`jurisprudencia.stf.jus.br` is an Angular application. Its bundle carries the
route map:

| Route | Purpose |
|---|---|
| `POST /api/search/search` | search, in Elasticsearch syntax |
| `GET /api/search/get/{id}` | one document by id |
| `POST /api/search/export` | export of a result set |
| `GET /api/admin/loadConfig` | configuration |
| `/api/favorite` · `/api/folder` · `/api/user` · `/api/log_doc_det_action` | favourites, folders, sign-in, click logging |

`GET /api/admin/loadConfig` answers 200 without authentication and returns the
sitting ministers. `GET /api/` answers `{"detail":"Not Found"}`, which is
FastAPI; the service sits behind an F5 Volterra ADC.

Being FastAPI, it would document itself if the Tribunal wanted it to:

```
/api/openapi.json   404
/api/docs           404
/api/redoc          404
```

They are turned off. Together with `favorite`, `folder` and `user`, that settles
what this is: the private backend of a web page, not an interface offered to
anyone. Its configuration also names `https://juris.api.digesto.com.br` as an
external API — the Tribunal's own search calls a commercial supplier.

Consuming it would repeat the BDJur: an endpoint that answered automated access
until the court's cyber-security coordination stopped it, after which access had
to be requested by e-mail.

## Corte Aberta

Instituted by Resolução 774/2022. Qlik panels at `transparencia.stf.jus.br`,
with CSV and XLSX export of the decision series from 2000 onward, and a data
dictionary.

This is genuinely open data, and it is counts. No ementa, no text. It cannot
feed search, it cannot feed the IDF weight of `core_precedente_judicial`, and it
cannot feed `core_decisao_contraria`, all of which read the decision's words.

## MNI and STF Tribunais

`portal.stf.jus.br/textos/verTexto.asp?servico=processoIntegracaoComoIntegrar`
describes the Tribunal's integration, managed by the Secretaria de Gestão de
Precedentes. It is a real protocol — MNI 2.2.2, the CNJ's national
interoperability model — and it is the wrong direction.

MNI carries Recursos Extraordinários *to* the STF: transmission, resubmission,
return, lowering, declining of competence, electronic summons, petitioning. It
does not serve jurisprudence out of the STF.

Access is by accession, and the accession is not open to a research project: the
applicant must be a Tribunal, Turma Recursal, Vara or Comarca, and the term must
be signed by its President and filed with the Ouvidoria through FALA BR. That is
why `ws.stf.jus.br` answers 403 to everyone.

## DataJud

The CNJ's public API is documented, and its key is published openly in the wiki.
It is the right shape of thing — and the STF is not in it. Among the superior
courts the wiki lists TST, TSE, STJ and STM only. DataJud also carries
*metadados dos processos*, cover data and movements, never the text of a
decision.

## LexML

An SRU API exists at `www.lexml.gov.br/busca/SRU`. It answers with the Senado's
security challenge page rather than records.

## Commercial suppliers

Several index the STF and sell access. Their terms are the obstacle, not the
price. One surveyed supplier forbids, in writing, *"exportação ou cacheamento
substancial da base"* and *"exportar ou cachear a base em escala"*, permitting
queries against the live service instead.

Loading the STF into `raw` and publishing it to the environments is precisely
exporting and caching the base at scale. The free plan does not change that; the
clause is about what is done with the data, not what is paid for it.

## The manual channel

`portal.stf.jus.br/jurisprudencia/pesquisajurisprudenciaexterno.asp` is the
Tribunal's own answer to someone outside asking for jurisprudence: a request
form answered by the Coordenadoria de Pesquisas Judiciárias, `copj@stf.jus.br`,
within fifteen working days, two requests per day.

It is staffed by people and it is the documented channel. It also names the unit
to ask about a collection.

---

## The path taken

Reading the search backend, decided on 18/11/2026. The collector identifies
itself, paces its requests and stops on the first refusal; the survey above is
what it stops with, so whoever meets a 403 finds the channel to ask through
rather than a stack trace.

What that reading costs is recorded here because none of it is visible from the
code alone.

### The contract is inferred, not given

The service wraps the Elasticsearch answer in `result`, beside a search id of
its own. Read as plain Elasticsearch — which is what the route name suggests —
every load reports zero documents **and succeeds**. That is the shape of every
failure to expect here: not an error, but a silent zero.

Paging walks `search_after` over `julgamento_data` and the index's own
`tiebreaker_sort`. The page the court serves uses `from` and `size`, which
Elasticsearch caps at ten thousand; nobody browsing past page one thousand ever
meets that cap, and a load meets it immediately.

### What the base holds

Measured on 18/11/2026. The index serves five bases and the collector reads one:

| base | documents |
|---|---:|
| `acordaos` | 373.191 |
| `decisoes` (monocratic) | 762.031 |
| `novo_informativo` | 11.654 |
| `sumulas` | 799 |
| `acordaos_externos` | 0 |

The 799 sumulas are worth a story of their own: the STJ's are reconstructed from
transcriptions in the collection, and the STF publishes its own, structured.

### Half the collection predates the old start

The oldest acordao is from **27/04/1892**, and **189.435 of the 373.189 — 50,8%
— precede 1989**, which is where `core.decisao` began, the STJ having been
created that year. Left there, those decisions would load into `raw` and vanish
in the transformation without an error or a missing line in any log. The start
moved to 1892, and the three models derived per decision moved with it, so that
no decision exists in the collection without ever yielding a reference or a
precedent.

### What had to be measured to transform it

Sampled across every band of years, 2.000 to 2.500 records per question:

- **The ementa is never empty, and 8,1% of it is the sentence "Acórdão sem
  ementa."** The audit `ementa_nao_vazia` approves it — the field has text. It
  is a placeholder, and indexed it would answer a search for the word "ementa"
  with a decision that has none. Excluded by its own rule.
- **The class is named by the whole abbreviated ladder**, as in `EMB.DECL.NO
  AG.REG.NO AGRAVO DE INSTRUMENTO`, and the class is the outermost of them. Five
  abbreviations, a leading ordinal and the first connective resolve **99,1%** of
  the sampled acordaos. The rest are incidents the CNJ does not classify —
  referendo, diligência, repercussão geral — and keep no code.
- **The CNJ table has a subtree of the STF's own**, root 1310, 67 classes.
  Without preferring it, `Agravo Regimental` resolves to 206, which is the civil
  one. The screen would show a plausible label from another court.
- **The address of the inteiro teor changes form with the era**: 79,9% open by
  `numero` and `classe`, 20,1% by `idDocumento`. The parameter's own name varies,
  so the token is the whole query string and the seed's template keeps only the
  path.
- **Absence is common in the old records**: 19,2% carry no judging body, 21,0% no
  publication date, 0,2% no reporting judge. All of it arrives as absence.

## What is still open

- The load itself has not been run. The collector and the transformation are
  tested against saved answers and the minimal collection; the 373.191 acordaos
  have not been written to `raw`.
- Entering 373.191 decisions into a collection of 991.163 changes the divisor of
  every IDF weight in `core.precedente_judicial`, and with it every pair in
  `core.decisao_contraria`. Both need rebuilding and republishing, and the
  numbers recorded in `opposing-decisions.md` need measuring again.
- The 799 sumulas and the 762.031 monocratic decisions are in reach of the same
  collector and belong to no story yet.
- Nothing has been asked of the COPJ. The channel is recorded above, and asking
  costs a message.
