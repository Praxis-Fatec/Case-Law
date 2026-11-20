# The BNP as a source

`SCRUM-194` asks whether a súmula is still in force. The collection cannot say:
`core.precedente` reconstructs enunciados from how decisions transcribe them,
and a transcription carries no standing, so `situacao` is null for all 383
súmulas on purpose. Presenting a cancelled súmula as current is the error the
story exists to avoid.

The BNP — Banco Nacional de Precedentes, the CNJ's register fed by the courts
under Resolução CNJ 444/2022 — is the only public register that carries a
situação for every entry. This document is the subtask that comes before the
connector: what is reachable, what the register holds, and whether its coverage
can replace the reconstructed enunciados.

Surveyed on 20/11/2026. Every figure below was counted over the 4.457 records
the register actually returned, not sampled, and every status code was read from
the service.

---

## The short answer

The register is reachable, complete enough to replace the reconstruction, and
its interface has four traps that each fail quietly.

Coverage is not the problem the story expected. The expected problem was missing
text: `Súmula Vinculante 1` comes back with `tese` reading `não informado`. That
is real, and it is not absence — **the field that carries the text depends on
the court and the species**. Read both fields, and not one of the 4.457 records
in scope lacks a text.

What the survey did find is worse than a gap, and it is on our side: **23 of the
1.525 reconstructed enunciados carry another precedent's words**, 18 of them
súmulas attributed to the wrong number. The reconstruction was right 87% of the
time and silently wrong the rest.

---

## The two interfaces

| Interface | Answer |
|---|---|
| `bnp-sempj.cloud.pje.jus.br/v1` · the documented BNP API | **401** to every path, including its own `api-docs` |
| `bnp-sempj.cloud.pje.jus.br/swagger-ui` | 200 · the UI loads and cannot read its own spec |
| `pangeabnp.pdpj.jus.br/api/v1/precedentes` | **200** · no authentication |
| `pangeabnp.pdpj.jus.br/api/v1/parametros` | 200 · the filter vocabulary |

The documented interface is behind the PDPJ's single sign-on and needs a
certificate the project does not have. What is open is the API the Pangea
portal's own pages call, and the connector reads that. The portal is the CNJ's
public face for the BNP, so this is published data served without credentials —
but it is an interface built for one web page, not a contract offered to anyone,
and it can change without notice. The connector is therefore tested against the
contract rather than trusted to it.

## The contract, and its four traps

The request is a POST with a body of `{"filtro": {...}}`. Each trap below cost
a debugging round, and each one fails without naming its cause.

**The filter travels wrapped, and whole.** A bare filter object answers 400. So
does a filter carrying only the fields that matter. The portal sends every field
of its own default object on every search, and only that is accepted. The 400
answers `Requisição inválida` as `text/html`, with no field name — there is
nothing to debug from the response.

**`orgaos` and `tipos` must both carry a value.** Empty lists are the 400 above.
This is the opposite of what a collector wants, because there is no way to ask
for everything: the whole register is reachable only by iterating the pairs.

**A sigla outside the vocabulary answers 200 with `total: 0`.** This is the
dangerous one. `tipos: ["Súmula"]` — the description, which is what the
`/parametros` payload shows beside each sigla — returns an empty result set and
no error, where `tipos: ["SUM"]` returns 734. A renamed species would reach the
collection as a court that stopped having súmulas, and every guard downstream
would approve it, because an empty source is not an invalid one. The connector
reads `/parametros` and checks its own vocabulary before loading, so a rename
fails by name.

**`cancelados` defaults to false, and hides exactly the rows this is for.** The
portal's checkbox is unchecked, and with it 257 cancelled precedents are absent
from every answer. A connector that copied the portal's defaults would have
collected the register and still been unable to say that a súmula was cancelled.
It is true here.

`pagina` is 1-based. `tamanhoPagina` of 100 is accepted and is what the
connector uses, which puts the whole scope in 45 requests, paced one per second.

## What the register holds

The scope is súmula, súmula vinculante and the two courts' temas. The other 16
species the register carries — notas técnicas, controvérsias, the concentrated
control actions — are not precedents this collection cites by number, and
`core.precedente` has no shape for them.

| Court | Species | Sigla | Records | Numbering |
|---|---|---|---:|---|
| STF | Súmula | `SUM` | 734 | 1–736, missing 152 and 274 |
| STF | Súmula Vinculante | `SV` | 62 | 1–62, complete |
| STF | Tema de Repercussão Geral | `RG` | 1.501 | 1–1.501, complete |
| STJ | Súmula | `SUM` | 676 | 1–676, complete |
| STJ | Recurso Especial Repetitivo | `RR` | 1.484 | 1–1.487, missing 3 |

`nr` is unique within a court and species, which is the same grain
`core.precedente` already keys on. `ultimaAtualizacao` spans 02/02/2016 to
19/11/2026 — the register is live, and the newest row is from the day before
this survey.

Three fields are attached to a minority of records: `suspensoes` on 1.323,
`processosParadigma` on 2.982, `historico` on 72 — a list of
`{dataCriacao, situacao}` pairs. `alertaSituacao` appears on exactly the 257
cancelled rows and reads `cancelado`, which `situacao` already says.

