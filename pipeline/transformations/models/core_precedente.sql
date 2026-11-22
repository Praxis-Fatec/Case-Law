MODEL (
  name core.precedente,
  kind FULL,
  grain (corte, tipo, numero),
  audits (
    not_null(columns := (corte, tipo, numero, enunciado, origem)),
    unique_combination_of_columns(columns := (corte, tipo, numero)),
    precedente_de_corte_conhecida,
    precedente_com_enunciado,
    precedente_com_volume
  )
);

/*
  O que as Cortes Superiores firmaram, e que as decisões citam.

  Três registros alimentam esta tabela, e a ordem entre eles é o conteúdo deste
  modelo: o oficial vence o catálogo, que vence a reconstrução.

  O oficial é o BNP, registro nacional de precedentes do CNJ, lido pelo portal
  Pangea. Até ele entrar, súmula não tinha catálogo público nenhum — o portal de
  dados abertos do STJ não publica, o BDJur só tem manuais da Secretaria de
  Jurisprudência, o scon responde 403 a quem se identifica — e o enunciado era
  reconstruído do próprio acervo, onde as decisões o transcrevem entre aspas.

  A reconstrução acertou 87,1% das vezes e errou calada no resto. Medido em
  20/11/2026 sobre os 1.525 precedentes em comum: 1.329 idênticos, 134 iguais a
  menos de acento, 30 em que um contém o outro, 9 de redação diferente e **23
  com o texto de outro precedente** — 18 deles súmulas com número trocado. A
  Súmula 70 do STF vinha com o enunciado da 323, e a 126 do STF com o da 126 do
  STJ. A causa é o próprio recorte: decisão cita súmulas em bloco — "Súmulas 70,
  323 e 547 do STF" — e o par número-texto mais próximo não é o par certo. O
  piso de três transcrições não pega isso, porque todas as decisões do bloco
  transcrevem do mesmo jeito: repetição confirma que o texto foi transcrito,
  nunca que foi transcrito para aquele número.

  Por isso o oficial vence, e `origem` registra de qual registro saiu o
  enunciado da linha. Nenhum precedente desaparece na troca — os 1.525 em comum
  existem todos no BNP, conferido antes de escrever isto —, e a reconstrução
  continua aqui como rede: sem carga do BNP, ela e o catálogo seguem entregando.

  `data` é exceção à precedência, e de propósito. Só o catálogo do STJ publica
  data de julgamento; o BNP não traz nenhuma. Tomar a data pela mesma regra do
  texto esvaziaria uma coluna 74,6% preenchida para substituí-la por nada, então
  ela atravessa a fusão: o texto vem do registro que venceu, a data vem de quem
  a tem.

  `situacao` deixa de ser nula onde o oficial entra, e é esta a razão da US. Dos
  precedentes que a tela já mostrava, 16 estão cancelados — 12 súmulas e 4
  temas — e apareciam como vigentes porque a reconstrução não carrega situação.
  O levantamento está em `documentation/architecture/pangea-source.md`.

  Súmula vinculante entra com tipo próprio. Os 62 números do BNP já existem como
  súmula do STF, e a Súmula Vinculante 1 não é a Súmula 1: fundir as duas na
  chave sobrescreveria 62 súmulas com o texto de outro instrumento.
*/
WITH citado AS (
  SELECT (REGEXP_MATCHES(
    UNACCENT(LOWER(REGEXP_REPLACE(ementa, '\s+', ' ', 'g'))),
    'sumula\s*(?:n[.oº°]*\s*)?([0-9]{1,4})\s*[/, -]*(?:do\s+)?(stj|stf)[^"]{0,70}"([^"]{40,})"',
    'g'
  )) AS achado
  FROM core.decisao
  WHERE ementa ~* 'S[uú]mula'
),

transcricao AS (
  SELECT
    UPPER(achado[2])  AS corte,
    achado[1]::BIGINT AS numero,
    BTRIM(achado[3])  AS enunciado,
    COUNT(*)          AS vezes
  FROM citado
  WHERE LENGTH(BTRIM(achado[3])) BETWEEN 40 AND 400
  GROUP BY 1, 2, 3
),

/* Sem corte declarada não há precedente: Súmula 7 do STJ e Súmula 7 do STF são
   coisas diferentes, e uma citação que não diz qual não tem chave. */
sumula AS (
  SELECT DISTINCT ON (corte, numero)
    corte              AS corte,
    'sumula'           AS tipo,
    numero             AS numero,
    enunciado          AS enunciado,
    CAST(NULL AS TEXT) AS situacao,
    CAST(NULL AS DATE) AS data,
    'reconstruido'     AS origem,
    vezes              AS transcricoes,
    CAST(NULL AS DATE) AS atualizado_em,
    3                  AS prioridade
  FROM transcricao
  WHERE vezes >= 3
  ORDER BY corte, numero, vezes DESC
),

/* O catálogo repete a mesma linha quando o tema tem vários processos ligados:
   mesmo sequencial, mesma tese. Tema sem tese firmada ainda está em
   julgamento e não é precedente — é pergunta. */
