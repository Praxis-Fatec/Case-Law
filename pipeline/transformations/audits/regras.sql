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
  name identificador_unico_entre_fontes,
  dialect postgres
);
/* verificacao.link casa só pelo identificador, sem a fonte. Se duas fontes
   usarem o mesmo, a decisão exibe o link_valido da outra. As faixas do TJDFT e
   do STJ não se cruzam hoje, e é só isso que separa as duas — esta auditoria
   avisa no dia em que deixarem de não se cruzar. */
SELECT d.*
FROM @this_model AS d
WHERE EXISTS (
  SELECT 1
  FROM @this_model AS o
  WHERE o.identificador_fonte = d.identificador_fonte
    AND o.fonte_codigo <> d.fonte_codigo
);

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
   {identificador}, nada falha: a fonte inteira passa a apontar para a mesma
   página. */
SELECT *
FROM @this_model
WHERE POSITION(identificador_fonte IN url_fonte) = 0;

AUDIT (
  name ementa_nao_vazia,
  dialect postgres
);
/* not_null não pega string vazia. Ementa vazia é resultado sem texto na tela e
   sem nada para o índice de busca. */
SELECT *
FROM @this_model
WHERE TRIM(ementa) = '';
