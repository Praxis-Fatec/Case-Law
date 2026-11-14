MODEL (
  name core.referencia_legislativa,
  kind INCREMENTAL_BY_TIME_RANGE (
    time_column data_referencia,
    -- Mesma escolha de core_decisao_precedente.sql, e pelo mesmo motivo: sem
    -- `batch_size` a reconstrução é uma passada só, e a carga semanal paga
    -- pela semana porque o trabalho é definido pela janela de datas.
    batch_concurrency 1
  ),
  start '1989-01-01',
  grain (fonte_codigo, identificador_fonte, ordem, sequencia),
  audits (
    not_null(columns := (
      fonte_codigo, identificador_fonte, ordem, sequencia, reconhecida,
      data_referencia
    )),
    unique_combination_of_columns(
      columns := (fonte_codigo, identificador_fonte, ordem, sequencia)
    ),
    referencia_reconhecida_tem_esfera_e_tipo,
    referencia_guarda_a_esfera_crua,
    referencia_com_artigo_legivel,
    referencia_sem_art_colado
  )
);

/*
  A lei que a decisão aplicou, como o tribunal a escreveu.

  O STJ publica cada referência num campo de texto de formato fixo, montado
  pela Secretaria de Jurisprudência:

      LEG:FED DEL:003365 ANO:1941
              ART:00026 PAR:00002

  Cabeçalho, bloco opcional de nome (`***** CPC-15 CÓDIGO DE PROCESSO CIVIL`),
  componentes repetidos (`ART:`, `PAR:`, `INC:`, `LET:`) e, às vezes, o órgão
  emissor entre parênteses. Isso é parsing de formato fixo, não extração: não há
  heurística aqui e não há modelo nenhum lendo texto livre.

  Medido em 14/11/2026 sobre as 1.243.281 linhas da origem — o detalhe está em
  documentation/architecture/legislative-references.md:

  - 99,2910% trazem esfera e tipo de ato; 0,7090% não, e essas ficam com
    `reconhecida = FALSE` e o texto do tribunal intacto. Nada é descartado.
  - A esfera é preservada como veio. FED é federal, DIS é distrital, EST é
    estadual — e MUN, INT e IES também aparecem, somando 0,426%. Traduzir ou
    adivinhar qualquer uma delas seria responder lei municipal como estadual.
  - 17,88% das referências citam dois artigos ou mais, até 24 numa só. Por isso
    o grão é (decisão, referência, artigo): guardar uma linha por linha de
    origem perderia o resto em silêncio.

  `paragrafos`, `incisos` e `letras` são vetores porque 2,16%, 2,49% e 0,66% dos
  segmentos nomeiam mais de um. Mostrar "art. 105, III" onde o tribunal escreveu
  "III e IV" estreita a citação e a apresenta como se fosse ela.

  `ano` não tem auditoria de plausibilidade de propósito: o campo vai de 1002 a
  8906, com 48 anos anteriores a 1824 e 10 posteriores a 2030. São erros de
  digitação do próprio tribunal, não do recorte, e uma regra sobre eles
  reprovaria a carga por algo que não está em nossas mãos consertar.
*/
WITH decisao AS (
  SELECT fonte_codigo, identificador_fonte, data_referencia
  FROM core.decisao
  WHERE fonte_codigo = 'stj-espelhos'
    AND data_referencia BETWEEN @start_ds::DATE AND @end_ds::DATE
),

/* Espaços colapsados antes de qualquer leitura: a quebra de linha está dentro
   do campo em 1.132.200 linhas e não é estrutura nenhuma. */
bruta AS (
  SELECT
    d.fonte_codigo        AS fonte_codigo,
    d.identificador_fonte AS identificador_fonte,
    d.data_referencia     AS data_referencia,
    r._dlt_list_idx       AS ordem,
    BTRIM(REGEXP_REPLACE(r.value, '\s+', ' ', 'g')) AS texto
  FROM decisao AS d
  JOIN raw.espelho_stj AS e
    ON e.id = d.identificador_fonte
  JOIN raw."espelho_stj▶referenciasLegislativas" AS r
    ON r._dlt_parent_id = e._dlt_id
),

