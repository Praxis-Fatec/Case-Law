# DoR, DoD e Critérios de Aceitação — Praxis · Case Law


## 1. Definition of Ready (DoR) do time

Checklist aplicado a cada User Story antes de ela entrar em uma Sprint.

Uma User Story está **pronta para entrar na Sprint** quando:

1. As regras de negócio associadas estão detalhadas.
3. As mensagens de confirmação, erro e aviso estão definidas.
4. Os critérios de aceitação estão escritos e são testáveis.
5. Existe um protótipo (ou descrição) de tela, quando a história envolver interface.
6. As dependências (fontes de dados, indicadores, integrações) estão identificadas.
7. A US está quebrada em sub-tasks com estimativa em horas, e cada sub-task
   cabe em uma pessoa.
8. A fonte de dados foi verificada de fato, não presumida: se a história
   depende de um tribunal ou de um campo, alguém confirmou que aquilo existe e é
   acessível antes de a história entrar.

## 2. Definition of Done (DoD) do time

Padrão de qualidade único do time. Uma sub-task está **pronta** quando:

**Código**
- Implementado e revisado por outro membro do time, via Pull Request.
- O CI está verde no PR — não apenas rodado, mas aprovado como condição de merge.

**Testes**
- Existem testes automatizados cobrindo os critérios de aceitação da sub-task.
- O teste foi provado quebrando o código de propósito.

**Qualidade**
- Não há bug crítico ou bloqueante conhecido em aberto.
- Quando a sub-task encontra um defeito fora do seu escopo, ele vira card
  próprio do tipo Bug, vinculado à sub-task que o causou.

> O modelo original tem quatro itens. Os acréscimos vieram do que deu errado na
> Sprint 1: o PR #57 mergeou com CI vermelho e quebrou a `dev`; a verificação de
> link aprovou 107.828 URLs que não abriam nada; e duas vezes o código foi
> mergeado sem os dados serem publicados, deixando o ambiente de
> desenvolvimento mostrando o comportamento antigo.

---

## 3. DoR detalhado por User Story

### SCRUM-62 — Pesquisar decisões por termo ou frase exata
*Épica: Busca e Recuperação · 8 pontos*

> Como analista jurídico, quero pesquisar decisões por termo ou frase exata, para
> localizar entendimentos sem precisar abrir o portal de cada tribunal.

**Regras de negócio**
- A pesquisa por termo livre não exige ordem exata das palavras.
- `"frase exata"` entre aspas casa a sequência; `um OR outro` casa qualquer um;
  `-termo` exclui.
- Acentos são ignorados: *usucapiao* encontra *usucapião*.
- A busca cobre as fontes integradas — hoje **TJDFT e STJ**.
- Documentos em segredo de justiça são excluídos na carga, não na consulta.
- O termo exige **mínimo de 2 caracteres**.

**Dados manipulados**
- Termo: texto, obrigatório, mínimo 2 caracteres.
- Resultado: lista com fonte, identificador, tribunal, processo, órgão julgador,
  relator, data, trecho destacado, URL da fonte e se o link responde.
- Total: inteiro, contando o recorte inteiro e não a página.

**Mensagens**
- Campo vazio: *"Digite uma expressão para pesquisar."*
- Carregando: *"Carregando resultados..."*
- Sem resultado: *"Nenhum resultado encontrado"*
- Falha: *"Não foi possível concluir a busca."*

**Critérios de aceitação**
- [ ] Permite pesquisar por termo livre.
- [ ] Permite pesquisar por frase exata.
- [ ] A pesquisa cobre todas as fontes integradas.
- [ ] Apresenta carregamento, ausência de resultados e erro de consulta.
- [ ] Registro em segredo de justiça não aparece no resultado.

**Verificado por:** `test_search_against_postgres.py`, `test_seal_filter.py`
(inclusive um teste que prova que remover o filtro deixaria o sigiloso passar).

> **Divergência do modelo:** o original exigia mínimo de 3 caracteres. São 2 —
> siglas de duas letras são comuns em jurisprudência. A ordenação por relevância
> é o padrão, e não havia essa definição no modelo.

---

### SCRUM-50 — Ver resultados com trecho da ementa e link para a fonte
*Épica: Busca e Recuperação · 5 pontos*

> Como analista jurídico, quero ver os resultados com um trecho da ementa e um
> link para a fonte oficial, para conferir a informação antes de citá-la.

**Regras de negócio**
- Cada resultado exibe tribunal, trecho da ementa, data e link da fonte.
- O termo pesquisado aparece destacado no trecho.
- O link é montado a partir do seed da fonte, com a **chave que aquele portal
  reconhece** — o TJDFT abre pelo `uuid`, o STJ pelo número de registro do
  processo. A chave do registro não serve para nenhum dos dois.
