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
/* Cada fonte abre o documento por uma chave própria, e trocá-las não quebra
   nada visível: a URL continua bem formada e o site responde 200. O TJDFT é uma
   SPA que só reconhece o uuid; o identificador leva para a home. O STJ entrega
   o inteiro teor pelo número de registro do processo; o id do espelho leva a
   uma página que diz que houve erro ao buscar o documento. Nenhuma das duas
   chaves é a que identifica o registro para nós, e é por isso que a primeira
   condição basta para o caso que importa: trocar a chave de volta deixaria as
   duas iguais em toda a coleção.

   O formato só é exigido do TJDFT. O número de registro do STJ vem como a fonte
   o publicou, e ela publica alguns quebrados — um registro de 1993 traz "19".
   Reprovar a carga por isso esconderia uma decisão real; a verificação do link
   é que tem de marcá-la como inalcançável. */
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
/* Veredicto gravado sob um código de fonte que não existe fica órfão: não casa
   com decisão nenhuma, não dá erro, e a decisão fica para sempre sem
   verificação como se ninguém tivesse olhado. Um erro de digitação na chave do
   registro de verificações produz exatamente isso. */
SELECT v.*
FROM verificacao.link AS v
LEFT JOIN core.fonte AS f
  ON f.codigo = v.fonte_codigo
WHERE f.codigo IS NULL
  AND EXISTS (SELECT 1 FROM @this_model);
