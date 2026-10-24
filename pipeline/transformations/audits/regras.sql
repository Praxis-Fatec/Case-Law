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
/* Valor que a tela não traduz não dá erro: ela mostra em branco. */
SELECT *
FROM @this_model
WHERE deliberacao IS NOT NULL
  AND deliberacao NOT IN ('unanime', 'maioria');

AUDIT (
  name deliberacao_com_cobertura,
  dialect postgres
);
/* Se o tribunal mudar a redação a expressão para de casar e a coluna fica nula
   em silêncio. O piso é sobre quem TEM dispositivo, e só a partir de 100 mil
   linhas, senão todo ambiente de amostra reprova. */
SELECT 1 AS falha
FROM @this_model
WHERE decisao_texto IS NOT NULL
HAVING COUNT(*) > 100000
   AND COUNT(deliberacao) < COUNT(*) * 0.95;

AUDIT (
  name resultado_de_valor_conhecido,
  dialect postgres
);
/* Valor que a tela não traduz não dá erro: ela mostra em branco. */
SELECT *
FROM @this_model
WHERE resultado IS NOT NULL
  AND resultado NOT IN ('provido', 'parcialmente_provido', 'negado');

AUDIT (
  name resultado_com_cobertura,
  dialect postgres
);
/* Se o tribunal mudar a redação a expressão para de casar e a coluna fica nula
   em silêncio. O piso é sobre quem TEM dispositivo, e só a partir de 100 mil
   linhas, senão todo ambiente de amostra reprova. */
SELECT 1 AS falha
FROM @this_model
WHERE decisao_texto IS NOT NULL
HAVING COUNT(*) > 100000
   AND COUNT(resultado) < COUNT(*) * 0.90;

AUDIT (
  name resultado_sem_contradicao,
  dialect postgres
);
/* Os padrões se contêm, então a ordem da cascata é a regra — e trocá-la não
   quebra nada visível, só erra o rótulo. Aqui cada rótulo é confrontado com o
   padrão que tem prioridade sobre ele. */
SELECT *
FROM @this_model
WHERE resultado IS NOT NULL
  AND (
    (resultado = 'provido'
     AND UNACCENT(LOWER(decisao_texto)) ~ '\mneg\w+\s+(-lhe\s+)?provimento|neg\w+-lhe\s+provimento|\mdesprovi|\mimprovi|\mnao\s+provi|\mnao\s+conhec|\mrejeit|\mindeferi|\mnao\s+acolh|\mdenega')
    OR (resultado <> 'parcialmente_provido'
     AND UNACCENT(LOWER(decisao_texto)) ~ 'parcial\w*\s+(provi|procedent)|provi\w*\s+(em\s+)?parte|provimento\s+parcial|acolh\w+\s+(em\s+)?parte|em\s+parte\s+provi')
    OR ((SELECT COUNT(*) FROM REGEXP_MATCHES(UNACCENT(LOWER(decisao_texto)), 'recurso d[eo] |recurso interposto|opostos? pel|interposto pel|apelacao d[eo] ', 'g')) >= 2
     AND UNACCENT(LOWER(decisao_texto)) ~ '\mneg\w+\s+(-lhe\s+)?provimento|neg\w+-lhe\s+provimento|\mdesprovi|\mimprovi|\mnao\s+provi'
     AND UNACCENT(LOWER(decisao_texto)) ~ '\md[aeo]\w*\s+(-lhe\s+)?provimento|deu-lhe\s+provimento|\mprovi[dm]')
  );

AUDIT (
  name classe_de_codigo_conhecido,
  dialect postgres
);
/* A ponte do STJ é um join por nome. Código que não existe na tabela significa
   que a semente andou sem o modelo, e a tela mostra um filtro que não filtra. */
SELECT d.*
FROM @this_model AS d
LEFT JOIN core.classe_processual AS c ON c.codigo_cnj = d.classe_cnj
WHERE d.classe_cnj IS NOT NULL
  AND c.codigo_cnj IS NULL;