- A validade do link é verificada **na carga**, nunca durante a busca.
- Link inacessível é sinalizado no cartão, não escondido do resultado.
- O documento oficial é sempre a referência principal.

**Dados manipulados**
- Trecho: texto com `<mark>` no termo, gerado pelo banco.
- URL da fonte: montada por template, validada na carga.
- Estado do link: `true` (abre), `false` (não abre), `null` (não verificado) —
  **três estados, não dois**.

**Mensagens**
- Link inacessível: *"Link indisponível no momento."*
- Sem processo: *"Decisão sem número de processo informado"*

**Critérios de aceitação**
- [ ] Cada resultado apresenta tribunal, trecho da ementa e data.
- [ ] O termo pesquisado aparece destacado no trecho.
- [ ] Cada resultado leva ao documento na fonte que o publicou.
- [ ] Link inacessível é informado ao usuário sem esconder o resultado.
- [ ] O documento oficial é apresentado como referência principal.

**Verificado por:** `test_document_url.py`, `test_link_validity.py`,
`snippet.test.tsx`, `officialLink.test.tsx`.

> **Divergência do modelo:** o original tratava o link como ativo/inativo. São
> três estados: *não verificado* não é o mesmo que *quebrado*. Colapsar os dois
> desabilitaria link que funciona, ou esconderia link que não.

---

### SCRUM-18 — Abrir o detalhe de uma decisão
*Épica: Leitura da Decisão · 5 pontos*

> Como advogado, quero abrir o detalhe de uma decisão com relator, órgão
> julgador, datas e ementa completa, para avaliar se ela serve ao meu caso.

**Regras de negócio**
- O detalhe exibe processo, tribunal, órgão julgador, relator, classe CNJ e datas.
- A ementa vem **inteira**, nunca truncada — diferente do trecho da busca.
- Quando a ementa segue o padrão de quatro seções do CNJ, as seções são
  identificadas e exibidas separadamente.
- Quando não há estrutura reconhecida, o texto é exibido corrido.
- A separação **não pode perder texto**: o que entra tem de sair.
- Cada decisão tem endereço próprio, que abre direto e sobrevive a recarregar.

**Dados manipulados**
- Metadados: texto, opcionais — `null` quando a fonte não informou.
- Ementa: texto longo, com seções quando estruturada.
- Endereço: `/decisoes/{fonte}/{identificador}`.

**Mensagens**
- Não encontrada: 404 com detalhe legível.
- Seções: *"I. Caso em exame"*, *"II. Questão em discussão"*,
  *"III. Razões de decidir"*, *"IV. Dispositivo"*.

**Critérios de aceitação**
- [ ] Exibe processo, tribunal, órgão julgador, relator e datas quando disponíveis.
- [ ] Exibe a ementa completa, sem corte.
- [ ] Ementa no padrão do CNJ tem as seções identificáveis.
- [ ] Ementa sem estrutura é exibida corrida e legível.
- [ ] O acesso ao documento oficial aparece em destaque.
- [ ] Identificador inexistente devolve 404, não erro de servidor.

**Verificado por:** `test_detail.py`, `test_ementa.py` (13 testes, um deles
conferindo que nenhuma ementa real perde texto ao ser dividida),
`decisionDetail.test.tsx`, `decisionAddress.test.tsx`.

> **Medido:** 78,9% das 107.828 ementas do TJDFT seguem o padrão de quatro
> seções, e a divisão não perdeu nenhum caractere.

---

### SCRUM-63 — Filtrar por tribunal e por período
*Épica: Busca e Recuperação · 5 pontos*

> Como analista jurídico, quero filtrar por tribunal e por período, para
> restringir a pesquisa ao recorte que interessa.

**Regras de negócio**
- O filtro de tribunal aceita vários valores; a decisão de qualquer um deles entra.
- A lista de tribunais vem **dos dados**, não de constante no código: fonte nova
  aparece sozinha no filtro.
- Período de julgamento e período de publicação são campos separados e combinam.
- O período de publicação lê só a data de publicação, sem cair para a de
  julgamento — decisão que o tribunal nunca datou como publicada fica de fora.
- Data final anterior à inicial é recusada, não devolve lista vazia.
- O total é recalculado a cada alteração.

**Dados manipulados**
- Tribunal: sigla exata como o endpoint devolve (`TJDFT`, não `tjdft`), múltipla,
  opcional. Valor em branco ou repetido é ignorado.
- Datas: `YYYY-MM-DD`, final ≥ inicial, opcionais.

**Mensagens**
- *"A data final deve ser igual ou posterior à data inicial."*
- *"A busca recusou um dos períodos. Revise as datas destacadas nos filtros."*

