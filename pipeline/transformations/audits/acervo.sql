/*
  Auditorias sobre o acervo inteiro, não sobre a janela que acabou de ser
  construída.

  As regras de cobertura existem para pegar uma extração que parou de casar: a
  coluna fica nula em silêncio e a tela mostra "sem tese" para a coleção toda
  com cara de funcionamento normal. Todas têm um piso de tamanho — 100 mil
  linhas — porque porcentagem não distingue "a extração quebrou" de "esta
  tabela é uma amostra", e sem o piso todo ambiente de desenvolvimento
  reprovaria.

  Esse piso é o problema. Depois que `core.decisao` e `core.decisao_precedente`
  passaram a ser construídos por faixa de data, uma auditoria presa ao modelo
  roda sobre a janela: uma semana traz alguns milhares de linhas, nunca cem
  mil, e a regra deixa de verificar qualquer coisa — sem falhar, sem avisar,
  exatamente o fim silencioso que ela foi escrita para evitar.

  Avulsas, leem a tabela publicada inteira. O piso volta a significar o que
  significava, e a regra volta a valer todo dia em vez de só na reconstrução
  completa.
*/

AUDIT (
  name cobertura_de_tese_no_acervo,
  standalone true,
  dialect postgres
);
/* O piso é 4%: medido em 5,6% sobre 984.824 decisões, e a tendência sobe
   porque o padrão do CNJ é de 2024. */
SELECT 1 AS falha
FROM core.decisao
HAVING COUNT(*) > 100000
   AND COUNT(*) FILTER (WHERE tese IS NOT NULL) < COUNT(*) * 0.04;

AUDIT (
  name cobertura_de_deliberacao_no_acervo,
  standalone true,
  dialect postgres
);
/* O piso é sobre quem TEM dispositivo: sem ele não há o que ler. */
SELECT 1 AS falha
FROM core.decisao
WHERE decisao_texto IS NOT NULL
HAVING COUNT(*) > 100000
   AND COUNT(deliberacao) < COUNT(*) * 0.95;

AUDIT (
  name cobertura_de_resultado_no_acervo,
  standalone true,
  dialect postgres
);
SELECT 1 AS falha
FROM core.decisao
WHERE decisao_texto IS NOT NULL
HAVING COUNT(*) > 100000
   AND COUNT(resultado) < COUNT(*) * 0.90;

AUDIT (
  name cobertura_de_classe_no_acervo,
  standalone true,
  dialect postgres
);
/* O STJ escreve a classe por extenso e já manda quebra de linha no meio. Se a
   grafia mudar, o join para de casar e o filtro encolhe sem avisar. */
SELECT 1 AS falha
FROM core.decisao
HAVING COUNT(*) > 100000
   AND COUNT(classe_cnj) < COUNT(*) * 0.95;

AUDIT (
  name decisao_unica_no_acervo,
  standalone true,
  dialect postgres
);
/*
  Que nenhuma decisão apareça duas vezes na tabela inteira.

  A auditoria de unicidade presa ao modelo confere dentro da janela, e é ali
  que ela não basta. `INCREMENTAL_BY_TIME_RANGE` apaga a faixa antes de
  reescrevê-la: se a data de uma decisão mudar entre duas execuções — o que
  acontece quando a fonte preenche a data de julgamento de um registro que
  antes só tinha a de publicação — a linha nova entra na faixa nova e a antiga
  continua na antiga, que ninguém apagou. Duas linhas, nenhuma janela errada,
  e só uma leitura do acervo inteiro enxerga.
*/
SELECT 1 AS falha
FROM (
  SELECT fonte_codigo, identificador_fonte
  FROM core.decisao
  GROUP BY 1, 2
  HAVING COUNT(*) > 1
) AS repetida;
