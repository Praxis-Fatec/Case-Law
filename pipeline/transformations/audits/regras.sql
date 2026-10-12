AUDIT (
  name sem_segredo_de_justica,
  dialect postgres
);
/* Nenhuma decisão em segredo de justiça pode chegar ao núcleo.
   O filtro está na transformação; esta auditoria é a rede de segurança. */
SELECT d.*
FROM @this_model AS d
JOIN raw.acordao_tjdft AS r
  ON r.identificador = d.identificador_fonte
WHERE COALESCE(r."segredoJustica", FALSE);

AUDIT (
  name data_referencia_preenchida,
  dialect postgres
);
/* Documento sem nenhuma data não é filtrável nem ordenável — não serve ao produto. */
SELECT * FROM @this_model WHERE data_referencia IS NULL;

AUDIT (
  name data_do_stj_convertida,
  dialect postgres
);
/* dataDecisao chega como texto YYYYMMDD. Mudou o formato, TO_DATE devolve NULL
   calado e a decisão some do filtro por período em vez de dar erro. */
SELECT d.*
FROM @this_model AS d
JOIN raw.espelho_stj AS r
  ON r.id = d.identificador_fonte
WHERE d.fonte_codigo = 'stj-espelhos'
  AND COALESCE(TRIM(r."dataDecisao"), '') <> ''
  AND d.data_julgamento IS NULL;

AUDIT (
  name url_carrega_o_identificador,
  dialect postgres
);
/* O link sai do template do seed por REPLACE. Se o template perder o
   {documento}, nada falha: a fonte inteira passa a apontar para a mesma página.
   O token não é a chave do registro: o TJDFT abre o acórdão pelo uuid, o STJ
   pelo próprio id. */
SELECT *
FROM @this_model
WHERE POSITION(identificador_documento IN url_fonte) = 0;

AUDIT (
  name ementa_nao_vazia,
  dialect postgres
);
/* not_null não pega string vazia. Ementa vazia é resultado sem texto na tela e
   sem nada para o índice de busca. */
SELECT *
FROM @this_model
WHERE TRIM(ementa) = '';

AUDIT (
  name token_do_documento_por_fonte,
  dialect postgres
);
/* Trocar a chave não quebra nada visível: a URL continua bem formada e o site
   responde 200. Nenhuma fonte abre pelo identificador do registro, então a
   primeira condição pega a troca em toda a coleção de uma vez. O formato só é
   exigido do TJDFT: o STJ publica alguns números de registro quebrados, e
   reprovar a carga por isso esconderia decisão real. */
SELECT *
FROM @this_model
WHERE identificador_documento = identificador_fonte
   OR (
     fonte_codigo = 'tjdft-jurisdf'
     AND identificador_documento !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
   );

AUDIT (
  name verdito_de_fonte_conhecida,
  dialect postgres
);
/* Veredicto sob código de fonte inexistente fica órfão: não casa com nada, não
   dá erro, e a decisão fica sem verificação para sempre. */
SELECT v.*
FROM verificacao.link AS v
LEFT JOIN core.fonte AS f
  ON f.codigo = v.fonte_codigo
WHERE f.codigo IS NULL
  AND EXISTS (SELECT 1 FROM @this_model);

AUDIT (
  name deliberacao_de_valor_conhecido,
  dialect postgres
);
/* Uma captura de grupo que vaze texto cru, ou um erro de digitação na
   expressão, enche a coluna de valor que a tela não sabe traduzir — e a tela
   não reclama, só mostra em branco. */
SELECT *
FROM @this_model
WHERE deliberacao IS NOT NULL
  AND deliberacao NOT IN ('unanime', 'maioria');

AUDIT (
  name deliberacao_com_cobertura,
  dialect postgres
);
/* O dispositivo declara unanimidade ou maioria em 99,81% das decisões que o
   trazem. No dia em que o TJDFT mudar a redação, ou o STJ mudar o preâmbulo do
   acórdão, a expressão para de casar e a coluna fica nula em silêncio: a tela
   mostra "não informado" para a coleção inteira, com aparência de normalidade.

   O piso é 95% das decisões COM dispositivo, não do acervo: 535 decisões não
   trazem o campo, e cobrá-las seria cobrar o que a fonte não mandou. Só vale a
   partir de 100 mil linhas, senão todo ambiente de amostra reprova e a equipe
   aprende a ignorar a auditoria. */
SELECT 1 AS falha
FROM @this_model
WHERE decisao_texto IS NOT NULL
HAVING COUNT(*) > 100000
   AND COUNT(deliberacao) < COUNT(*) * 0.95;
