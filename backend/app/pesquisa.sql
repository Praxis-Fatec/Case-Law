-- A named search belongs to the account that saved it, not to a publication.
--
-- Deliberately outside `core`, like `identidade` and `leitura`: publishing the
-- collection drops the whole core schema. The saved expression and filters
-- must survive that replacement and run against the newly published data.
-- Nothing here references a core table; saving a search does not freeze its
-- matching decisions.
--
-- Applied after `identidade.sql`, because the owner must already exist.

CREATE SCHEMA IF NOT EXISTS pesquisa;

CREATE TABLE IF NOT EXISTS pesquisa.salva (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id  UUID        NOT NULL REFERENCES identidade.usuario (id),
    nome        TEXT        NOT NULL,
    -- The request's expression (`q`) and applied filters travel together.
    -- JSONB keeps arrays, dates and future filter fields without flattening
    -- them into a URL or coupling this table to the collection's vocabulary.
    filtros     JSONB       NOT NULL,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT CLOCK_TIMESTAMP(),

    CONSTRAINT nome_tem_conteudo CHECK (LENGTH(BTRIM(nome)) > 0),
    CONSTRAINT filtros_sao_objeto CHECK (JSONB_TYPEOF(filtros) = 'object')
);

-- List the account's searches, newest first, without reading anyone else's.
CREATE INDEX IF NOT EXISTS salva_do_usuario
    ON pesquisa.salva (usuario_id, criado_em DESC);
