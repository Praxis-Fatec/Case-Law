-- Runs once, the first time the database is created.
-- Dropping the volume and bringing the service up again replays it.

-- Similarity search that tolerates typing errors: "usucapiao" finds "usucapião".
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Makes accents irrelevant when searching: "acao" finds "ação".
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Vector column and distance operators, used by semantic search later on.
CREATE EXTENSION IF NOT EXISTS vector;

-- Portuguese search that folds accents inside the dictionary instead of on the
-- text. Searching "acao" still finds "ação", and the highlighted snippet keeps
-- the accents the court actually wrote.
CREATE TEXT SEARCH CONFIGURATION portugues_sem_acento ( COPY = portuguese );
ALTER TEXT SEARCH CONFIGURATION portugues_sem_acento
  ALTER MAPPING FOR hword, hword_part, word WITH unaccent, portuguese_stem;
