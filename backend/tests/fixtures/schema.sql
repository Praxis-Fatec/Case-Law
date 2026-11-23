CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS vector;

DROP TEXT SEARCH CONFIGURATION IF EXISTS portugues_sem_acento;
CREATE TEXT SEARCH CONFIGURATION portugues_sem_acento ( COPY = portuguese );
ALTER TEXT SEARCH CONFIGURATION portugues_sem_acento
  ALTER MAPPING FOR hword, hword_part, word WITH unaccent, portuguese_stem;

DROP SCHEMA IF EXISTS core CASCADE;
CREATE SCHEMA core;

CREATE TABLE core.decisao (
    fonte_codigo         TEXT    NOT NULL,
    identificador_fonte  TEXT    NOT NULL,
    tribunal_sigla       TEXT    NOT NULL,
    processo             TEXT,
    orgao_julgador       TEXT,
    relator              TEXT,
    classe_cnj           BIGINT,
    data_julgamento      DATE,
    data_publicacao      DATE,
    data_referencia      DATE    NOT NULL,
    ementa               TEXT    NOT NULL,
    tipo_texto           TEXT,
    decisao_texto        TEXT,
    tese                 TEXT,
    resultado            TEXT,
    deliberacao          TEXT,
    turma_recursal       BOOLEAN NOT NULL,
    possui_inteiro_teor  BOOLEAN NOT NULL,
    url_fonte            TEXT    NOT NULL,
    link_valido          BOOLEAN,
    ementa_busca         TSVECTOR
);

CREATE UNIQUE INDEX ON core.decisao (fonte_codigo, identificador_fonte);
CREATE INDEX ON core.decisao USING gin (ementa_busca);

-- Whether a decision's source link still reaches more than one decision of
-- ours. Its own table because it is a property of the whole collection: the
-- answer for a decision from 2019 changes when a 2026 one arrives sharing the
-- link, which is what stopped `core.decisao` from being built by date range.
CREATE TABLE core.url_compartilhada (
    fonte_codigo         TEXT    NOT NULL,
    identificador_fonte  TEXT    NOT NULL,
    url_fonte            TEXT    NOT NULL,
    url_compartilhada    BOOLEAN NOT NULL,
    PRIMARY KEY (fonte_codigo, identificador_fonte)
);

CREATE TABLE core.termo_frequente (
    lexema       TEXT   NOT NULL,
    decisoes     BIGINT NOT NULL,
    carregado_em TIMESTAMPTZ,
    PRIMARY KEY (lexema)
);

CREATE TABLE core.busca_ampla (
    lexema              TEXT    NOT NULL,
    posicao             INTEGER NOT NULL,
    rank                REAL    NOT NULL,
    data_referencia     DATE    NOT NULL,
    fonte_codigo        TEXT    NOT NULL,
    identificador_fonte TEXT    NOT NULL,
    PRIMARY KEY (lexema, fonte_codigo, identificador_fonte)
);
-- The index is the feature, so the fixture carries it too: a test that asks
-- the planner how it answered has nothing to see without it.
CREATE INDEX ON core.busca_ampla
    (lexema, rank DESC, data_referencia DESC, fonte_codigo DESC, identificador_fonte DESC);

CREATE TABLE core.fonte (
    codigo                 TEXT NOT NULL,
    nome                   TEXT NOT NULL,
    conteudo               TEXT NOT NULL,
    tribunal_sigla         TEXT NOT NULL,
    url_documento_template TEXT NOT NULL,
    status                 TEXT NOT NULL
);

-- The four sources of seeds/fonte.csv, including the two that carry no
-- decision: RF16 answers for every source in the catalogue, and a source with
-- no decision is exactly the case a per-court answer cannot reach.
INSERT INTO core.fonte VALUES
('tjdft-jurisdf', 'TJDFT JurisDF', 'decisao', 'TJDFT',
 'https://jurisdf.tjdft.jus.br/acordaos/{documento}', 'ativa'),
('stj-espelhos', 'STJ Espelhos de Acórdãos', 'decisao', 'STJ',
 'https://processo.stj.jus.br/processo/revista/documento/mediado/?componente=ITA&sequencial={documento}', 'ativa'),
('stj-precedentes', 'STJ Precedentes Qualificados', 'precedente', 'STJ',
 '', 'ativa'),
