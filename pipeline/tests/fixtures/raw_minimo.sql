-- The smallest collection that still exercises what the incremental build can
-- get wrong. Only the columns the models read: the real raw tables carry
-- dozens more that no transformation ever looks at.
--
-- The dates are chosen so a weekly window splits the set. Two decisions six
-- months apart share a source link on purpose: that pair is the reason
-- `url_compartilhada` had to leave `core.decisao`, and a build that answers it
-- from one window alone gets it wrong.

DROP SCHEMA IF EXISTS raw CASCADE;
DROP SCHEMA IF EXISTS verificacao CASCADE;
DROP SCHEMA IF EXISTS core CASCADE;
CREATE SCHEMA raw;
CREATE SCHEMA verificacao;
CREATE SCHEMA core;

CREATE TABLE raw.acordao_tjdft (
    uuid                     VARCHAR,
    identificador            VARCHAR NOT NULL,
    "dataJulgamento"         TIMESTAMPTZ,
    "dataPublicacao"         TIMESTAMPTZ,
    decisao                  VARCHAR,
    ementa                   VARCHAR,
    processo                 VARCHAR,
    "nomeRelator"            VARCHAR,
    "segredoJustica"         BOOLEAN,
    "turmaRecursal"          BOOLEAN,
    "descricaoOrgaoJulgador" VARCHAR,
    "codigoClasseCnj"        BIGINT,
    "possuiInteiroTeor"      BOOLEAN,
    _dlt_load_id             VARCHAR NOT NULL
);

CREATE TABLE raw.espelho_stj (
    id                  VARCHAR NOT NULL,
    "numeroProcesso"    VARCHAR,
    "numeroRegistro"    VARCHAR,
    "descricaoClasse"   VARCHAR,
    "nomeOrgaoJulgador" VARCHAR,
    "ministroRelator"   VARCHAR,
    "dataPublicacao"    VARCHAR,
    ementa              VARCHAR,
    "dataDecisao"       VARCHAR,
    decisao             VARCHAR,
    _dlt_load_id        VARCHAR NOT NULL,
    _dlt_id             VARCHAR NOT NULL
);

-- dlt puts a repeated field in a child table of its own, linked by the parent's
-- `_dlt_id`. The real name carries the arrow dlt builds it with.
CREATE TABLE raw."espelho_stj▶referenciasLegislativas" (
    value          VARCHAR,
    _dlt_parent_id VARCHAR NOT NULL,
    _dlt_list_idx  BIGINT NOT NULL,
    _dlt_id        VARCHAR NOT NULL
);

CREATE TABLE verificacao.link (
    fonte_codigo  TEXT NOT NULL,
    identificador TEXT NOT NULL,
    valido        BOOLEAN NOT NULL,
    verificado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (fonte_codigo, identificador)
);

CREATE TABLE core.precedente (
    corte        TEXT,
    tipo         TEXT,
    numero       BIGINT,
    enunciado    TEXT,
    situacao     TEXT,
    data         DATE,
    url_fonte    TEXT,
    origem       TEXT,
    transcricoes BIGINT
);

INSERT INTO raw.acordao_tjdft
    (uuid, identificador, "dataJulgamento", "dataPublicacao", decisao, ementa,
     processo, "nomeRelator", "segredoJustica", "turmaRecursal",
     "descricaoOrgaoJulgador", "codigoClasseCnj", "possuiInteiroTeor", _dlt_load_id)
VALUES
    ('3f1a9c2e-4b7d-4e81-9a2f-0c5d6e7a8b91', 'tj-001', '2026-01-05', '2026-01-09',
     'ACORDO: negar provimento ao recurso.',
     'APELACAO CIVEL. DANO MORAL. A ofensa a honra objetiva da pessoa juridica '
     'prescinde de prova do prejuizo. Recurso conhecido e nao provido. Decisao unanime.',
     '0700001-11.2026.8.07.0001', 'JOAO DA SILVA', FALSE, FALSE,
     '1a Turma Civel', 198, TRUE, 'carga-1'),

    ('7c2b8d4f-91a3-4c62-8e15-2d9f0a3b6c47', 'tj-002', '2026-01-12', '2026-01-16',
     'Deu-se provimento.',
     'APELACAO. USUCAPIAO EXTRAORDINARIO. Sumula 11 do STJ. A posse mansa e '
     'pacifica por quinze anos dispensa justo titulo. Recurso provido por maioria.',
     '0700002-11.2026.8.07.0001', 'MARIA SOUZA', FALSE, FALSE,
     '2a Turma Civel', 198, TRUE, 'carga-1'),

    -- Judged in one window, published in the next: the reference date is the
    -- judgement, so it belongs to the first and must not land in the second.
    ('a94e1b73-62cf-4d08-97b5-1e4a8c0d2f63', 'tj-003', '2026-01-19', '2026-02-02',
     NULL,
     'AGRAVO DE INSTRUMENTO. Tema 69 do STF. Exclusao do ICMS da base de calculo. '
     'Agravo conhecido e improvido. Votacao unanime.',
     '0700003-11.2026.8.07.0001', 'ANA PEREIRA', FALSE, TRUE,
     '3a Turma Civel', 202, FALSE, 'carga-2'),

    -- No judgement date at all: the reference date falls back to publication.
    ('5d0f7a16-83be-42c9-a6d1-7b3e9f2c4081', 'tj-004', NULL, '2026-02-10',
     NULL,
     'EMBARGOS DE DECLARACAO. Omissao inexistente. Embargos rejeitados a unanimidade.',
     '0700004-11.2026.8.07.0001', 'CARLOS LIMA', FALSE, FALSE,
     '1a Turma Civel', 1689, FALSE, 'carga-2'),

    -- Never reaches core.decisao, in any window.
    ('b62d4e09-17ca-4f35-8d90-3a6b1c8e5027', 'tj-005', '2026-01-07', '2026-01-11',
     NULL, 'SEGREDO DE JUSTICA. Conteudo reservado.',
     '0700005-11.2026.8.07.0001', 'JOAO DA SILVA', TRUE, FALSE,
     '1a Turma Civel', 198, FALSE, 'carga-1');

