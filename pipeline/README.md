# Case Law — Pipeline

Extraction and transformation of judicial decision data. Runs on a developer
machine, not on a server: the data is historical and loaded in batches.

```
  court APIs  ──dlt──>  raw schema  ──SQLMesh──>  treated  ──>  core
```

Two tools for two jobs. **dlt** brings data in without changing it, so a reload
never needs to hit the API again. **SQLMesh** turns the raw data into the tables
the API reads.

## Requirements

- [uv](https://docs.astral.sh/uv/)
- A PostgreSQL to load into — `docker compose up -d` at the repository root

## Setup

```bash
cd pipeline
uv sync
cp .env.example .env
```

## Running the extraction

```bash
uv run python -m sources.example
```

Loads a single row into `raw.connection_check`. It exists to prove the connection
works and to show the shape of a source; the real TJDFT connector arrives with
the search User Story.

dlt also creates `raw._dlt_loads` on its own, recording every run with its id,
status and timestamp.

## Running the transformation

```bash
cd transformations
uv run sqlmesh info      # checks the connection and lists the models
uv run sqlmesh plan      # shows what changed before touching anything
```

`plan` is the important one: it reports which models changed and what would be
rebuilt, and waits for confirmation. Add `--auto-apply` to skip the prompt.

## Configuration

Everything comes from the environment. Nothing is hardcoded.

| Variable | Used by | Default |
|---|---|---|
| `POSTGRES_HOST` `POSTGRES_PORT` | SQLMesh | `localhost` `5432` |
| `POSTGRES_DB` `POSTGRES_USER` `POSTGRES_PASSWORD` | SQLMesh | `caselaw` `postgres` `postgres` |
| `DESTINATION__POSTGRES__CREDENTIALS` | dlt | full connection URL |

dlt uses its own variable name because that is the convention it reads by
default. Keeping it avoids a translation layer that would only be one more thing
to get wrong.

## Structure

```
pipeline/
├── sources/             connectors: what reads each court API
└── transformations/     SQLMesh project
    ├── config.yaml      connection and defaults
    └── models/          SQL models
```

## What is not committed

Credentials (`.dlt/secrets.toml`, `.env`), the loaded data, and the caches and
logs both tools write while running.
