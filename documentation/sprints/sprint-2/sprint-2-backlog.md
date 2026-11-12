## Backlog da Sprint 2 <a id="backlog"></a>

### 1. Objetivo da sprint

**Período:** 05/10/2026 - 25/10/2026

**Objetivo:** Analisar o recorte filtrado por meio de indicadores, conferir as decisões que os compõem e exportar os resultados com referências.

### 2. Escopo priorizado

A ordem de execução considera as dependências e o objetivo da sprint.
**P1:** essencial ao objetivo. **P2:** complementar, após os itens essenciais.

| Ordem | Prioridade | Item do backlog | Pontos | Dependências |
|---:|---|---|---:|---|
| 1 | P1 | Filtros jurídicos adicionais · RF11 | 5 | Contrato de consulta da Sprint 1; dimensões verificadas |
| 2 | P1 | Evolução do volume ao longo do tempo · RF09 | 8 | Contrato de filtros do RF11; datas válidas |
| 3 | P1 | Documentos que compõem os indicadores · RF12 | 5 | Regras de agrupamento do RF09; listagem e detalhe da Sprint 1 |
| 4 | P1 | Proporção dos resultados dos recursos · RF10 | 8 | RF11, RF12; amostras de resultados verificadas |
| 5 | P1 | Exportação do recorte · RF14 | 5 | RF11; recorte e referências estáveis |
| 6 | P2 | Unanimidade ou maioria · RF13 | 3 | Detalhe da Sprint 1; amostras de deliberação verificadas |

**Total:** 34 pontos de história.

### 3. Tarefas de implementação

#### RF11: Definir um recorte consistente para análise

- Verificar órgão julgador, relator e classe por fonte; registrar amostras e campos ausentes.
- Ampliar o contrato de consulta com opções de filtros obtidas da base e condições combinadas.
- Criar controles, exibição dos filtros ativos e remoção individual.
- Testar cada dimensão e suas combinações com expressão, tribunal e períodos.

#### RF09: Apresentar a evolução do volume ao longo do tempo

- Definir agrupamentos mensais por data de julgamento, regras de limites e tratamento de datas ausentes.
- Agregar o recorte completo, incluindo meses sem decisões no intervalo exibido.
- Criar gráfico com contagens, data de referência, recorte e estados de ausência de dados e erro.
- Validar limites de mês e ano, datas ausentes e totais com consultas aos documentos.

#### RF12: Conferir os documentos que compõem cada indicador

- Definir parâmetros de navegação para a listagem, preservando o recorte e o agrupamento ou categoria selecionada.
- Conectar contagens por tribunal, agrupamentos temporais e categorias de resultado à listagem paginada.
- Preservar o contexto da análise e o acesso ao detalhe e à fonte oficial na navegação e no retorno.
- Comparar conjuntos e totais dos indicadores com as listagens, incluindo categorias sem informação.

#### RF10: Apresentar a proporção dos resultados dos recursos

- Conferir classificações derivadas com amostras das fontes e documentar limitações.
- Agregar recursos providos, parcialmente providos, negados e sem classificação, com denominador explícito.
- Exibir proporções, contagens, quantidade sem classificação e acesso aos documentos pelo RF12.
- Testar consistência dos totais, arredondamento, ausência de classificação e recortes vazios.

#### RF14: Exportar o recorte com referências verificáveis

- Definir formato de exportação, colunas, metadados e limites de tamanho.
- Implementar exportação com as mesmas condições da busca, ordenação estável, referências das fontes e proteção contra fórmulas em campos de texto.
- Adicionar ação de exportação e mensagens de progresso, erro e limite excedido.
- Abrir arquivos e conferir linhas, filtros, referências, datas e limites com a busca.

#### RF13: Identificar a forma de deliberação

- Conferir classificações de unanimidade e maioria com amostras das fontes, preservando valores desconhecidos.
- Exibir a deliberação no detalhe, com indicação clara quando não informada.
- Verificar exemplos de unanimidade, maioria e ausência de informação com o texto original.

### 4. Critérios de aceitação

| Item | Resultado esperado |
|---|---|
| RF11 | Filtros jurídicos combinam com expressão, tribunal e datas; resultados e indicadores usam o mesmo recorte |
| RF09 | Agrupamentos temporais identificam a data utilizada e seus totais conferem com o recorte; datas ausentes são informadas |
| RF12 | Selecionar um indicador abre os documentos correspondentes, preservando filtros e apresentando a mesma contagem |
| RF10 | Contagens conferem com o recorte; o denominador é explícito e decisões sem classificação permanecem separadas |
| RF14 | O arquivo preserva recorte, filtros, referências oficiais e datas de exportação e coleta; limites são informados, sem cortes silenciosos |
| RF13 | O detalhe distingue unanimidade, maioria e informação ausente, com respaldo na fonte |

Padrões de conclusão compartilhados: [DoR e DoD](../Artefatos.md).