-- Both carry the same register number AND the same gazette date, so both
-- build the same source URL. The register alone names the case, not the
-- judgement: the publication date is what usually tells two of them apart, and
-- when the court publishes both in the same gazette it cannot. They are judged
-- six months apart, so they land in windows that are never built together.
INSERT INTO raw.espelho_stj
    (id, "numeroProcesso", "numeroRegistro", "descricaoClasse", "nomeOrgaoJulgador",
     "ministroRelator", "dataPublicacao", ementa, "dataDecisao", decisao, _dlt_load_id,
     _dlt_id)
VALUES
    ('stj-001', '2026/0000001-0', 'REG-777', 'RECURSO ESPECIAL', 'TERCEIRA TURMA',
     'MIN. PAULO COSTA', 'DJE DATA:20/01/2026',
     'RECURSO ESPECIAL. DANO MORAL. Sumula 7 do STJ. Incidencia. Agravo nao provido.',
     '20260115', 'Negaram provimento.', 'carga-1', 'dlt-stj-001'),

    ('stj-002', '2026/0000001-0', 'REG-777', 'AGRAVO INTERNO NO RECURSO ESPECIAL',
     'TERCEIRA TURMA', 'MIN. PAULO COSTA', 'DJE DATA:20/01/2026',
     'AGRAVO INTERNO. Sumula 7 do STJ. Reexame de provas. Agravo improvido.',
     '20260715', 'Negaram provimento.', 'carga-3', 'dlt-stj-002');

-- The legislative references, in the court's own fixed format and with the
-- shapes that can go wrong: a paragraph that belongs to its own article, one
-- reference naming three articles, a lettered article, a sphere outside the
-- three the story named, a header with no act code at all, and a blank entry.
-- The two decisions are judged six months apart, so the set is also split
-- across windows that are never built together.
INSERT INTO raw."espelho_stj▶referenciasLegislativas"
    (value, _dlt_parent_id, _dlt_list_idx, _dlt_id)
VALUES
    (E'LEG:FED DEL:003365 ANO:1941\n        ART:00026 PAR:00002',
     'dlt-stj-001', 0, 'ref-001'),

    (E'LEG:FED LEI:013105 ANO:2015\n *****  CPC-15    CODIGO DE PROCESSO CIVIL DE 2015\n        ART:00926   ART:00927 PAR:00003 PAR:00004',
     'dlt-stj-001', 1, 'ref-002'),

    (E'LEG:FED LEI:005869 ANO:1973\n        ART:0543B   INC:00003   LET:A   LET:C',
     'dlt-stj-001', 2, 'ref-003'),

    (E'LEG:MUN LEI:000123 ANO:2009\n        ART:00007\n (SAO PAULO - SP)',
     'dlt-stj-001', 3, 'ref-004'),

    (E'LEG:FED\n *****  SUM(STF)  SUMULA DO SUPREMO TRIBUNAL FEDERAL\n        SUM:000282',
     'dlt-stj-001', 4, 'ref-005'),

    ('   ', 'dlt-stj-001', 5, 'ref-006'),

    (E'LEG:FED CFB:****** ANO:1988\n        ART:00105   INC:00003   LET:A',
     'dlt-stj-002', 0, 'ref-007'),

    (E'LEG:FED LEI:007711 ANO:1988\n        ART:00003   PAR:UNICO',
     'dlt-stj-002', 1, 'ref-008');

INSERT INTO verificacao.link (fonte_codigo, identificador, valido) VALUES
    ('tjdft-jurisdf', 'tj-001', TRUE),
    ('tjdft-jurisdf', 'tj-002', FALSE),
    ('stj-espelhos',  'stj-001', TRUE);

-- Os mesmos valores de `origem` que core_precedente.sql escreve. A sumula
-- reconstruida nao tem data porque nenhuma tem: ela sai das transcricoes do
-- acervo, nao de coleta.
INSERT INTO core.precedente (corte, tipo, numero, enunciado, situacao, data, origem) VALUES
    ('STJ', 'sumula', 7, 'A pretensao de simples reexame de prova nao enseja recurso especial.', 'vigente', NULL, 'reconstruido'),
    ('STF', 'tema', 69, 'O ICMS nao compoe a base de calculo do PIS e da COFINS.', 'vigente', '2017-03-15', 'catalogo');
