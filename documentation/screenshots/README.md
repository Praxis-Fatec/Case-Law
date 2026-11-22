# Screenshots

What the search by subject looks like on screen. Taken on **2026-11-21**
against the local collection of 1.360.708 decisions, with the model of
[`query-embedding.md`](../architecture/query-embedding.md) and the index of
[`vector-index.md`](../architecture/vector-index.md) — not mock-ups.

| | What it shows |
|---|---|
| `a-duas-listas-numa-tela.png` | The join between the two lists, in one screen |
| `b-so-as-minhas-palavras.png` | The same search with the subject block off |
| `c-tres-faixas-de-proximidade.png` | The three proximity bands together |
| `d-panorama-classificacoes.png` | The panorama of the same cut |

---

### `a-duas-listas-numa-tela.png`

A search for `demora no voo`, scrolled to where one list ends and the other
begins. Above the divider, results 05 and 06 of the word search, with `voo`
and `demora` highlighted and no tag. Below it, the heading **Também sobre o
mesmo assunto**, its one-line explanation, and decisions carrying two tags:
`relacionado` for how close they are and `assunto parecido` for where they
came from.

None of the decisions below the divider contains the words typed. Checked
against the database for all ten: `ementa_busca @@ websearch_to_tsquery(…)`
is false for every one, so the word search could not have produced them.

### `b-so-as-minhas-palavras.png`

The same query with **Só as minhas palavras** chosen. The list is the same
decisions in the same order with the same total of 127 — and no block and no
proximity tags, because that mode never loads the model and never reads a
vector. Measured on the API: 9,4 ms against 49,8 ms, `subject_matches` 0
against 10.

### `c-tres-faixas-de-proximidade.png`

`dano moral por inscrição indevida`, where **muito próximo** and **próximo**
appear together. The bands are thirds of the range the search keeps, measured
over ten real queries.

### `d-panorama-classificacoes.png`

The indicators over the same cut: volume by court, how it changed, how the
appeals were decided, how precedents were used, and who decided. Unchanged by
this story, and here because the search feeds it.
