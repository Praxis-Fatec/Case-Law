MODEL (
  name core.decisao_precedente,
  kind FULL,
  grain (fonte_codigo, identificador_fonte, corte, tipo, numero),
  audits (
    not_null(columns := (fonte_codigo, identificador_fonte, corte, tipo, numero, trecho)),
    unique_combination_of_columns(
      columns := (fonte_codigo, identificador_fonte, corte, tipo, numero)
    ),
    citacao_de_tipo_conhecido,
    citacao_com_volume
  )
);

/* A citação sem par no catálogo fica, marcada em `resolvida`: o buraco é a
   medida que diz se vale ampliar a coleta. */
WITH base AS (
  SELECT
    fonte_codigo,
    identificador_fonte,
    UNACCENT(LOWER(REGEXP_REPLACE(ementa, '\s+', ' ', 'g'))) AS texto
  FROM core.decisao
  WHERE ementa ~* 'S[uú]mula|\mtema'
),

citada AS (
  SELECT DISTINCT
    b.fonte_codigo,
    b.identificador_fonte,
    b.texto,
    UPPER(achado[2]) AS corte,
    'sumula'         AS tipo,
    achado[1]::BIGINT AS numero
  FROM base AS b,
       LATERAL (
         SELECT (REGEXP_MATCHES(
           b.texto,
           'sumula\s*(?:n[.o]*\s*)?([0-9]{1,4})\s*[/, -]*(?:do\s+)?(stj|stf)',
           'g'
         )) AS achado
       ) AS s

  UNION

  /* "relevância do tema e da urgência" não é citação: o número é o que separa
     o substantivo comum do precedente. */
  SELECT DISTINCT
    b.fonte_codigo,
    b.identificador_fonte,
    b.texto,
    'STJ'             AS corte,
    'tema'            AS tipo,
    achado[1]::BIGINT AS numero
  FROM base AS b,
       LATERAL (
         SELECT (REGEXP_MATCHES(
           b.texto, '\mtema[s]?\s*(?:n[.o]*\s*)?([0-9]{1,4})\M', 'g'
         )) AS achado
       ) AS t
),

/* Recorte por posição: capturar o contexto na mesma expressão faz uma citação
   engolir a seguinte — medido, custava 5,07% das ligações. */
situada AS (
  SELECT
    c.*,
    REGEXP_INSTR(
      c.texto,
      CASE c.tipo WHEN 'sumula' THEN 'sumula' ELSE 'tema[s]?' END
        || '\s*(?:n[.o]*\s*)?' || c.numero || '\M'
    ) AS posicao
  FROM citada AS c
),

recortada AS (
  SELECT
    s.*,
    BTRIM(SUBSTRING(s.texto FROM GREATEST(1, s.posicao - 80) FOR 220)) AS trecho
  FROM situada AS s
)

SELECT
  r.fonte_codigo        AS fonte_codigo,
  r.identificador_fonte AS identificador_fonte,
  r.corte               AS corte,
  r.tipo                AS tipo,
  r.numero              AS numero,
  r.trecho              AS trecho,
  (p.corte IS NOT NULL) AS resolvida,
  CAST(NULL AS TEXT)    AS aderencia,
  NOW()                 AS carregado_em
FROM recortada AS r
LEFT JOIN core.precedente AS p
  ON p.corte = r.corte AND p.tipo = r.tipo AND p.numero = r.numero

;

JINJA_STATEMENT_BEGIN;
CREATE UNIQUE INDEX ON {{ this_model }} (fonte_codigo, identificador_fonte, corte, tipo, numero);
CREATE INDEX ON {{ this_model }} (corte, tipo, numero);
CREATE INDEX ON {{ this_model }} (resolvida);
JINJA_END;