/* O corte por artigo. `ART:` vira sentinela e o campo é partido nela, então o
   primeiro pedaço é o cabeçalho e cada pedaço seguinte é um artigo com os
   componentes que o seguem — que é como o tribunal escreve: os tokens valem em
   sequência, e `PAR:00002` depois de `ART:00026` é o §2º do art. 26.
   Conferido: nenhuma das 1.243.281 linhas tem `ART:` colado a outra palavra,
   então a sentinela não parte nada que não seja um artigo. */
pedaco AS (
  SELECT
    b.fonte_codigo,
    b.identificador_fonte,
    b.data_referencia,
    b.ordem,
    b.texto,
    p.indice,
    p.partes[p.indice] AS trecho
  FROM bruta AS b
  CROSS JOIN LATERAL (
    SELECT q.partes, i.indice
    FROM (
      /* O COALESCE é pelas 12 linhas que a origem manda em branco:
         STRING_TO_ARRAY('') devolve vetor vazio, e sem ele essas 12 sairiam da
         tabela sem aparecer em auditoria nenhuma. Ficam, como referência não
         reconhecida e sem texto, que é o que elas são. */
      SELECT STRING_TO_ARRAY(
        REPLACE(COALESCE(NULLIF(b.texto, ''), ' '), 'ART:', CHR(1) || 'ART:'),
        CHR(1)
      ) AS partes
    ) AS q
    CROSS JOIN LATERAL GENERATE_SUBSCRIPTS(q.partes, 1) AS i(indice)
  ) AS p
),

/* Referência sem artigo nenhum — 36,68% delas — rende uma linha com o artigo
   nulo: a lei foi citada por inteiro, e é isso que a tela diz. */
segmento AS (
  SELECT
    fonte_codigo,
    identificador_fonte,
    data_referencia,
    ordem,
    texto,
    CASE WHEN texto LIKE '%ART:%' THEN indice - 1 ELSE 1 END AS sequencia,
    trecho
  FROM pedaco
  WHERE indice > 1 OR texto NOT LIKE '%ART:%'
),

/* Um token por linha, na ordem em que o tribunal os escreveu. O índice do
   vetor é o que garante essa ordem: sem ele, a ordem de uma função de conjunto
   é promessa de implementação, não do SQL. */
componente AS (
  SELECT
    s.fonte_codigo,
    s.identificador_fonte,
    s.ordem,
    s.sequencia,
    t.indice,
    (REGEXP_MATCH(t.tokens[t.indice], '^(PAR|INC|LET):(.+)$'))[1] AS rotulo,
    (REGEXP_MATCH(t.tokens[t.indice], '^(PAR|INC|LET):(.+)$'))[2] AS valor
  FROM segmento AS s
  CROSS JOIN LATERAL (
    SELECT q.tokens, i.indice
    FROM (SELECT STRING_TO_ARRAY(s.trecho, ' ') AS tokens) AS q
    CROSS JOIN LATERAL GENERATE_SUBSCRIPTS(q.tokens, 1) AS i(indice)
  ) AS t
  WHERE t.tokens[t.indice] ~ '^(PAR|INC|LET):'
),

/* `ÚNICO` e `UNICO` são a mesma coisa escrita de dois jeitos, 29.666 e 8.042
   vezes. Os zeros à esquerda saem porque `00002` é o §2º, não o §00002. */
legivel AS (
  SELECT
    fonte_codigo,
    identificador_fonte,
    ordem,
    sequencia,
    indice,
    rotulo,
    CASE
      WHEN rotulo = 'LET' THEN UPPER(valor)
      WHEN valor ~ '^[0-9]+$'
        THEN COALESCE(NULLIF(LTRIM(valor, '0'), ''), '0')
      WHEN UPPER(UNACCENT(valor)) = 'UNICO' THEN 'único'
      ELSE valor
    END AS valor
  FROM componente
),

agrupado AS (
  SELECT
    fonte_codigo,
    identificador_fonte,
    ordem,
    sequencia,
    ARRAY_AGG(valor ORDER BY indice) FILTER (WHERE rotulo = 'PAR') AS paragrafos,
    ARRAY_AGG(valor ORDER BY indice) FILTER (WHERE rotulo = 'INC') AS incisos,
    ARRAY_AGG(valor ORDER BY indice) FILTER (WHERE rotulo = 'LET') AS letras
  FROM legivel
  GROUP BY 1, 2, 3, 4
),

