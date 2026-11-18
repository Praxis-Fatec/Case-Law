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

The first measurements here were taken from samples, and they were wrong. The
sampler walked the first pages of each band of years over a date-ascending sort,
so it always read the oldest records of each band — the sparsest ones. It
reported 8,1% of the ementas as placeholders where the base has 0,97%, and 19,2%
without a judging body where the base has 6,8%.

The figures below are counted over all 373.178 acordaos after the load, not
sampled. The lesson is worth keeping: on a source sorted by date, the first page
of a window is not a sample of that window.

- **"Acórdão sem ementa." is the source's own placeholder**: 3.608 records,
  0,97%, plus 16 whose ementa is genuinely empty. The audit `ementa_nao_vazia`
  approves the placeholder — the field has text. Indexed, it would answer a
  search for the word "ementa" with a decision that has none. Excluded by its
  own rule.
- **The class is named by the whole abbreviated ladder**, as in `EMB.DECL.NO
  AG.REG.NO AGRAVO DE INSTRUMENTO`, and the class is the outermost of them. Five
  abbreviations, a leading ordinal and the first connective resolve **369.273 of
  373.178 — 98,95%**. The remaining 3.905 are incidents the CNJ does not
  classify — referendo, diligência, repercussão geral — and keep no code.
- **The CNJ table has a subtree of the STF's own**, root 1310, 67 classes.
  Without preferring it, `Agravo Regimental` resolves to 206, which is the civil
  one. The screen would show a plausible label from another court.
- **The address of the inteiro teor changes form with the era**: 68,0% open by
  `numero` and `classe`, 32,0% by `idDocumento`, and none is missing. The
  parameter's own name varies, so the token is the whole query string and the
  seed's template keeps only the path.
- **Absence is concentrated in the old records**: 6,8% carry no judging body,
  6,8% no publication date, 0,1% no reporting judge. All of it arrives as
  absence.

### The walk had a silent hole

The index advertises a field called `tiebreaker_sort`, and the court's own page
sorts by it. The field does not exist: Elasticsearch answers `Long.MAX` for every
document. The sort tuple is then unique only in its date, and `search_after`
means "after this date" — every other decision judged that day is skipped.

Nothing fails. The walk ends early and reports success. Measured over 2026 before
the fix: **3.593 of 11.568 acordaos**, a third of the window, loaded without a
warning. The walk now sorts by `julgamento_data` and `id`, which is the
document's own key, and reads 11.568 of 11.568.

This is the shape every failure of this source will take, and the reason the
collector is tested against its contract rather than trusted to it.

### The load

Run on 18/11/2026: **373.178 acordaos**, every id distinct, from **27/04/1892 to
16/11/2026**. Beside them the service's repeated fields landed in child tables of
their own — **677.943 legislative references** and 382.423 reporting-judge
entries. **189.435 of the acordaos, 50,8%, precede 1989.**

### Into the collection

Of the 373.178 acordaos read, **369.545 became decisions**. The whole difference
is accounted for, which is the point of listing it:

| | |
|---|---:|
| read from the source | 373.178 |
| ementa is the literal `Acórdão sem ementa.` | −3.608 |
| ementa empty | −16 |
| neither a judgment nor a publication date | −9 |
| **in the collection** | **369.545** |

The placeholder ementas are dropped because the ementa is the search target and
the only text the screen can show: a result whose body reads "Acórdão sem
ementa." is a row that matches nothing and says nothing. The nine dateless ones
are a real loss rather than a cleanup — `CJ 1585`, `AI 6093`, `MS 285` and six
others are decisions with real holdings, and every filter and sort in the
product is by date, so a decision with no date has no place in the collection as
it is built. They stay in `raw`, and `core.cobertura_fonte` reports 44 items
with no date on the STF's row so the gap is counted rather than implied.

With them the collection goes from 991.163 decisions to **1.360.708**, and its
floor from 1989 to **27/04/1892**.

### Three guards that could not have let it in

Adding a court exercised the pipeline in a way that nothing had since the audits
were written, and three of them turned out to be checking something other than
what they claimed. All three failed the same way: a model audit is applied by
SQLMesh **only to the window just written**, and it resolves **only the models
the audited model itself reads**. Break either rule and the audit silently
compares the wrong things.

