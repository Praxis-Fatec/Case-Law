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
uv run python -m sources.tjdft
```

Loads acordaos from the TJDFT JurisDF API into `raw.acordao_tjdft`. With no date
window it walks the whole collection: 1,749,377 documents, 40 per request.

```bash
TJDFT_START_DATE=2026-01-01 TJDFT_END_DATE=2026-01-31 uv run python -m sources.tjdft
```

Restricting the window is the normal way to work. January 2026 alone is 5,417
documents, which is enough to develop against and takes about a minute.

`TJDFT_SUBJECT` narrows further by free text: the same month restricted to
`dano moral` is 533 documents.

### Not hammering the source

One request every half second, measured from the end of the previous one. The
whole collection is 43,734 requests, so the pace decides whether the run takes
six hours or gets the address blocked. `TJDFT_REQUEST_INTERVAL` changes it.

Network failures are retried five times with growing delay, and a `Retry-After`
header is obeyed when the portal sends one. A page that fails every attempt
stops the run rather than leaving a silent hole in the collection.

dlt also creates `raw._dlt_loads` on its own, recording every run with its id,
status and timestamp. That is what `core.carga` reads.

### What the connector does

The API serves five collections from one endpoint, and the default response
mixes acordaos with monocratic decisions, sumulas and newsletters. The connector
asks for `base: acordaos` only, which is the 1,749,377 figure above.

Records are written with `merge` on `identificador`, so running the same window
twice updates rather than duplicates. This matters because `core.decisao`
audits that the pair source plus identifier is unique.

Documents under seal arrive with their full text — the API reports the flag but
does not redact the content. They are kept in the raw layer, because `core.carga`
counts them to report how many were discarded, and dropped on the way into
`core.decisao`.

Two pieces of the response are left out. `marcadores` holds the highlight
positions for the search screen, not anything about the decision. And inside
`jurisprudenciaEmFoco`, the `conteudo` buffer is dropped while its description
and link are kept: dlt writes a buffer as one row per byte, which turned 120
decisions into 1.9 million rows and 328 MB. The whole collection would be
measured in terabytes.

Field names are preserved exactly as the API returns them, camel case included,
which is why the SQL models quote `"dataJulgamento"`. The raw layer mirrors the
source; renaming belongs to the transformation.

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
| `TJDFT_START_DATE` `TJDFT_END_DATE` | TJDFT connector | none — the whole collection |
| `TJDFT_SUBJECT` | TJDFT connector | none — every subject |
| `TJDFT_MAX_PAGES` | TJDFT connector | none — until the source runs out |
| `TJDFT_REQUEST_INTERVAL` | TJDFT connector | `0.5` seconds between requests |

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
