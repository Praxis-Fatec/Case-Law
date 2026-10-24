MODEL (
  name core.decisao_precedente,
  kind FULL,
  grain (fonte_codigo, identificador_fonte, corte, tipo, numero),
  audits (
    not_null(columns := (fonte_codigo, identificador_fonte, corte, tipo, numero, trecho, aderencia)),
    unique_combination_of_columns(
      columns := (fonte_codigo, identificador_fonte, corte, tipo, numero)
    ),
    citacao_de_tipo_conhecido,
    citacao_com_volume,
    citacao_resolvida_com_precedente,
    citacao_com_alcance,
    aderencia_de_valor_conhecido,
    aderencia_sem_contradicao,
    aderencia_com_cobertura
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
),

/* Citando um precedente só, o verbo da ementa não tem outro a que se referir;
   com vários, atribuí-lo seria chute. */
unica AS (
  SELECT fonte_codigo, identificador_fonte
  FROM situada
  GROUP BY 1, 2
  HAVING COUNT(*) = 1
),

sinal AS (
  SELECT
    'nao\s+(se\s+)?(aplica|incid|atrai)|inaplica|superad[oa]|nao\s+obsta|nao\s+ha\s+falar\s+em\s+(aplicacao|incidencia)|afastad\w*\s+(a\s+|o\s+)?(incidencia|aplicacao|obice)' AS afasta,
    'distingu|distincao' AS distingue,
    'incid|aplica|obice|obsta|esbarra|atrai|conforme|consoante|conformidade|nos\s+termos|a\s+teor|a\s+luz|consonancia|orientacao|entendimento|enunciado|observ|vedad|impede' AS segue,
    /* Lista de precedentes não é juízo de aplicação: 6.151 ligações eram lidas
       como `seguiu` só por conter a palavra. */
    'precedente|no\s+mesmo\s+sentido|\mcf\.|\mvide|\mv\.g\.|a\s+exemplo\s+d|dentre\s+outros|entre\s+outros' AS referencia
)

SELECT
  r.fonte_codigo        AS fonte_codigo,
  r.identificador_fonte AS identificador_fonte,
  r.corte               AS corte,
  r.tipo                AS tipo,
  r.numero              AS numero,
  r.trecho              AS trecho,
  (p.corte IS NOT NULL) AS resolvida,
  CASE
    WHEN r.trecho ~ g.afasta     THEN 'afastou'
    WHEN r.trecho ~ g.distingue  THEN 'distinguiu'
    WHEN r.trecho ~ g.segue      THEN 'seguiu'
    WHEN r.trecho ~ g.referencia THEN 'mencionou'
    WHEN u.fonte_codigo IS NULL  THEN 'indeterminado'
    WHEN r.texto ~ g.afasta      THEN 'afastou'
    WHEN r.texto ~ g.distingue   THEN 'distinguiu'
    WHEN r.texto ~ g.segue       THEN 'seguiu'
    WHEN r.texto ~ g.referencia  THEN 'mencionou'
    ELSE 'indeterminado'
  END                   AS aderencia,
  NOW()                 AS carregado_em
FROM recortada AS r
CROSS JOIN sinal AS g
LEFT JOIN core.precedente AS p
  ON p.corte = r.corte AND p.tipo = r.tipo AND p.numero = r.numero
LEFT JOIN unica AS u
  ON u.fonte_codigo = r.fonte_codigo AND u.identificador_fonte = r.identificador_fonte

;

JINJA_STATEMENT_BEGIN;
CREATE UNIQUE INDEX ON {{ this_model }} (fonte_codigo, identificador_fonte, corte, tipo, numero);
CREATE INDEX ON {{ this_model }} (corte, tipo, numero);
CREATE INDEX ON {{ this_model }} (resolvida);
JINJA_END;