**Critérios de aceitação**
- [ ] O filtro de tribunal permite seleção múltipla.
- [ ] Os dois períodos são aceitos separadamente e combinam.
- [ ] Os filtros ativos ficam visíveis e podem ser removidos um a um.
- [ ] O total é atualizado a cada filtro.
- [ ] Período invertido é recusado com mensagem.

**Verificado por:** `test_search_filters.py` (29 testes), `searchFilterPanel.test.tsx`.

> **Divergência do modelo:** o original dizia "lista pré-definida" de tribunais.
> A lista sai dos dados — é o que permitiu o STJ aparecer no filtro sem tocar em
> código.

---

### SCRUM-51 — Ver o volume de decisões por tribunal
*Épica: Indicadores e Análise · 5 pontos*

> Como gestor jurídico, quero ver o volume de decisões por tribunal, para saber
> onde o tema se concentra.

**Regras de negócio**
- O volume é calculado sobre **o mesmo conjunto que a busca devolveu**, com os
  mesmos parâmetros.
- A soma das contagens por tribunal é **igual ao total da busca**. É isso que
  garante que o gráfico não contradiga o número ao lado dos resultados.
- Busca sem resultado devolve lista vazia, não erro.
- O indicador avisa que frequência não representa relevância jurídica.

**Dados manipulados**
- Contagem por tribunal: inteiro, sobre o recorte filtrado.
- Total: inteiro, igual ao da busca.

**Mensagens**
- Aviso fixo: *"A frequência de decisões não indica relevância jurídica do tema."*
- Falha: *"Não foi possível calcular o volume para este recorte."*

**Critérios de aceitação**
- [ ] Apresenta a quantidade de decisões por tribunal no recorte aplicado.
- [ ] A soma confere com o total da busca.
- [ ] Recorte sem resultado devolve lista vazia, não erro.
- [ ] Informa que frequência não representa relevância jurídica.

**Verificado por:** `test_volume_by_court.py` (7 testes, a soma conferida em
seis combinações de filtro).

---

### SCRUM-64 — Ordenar os resultados por relevância ou por data
*Épica: Busca e Recuperação · 3 pontos*

> Como analista jurídico, quero ordenar os resultados por relevância ou data,
> para ver primeiro o conteúdo mais aderente ou o mais recente.

**Regras de negócio**
- As opções são **relevância** e **data**. O padrão é relevância.
- A ordenação é escolhida de um conjunto fechado, nunca montada a partir da
  entrada do usuário.
- Toda ordenação termina na chave única da decisão, para que a sequência seja a
  mesma entre consultas.
- A ordenação é mantida ao paginar e ao filtrar.
- Valor fora do conjunto é recusado com 422, informando quais existem.

**Dados manipulados**
- Critério: `relevance` | `date`, padrão `relevance`.

**Mensagens**
- *"Não foi possível reordenar os resultados."*

**Critérios de aceitação**
- [ ] Permite ordenar por relevância e por data.
- [ ] Relevância é o padrão quando nada é pedido.
- [ ] A ordenação permanece ao paginar e ao filtrar.
- [ ] A ordenação vigente fica visível.
- [ ] Valor inválido é recusado sem erro de servidor.

**Verificado por:** `test_ordering.py`, `test_ordering_with_filters.py`,
`resultsSort.test.tsx`.

> **Divergência do modelo:** o original previa três critérios, incluindo data de
> publicação. São dois. A data de publicação está ausente em 12% dos registros do
> TJDFT, e ordenar por um campo que falta em um de cada oito documentos
> produziria uma lista que o leitor não entenderia.

---

### SCRUM-65 — Navegar entre as páginas de resultados
*Épica: Busca e Recuperação · 3 pontos*

> Como analista jurídico, quero navegar entre as páginas de resultados, para
> percorrer um recorte grande sem perder a posição.

**Regras de negócio**
- A resposta informa a faixa que a página ocupa no total (ex.: 21–40 de 1.847).
- Percorrer todas as páginas devolve o total **sem repetir nem pular** registro.
- Empate de relevância ou de data é desempatado pela chave única, para que a
  sequência não mude entre consultas nem com tamanho de página diferente.
- Filtros e ordenação são preservados na navegação.
- Página além do total devolve lista vazia, não erro.
- Tamanho de página tem teto de **100**; acima disso é servido no teto.
- Tamanho zero ou negativo é recusado.

**Dados manipulados**
- Página: inteiro ≥ 1. Tamanho: inteiro entre 1 e 100, padrão 20.
- Faixa: dois inteiros contando de 1, ou `null` quando a página não traz nada.

**Mensagens**
- *"Não foi possível carregar esta página. Tente novamente."*

