MODEL (
  name core.precedente_judicial,
  kind FULL,
  cron '@monthly',
  grain (corte, tipo, numero),
  audits (
    not_null(columns := (corte, tipo, numero, decisoes, peso)),
    unique_combination_of_columns(columns := (corte, tipo, numero)),
    precedente_judicial_com_peso
  )
);

/*
  Cada precedente que o acervo cita, com o quanto ele distingue uma decisão das
  outras. É o `core.termo_judicial` dos precedentes, e existe pelo mesmo motivo.

  O peso é o mesmo IDF — LN(decisões / decisões que citam o precedente) — e ele
  separa duas coisas que a tabela de citações mistura. A Súmula 7/STJ é citada
  por 128.176 decisões de todo assunto: ela não diz nada sobre o que a decisão
  trata, só que alguém tentou reexaminar fatos. A Súmula 596/STJ é citada por
  algumas centenas, todas sobre a mesma coisa.

  Medido em 17/11/2026 sobre os 1.002 precedentes resolvidos do acervo. A ordem
  que o peso produz é a prova de que ele mede o que se queria: Súmula 7/STJ em
  2,05, STF 284 em 3,50, STJ 83 em 3,52, STF 280 em 4,70 — as quatro
  admissibilidades mais citadas são os quatro menores pesos da tabela, sem que
  ninguém tenha escrito uma lista de súmulas processuais.

  Sem piso, ao contrário de `core.termo_judicial`. Lá o piso de 2,0 derruba 95
  de 540.198 termos e é proteção contra caso extremo; aqui qualquer piso
  derrubaria justamente os precedentes mais citados do acervo, e uma tabela
  chamada `precedente_judicial` sem a Súmula 7 seria uma tabela que mente. Quem
  precisa de corte aplica o seu: `core.decisao_contraria_candidata` usa 6,0.

  Mensal pela mesma razão que o vocabulário: o IDF obriga a ler o acervo
  inteiro, não cabe em faixa de data, e não se move quando o acervo cresce 0,1%
  numa semana.
*/

WITH acervo AS (
  SELECT COUNT(*)::DOUBLE PRECISION AS decisoes FROM core.decisao
),

citacao AS (
  SELECT
    corte                                                             AS corte,
    tipo                                                              AS tipo,
    numero                                                            AS numero,
    COUNT(DISTINCT CONCAT(fonte_codigo, '|', identificador_fonte))    AS decisoes
  FROM core.decisao_precedente
  WHERE resolvida
  GROUP BY corte, tipo, numero
)

SELECT
  c.corte                                       AS corte,
  c.tipo                                        AS tipo,
  c.numero                                      AS numero,
  c.decisoes                                    AS decisoes,
  LN(a.decisoes / GREATEST(c.decisoes, 1))      AS peso,
  NOW()                                         AS carregado_em
FROM citacao AS c
CROSS JOIN acervo AS a

;

JINJA_STATEMENT_BEGIN;
{% set tabela = this_model.split('.')[-1] | replace('"', '') %}
CREATE UNIQUE INDEX IF NOT EXISTS "{{ tabela }}_chave"
  ON {{ this_model }} (corte, tipo, numero);
CREATE INDEX IF NOT EXISTS "{{ tabela }}_peso" ON {{ this_model }} (peso);

/* Pelo mesmo motivo que `core.decisao` faz isto: tabela recém-escrita não tem
   estatística até o autovacuum passar, e `core.decisao_contraria_candidata` lê
   esta aqui logo em seguida, na mesma execução. Sem o ANALYZE, o piso de 6,0
   cai sobre a seletividade padrão de um terço — 334 precedentes em vez de 989 —
   e o plano dos candidatos muda de forma: 18 minutos sem terminar, contra
   2min10s com a estatística no lugar. Custa menos de um segundo em 232 kB. */
ANALYZE {{ this_model }};
JINJA_END;