## The measurement the subtask asks for

The rate of records without text, by court and species — reading `tese`, the
field whose name says it holds the thesis:

| Court / species | Records | `tese` absent | `questao` absent | both absent |
|---|---:|---:|---:|---:|
| STF / `SUM` | 734 | **734 · 100%** | 0 | 0 |
| STF / `SV` | 62 | **62 · 100%** | 0 | 0 |
| STF / `RG` | 1.501 | 183 · 12,2% | 0 | 0 |
| STJ / `SUM` | 676 | 0 | **676 · 100%** | 0 |
| STJ / `RR` | 1.484 | 323 · 21,8% | 1 · 0,1% | 0 |
| **Total** | **4.457** | **1.302 · 29,2%** | **677 · 15,2%** | **0** |

The last column is the finding. **No record in scope is without a text**, and a
connector that read `tese` alone would report 29,2% of the register as empty.

The two courts use opposite fields for their súmulas, and the register is
consistent about it: the STF's súmula text is in `questao` and its `tese` is
always the literal string `não informado`; the STJ's is in `tese` and its
`questao` is always empty. For the temas the fields mean different things and
both are filled — `tese` is what was settled, `questao` is the question that was
put — so there the thesis is the one to take, and the 183 and 323 absences are
temas with no thesis settled yet, which is a real state, not a gap.

The STJ's texts arrive as HTML: `<p>O foro do domicílio…`. The STF's do not. The
transformation strips tags, because `core.precedente.enunciado` is read into a
blockquote as text.

## Whether this replaces the reconstruction

Yes, and nothing is lost by it.

| Court / kind | In the collection today | In the register | Reconstructed and absent from the register |
|---|---:|---:|---:|
| STF / súmula | 99 · reconstructed | 734 | **0** |
| STJ / súmula | 284 · reconstructed | 676 | **0** |
| STJ / tema | 1.142 · catalogue | 1.484 | **0** |
| STF / tema | — | 1.501 | — |
| STF / súmula vinculante | — | 62 | — |

Every precedent the collection holds today exists in the register, so the
replacement cannot make one disappear — the acceptance criterion is satisfied by
the data, not by a fallback. And the register adds more than it replaces: STF
temas are entirely new, and `Tema 793 do STF` is a citation the collection
currently cannot resolve at all.

Where both hold the same precedent, the texts compare like this:

| | Of 1.525 in common |
|---|---:|
| Identical | 1.329 · 87,1% |
| Same text, differing in accent or punctuation | 134 · 8,8% |
| One contains the other | 30 · 2,0% |
| Same rule, different wording | 9 · 0,6% |
| **Another precedent's text** | **23 · 1,5%** |

Five of the 23 are STJ temas where the catalogue holds the placeholder
`*Aguardando a publicação do acórdão do julgamento de mérito.` and the register
holds the thesis. The other **18 are súmulas carrying the wrong text**, and they
are not near misses:

| Precedent | Reconstructed from the collection | The register |
|---|---|---|
| Súmula 70 · STF | *…a apreensão de mercadorias como meio coercitivo para pagamento de tributos* — which is Súmula 323 | *É inadmissível a interdição de estabelecimento como meio coercitivo para cobrança de tributo.* |
| Súmula 126 · STF | *É inadmissível recurso especial, quando o acórdão recorrido assenta em fundamentos constitucional e infraconstitucional…* — which is Súmula 126 of the **STJ** | *É inconstitucional a chamada taxa de aguardente…* |
| Súmula 252 · STJ | *A Caixa Econômica Federal tem legitimidade passiva…* — which is Súmula 249 | *Os saldos das contas do FGTS… são corrigidos em 42,72% (IPC)…* |

The failure mode is visible in all three: decisions cite súmulas in groups —
*"Súmulas 70, 323 e 547 do STF"* — and the regex that pairs a number with the
quoted text nearest it pairs the wrong ones. The three-transcription floor does
not catch it, because every decision in the group transcribes the same way, so
the wrong pairing is repeated as reliably as a right one. Repetition verifies
that a text was transcribed, never that it was transcribed for that number.

This is the argument for the register winning, and it is stronger than coverage:
a tool that shows a lawyer Súmula 323's words under Súmula 70's name is wrong in
a way they cannot detect from the screen.

## What the screen is getting wrong today

The register answers the story's question for every súmula it holds:

| | In force | Cancelled | Superseded | Altered |
|---|---:|---:|---:|---:|
| STF · 734 súmulas | 724 `APROVADO` | 8 | 1 | 1 |
| STJ · 676 súmulas | 646 `Vigente` | 30 | — | — |

Of the precedents the collection already holds and the detail screen already
shows, **16 are cancelled**, and the screen presents every one of them as
current, because `situacao` is null and the warning is therefore never rendered:

| | How many | Which |
|---|---:|---|
| STF súmulas | 1 | 619 |
| STJ súmulas | 11 | 68, 94, 212, 222, 256, 276, 343, 348, 408, 418, 421 |
| STJ temas | 4 | 479, 701, 739, 1055 |