AUDIT (
  name classe_com_cobertura,
  dialect postgres
);
/* O STJ escreve a classe por extenso e já manda quebra de linha no meio. Se a
   grafia mudar, o join para de casar e a coluna fica nula em silêncio: o filtro
   encolhe sem avisar. Só vale a partir de 100 mil linhas, senão todo ambiente
   de amostra reprova. */
SELECT 1 AS falha
FROM @this_model
HAVING COUNT(*) > 100000
   AND COUNT(classe_cnj) < COUNT(*) * 0.95;

AUDIT (
  name precedente_de_corte_conhecida,
  dialect postgres
);
/* Súmula 7 do STJ e Súmula 7 do STF são precedentes diferentes. Uma linha sem
   corte declarada colidiria com a outra na chave. */
SELECT *
FROM @this_model
WHERE corte NOT IN ('STJ', 'STF');

AUDIT (
  name precedente_com_enunciado,
  dialect postgres
);
/* O enunciado é o produto: sem ele, sobra a contagem de citações, que é outra
   história. Um recorte que pegou pontuação em vez de texto cai aqui. */
SELECT *
FROM @this_model
WHERE LENGTH(BTRIM(COALESCE(enunciado, ''))) < 40;

AUDIT (
  name precedente_com_volume,
  dialect postgres
);
/* Se o tribunal mudar a forma de transcrever, o recorte para de casar e a
   tabela encolhe em silêncio — a tela mostraria menos precedentes sem avisar.
   As duas origens degradam por motivos diferentes — o tribunal muda a forma de
   transcrever, ou o portal muda o CSV —, então cada uma tem o próprio piso.
   Hoje: 340 súmulas reconstruídas e 1.142 temas do catálogo. */
SELECT 1 AS falha
FROM @this_model
GROUP BY origem
HAVING (origem = 'reconstruido' AND COUNT(*) < 300)
    OR (origem = 'catalogo' AND COUNT(*) < 1000);

AUDIT (
  name citacao_de_tipo_conhecido,
  dialect postgres
);
/* Tipo fora da lista não casa com core.precedente: órfã, e sem erro. */
SELECT *
FROM @this_model
WHERE tipo NOT IN ('sumula', 'tema')
   OR corte NOT IN ('STJ', 'STF');

AUDIT (
  name citacao_com_volume,
  dialect postgres
);
/* Redação muda, extração encolhe calada: o indicador mediria menos acervo. */
SELECT 1 AS falha
FROM @this_model
HAVING COUNT(*) < 300000;

AUDIT (
  name aderencia_de_valor_conhecido,
  dialect postgres
);
/* Valor que a tela não traduz não dá erro: ela mostra em branco. */
SELECT *
FROM @this_model
WHERE aderencia IS NOT NULL
  AND aderencia NOT IN ('seguiu', 'afastou', 'distinguiu');

AUDIT (
  name aderencia_sem_contradicao,
  dialect postgres
);
/* "nao se aplica" contém "aplica": trocar a ordem da cascata não quebra nada
   visível, só inverte o rótulo. */
SELECT *
FROM @this_model
WHERE aderencia IN ('seguiu', 'distinguiu')
  AND trecho ~ 'nao\s+(se\s+)?(aplica|incid|atrai)|inaplica|superad[oa]|nao\s+obsta|nao\s+ha\s+falar\s+em\s+(aplicacao|incidencia)|afastad\w*\s+(a\s+|o\s+)?(incidencia|aplicacao|obice)';

AUDIT (
  name aderencia_com_cobertura,
  dialect postgres
);
/* Se o vocabulário do tribunal mudar, a coluna fica nula em silêncio e o
   indicador encolhe sem avisar. Hoje a cobertura é de 76%. */
SELECT 1 AS falha
FROM @this_model
HAVING COUNT(*) > 100000
   AND COUNT(aderencia) < COUNT(*) * 0.65;
