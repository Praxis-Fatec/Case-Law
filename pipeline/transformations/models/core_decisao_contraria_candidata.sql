MODEL (
  name core.decisao_contraria_candidata,
  kind FULL,
  grain (fonte_codigo, identificador_fonte, contraria_fonte, contraria_identificador, corte, tipo, numero),
  audits (
    not_null(columns := (fonte_codigo, identificador_fonte, contraria_fonte, contraria_identificador, corte, tipo, numero, aderencia, contraria_aderencia, termos_comuns, peso_precedente)),
    unique_combination_of_columns(columns := (fonte_codigo, identificador_fonte, contraria_fonte, contraria_identificador, corte, tipo, numero)),
    contraria_tem_motivo,
    contraria_nao_e_ela_mesma,
    contraria_e_simetrica,
    contraria_acima_do_piso
  )
);

/*
  Os pares de decisões que disputam o mesmo precedente, antes de medir o quanto
  se parecem. O motivo da contradição mora aqui; `core.decisao_contraria`
  acrescenta o cosseno e é o que a API lê.

  O motivo é a aderência: duas decisões citando o MESMO precedente, uma
  seguindo e outra afastando ou distinguindo. É uma discordância que o próprio
  tribunal escreveu, e não uma leitura nossa de dois resultados. Resultado
  oposto NÃO é motivo — medido sobre 14.546 pares semelhantes, decisões
  parecidas divergem no resultado em 11,9% das vezes contra 25,7% esperados por
  acaso, então ele aponta para o lado contrário do que parece. Ele viaja em
  `core.decisao_contraria` como contexto, nunca como razão.

  O piso de 6,0 sobre `core.precedente_judicial` é o que separa precedente de
  assunto de súmula de admissibilidade. A Súmula 7/STJ é citada por 128.176
  decisões de todo assunto: duas decisões "disputando" a Súmula 7 quase sempre
  são dois casos sem nada em comum. Sem corte a regra gera 666 milhões de pares,
  quase todos assim; com o piso sobram 988 dos 1.002 precedentes e 3.325.818
  pares sobre 50.925 decisões, medidos em 17/11/2026. O menor peso que sobrevive
  ao corte é 6,05. A primeira versão disto
  usava uma lista de dez súmulas processuais escrita à mão, e ela estava errada
  por omissão: STF 280, STJ 568 e STJ 126 são tão processuais quanto as outras e
  respondiam sozinhas por 2,8 milhões de pares. Lista à mão é a armadilha que
  `publish.py` documenta no próprio cabeçalho.

  São dois modelos e não um por causa do planejador, medido no mesmo dia. Numa
  consulta só, o filtro de peso caía sobre uma expressão agregada —
  LN(contagem/contagem) — e o Postgres não sabe estimar isso: previa 9 linhas de
  aderência onde há 109.730, previa 1 par onde há 3,3 milhões, e com isso
  escolhia laço aninhado com o cosseno dentro. O build passou de 1h19 sem
  terminar, derramando 5,4 GB, já com `work_mem` de 1 GB aplicado — memória
  nunca foi o problema. Lendo uma tabela com estatística real, o cosseno escolhe
  joins de hash e busca por índice: 145,5 s aqui e 19min31s lá.

  Esta tabela tem 411 MB e vai para a dev e para a produção sem que nenhuma tela
  a leia, porque `publish.py` copia todo modelo do `core` e `test_publicacao`
  exige isso nas duas direções — a regra existe porque `core.precedente` e
  `core.doutrina` ficaram prontos no código e ausentes dos ambientes. O caminho
  que pouparia os 411 MB é uma tabela temporária na sessão do build, e ele custa
  mais do que economiza: o `depends_on` do SQLMesh não lê pre-statements, então
  a ordem de construção passaria a depender de uma lista de dependências escrita
  à mão, sem teste que a cobrisse. Preferiu-se o espaço.

  FULL, e não por faixa de data, pela mesma razão que `core.url_compartilhada`:
  ser contrária é propriedade do par, não da decisão. Uma decisão de ontem pode
  contradizer uma de 1998, e uma janela de datas só veria metade de cada par.

  Os dois `SET` valem para a sessão do build. O `work_mem` é a diferença entre
  terminar e não terminar: com os 4 MB padrão do servidor os joins sobre 14,6
  milhões de linhas de termo vão para o disco. O paralelismo fica desligado de
  propósito e não por ser lento — com memória suficiente o join escolhe um plano
  que estoura o `/dev/shm` de 64 MB padrão do container e morre com "could not
  resize shared memory segment". As duas coisas se escondem uma atrás da outra,
  porque sem memória o plano derrama em disco e nunca chega a pedir memória
  compartilhada. Pôr `shm_size: 1gb` nos três compose resolveria a segunda.
*/

SET work_mem = '1GB';