('stj-bdjur', 'BDJur Biblioteca Digital do STJ', 'doutrina', 'STJ',
 'https://bdjur.stj.jus.br/handle/{documento}', 'bloqueada');

-- What each source covers, derived by core.cobertura_fonte. `stj-precedentes`
-- is here with nothing collected: a source in the catalogue that has never
-- delivered has to be able to say so.
CREATE TABLE core.cobertura_fonte (
    fonte_codigo     TEXT   NOT NULL,
    conteudo         TEXT   NOT NULL,
    itens            BIGINT NOT NULL,
    itens_sem_data   BIGINT NOT NULL,
    cobertura_inicio DATE,
    cobertura_fim    DATE,
    precisao         TEXT   NOT NULL
);

INSERT INTO core.cobertura_fonte VALUES
('tjdft-jurisdf',   'decisao',    9, 0, '2026-02-02', '2026-03-11', 'dia'),
('stj-espelhos',    'decisao',    4, 1, '1989-02-19', '2026-01-20', 'dia'),
('stj-bdjur',       'doutrina',   2, 0, '1953-01-01', '2026-01-01', 'ano'),
('stj-precedentes', 'precedente', 0, 0, NULL,         NULL,         'nenhuma');

-- The same row as pipeline/transformations/seeds/tribunal.csv.
CREATE TABLE core.tribunal (
    sigla  TEXT NOT NULL PRIMARY KEY,
    nome   TEXT NOT NULL,
    esfera TEXT,
    uf     TEXT
);

INSERT INTO core.tribunal VALUES (
    'TJDFT', 'Tribunal de Justiça do Distrito Federal e dos Territórios',
    'distrital', 'DF'
);

-- Written by the pipeline's link check, read by the core model.
DROP SCHEMA IF EXISTS verificacao CASCADE;
CREATE SCHEMA verificacao;
-- `fonte_codigo` is nullable, and so are the three columns only the JurisDF
-- can fill. A load that wrote nothing cannot be attributed to a source, and a
-- source with no secrecy flag and no link check reports nothing rather than
-- zero: zero would claim nobody looked and nothing was wrong at once.
CREATE TABLE core.carga (
    carga_id              TEXT        NOT NULL,
    fonte_codigo          TEXT,
    concluida_em          TIMESTAMPTZ NOT NULL,
    status                TEXT        NOT NULL,
    registros_lidos       BIGINT      NOT NULL,
    registros_gravados    BIGINT      NOT NULL,
    descartados_sigilo    BIGINT,
    links_invalidos       BIGINT,
    links_nao_verificados BIGINT
);

-- Two successful loads, so a test can tell "the most recent" from "any", and a
-- failed one dated after both: if the endpoint ever sorts before filtering, the
-- failure becomes the answer and the tests say so.
--
-- The rows below those three are dated earlier on purpose, so the collection's
-- own last update stays the JurisDF one and the per-source answers are the only
-- thing they change. Each carries a shape RF16 has to tell apart:
-- `stj-espelhos` succeeded and then failed, `stj-bdjur` only ever succeeded,
-- `stj-precedentes` has no load at all, and the last row belongs to no source.
INSERT INTO core.carga VALUES
('1789000000.0', 'tjdft-jurisdf', '2026-03-16 02:00:00+00', 'concluida', 6, 4, 2, 0, 4),
('1789000001.0', 'tjdft-jurisdf', '2026-03-17 02:00:00+00', 'concluida', 9, 9, 0, 0, 9),
('1789000002.0', 'tjdft-jurisdf', '2026-03-18 02:00:00+00', 'falhou',    0, 0, 0, 0, 0),
('1788000000.0', 'stj-espelhos',  '2026-01-10 02:00:00+00', 'concluida', 4, 4, NULL, NULL, NULL),
('1788000001.0', 'stj-espelhos',  '2026-01-21 02:00:00+00', 'falhou',    0, 0, NULL, NULL, NULL),
('1788000002.0', 'stj-bdjur',     '2026-01-05 02:00:00+00', 'concluida', 2, 2, NULL, NULL, NULL),
('1788000003.0', NULL,            '2026-01-06 02:00:00+00', 'concluida', 0, 0, NULL, NULL, NULL);

