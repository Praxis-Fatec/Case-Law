MODEL (
  name core.cobertura_fonte,
  kind FULL,
  grain fonte_codigo,
  audits (
    not_null(columns := (fonte_codigo, conteudo, itens, itens_sem_data, precisao)),
    unique_values(columns := (fonte_codigo)),
    cobertura_preenchida
  )
);

/*
  O período que cada fonte cobre de fato, medido no acervo publicado.

  Existia como duas colunas do seed `fonte.csv`, e o SCRUM-156 apontou o que
  isso produzia: o CSV nasceu com as duas vazias, o SQLMesh inferiu
  `double precision` de coluna sem valor, e `infra/postgres/core.sql` declarava
  `date` — três respostas para o tipo de uma coluna que nunca foi preenchida.
  O dicionário de dados ainda trazia uma quarta, "primeiro ano coberto".

  Derivar resolve as duas metades de uma vez. O tipo deixa de ser inferido de
  célula vazia, e a data deixa de envelhecer: período coberto muda a cada
  carga, e coluna que precisa acompanhar o acervo não pode morar num CSV
  editado à mão. É também o que o RF16 exige — não substituir data
  desconhecida por valor estimado.

  `precisao` é o que impede a estimativa de entrar pela porta de trás. A
  doutrina do BDJur traz ano, não data: gravar 1953-01-01 sem dizer que o dia
  foi inventado seria afirmar um 1º de janeiro que ninguém publicou. A tela lê
  este campo e escreve "1953" onde a precisão é anual.

  Fonte sem item coletado aparece com zero e sem período, em vez de não
  aparecer: "nunca coletamos" e "não sei" são notícias diferentes. O
  `HAVING COUNT(*) > 0` é o que faz isso funcionar: agregado sem GROUP BY
  devolve uma linha mesmo sobre tabela vazia, e sem ele a fonte sem item
  herdaria a precisão da consulta em vez de declarar que não tem nenhuma.

  As súmulas reconstruídas ficam fora da conta dos precedentes. Elas não vêm
  de coleta — saem das transcrições do próprio acervo — e as 371 não têm data
  nenhuma, então contá-las como coleta do portal do STJ atribuiria ao portal
  um período que ele não forneceu.
*/

WITH decisao AS (
  SELECT
    fonte_codigo,
    COUNT(*)                                            AS itens,
    COUNT(*) FILTER (WHERE data_julgamento IS NULL)      AS itens_sem_data,
    MIN(data_julgamento)                                 AS cobertura_inicio,
    MAX(data_julgamento)                                 AS cobertura_fim,
    'dia'                                                AS precisao
  FROM core.decisao
  GROUP BY 1
),

precedente AS (
  SELECT
    'stj-precedentes'                                    AS fonte_codigo,
    COUNT(*)                                             AS itens,
    COUNT(*) FILTER (WHERE data IS NULL)                 AS itens_sem_data,
    MIN(data)                                            AS cobertura_inicio,
    MAX(data)                                            AS cobertura_fim,
    'dia'                                                AS precisao
  FROM core.precedente
  WHERE origem = 'catalogo'
  HAVING COUNT(*) > 0
),

doutrina AS (
  SELECT
    'stj-bdjur'                                          AS fonte_codigo,
    COUNT(*)                                             AS itens,
    COUNT(*) FILTER (WHERE ano IS NULL)                  AS itens_sem_data,
    MAKE_DATE(MIN(ano)::INT, 1, 1)                       AS cobertura_inicio,
    MAKE_DATE(MAX(ano)::INT, 1, 1)                       AS cobertura_fim,
    'ano'                                                AS precisao
  FROM core.doutrina
  WHERE repositorio = 'bdjur'
  HAVING COUNT(*) > 0
),

coletado AS (
  SELECT * FROM decisao
  UNION ALL SELECT * FROM precedente
  UNION ALL SELECT * FROM doutrina
)

SELECT
  f.codigo                                   AS fonte_codigo,
  f.conteudo                                 AS conteudo,
  COALESCE(c.itens, 0)                       AS itens,
  COALESCE(c.itens_sem_data, 0)              AS itens_sem_data,
  c.cobertura_inicio                         AS cobertura_inicio,
  c.cobertura_fim                            AS cobertura_fim,
  COALESCE(c.precisao, 'nenhuma')            AS precisao
FROM core.fonte AS f
LEFT JOIN coletado AS c
  ON c.fonte_codigo = f.codigo
