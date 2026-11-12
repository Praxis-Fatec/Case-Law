## Backlog da Sprint 1 <a id="backlog"></a>

### 1. Objetivo da sprint

**Período:** 07/09/2026 - 27/09/2026

**Objetivo:** Pesquisar decisões de diferentes tribunais, consultar seu conteúdo e verificar a cobertura da base.

### 2. Escopo priorizado

A ordem de execução considera as dependências e o objetivo da sprint.
**P1:** essencial ao objetivo. **P2:** complementar, após os itens essenciais.

| Ordem | Prioridade | Item do backlog | Pontos | Dependências |
|---:|---|---|---:|---|
| 1 | P1 | SCRUM-62 · Busca · RF01 | 8 | Dados das fontes verificados |
| 2 | P1 | SCRUM-50 · Resultados e fonte oficial · RF02 | 5 | SCRUM-62 |
| 3 | P1 | SCRUM-63 · Filtros por tribunal e período · RF03 | 5 | SCRUM-62 |
| 4 | P1 | SCRUM-64 · Ordenação estável · RF06 | 3 | SCRUM-62 |
| 5 | P1 | SCRUM-65 · Paginação · RF07 | 3 | SCRUM-63, SCRUM-64 |
| 6 | P1 | SCRUM-18 · Detalhe da decisão · RF04 | 5 | SCRUM-50 |
| 7 | P1 | SCRUM-27 · Cobertura da base · RF08 | 2 | Metadados das fontes e cargas |
| 8 | P2 | SCRUM-51 · Volume por tribunal · RF05 | 5 | SCRUM-62, SCRUM-63 |

**Total:** 36 pontos de história.

### 3. Tarefas de implementação

#### SCRUM-62: Pesquisar nas fontes integradas

- Verificar amostras das fontes, campos pesquisáveis e exclusão de registros restritos; registrar evidências.
- Implementar interpretação da consulta, frases exatas, operadores, tratamento de acentos e validação do tamanho mínimo.
- Integrar o formulário à busca, ao total de resultados e aos estados de carregamento, ausência de resultados e erro.
- Automatizar testes com documentos conhecidos, frases exatas, entradas inválidas e registros restritos.

#### SCRUM-50: Apresentar resultados e permitir conferir a origem

- Retornar trechos contextualizados e URLs oficiais usando o identificador de documento de cada portal.
- Criar cartões com tribunal, data, trecho destacado e acesso à fonte oficial.
- Conferir links de uma amostra e testar os estados disponível, indisponível e não verificado.

#### SCRUM-63: Definir o recorte da pesquisa

- Obter tribunais da base e implementar filtros combinados por tribunal, julgamento e publicação.
- Criar controles, exibição dos filtros ativos e remoção individual.
- Testar datas-limite, períodos invertidos, múltiplos tribunais e combinações de filtros.

#### SCRUM-64: Garantir uma ordenação estável

- Implementar ordenação por relevância e data, com desempate por chave única; documentar as regras.
- Adicionar o controle de ordenação e preservar sua seleção junto ao recorte.
- Testar empates, ordenação padrão e critérios inválidos.

#### SCRUM-65: Navegar pelos resultados sem perder o contexto

- Implementar paginação com limite de tamanho, total e faixa atual de resultados.
- Adicionar controles para avançar, voltar e selecionar uma página, preservando expressão, filtros e ordenação.
- Verificar navegação completa, empates, páginas vazias e limites de tamanho da página.

#### SCRUM-18: Consultar a decisão completa

- Disponibilizar o detalhe por fonte e identificador, com texto completo e metadados disponíveis.
- Criar rota de acesso direto, exibição das seções do CNJ sem perda de texto e retorno ao contexto da busca.
- Testar textos longos ou sem estrutura, metadados ausentes, recarregamento e identificadores inexistentes.

#### SCRUM-27: Informar a cobertura da base

- Agregar totais gerais, períodos por tribunal e metadados da última carga bem-sucedida.
- Exibir cobertura, limitações das fontes e mensagens distintas para base vazia e falha de carga.
- Verificar períodos por tribunal, distinção entre base completa e recorte filtrado e estados das cargas.

#### SCRUM-51: Contar decisões por tribunal

- Agregar contagens por tribunal com as mesmas regras de expressão e filtros da busca.
- Apresentar contagens, estados de ausência de dados e erro e aviso sobre os limites da frequência.
- Conferir as contagens com o conjunto completo de resultados filtrados.

### 4. Critérios de aceitação

| Item | Resultado esperado |
|---|---|
| SCRUM-62 · RF01 | A busca permite termos livres e frases exatas nas fontes integradas, ignora diferenças de acentuação e não retorna registros restritos; entradas inválidas, carregamento, ausência de resultados e falhas têm mensagens apropriadas |
| SCRUM-50 · RF02 | Cada resultado apresenta tribunal, data, trecho da ementa com destaque do termo e acesso à decisão correta na fonte oficial; links indisponíveis são sinalizados sem ocultar o resultado e são distintos dos não verificados |
| SCRUM-63 · RF03 | A seleção de múltiplos tribunais combina com períodos de julgamento e publicação separados; filtros ativos são visíveis e removíveis, o total é atualizado e períodos invertidos são recusados com mensagem |
| SCRUM-64 · RF06 | É possível ordenar por relevância ou data, com relevância como padrão; a seleção fica visível e é preservada ao filtrar e paginar, empates mantêm ordem estável e critérios inválidos são recusados |
| SCRUM-65 · RF07 | A navegação informa a faixa atual e o total, permite avançar, voltar e selecionar páginas sem repetir ou omitir decisões em uma base estável; expressão, filtros e ordenação são preservados e páginas além do total retornam vazias |
| SCRUM-18 · RF04 | O detalhe apresenta a ementa completa, metadados disponíveis e acesso à fonte oficial; seções do CNJ são identificadas sem perda de texto, conteúdo sem estrutura permanece legível e identificadores inexistentes retornam 404 |
| SCRUM-27 · RF08 | A cobertura informa total de documentos, tribunais, períodos geral e por tribunal e última atualização; fontes parciais são identificadas e fica explícito que os dados representam a base inteira, com mensagens distintas para ausência de carga e falha |
| SCRUM-51 · RF05 | As contagens por tribunal consideram todo o recorte filtrado, independentemente da página, e sua soma corresponde ao total da busca; recortes vazios não causam erro e há aviso de que frequência não representa relevância jurídica |

Regras detalhadas e padrões de conclusão: [DoR e DoD](../Artefatos.md).
