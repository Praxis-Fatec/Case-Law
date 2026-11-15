MODEL (
  name core.decisao_norma,
  kind INCREMENTAL_BY_TIME_RANGE (
    time_column data_referencia,
    batch_concurrency 1
  ),
  -- O mesmo início de `core.decisao`, e não o padrão de `config.yaml`. Sem
  -- isto o modelo nasce cobrindo só 2026: as decisões anteriores ficam sem
  -- norma, e decisão sem norma nunca é sugerida. Seria um acervo que só
  -- encontra parecidas entre as recentes, sem nada denunciando o corte.
  start '1989-01-01',
  grain (fonte_codigo, identificador_fonte),
  audits (
    not_null(columns := (fonte_codigo, identificador_fonte, norma)),
    unique_combination_of_columns(columns := (fonte_codigo, identificador_fonte)),
    norma_positiva
  )
);

/*
  O comprimento do vetor de cada decisão, para o cosseno de
  `RF20` não ter de recalculá-lo a cada consulta.

  Por que existe, medido em 11/11/2026. Pontuar por soma dos pesos
  compartilhados dá 0,426 de precisão@10 no acervo; normalizar por cosseno
  sobe para 0,470, e somar a frequência do termo no documento sobe para
  0,529. O cosseno vale os 0,044 — mas ele divide pelo comprimento dos dois
  vetores, e o do candidato só sai lendo o vetor inteiro dele.

  É isso que torna a consulta cara, e esta tabela é o que paga. Medido em 15
  decisões sorteadas, pedindo cinco sugestões: com a norma pronta, 706 ms de
  mediana e 4,6 s no pior caso; calculada na hora, 4,8 s de mediana e 23,4 s
  no pior. A tabela custa 71 MB de dados e 66 MB de índice, e poupa ler o
  vetor de cada candidato — que chegam a 72.811 numa decisão do sorteio.

  Por faixa de data, e não mensal como o vocabulário de que depende. Uma
  decisão sem norma não aparece como sugestão, então uma tabela mensal
  deixaria a carga da semana invisível até o mês virar. O preço é que as
  normas ficam de safras diferentes entre duas reconstruções do vocabulário:
  as linhas antigas usam os pesos do mês passado e as novas, os de agora.
  O efeito é desprezível pelo mesmo motivo que já justifica o vocabulário ser
  mensal — uma semana acrescenta 0,1% ao acervo e quase não move o IDF — e a
  diferença entra num denominador, que é onde ela menos importa.

  As 35 decisões cujo vetor não tem nenhum termo pesado ficam de fora: sem
  termo, não há o que casar, e elas nunca seriam candidatas de ninguém.
*/

SELECT
  d.fonte_codigo                                                     AS fonte_codigo,
  d.identificador_fonte                                              AS identificador_fonte,
  d.data_referencia                                                  AS data_referencia,
  SQRT(SUM(POWER(j.peso * (1 + LN(ARRAY_LENGTH(t.positions, 1))), 2))) AS norma,
  NOW()                                                              AS carregado_em
FROM core.decisao AS d
CROSS JOIN LATERAL UNNEST(d.ementa_busca) AS t
JOIN core.termo_judicial AS j ON j.termo = t.lexeme
WHERE d.data_referencia BETWEEN @start_ds::DATE AND @end_ds::DATE
GROUP BY d.fonte_codigo, d.identificador_fonte, d.data_referencia

;

JINJA_STATEMENT_BEGIN;
{% set tabela = this_model.split('.')[-1] | replace('"', '') %}
CREATE UNIQUE INDEX IF NOT EXISTS "{{ tabela }}_chave"
  ON {{ this_model }} (fonte_codigo, identificador_fonte);
JINJA_END;