SET max_parallel_workers_per_gather = 0;

WITH aderencia AS (
  SELECT
    p.fonte_codigo,
    p.identificador_fonte,
    p.corte,
    p.tipo,
    p.numero,
    p.aderencia,
    w.peso
  FROM core.decisao_precedente AS p
  JOIN core.precedente_judicial AS w
    ON w.corte = p.corte AND w.tipo = p.tipo AND w.numero = p.numero
  WHERE p.resolvida
    AND p.aderencia IN ('seguiu', 'afastou', 'distinguiu')
    AND w.peso >= 6.0
),

-- Os termos raros são os mesmos que a US 20 usa para buscar candidatos: o piso
-- de 4,5 é o que `related.py` mede e justifica. Aqui eles fazem o papel de
-- peneira barata, antes de qualquer cosseno.
raros AS (
  SELECT
    d.fonte_codigo,
    d.identificador_fonte,
    ARRAY_AGG(t.lexeme) AS termos
  FROM core.decisao AS d
  CROSS JOIN LATERAL UNNEST(d.ementa_busca) AS t
  JOIN core.termo_judicial AS j ON j.termo = t.lexeme AND j.peso >= 4.5
  GROUP BY d.fonte_codigo, d.identificador_fonte
)

-- Nos dois sentidos: quem lê a decisão que seguiu o precedente e quem lê a que
-- o afastou merecem a mesma resposta, e `contraria_e_simetrica` é o que impede
-- uma direção de sumir.
SELECT
  a.fonte_codigo         AS fonte_codigo,
  a.identificador_fonte  AS identificador_fonte,
  b.fonte_codigo         AS contraria_fonte,
  b.identificador_fonte  AS contraria_identificador,
  a.corte                AS corte,
  a.tipo                 AS tipo,
  a.numero               AS numero,
  a.aderencia            AS aderencia,
  b.aderencia            AS contraria_aderencia,
  comum.termos_comuns    AS termos_comuns,
  a.peso                 AS peso_precedente,
  NOW()                  AS carregado_em
FROM aderencia AS a
JOIN aderencia AS b
  ON b.corte = a.corte
 AND b.tipo = a.tipo
 AND b.numero = a.numero
 AND (b.fonte_codigo, b.identificador_fonte) <> (a.fonte_codigo, a.identificador_fonte)
 AND (
       (a.aderencia = 'seguiu' AND b.aderencia IN ('afastou', 'distinguiu'))
    OR (b.aderencia = 'seguiu' AND a.aderencia IN ('afastou', 'distinguiu'))
     )
JOIN raros AS ra
  ON ra.fonte_codigo = a.fonte_codigo AND ra.identificador_fonte = a.identificador_fonte
JOIN raros AS rb
  ON rb.fonte_codigo = b.fonte_codigo AND rb.identificador_fonte = b.identificador_fonte
CROSS JOIN LATERAL (
  SELECT COUNT(*) AS termos_comuns
  FROM UNNEST(ra.termos) AS compartilhado(termo)
  WHERE compartilhado.termo = ANY(rb.termos)
) AS comum
WHERE ra.termos && rb.termos
  AND comum.termos_comuns >= 2

;

JINJA_STATEMENT_BEGIN;
/* O nome sai da VERSÃO do modelo, não do nome inteiro da tabela física, e a
   diferença é um caractere. `core.decisao_contraria_candidata` é o modelo de
   nome mais longo do projeto: a tabela física dá 45 caracteres, o SQLMesh
   acrescenta `_schema_tmp` ao construir um modelo FULL porque as declarações
   de pós-execução rodam contra a temporária antes da troca, e `_leitura` fecha
   em 64 — um acima do limite do Postgres, que o SQLMesh recusa em vez de
   truncar calado.

   Passou despercebido porque o estouro depende do hash: as versões anteriores
   terminaram em nove dígitos e couberam em 63 por um caractere. Nada no modelo
   mudou para quebrá-lo; mudou o número que o SQLMesh sorteou.

   A versão é a única parte que precisa variar — é dela que vem tanto a troca a
   cada mudança de modelo quanto a estabilidade entre os lotes de uma mesma
   construção, que é o que faz IF NOT EXISTS significar "já criei este". */
{% set tabela = this_model.split('.')[-1] | replace('"', '') %}
{% set versao = tabela.split('__')[-1] %}
CREATE INDEX IF NOT EXISTS "candidata_{{ versao }}_leitura"
  ON {{ this_model }} (fonte_codigo, identificador_fonte);

/* `core.decisao_contraria` lê esta tabela na mesma execução, e o cosseno só
   escolhe joins de hash sabendo que aqui há 6,3 milhões de linhas. Ver o ANALYZE
   de `core.precedente_judicial` para o que acontece sem isto. */
ANALYZE {{ this_model }};
JINJA_END;