CREATE TABLE verificacao.link (
    fonte_codigo  TEXT        NOT NULL,
    identificador TEXT        NOT NULL,
    valido        BOOLEAN     NOT NULL,
    verificado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (fonte_codigo, identificador)
);

-- A amostra da tabela do CNJ que a transformação consulta. Traz de propósito
-- "Ação Rescisória" em dois códigos, um deles sob a árvore do STJ, para que o
-- desempate por raiz seja exercitado em vez de assumido.
CREATE TABLE core.classe_processual (
    codigo_cnj BIGINT NOT NULL PRIMARY KEY,
    codigo_pai BIGINT,
    nome       TEXT   NOT NULL
);

INSERT INTO core.classe_processual VALUES
(2,     NULL, 'PROCESSO CÍVEL E DO TRABALHO'),
(5,     NULL, 'SUPERIOR TRIBUNAL DE JUSTIÇA'),
(47,    2,    'Ação Rescisória'),
(1669,  5,    'Ação Rescisória'),
(198,   2,    'Apelação Cível'),
(213,   5,    'Recurso Especial'),
(1321,  5,    'Agravo Regimental'),
(1331,  5,    'Habeas Corpus');

CREATE TABLE core.precedente (
    corte        TEXT   NOT NULL,
    tipo         TEXT   NOT NULL,
    numero       BIGINT NOT NULL,
    enunciado    TEXT   NOT NULL,
    situacao     TEXT,
    data         DATE,
    url_fonte    TEXT,
    origem       TEXT   NOT NULL,
    transcricoes BIGINT,
    atualizado_em DATE,
    carregado_em TIMESTAMPTZ,
    PRIMARY KEY (corte, tipo, numero)
);

CREATE TABLE core.decisao_precedente (
    fonte_codigo        TEXT   NOT NULL,
    identificador_fonte TEXT   NOT NULL,
    corte               TEXT   NOT NULL,
    tipo                TEXT   NOT NULL,
    numero              BIGINT NOT NULL,
    trecho              TEXT   NOT NULL,
    resolvida           BOOLEAN NOT NULL,
    corte_declarada     BOOLEAN NOT NULL DEFAULT TRUE,
    aderencia           TEXT   NOT NULL,
    carregado_em        TIMESTAMPTZ,
    PRIMARY KEY (fonte_codigo, identificador_fonte, corte, tipo, numero)
);

-- One row per article cited, not per reference: a reference naming six
-- articles is six rows, which is why the article is part of the key.
CREATE TABLE core.referencia_legislativa (
    fonte_codigo        TEXT    NOT NULL,
    identificador_fonte TEXT    NOT NULL,
    ordem               BIGINT  NOT NULL,
    sequencia           INTEGER NOT NULL,
    esfera              TEXT,
    tipo_ato            TEXT,
    numero              BIGINT,
    ano                 INTEGER,
    artigo              TEXT,
    paragrafos          TEXT[],
    incisos             TEXT[],
    letras              TEXT[],
    reconhecida         BOOLEAN NOT NULL,
    texto_bruto         TEXT,
    data_referencia     DATE,
    carregado_em        TIMESTAMPTZ,
    PRIMARY KEY (fonte_codigo, identificador_fonte, ordem, sequencia)
);

CREATE TABLE core.doutrina (
    repositorio          TEXT NOT NULL,
    identificador_oai    TEXT NOT NULL,
    titulo               TEXT NOT NULL,
    titulos_alternativos TEXT[] NOT NULL DEFAULT '{}',
    autores              TEXT[] NOT NULL DEFAULT '{}',
    assuntos             TEXT[] NOT NULL DEFAULT '{}',
    tipo                 TEXT,
    data                 TEXT,
    ano                  BIGINT,
    idioma               TEXT,
    publicacao           TEXT,
    resumo               TEXT,
    referencia           TEXT,
    url_fonte            TEXT NOT NULL,
    direitos             TEXT,
    conjuntos            TEXT[] NOT NULL DEFAULT '{}',
    arquivada_em         TIMESTAMPTZ,
    alterada_em          TIMESTAMPTZ,
    busca                TSVECTOR,
    carregado_em         TIMESTAMPTZ,
    PRIMARY KEY (repositorio, identificador_oai)
);

