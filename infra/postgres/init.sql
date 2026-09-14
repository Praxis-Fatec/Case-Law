-- Runs once, the first time the database is created.
-- Dropping the volume and bringing the service up again replays it.

-- Similarity search that tolerates typing errors: "usucapiao" finds "usucapião".
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Makes accents irrelevant when searching: "acao" finds "ação".
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Vector column and distance operators, used by semantic search later on.
CREATE EXTENSION IF NOT EXISTS vector;