/* O cabeçalho. O tipo de ato é o primeiro código de três letras depois da
   esfera que NÃO seja um componente: 3.060 linhas vêm como `LEG:FED ANO:1988`,
   sem código de ato nenhum, e ler `ANO` como tipo de ato inventaria um ato
   chamado "ano de 1988".

   `******` e `****` são como o tribunal escreve "não tem número" e "não tem
   ano" — é assim que a Constituição aparece — então os dois viram nulo em vez
   de virarem zero. */
cabecalho AS (
  SELECT
    s.fonte_codigo,
    s.identificador_fonte,
    s.data_referencia,
    s.ordem,
    s.sequencia,
    s.texto,
    s.trecho,
    SUBSTRING(s.texto FROM '^LEG:([A-Z]{2,4})\M') AS esfera,
    (REGEXP_MATCH(
      s.texto,
      '^LEG:[A-Z]{2,4} ((?!ANO|ART|PAR|INC|LET|NUM|TEM)[A-Z]{3}):([0-9*]{1,6})'
    ))[1] AS tipo_ato,
    (REGEXP_MATCH(
      s.texto,
      '^LEG:[A-Z]{2,4} ((?!ANO|ART|PAR|INC|LET|NUM|TEM)[A-Z]{3}):([0-9*]{1,6})'
    ))[2] AS numero_bruto,
    SUBSTRING(s.texto FROM 'ANO:([0-9]{4})\M') AS ano_bruto,
    /* Quatro dígitos e uma letra é `ART:0543B`, o art. 543-B; cinco dígitos é
       `ART:00026`, o art. 26. Um parser que só aceitasse cinco dígitos leria
       24.222 tokens como artigos de quatro algarismos. */
    REGEXP_MATCH(s.trecho, '^ART:([0-9]{4,5})([A-Z]?)\M') AS artigo_bruto
  FROM segmento AS s
)

SELECT
  c.fonte_codigo        AS fonte_codigo,
  c.identificador_fonte AS identificador_fonte,
  c.ordem               AS ordem,
  c.sequencia           AS sequencia,
  c.esfera              AS esfera,
  c.tipo_ato            AS tipo_ato,
  CASE
    WHEN c.numero_bruto ~ '^[0-9]+$' THEN NULLIF(c.numero_bruto::BIGINT, 0)
  END                   AS numero,
  c.ano_bruto::INT      AS ano,
  CASE
    WHEN c.artigo_bruto IS NULL THEN NULL
    ELSE COALESCE(NULLIF(LTRIM(c.artigo_bruto[1], '0'), ''), '0')
         || CASE
              WHEN c.artigo_bruto[2] <> '' THEN '-' || c.artigo_bruto[2]
              ELSE ''
            END
  END                   AS artigo,
  a.paragrafos          AS paragrafos,
  a.incisos             AS incisos,
  a.letras              AS letras,
  (c.esfera IS NOT NULL AND c.tipo_ato IS NOT NULL) AS reconhecida,
  /* O texto do tribunal fica em toda linha: é o que a tela mostra quando o
     parser não reconheceu a referência, e é onde está o que o recorte por
     artigo não carrega. Nulo nas 12 linhas que a origem manda em branco. */
  NULLIF(c.texto, '')   AS texto_bruto,
  c.data_referencia     AS data_referencia,
  NOW()                 AS carregado_em
FROM cabecalho AS c
LEFT JOIN agrupado AS a
  ON a.fonte_codigo = c.fonte_codigo
 AND a.identificador_fonte = c.identificador_fonte
 AND a.ordem = c.ordem
 AND a.sequencia = c.sequencia

;

JINJA_STATEMENT_BEGIN;
/* Nome derivado da tabela física, pela razão explicada em core_decisao.sql:
   sem nome, cada lote cria uma cópia nova em vez de reconhecer a existente. */
{% set tabela = this_model.split('.')[-1] | replace('"', '') %}
CREATE UNIQUE INDEX IF NOT EXISTS "{{ tabela }}_chave" ON {{ this_model }} (fonte_codigo, identificador_fonte, ordem, sequencia);
/* Parcial porque é a minoria que interessa: 0,61% das linhas, que é o que a
   auditoria conta e o que alguém abre para ver o que o tribunal mudou. */
CREATE INDEX IF NOT EXISTS "{{ tabela }}_nao_reconhecida" ON {{ this_model }} (fonte_codigo, identificador_fonte) WHERE NOT reconhecida;
JINJA_END;