tema AS (
  SELECT DISTINCT ON (numero)
    'STJ'                                       AS corte,
    'tema'                                      AS tipo,
    "numeroPrecedente"::BIGINT                  AS numero,
    BTRIM("teseFirmada")                        AS enunciado,
    NULLIF(BTRIM(situacao), '')                 AS situacao,
    TO_DATE(NULLIF("dataJulgamento", ''), 'YYYY-MM-DD') AS data,
    'catalogo'                                  AS origem,
    CAST(NULL AS BIGINT)                        AS transcricoes,
    CAST(NULL AS DATE)                          AS atualizado_em,
    2                                           AS prioridade
  FROM raw.precedente_stj
  WHERE "tipoPrecedente" = 'Tema'
    AND COALESCE(BTRIM("teseFirmada"), '') <> ''
    AND "numeroPrecedente" ~ '^[0-9]+$'
  ORDER BY numero, "dataJulgamento" DESC NULLS LAST
),

/* O texto do BNP chega em dois campos e com marcação.

   Qual campo carrega o enunciado depende da corte, e o registro é consistente
   nisso: a súmula do STF vem em `questao` e tem `tese` igual à string literal
   "não informado" nas 734; a do STJ vem em `tese` e tem `questao` vazia nas
   676. Ler só `tese` daria 29,2% do registro como vazio. Para tema os dois
   campos querem dizer coisas diferentes — `tese` é o que foi firmado, `questao`
   é a pergunta que foi posta —, então ali vale a tese e só ela, pela mesma
   regra que o catálogo já aplica: tema sem tese é pergunta, não precedente.

   O STJ manda HTML — `<p>`, `<br>`, `<b>`, `<i>` — e o STF não. A tela lê o
   enunciado como texto dentro de uma citação, então a marcação sai aqui. Sai
   duas vezes: três temas trazem a tag escapada (`&lt;span&gt;`), e desescapar
   depois de limpar devolveria à tela a marcação que a primeira limpeza não
   podia ver. */
pangea AS (
  SELECT
    orgao                                                        AS orgao,
    tipo                                                         AS especie,
    nr::BIGINT                                                   AS numero,
    NULLIF(BTRIM(situacao), '')                                  AS situacao,
    TO_DATE(NULLIF(BTRIM("ultimaAtualizacao"), ''), 'DD/MM/YYYY') AS atualizado_em,
    REGEXP_REPLACE(
      REGEXP_REPLACE(
        REPLACE(REPLACE(REGEXP_REPLACE(COALESCE(tese, ''), '<[^>]+>', ' ', 'g'),
          '&lt;', '<'), '&gt;', '>'),
        '<[^>]+>', ' ', 'g'
      ),
      '\s+', ' ', 'g'
    )                                                            AS tese,
    REGEXP_REPLACE(
      REGEXP_REPLACE(
        REPLACE(REPLACE(REGEXP_REPLACE(COALESCE(questao, ''), '<[^>]+>', ' ', 'g'),
          '&lt;', '<'), '&gt;', '>'),
        '<[^>]+>', ' ', 'g'
      ),
      '\s+', ' ', 'g'
    )                                                            AS questao
  FROM raw.precedente_pangea
  WHERE orgao IN ('STF', 'STJ')
    AND tipo IN ('SUM', 'SV', 'RG', 'RR')
),

escolhivel AS (
  SELECT
    orgao,
    especie,
    numero,
    situacao,
    atualizado_em,
    CASE
      WHEN LOWER(BTRIM(tese)) IN ('', 'não informado', 'nao informado')
        THEN NULL
      ELSE BTRIM(tese)
    END AS tese,
    CASE
      WHEN LOWER(BTRIM(questao)) IN ('', 'não informado', 'nao informado')
        THEN NULL
      ELSE BTRIM(questao)
    END AS questao
  FROM pangea
),

oficial AS (
  SELECT DISTINCT ON (orgao, especie, numero)
    orgao   AS corte,
    CASE especie
      WHEN 'SUM' THEN 'sumula'
      WHEN 'SV'  THEN 'sumula_vinculante'
      ELSE 'tema'
    END     AS tipo,
    numero  AS numero,
    CASE
      WHEN especie IN ('SUM', 'SV') THEN COALESCE(tese, questao)
      ELSE tese
    END     AS enunciado,
    situacao             AS situacao,
    CAST(NULL AS DATE)   AS data,
    'oficial'            AS origem,
    CAST(NULL AS BIGINT) AS transcricoes,
    atualizado_em        AS atualizado_em,
    1                    AS prioridade
  FROM escolhivel
  WHERE CASE
          WHEN especie IN ('SUM', 'SV') THEN COALESCE(tese, questao)
          ELSE tese
        END IS NOT NULL
  ORDER BY orgao, especie, numero, atualizado_em DESC NULLS LAST
),

candidato AS (
  SELECT * FROM oficial
  UNION ALL SELECT * FROM tema
  UNION ALL SELECT * FROM sumula
),

escolhido AS (
  SELECT DISTINCT ON (corte, tipo, numero) *
  FROM candidato
  ORDER BY corte, tipo, numero, prioridade
)

SELECT
  e.corte                      AS corte,
  e.tipo                       AS tipo,
  e.numero                     AS numero,
  e.enunciado                  AS enunciado,
  e.situacao                   AS situacao,
  COALESCE(e.data, c.data)     AS data,
  CAST(NULL AS TEXT)           AS url_fonte,
  e.origem                     AS origem,
  e.transcricoes               AS transcricoes,
  e.atualizado_em              AS atualizado_em,
  NOW()                        AS carregado_em
FROM escolhido AS e
LEFT JOIN tema AS c
  ON c.corte = e.corte AND c.tipo = e.tipo AND c.numero = e.numero

;

JINJA_STATEMENT_BEGIN;
CREATE UNIQUE INDEX ON {{ this_model }} (corte, tipo, numero);
CREATE INDEX ON {{ this_model }} (tipo, numero);
JINJA_END;
