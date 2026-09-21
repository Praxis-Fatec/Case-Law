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
    turma_recursal       BOOLEAN NOT NULL,
    possui_inteiro_teor  BOOLEAN NOT NULL,
    url_fonte            TEXT    NOT NULL,
    link_valido          BOOLEAN,
    ementa_busca         TSVECTOR
);

CREATE UNIQUE INDEX ON core.decisao (fonte_codigo, identificador_fonte);
CREATE INDEX ON core.decisao USING gin (ementa_busca);

CREATE TABLE core.fonte (
    codigo                 TEXT NOT NULL,
    nome                   TEXT NOT NULL,
    tribunal_sigla         TEXT NOT NULL,
    url_documento_template TEXT NOT NULL
);

INSERT INTO core.fonte VALUES (
    'tjdft-jurisdf', 'TJDFT JurisDF', 'TJDFT',
    'https://jurisdf.tjdft.jus.br/detalhes/{identificador}'
);

-- Written by the pipeline's link check, read by the core model.
DROP SCHEMA IF EXISTS verificacao CASCADE;
CREATE SCHEMA verificacao;
CREATE TABLE verificacao.link (
    identificador TEXT        PRIMARY KEY,
    valido        BOOLEAN     NOT NULL,
    verificado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