CREATE INDEX ON core.doutrina USING gin (busca);

CREATE TABLE core.decisao_doutrina (
    fonte_codigo        TEXT NOT NULL,
    identificador_fonte TEXT NOT NULL,
    repositorio         TEXT NOT NULL,
    identificador_oai   TEXT NOT NULL,
    nota                DOUBLE PRECISION NOT NULL,
    termos              BIGINT NOT NULL,
    termo_mais_forte    DOUBLE PRECISION NOT NULL,
    casou_em            TEXT[] NOT NULL,
    distancia           INTEGER NOT NULL,
    carregado_em        TIMESTAMPTZ,
    PRIMARY KEY (fonte_codigo, identificador_fonte, repositorio, identificador_oai)
);

CREATE TABLE core.doutrina_termo (
    repositorio       TEXT NOT NULL,
    identificador_oai TEXT NOT NULL,
    termo             TEXT NOT NULL,
    decisoes          BIGINT NOT NULL,
    peso              DOUBLE PRECISION NOT NULL,
    carregado_em      TIMESTAMPTZ,
    PRIMARY KEY (repositorio, identificador_oai, termo)
);

-- The weights behind RF20, and the length of each decision's vector. The
-- endpoint probes for both with TO_REGCLASS and answers an empty list when
-- either is missing, so a suite that left them out would exercise only that
-- fallback and never the matching itself.
CREATE TABLE core.termo_judicial (
    termo        TEXT             NOT NULL,
    decisoes     BIGINT           NOT NULL,
    peso         DOUBLE PRECISION NOT NULL,
    carregado_em TIMESTAMPTZ,
    PRIMARY KEY (termo)
);

CREATE TABLE core.decisao_norma (
    fonte_codigo        TEXT             NOT NULL,
    identificador_fonte TEXT             NOT NULL,
    data_referencia     DATE             NOT NULL,
    norma               DOUBLE PRECISION NOT NULL,
    carregado_em        TIMESTAMPTZ,
    PRIMARY KEY (fonte_codigo, identificador_fonte)
);

-- `RF23`. No probe guards this one: where the table is absent the endpoint
-- answers 503, because an empty list on that screen reads as "no contradiction"
-- and saying that when nobody looked is the one wrong answer it cannot afford.
-- So the suite needs the table to exercise anything but the failure.
CREATE TABLE core.decisao_contraria (
    fonte_codigo            TEXT             NOT NULL,
    identificador_fonte     TEXT             NOT NULL,
    contraria_fonte         TEXT             NOT NULL,
    contraria_identificador TEXT             NOT NULL,
    corte                   TEXT             NOT NULL,
    tipo                    TEXT             NOT NULL,
    numero                  BIGINT           NOT NULL,
    aderencia               TEXT             NOT NULL,
    contraria_aderencia     TEXT             NOT NULL,
    termos_comuns           BIGINT           NOT NULL,
    peso_precedente         DOUBLE PRECISION NOT NULL,
    semelhanca              DOUBLE PRECISION NOT NULL,
    resultado_oposto        BOOLEAN,
    carregado_em            TIMESTAMPTZ,
    PRIMARY KEY (
        fonte_codigo, identificador_fonte,
        contraria_fonte, contraria_identificador,
        corte, tipo, numero
    )
);

-- Dropped here, created by `app/identidade.sql`: the accounts schema has one
-- definition, and a copy of it here would be a copy that drifts.
DROP SCHEMA IF EXISTS identidade CASCADE;

-- Likewise for `app/qualidade.sql`. Dropped too, not only recreated: its
-- reports reference the accounts dropped above, and `IF NOT EXISTS` would keep
-- a table whose foreign key the cascade already took away.
DROP SCHEMA IF EXISTS qualidade CASCADE;

-- And the same for the two that were left out, which is how the reason above
-- stopped being hypothetical: `pesquisa.salva` and `leitura` both reference
-- `identidade.usuario`, the cascade above dropped those keys, and the
-- `IF NOT EXISTS` in `app/pesquisa.sql` kept the table without them. The suite
-- passed on a database created that minute and failed on every run after, so
-- it was green in CI and red on the machine where somebody would see it.
DROP SCHEMA IF EXISTS pesquisa CASCADE;

DROP SCHEMA IF EXISTS leitura CASCADE;
