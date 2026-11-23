MODEL (
  name core.decisao_contraria,
  kind FULL,
  grain (fonte_codigo, identificador_fonte, contraria_fonte, contraria_identificador, corte, tipo, numero),
  audits (
    not_null(columns := (fonte_codigo, identificador_fonte, contraria_fonte, contraria_identificador, corte, tipo, numero, aderencia, contraria_aderencia, semelhanca, termos_comuns, peso_precedente)),
    unique_combination_of_columns(columns := (fonte_codigo, identificador_fonte, contraria_fonte, contraria_identificador, corte, tipo, numero)),
    contraria_tem_motivo,
    contraria_nao_e_ela_mesma,
    contraria_e_simetrica,
    contraria_acima_do_piso
  )
);

/*
  O par de decisões que se contradizem, o motivo da contradição e o quanto as
  duas se parecem — `RF23`. É esta tabela que a API lê.

  Quais pares existem é `core.decisao_contraria_candidata` que decide, e a
  medição que define a regra está em `opposing-decisions.md`. Aqui se acrescenta
  o cosseno, que é o que ordena a lista na tela, e o contexto de resultado.

  O cosseno é o mesmo de `RF20`, com os mesmos pesos e a mesma norma pronta em
  `core.decisao_norma`. Ser o mesmo importa: duas telas da mesma decisão dizendo
  semelhanças diferentes para o mesmo par seriam duas ferramentas discordando
  sobre o próprio acervo.

  `resultado_oposto` é contexto, nunca motivo. Medido sobre 14.546 pares
  semelhantes, decisões parecidas divergem no resultado em 11,9% das vezes
  contra 25,7% esperados por acaso: resultado oposto aponta para o lado
  contrário do que parece, e uma lista construída sobre ele seria uma lista de
  pares menos contraditórios que o acaso. Ele viaja na linha porque quem lê a
  tela quer saber, e não porque a linha exista por causa dele.

  Sem limiar de semelhança. A US 20 não usa nenhum — ordena e corta no topo — e
  inventar um aqui seria um número sem medição por trás. A distribuição está no
  documento e quem corta é o endpoint.

  Custo medido em 17/11/2026: 19min31s sobre os 3.325.818 pares, com os dois
  `SET` abaixo — 1170,73 s de insert mais as seis auditorias. O número vale
  anotado porque é a etapa cara da carga: o peso dos precedentes custa 1,2 s e
  os candidatos 145,5 s, e o cosseno custa oito vezes os dois juntos. Uma
  medição anterior deste mesmo passo deu 6min20s e estava medindo outra coisa —
  um recorte dos pares, não os 3,3 milhões. Os dois `SET` continuam sendo a
  diferença entre terminar e não terminar. Com o
  `work_mem` padrão do servidor, de 4 MB, os dois joins sobre 14,6 milhões de
  linhas de termo não cabem na memória e vão para o disco: 38 minutos sem
  terminar e 8,8 GB de arquivos temporários. O paralelismo fica desligado de
  propósito e não por ser lento — com memória suficiente, o join escolhe um
  plano que estoura o `/dev/shm` de 64 MB padrão do container e morre com "could
  not resize shared memory segment". As duas coisas se escondem uma atrás da
  outra, porque sem memória o plano derrama em disco e nunca chega a pedir
  memória compartilhada. Pôr `shm_size: 1gb` nos três compose resolveria o
  segundo problema e devolveria o paralelismo.

  Os `SET` valem para a sessão do build e não alcançam a API, que lê a tabela
  pronta pelo índice.
*/

SET work_mem = '1GB';

SET max_parallel_workers_per_gather = 0;

WITH termos AS (
  SELECT
    d.fonte_codigo,
    d.identificador_fonte,
    t.lexeme AS termo,
    j.peso * (1 + LN(ARRAY_LENGTH(t.positions, 1))) AS valor
  FROM core.decisao AS d
  CROSS JOIN LATERAL UNNEST(d.ementa_busca) AS t
  JOIN core.termo_judicial AS j ON j.termo = t.lexeme
)

SELECT
  p.fonte_codigo                                      AS fonte_codigo,
  p.identificador_fonte                               AS identificador_fonte,
  p.contraria_fonte                                   AS contraria_fonte,
  p.contraria_identificador                           AS contraria_identificador,
  p.corte                                             AS corte,
  p.tipo                                              AS tipo,
  p.numero                                            AS numero,
  p.aderencia                                         AS aderencia,
  p.contraria_aderencia                               AS contraria_aderencia,
  p.termos_comuns                                     AS termos_comuns,
  p.peso_precedente                                   AS peso_precedente,
  SUM(ta.valor * tb.valor) / (na.norma * nb.norma)    AS semelhanca,
  (da.resultado IS NOT NULL
   AND db.resultado IS NOT NULL
   AND da.resultado <> db.resultado
   AND da.resultado IN ('provido', 'negado')
   AND db.resultado IN ('provido', 'negado'))         AS resultado_oposto,
  NOW()                                               AS carregado_em
FROM core.decisao_contraria_candidata AS p
JOIN termos AS ta
  ON ta.fonte_codigo = p.fonte_codigo AND ta.identificador_fonte = p.identificador_fonte
JOIN termos AS tb
  ON tb.fonte_codigo = p.contraria_fonte
 AND tb.identificador_fonte = p.contraria_identificador
 AND tb.termo = ta.termo
JOIN core.decisao_norma AS na
  ON na.fonte_codigo = p.fonte_codigo AND na.identificador_fonte = p.identificador_fonte
JOIN core.decisao_norma AS nb
  ON nb.fonte_codigo = p.contraria_fonte AND nb.identificador_fonte = p.contraria_identificador
JOIN core.decisao AS da
  ON da.fonte_codigo = p.fonte_codigo AND da.identificador_fonte = p.identificador_fonte
JOIN core.decisao AS db
  ON db.fonte_codigo = p.contraria_fonte AND db.identificador_fonte = p.contraria_identificador
GROUP BY
  p.fonte_codigo, p.identificador_fonte, p.contraria_fonte, p.contraria_identificador,
  p.corte, p.tipo, p.numero, p.aderencia, p.contraria_aderencia, p.termos_comuns,
  p.peso_precedente,
  na.norma, nb.norma, da.resultado, db.resultado

;

JINJA_STATEMENT_BEGIN;
{% set tabela = this_model.split('.')[-1] | replace('"', '') %}
CREATE INDEX IF NOT EXISTS "{{ tabela }}_leitura"
  ON {{ this_model }} (fonte_codigo, identificador_fonte, semelhanca DESC);
JINJA_END;
