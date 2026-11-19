MODEL (
  name core.termo_judicial,
  kind FULL,
  cron '@monthly',
  grain (termo),
  audits (
    not_null(columns := (termo, decisoes, peso)),
    unique_combination_of_columns(columns := (termo)),
    termo_judicial_acima_do_piso,
    termo_judicial_com_cobertura
  )
);

/*
  O vocabulário do acervo inteiro, com o quanto cada palavra distingue uma
  decisão das outras.

  `core.doutrina_termo` já guarda esse peso, mas só para as palavras que a
  doutrina usa, e com a justificativa escrita de que varrer as 548.197
  palavras das ementas custaria carga sem mudar resultado. Para ligar uma
  decisão a outra, essas palavras são exatamente o que importa: a doutrina
  não tem nada a dizer sobre o vocabulário que duas decisões compartilham.

  O peso é o mesmo IDF, pela mesma razão medida em `doctrine-matching.md`:
  palavra de processo é comum e não distingue nada, palavra de assunto é rara
  e distingue tudo. Casar duas decisões por busca textual traz as que
  compartilham a prosa processual — e todas compartilham.

  Medido sobre o acervo em 11/11/2026: 540.198 termos de quatro letras ou
  mais, dos quais 540.103 passam do piso de 2,0. O piso derruba 95 termos, e
  não os milhares que a redação de `core.doutrina_termo` sugere: ele
  corresponde a aparecer em mais de 134.133 decisões, o que quase nenhuma
  palavra faz. Fica porque custa nada e protege do caso extremo, não porque
  esteja filtrando muito.

  Lido de `ementa_busca` e não de `ementa`: a coluna já é o tsvector que a
  busca usa, com a mesma configuração, então o peso vale para os mesmos
  lexemas que o casamento vai comparar. Tokenizar de novo abriria espaço para
  as duas pontas discordarem.

  Contado com UNNEST e não com `TS_STAT`, que seria o caminho óbvio. O
  argumento do `TS_STAT` é uma string, e o SQLMesh não reescreve nome de
  tabela dentro de string: o `FROM core.decisao` escrito ali continuaria
  apontando para a view publicada enquanto o resto da consulta lê o snapshot
  sendo construído. A contagem viria de uma versão do acervo e as frequências
  de outra, sem erro nenhum para denunciar.

  Mensal, não a cada ingestão, pelo mesmo motivo do vocabulário da doutrina:
  o IDF obriga a ler o acervo inteiro e não cabe em faixa de data, mas o
  número quase não se move quando o acervo cresce 0,1% numa semana.
*/

WITH acervo AS (
  SELECT COUNT(*)::DOUBLE PRECISION AS decisoes FROM core.decisao
),

frequencia AS (
  SELECT
    t.lexeme             AS termo,
    COUNT(*)             AS decisoes
  FROM core.decisao AS d
  CROSS JOIN LATERAL UNNEST(d.ementa_busca) AS t
  WHERE LENGTH(t.lexeme) >= 4
  GROUP BY t.lexeme
)

SELECT
  f.termo                                       AS termo,
  f.decisoes                                    AS decisoes,
  LN(a.decisoes / GREATEST(f.decisoes, 1))      AS peso,
  NOW()                                         AS carregado_em
FROM frequencia AS f
CROSS JOIN acervo AS a
WHERE LN(a.decisoes / GREATEST(f.decisoes, 1)) >= 2.0

;

JINJA_STATEMENT_BEGIN;
{% set tabela = this_model.split('.')[-1] | replace('"', '') %}
CREATE UNIQUE INDEX IF NOT EXISTS "{{ tabela }}_termo" ON {{ this_model }} (termo);
JINJA_END;