**Critérios de aceitação**
- [ ] Informa a posição atual no total.
- [ ] Permite avançar, voltar e ir a uma página específica.
- [ ] A soma das páginas é o total, sem repetição.
- [ ] Empatados mantêm a ordem entre consultas.
- [ ] Filtros e ordenação são preservados.
- [ ] Página além do total devolve vazio, não erro.

**Verificado por:** `test_pagination.py` (17 testes, sobre uma coleção construída
para empatar em tudo que a busca ordena).

> **Divergência do modelo:** o original fixava o tamanho de página. Ele é
> ajustável com teto, porque a agregação por tribunal e a exportação precisam de
> páginas maiores que a tela.

---

### SCRUM-27 — Ver a cobertura da base
*Épica: Confiabilidade da Base · 2 pontos*

> Como magistrado, quero ver quantos documentos, tribunais e qual período a base
> cobre, para saber o alcance da pesquisa antes de confiar no resultado.

**Regras de negócio**
- A cobertura exibe total de documentos, tribunais presentes e período.
- **Cada tribunal carrega o seu próprio período.** O intervalo agregado sozinho
  engana: hoje ele diz 1989–2026, mas só o STJ alcança 1989 — o TJDFT começa em
  setembro de 2025.
- A data da última atualização é exibida junto.
- Fonte com cobertura parcial é sinalizada: o STJ são **espelhos de acórdãos**,
  jurisprudência selecionada pela Secretaria de Jurisprudência do tribunal, não a
  base inteira dele.
- A cobertura fala da base inteira, nunca do recorte pesquisado, e isso precisa
  estar explícito na tela.
- Base vazia devolve resposta, não erro.

**Dados manipulados**
- Total de documentos, número de tribunais: inteiros.
- Período geral e por tribunal: intervalos de datas, `null` em base vazia.
- Situação da carga: `loaded` | `never_loaded` | `all_loads_failed` — **três
  estados**: ambiente novo e pipeline quebrado não são a mesma notícia.

**Mensagens**
- *"Algumas fontes possuem cobertura parcial no período selecionado."*
- Base nunca carregada: *"Ainda não há dados neste ambiente."*
- Todas as cargas falharam: mensagem distinta, sinalizando problema.

**Critérios de aceitação**
- [ ] Exibe total de documentos, número de tribunais e período coberto.
- [ ] Exibe o período de cada tribunal, além do geral.
- [ ] Informa a data da última atualização.
- [ ] Identifica fonte com cobertura parcial.
- [ ] Deixa explícito que o recorte é a base inteira, não a busca atual.
- [ ] Base vazia mostra mensagem apropriada.

**Verificado por:** `test_coverage.py` (7 testes, incluindo a base vazia).

> **Divergência do modelo:** o original não previa período por tribunal. Com duas
> fontes de alcance muito diferente, o intervalo agregado passou a ser a
> informação mais enganosa do painel.

---

### SCRUM-32 — Fundação do projeto
*Épica: Plataforma e Entrega · 19 sub-tasks*

Não é User Story: é o que precisa existir para as User Stories poderem ser
desenvolvidas, testadas e publicadas. Não tem critério de aceitação de usuário;
o DoD dela é o DoD do time.

**Dependências identificadas**
- API pública do TJDFT JurisDF, sem credencial.
- Portal de dados abertos do STJ (CKAN), licença CC-BY.
- Servidores: Raspberry Pi 5 (ARM64) para desenvolvimento, VPS x86 para produção.
- Rede privada Tailscale entre o CI e os servidores.

---

## 4. Bugs abertos na Sprint 1

Card do tipo **Bug** é aberto quando o defeito atinge algo já marcado como
concluído. Enquanto a sub-task está em andamento, o conserto é dela.

| Card | Defeito | Causa |
|---|---|---|
| SCRUM-92 | O painel de filtros não compila | Chave não fechada na resolução de um conflito de merge |
| SCRUM-94 | O link do TJDFT abre a home, não o acórdão | A URL usava rota e chave que o portal não reconhece |
| SCRUM-95 | A verificação de link ignorava a fonte | O verificador perguntava ao tribunal errado |

Os três têm a mesma lição, e ela virou item de DoD: **o CI já apontava o
problema em dois deles, e o merge aconteceu assim mesmo.**

---

## 5. Responsabilidade

A responsabilidade pelos artefatos é compartilhada pelo time. O Product Owner
contribui principalmente com os critérios de aceitação, mas a definição e a
evolução desses acordos são de todos.

Este documento é revisado ao fim de cada Sprint, comparando o que ficou escrito
com o que o sistema passou a fazer. Um DoR que descreve o plano e não o produto
deixa de servir para decidir se a próxima história está pronta.
