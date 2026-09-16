MODEL (
  name core.carga,
  kind FULL,
  grain carga_id,
  audits (
    not_null(columns := (carga_id, fonte_codigo, status)),
    unique_values(columns := (carga_id))
  )
);

/*
  Uma execução de coleta. Deriva de _dlt_loads, que o dlt mantém sozinho, e
  acrescenta o que é regra nossa: quantos registros vieram em segredo de
  justiça e foram descartados antes de chegar ao núcleo.

  É desta tabela que sai a "data da última atualização" exibida nas US5 e US8.
*/

WITH contagem AS (
  SELECT
    _dlt_load_id                                           AS carga_id,
    COUNT(*)                                               AS registros_lidos,
    COUNT(*) FILTER (WHERE COALESCE("segredoJustica", FALSE))       AS descartados_sigilo,
    COUNT(*) FILTER (WHERE NOT COALESCE("segredoJustica", FALSE))   AS registros_gravados
  FROM raw.acordao_tjdft
  GROUP BY 1
)

SELECT
  l.load_id                                    AS carga_id,
  'tjdft-jurisdf'                              AS fonte_codigo,
  l.inserted_at                                AS concluida_em,
  CASE WHEN l.status = 0 THEN 'concluida' ELSE 'falhou' END AS status,
  COALESCE(c.registros_lidos, 0)               AS registros_lidos,
  COALESCE(c.registros_gravados, 0)            AS registros_gravados,
  COALESCE(c.descartados_sigilo, 0)            AS descartados_sigilo
FROM raw._dlt_loads AS l
LEFT JOIN contagem AS c
  ON c.carga_id = l.load_id
