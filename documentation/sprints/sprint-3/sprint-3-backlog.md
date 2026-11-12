## Backlog da Sprint 3 <a id="backlog"></a>

### 1. Objetivo da sprint

**Período:** A definir.

**Objetivo:** Aprofundar a análise do recorte com comparações entre tribunais e concentração por órgão julgador e relator, informando a situação das fontes e permitindo retomar pesquisas.

### 2. Escopo priorizado

A ordem de execução considera as dependências e o objetivo da sprint.
**P1:** essencial ao objetivo. **P2:** complementar, após os itens essenciais.

| Ordem | Prioridade | Item do backlog | Pontos | Dependências |
|---:|---|---|---:|---|
| 1 | P1 | Situação das fontes e última coleta · RF16 | 5 | Metadados de cobertura da Sprint 1; registros das cargas |
| 2 | P1 | Concentração por órgão julgador e relator · RF18 | 5 | Filtros do RF11 e acesso aos documentos do RF12 |
| 3 | P1 | Comparação entre tribunais · RF15 | 8 | Indicadores das sprints anteriores; cobertura por tribunal; RF16 |
| 4 | P1 | Pesquisa salva · RF17 | 5 | Contrato de consulta e filtros; definição de persistência e acesso |
| 5 | P2 | Relato de classificação incorreta · RF21 | 3 | Detalhe da decisão; classificações exibidas; armazenamento dos relatos |
| 6 | P2 | Leis, artigos e precedentes citados · RF19 | 8 | Texto das decisões; fontes das referências verificadas |
| 7 | P2 | Decisões semanticamente próximas · RF20 | 13 | Texto das decisões; método de similaridade validado |

**Total:** 47 pontos de história. As pontuações são estimativas iniciais de complexidade, esforço e incerteza para validação do time.

### 3. Tarefas de implementação

#### RF16: Informar a situação das fontes e a última coleta

- Verificar registros das cargas e definir os estados de sucesso, falha e ausência de coleta.
- Disponibilizar situação por fonte, última coleta bem-sucedida e última tentativa.
- Criar apresentação por fonte, distinguindo indisponibilidade de ausência de documentos.
- Testar cargas bem-sucedidas, falhas, datas desconhecidas e fontes nunca carregadas.

#### RF18: Apresentar concentração por órgão julgador e relator

- Definir identificação dos grupos, tratamento de metadados ausentes e regra para a categoria “Outros”, se utilizada.
- Implementar agregações por órgão julgador e relator sobre o recorte completo.
- Exibir contagens e conectar cada grupo aos documentos correspondentes pelo RF12.
- Conferir totais, grupos com nomes iguais em tribunais distintos e registros sem metadados.

#### RF15: Comparar tribunais no mesmo recorte

- Definir métricas comparáveis e regras para aplicar a mesma expressão, período e critérios aos tribunais.
- Implementar consultas por tribunal preservando o recorte comum e os indicadores selecionados.
- Criar visualização lado a lado com cobertura, situação das fontes e acesso aos documentos.
- Conferir cada resultado com a busca equivalente e testar coberturas distintas, recortes vazios e fontes indisponíveis.

#### RF17: Salvar e retomar pesquisas

- Definir identificação da pesquisa, titularidade, compartilhamento e forma de persistência.
- Implementar gravação e recuperação da expressão, filtros e ordenação.
- Criar ações para salvar e reabrir pesquisas, com confirmação e mensagens de erro.
- Testar restauração dos parâmetros e atualização dos resultados após mudanças na base.

#### RF21: Receber relatos de classificação incorreta

- Definir campos do relato, informação contestada e vínculo com a decisão.
- Implementar armazenamento do relato sem alterar automaticamente a classificação publicada.
- Criar formulário no detalhe e confirmação de recebimento.
- Testar campos obrigatórios, registro do relato, falha no envio e preservação da classificação.

#### RF19: Exibir fundamentos citados na decisão

- Verificar amostras de citações e definir extração, contexto e identificação das referências.
- Implementar identificação de leis, artigos e precedentes, preservando o trecho em que foram citados.
- Exibir referências no detalhe, com acesso à origem quando disponível e indicação das não resolvidas.
- Conferir citações e destinos dos links com o texto original, incluindo decisões sem referências identificadas.

#### RF20: Localizar decisões semanticamente próximas

- Definir método de similaridade, dados necessários e amostra para avaliação dos resultados.
- Implementar preparação dos textos e recuperação de decisões próximas, excluindo a própria decisão.
- Exibir sugestões com acesso ao detalhe, identificação do método e aviso sobre os limites da similaridade.
- Validar uma amostra de relações e testar ausência de sugestões, duplicatas e falhas no processamento.

### 4. Critérios de aceitação

| Item | Resultado esperado |
|---|---|
| RF16 | Cada fonte informa sua situação e a última coleta bem-sucedida; tentativas com falha e datas desconhecidas são identificadas |
| RF18 | Grupos por órgão e relator preservam o recorte, incluem metadados ausentes e permitem conferir documentos e totais; a regra de “Outros” é explícita |
| RF15 | Tribunais são comparados com os mesmos critérios e métricas, com diferenças de cobertura visíveis; ausência de documentos e indisponibilidade são distintas |
| RF17 | Reabrir a pesquisa restaura expressão, filtros e ordenação; os resultados refletem a base atual, sem promessa de congelar os documentos |
| RF21 | O relato fica vinculado à decisão e à classificação contestada; o recebimento é confirmado e a classificação permanece até revisão |
| RF19 | Referências exibidas estão presentes no texto e têm contexto verificável; referências não resolvidas são identificadas |
| RF20 | Sugestões abrem decisões existentes e informam o método utilizado; similaridade calculada é distinta de relação oficial e não implica identidade de entendimento jurídico |