| audit | what it actually checked | effect |
|---|---|---|
| `carga_de_fonte_conhecida` | joined `core.fonte`, which `core.carga` does not read, so it resolved to the **previously published** catalogue | a run carrying a source that was not in the last published catalogue always failed — **no new source could ever enter**, and the replan failed too, because promotion needs the plan to pass |
| `citacao_com_volume` | a floor of 300.000 citations, applied to one window | failed every incremental load; a week has hundreds of citations, not hundreds of thousands |
| `citacao_com_alcance` | the window's decisions against 24 % of the **whole** collection | could not pass incrementally at all |

All three are standalone audits now, which is the pattern
`referencia_reconhecida_no_limite` had already established in the same file for
the same reason. `citacao_com_alcance`'s floor also had to move, and that one is
not a mechanical fix:

| source | decisions | cite a precedent |
|---|---:|---:|
| STJ | 876.996 | 30,9 % |
| TJDFT | 114.167 | 24,7 % |
| STF | 369.545 | **11,2 %** |
| collection | 1.360.708 | 25,04 % |

The STF cites fewer because its collection reaches back to 1892 and citing a
súmula is a recent drafting practice — the extraction is not failing. Against a
floor of 24 % that left 1,04 points of headroom, so the floor is 15 % now: a
collapse of the extraction takes the rate to zero, and losing the STJ alone,
which carries 59 % of the links, takes it to 5,1 %. A floor that has to be
recalibrated every time a source is added is a floor that stops guarding.

A fourth defect was waiting on luck rather than on the STF.
`core.decisao_contraria_candidata` is the longest model name in the project; its
physical table is 45 characters, SQLMesh appends `_schema_tmp` when building a
FULL model because post-statements run against the temporary table before the
swap, and the index suffix `_leitura` closed at **64** — one over Postgres's
limit, which SQLMesh refuses rather than truncating. Earlier snapshot versions
ended in nine digits and fit in 63 by one character. Nothing in the model
changed to break it; the number SQLMesh drew did. The index name is composed
from the version alone now.

### What the rebuild moved

| | before | after |
|---|---:|---:|
| decisions | 991.163 | 1.360.708 |
| period | 19/02/1989 → 17/09/2026 | 27/04/1892 → 16/11/2026 |
| citation links | 375.189 | 459.800 |
| reconstructed súmulas | 340 | 383 |
| judicial vocabulary | 540.103 terms | 592.962 |
| contrary pairs | 3.325.818 | 6.323.556 |
| decisions with a contrary | 50.925 | 61.644 |

The 43 new súmulas came for free: holdings that only the STF's own acordaos
transcribe, found by the same reconstruction rule. The contrary pairs nearly
doubled, and `documentation/architecture/opposing-decisions.md` carries the
re-measured distribution.

## What is still open

- **The STF yields no legislative references.** It publishes them in the same
  fixed format the STJ does, with a hyphen where the STJ uses a colon —
  `LEG-FED DEC-029784 ANO-1951 ART-00002` against
  `LEG:FED DEL:003365 ANO:1941 ART:00026`. Of its 677.943 citation lines,
  565.445 (83,4 %) carry a readable header and 326.293 (48,1 %) name an article.
  But `core.referencia_legislativa` is scoped `WHERE fonte_codigo =
  'stj-espelhos'` and joins the STJ's own child table, so every STF decision
  shows an empty "legislação citada". That is a feature of its own, with four
  audits and its own document; it belongs to no story yet.
- **The STF declares 108.060 citations of its own súmulas** in that same
  structured field (`LEG-FED SUMSTF-000279`), plus 1.873 TST and 1.138 STJ.
  `core.decisao_precedente` infers citations with a regular expression over the
  ementa; here the court states them. Reading the declared field would be a
  stronger signal than the inference, and it is measurable against it.
- **The STF's temas do not resolve.** 12,9 % of tema citations match a row in
  `core.precedente`, against 97,3 % of súmula citations, because the catalogue
  comes from the STJ's open data portal and the STF publishes no equivalent.
  The links are kept and marked unresolved, which is what makes the size of the
  gap visible.
- The 799 sumulas and the 762.031 monocratic decisions are in reach of the same
  collector and belong to no story yet. The monocratic ones would roughly
  double the collection, and would take the precedent-citation rate on their
  own to near 18 % — which the floor above already allows for.
- `core.decisao_contraria_candidata` is **1.788 MB** against the 461 MB that
  SCRUM-205 measured. The table is built, audited and read within one execution
  and is not published, but the growth is worth watching.
- Nothing has been asked of the COPJ. The channel is recorded above, and asking
  costs a message.
