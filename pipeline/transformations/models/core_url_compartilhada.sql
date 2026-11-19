MODEL (
  name core.url_compartilhada,
  kind FULL,
  grain (fonte_codigo, identificador_fonte),
  audits (
    not_null(columns := (fonte_codigo, identificador_fonte, url_fonte, url_compartilhada)),
    unique_combination_of_columns(columns := (fonte_codigo, identificador_fonte)),
    url_aponta_para_um_acordao
  )
);

/*
  Quais decisões dividem o link da fonte com outra decisão nossa.

  Morava em `core.decisao`, como `COUNT(*) OVER (PARTITION BY url_fonte)`. É
  uma propriedade da coleção inteira: nenhuma linha sabe sozinha se o seu link
  alcança outra, e a resposta de uma decisão antiga muda quando chega uma nova
  que divide o link com ela. Enquanto estava lá, `core.decisao` não podia ser
  incremental — processar só a semana que chegou daria a resposta errada para
  tudo o que já estava na base.

  Aqui fora o cálculo continua sendo sobre a coleção inteira, e é barato
  porque lê só a chave e o endereço: nenhuma ementa, nenhum tsvector, nenhuma
  expressão regular. É o modelo que se reconstrói por completo a cada execução
  justamente para que o grande não precise.
*/

SELECT
  fonte_codigo,
  identificador_fonte,
  url_fonte,
  COUNT(*) OVER (PARTITION BY url_fonte) > 1 AS url_compartilhada
FROM core.decisao

;

JINJA_STATEMENT_BEGIN;
CREATE UNIQUE INDEX ON {{ this_model }} (fonte_codigo, identificador_fonte);
JINJA_END;
