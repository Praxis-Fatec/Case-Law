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
    ementa_busca         TSVECTOR
);

CREATE UNIQUE INDEX ON core.decisao (fonte_codigo, identificador_fonte);
CREATE INDEX ON core.decisao USING gin (ementa_busca);
