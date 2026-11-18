MODEL (
  name core.carga,
  kind FULL,
  grain carga_id,
  audits (
    not_null(columns := (carga_id, status)),
    unique_values(columns := (carga_id)),
    carga_de_fonte_conhecida
  )
);

/*
  Uma execução de coleta. Deriva de _dlt_loads, que o dlt mantém sozinho, e
  acrescenta o que é regra nossa: quantos registros vieram em segredo de
  justiça e foram descartados antes de chegar ao núcleo, e quantos ficaram com
  link que não alcança documento.

  links_nao_verificados anda ao lado de links_invalidos de propósito: "nenhum
  link inválido" significa pouco quando ninguém verificou. Os dois juntos dizem
  o que a carga realmente sabe.

  É desta tabela que sai a "data da última atualização" exibida nas US5 e US8,
  e o estado por fonte que o RF16 pede.

  A fonte é derivada, e isto é o conserto da SCRUM-200. Antes a coluna era o
  literal 'tjdft-jurisdf' em toda linha de _dlt_loads: as 877 mil decisões do
  STJ, os precedentes e a doutrina entravam como coleta do TJDFT com zero
  registro lidos, e três das quatro fontes não existiam para quem lesse a
  tabela. O dlt não registra a fonte — as quatro coletas compartilham
  pipeline_name 'case_law' e o mesmo _dlt_loads —, então a atribuição sai de
  qual tabela recebeu linha naquela carga.

  Carga que nenhuma tabela reivindica fica com fonte nula em vez de ser
  atribuída por proximidade. São execuções que terminaram sem gravar nada, e
  no acervo de 13/11/2026 são 7 das 23: a janela incremental não achou
  novidade. Dizer qual fonte rodou exigiria que o extrator gravasse o próprio
  código na carga, o que ele ainda não faz; chutar poria uma data de coleta
  debaixo de uma fonte que talvez não tenha rodado.

  As colunas de sigilo e de link ficam nulas fora do TJDFT, não em zero. Só o
  JurisDF publica `segredoJustica`, e só ele tem link verificado: zero ali
  afirmaria que nada foi descartado e que nenhum link falhou, quando o que
  houve foi ninguém ter olhado.
*/

WITH tjdft AS (
  SELECT
    b._dlt_load_id                                                  AS carga_id,
    'tjdft-jurisdf'                                                 AS fonte_codigo,
    COUNT(*)                                                        AS registros_lidos,
    COUNT(*) FILTER (WHERE NOT COALESCE(b."segredoJustica", FALSE))  AS registros_gravados,
    COUNT(*) FILTER (WHERE COALESCE(b."segredoJustica", FALSE))      AS descartados_sigilo,
    COUNT(*) FILTER (
      WHERE NOT COALESCE(b."segredoJustica", FALSE) AND v.valido IS FALSE
    )                                                               AS links_invalidos,
    COUNT(*) FILTER (
      WHERE NOT COALESCE(b."segredoJustica", FALSE) AND v.identificador IS NULL
    )                                                               AS links_nao_verificados
  FROM raw.acordao_tjdft AS b
  LEFT JOIN verificacao.link AS v ON v.identificador = b.identificador
  GROUP BY 1
),

espelhos AS (
  SELECT
    _dlt_load_id                  AS carga_id,
    'stj-espelhos'                AS fonte_codigo,
    COUNT(*)                      AS registros_lidos,
    COUNT(*)                      AS registros_gravados,
    CAST(NULL AS BIGINT)          AS descartados_sigilo,
    CAST(NULL AS BIGINT)          AS links_invalidos,
    CAST(NULL AS BIGINT)          AS links_nao_verificados
  FROM raw.espelho_stj
  GROUP BY 1
),

precedentes AS (
  SELECT
    _dlt_load_id                  AS carga_id,
    'stj-precedentes'             AS fonte_codigo,
    COUNT(*)                      AS registros_lidos,
    COUNT(*)                      AS registros_gravados,
    CAST(NULL AS BIGINT)          AS descartados_sigilo,
    CAST(NULL AS BIGINT)          AS links_invalidos,
    CAST(NULL AS BIGINT)          AS links_nao_verificados
  FROM raw.precedente_stj
  GROUP BY 1
),

doutrina AS (
  SELECT
    _dlt_load_id                  AS carga_id,
    'stj-bdjur'                   AS fonte_codigo,
    COUNT(*)                      AS registros_lidos,
    COUNT(*)                      AS registros_gravados,
    CAST(NULL AS BIGINT)          AS descartados_sigilo,
    CAST(NULL AS BIGINT)          AS links_invalidos,
    CAST(NULL AS BIGINT)          AS links_nao_verificados
  FROM raw.doutrina_bdjur
  GROUP BY 1
),

/*
  O STF lê os acórdãos e grava todos; o descarte que esta fonte faz é por
  ementa, não por sigilo, e acontece na transformação. `registros_lidos` e
  `registros_gravados` contam a carga, não a coleção.
*/
stf AS (
  SELECT
    _dlt_load_id                  AS carga_id,
    'stf-jurisprudencia'          AS fonte_codigo,
    COUNT(*)                      AS registros_lidos,
    COUNT(*)                      AS registros_gravados,
    CAST(NULL AS BIGINT)          AS descartados_sigilo,
    CAST(NULL AS BIGINT)          AS links_invalidos,
    CAST(NULL AS BIGINT)          AS links_nao_verificados
  FROM raw.acordao_stf
  GROUP BY 1
),

contagem AS (
  SELECT * FROM tjdft
  UNION ALL SELECT * FROM espelhos
  UNION ALL SELECT * FROM precedentes
  UNION ALL SELECT * FROM doutrina
  UNION ALL SELECT * FROM stf
)

SELECT
  l.load_id                                    AS carga_id,
  c.fonte_codigo                               AS fonte_codigo,
  l.inserted_at                                AS concluida_em,
  CASE WHEN l.status = 0 THEN 'concluida' ELSE 'falhou' END AS status,
  COALESCE(c.registros_lidos, 0)               AS registros_lidos,
  COALESCE(c.registros_gravados, 0)            AS registros_gravados,
  c.descartados_sigilo                         AS descartados_sigilo,
  c.links_invalidos                            AS links_invalidos,
  c.links_nao_verificados                      AS links_nao_verificados
FROM raw._dlt_loads AS l
LEFT JOIN contagem AS c
  ON c.carga_id = l.load_id