This is the defect in the story's own words, counted. A lawyer reading one of
those 16 decisions today is shown a súmula, with its text, and nothing says it
was cancelled.

Two more groups are not cancelled and are not plainly in force either, and
lumping them in with the 16 would be its own error:

- **53 are under way or suspended** — a tema whose leading case has not ended, a
  súmula whose publication is suspended.
- **16 carry a word this project will not translate**: 15 temas read `Revisado`
  and Súmula 359 of the STF reads `ALTERADO`. Both mean the wording moved, and
  the register hands over the moved wording — so calling them superseded would
  be as wrong as calling them current. They are shown with the register's own
  word and a line saying it is not interpreted.

## What the merge produced

Built against the collection on 20/11/2026, with the register loaded into
`raw.precedente_pangea` and `core.precedente` rendered into a table of its own
rather than over the published one. **3.951 rows, against 1.525 before:**

| Court / kind | Rows | Origin |
|---|---:|---|
| STF / súmula | 734 | official |
| STF / súmula vinculante | 62 | official |
| STF / tema | 1.318 | official |
| STJ / súmula | 676 | official |
| STJ / tema | 1.161 | official |

Nothing was left with an earlier origin, which is the measured form of "nothing
disappears": every reconstructed and catalogue precedent has an official
counterpart that carries a text, so the official row wins all 1.525 of them.
`situacao` goes from 74,9% filled to **100%**, and the four audits over the
table pass with no failures — including the unique key, which a merge is the
natural way to break.

The reconstruction and the catalogue stay in the model as the fallback they now
are: without a load from the register, the two still build the 1.525, and the
volume audit's floor is what notices if the register stops answering.

The gain the screen sees is in citation resolution, measured over the 459.800
links already in `core.decisao_precedente`:

| | Before | After |
|---|---:|---:|
| Súmula citations resolved | 380.428 · 97,3% | 391.044 · **100,0%** |
| Tema citations resolved | 8.841 · 12,9% | 29.366 · **42,8%** |
| All citations | 389.269 · 84,7% | 420.410 · **91,4%** |

The temas' gap closes by a third rather than entirely, and the reason is on our
side of the line: 6,3% of tema citations name no court, and a bare "Tema 793"
identifies no precedent because both courts have one. The register supplies the
rows those citations would need; it cannot supply the word the court left out.

## Súmula vinculante needs its own kind

It cannot be folded into `sumula`. All 62 vinculante numbers already exist as
STF súmulas — `Súmula Vinculante 1` and `Súmula 1` are different precedents
saying different things — so a merge on `(corte, tipo, numero)` would overwrite
62 súmulas with another instrument's text. The transformation carries them as
`sumula_vinculante`.

Nothing cites them yet: the citation regex matches `súmula` followed by a
number, and `súmula vinculante 1` puts a word in between. The rows are therefore
loaded and unreferenced for now, which is the right order — the catalogue has to
hold a precedent before a citation can resolve to it.

## The status field

`situacao` is free text, not an enumeration: 26 distinct values over 4.457
records, in three casing conventions (`APROVADO`, `Vigente`, `Cancelado`,
`PUBLICACAO_SUSPENSA`), and for temas it is a whole sentence — *"Há repercussão
geral. Leading case: transitado em julgado"*, 612 records.

Grouped by what a reader needs to know:

| | Records | Values include |
|---|---:|---|
| In force | 3.865 | `Transitado em julgado` (1.022), `APROVADO` (785), `Vigente` (646) |
| Under way or suspended | 333 | `Afetado` (102), `Em julgamento` (22), `Sobrestado (outro motivo)` (12) |
| No longer stands | 259 | `Cancelado` (257), `Superado` (1), `ALTERADO` (1) |

The screen's current rule reads a status as superseded when it matches
`cancelad|superad|revogad|prejudicad` and as current otherwise. Against this
vocabulary that rule is wrong twice: `ALTERADO` would read as current, and the
333 under way — a tema whose thesis is not settled, a súmula whose publication
is suspended — would read as current too. The third family is the one the
acceptance criterion names: a precedent whose standing is not plainly settled
has to say so rather than look current.

## What is still open

- **The register is not a licensed product.** It is the CNJ's public portal, and
  its interface is undocumented. The standing of the source is recorded on its
  row in `fonte.csv`; access to the documented interface is asked of the CNJ
  through the PDPJ, at <https://docs.pdpj.jus.br>.
- **`historico` is on 72 of 4.457 records**, so the history of a status change
  is available for almost none of them. The screen shows the current situação and
  the date it last moved, which is what every record carries.
- **Súmulas 152 and 274 of the STF are absent** from the register, and the
  collection does not cite them either. Not investigated further.
- **The STF's temas arrive unreferenced**, like the vinculantes: the citation
  extractor resolves `Tema N` against the court the ementa states, and 6,3% of
  tema citations state none. Those stay unresolved as before — the register adds
  the rows they would need, not the words the court omitted.
