# Case Law — Backend

FastAPI application that serves the search, detail and indicator endpoints.

## Requirements

- [uv](https://docs.astral.sh/uv/) — manages Python and the dependencies
- Docker — only for the PostgreSQL container

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

You do **not** need to install Python by hand. `uv` reads `.python-version`
and downloads the right version on its own.

## Setup

```bash
cd backend
uv sync
cp .env.example .env
```

## Running

```bash
uv run uvicorn app.main:app --reload
```

| Address | What it is |
|---|---|
| http://localhost:8000/health | health check |
| http://localhost:8000/docs | Swagger UI |
| http://localhost:8000/redoc | ReDoc |
| http://localhost:8000/openapi.json | the OpenAPI spec |

The port is **not** set in the code — `uvicorn` defaults to 8000. Pass
`--port 8001` to change it.

## Quality checks

The same four commands the CI runs. Run them before opening a pull request:

```bash
uv run ruff check .          # lint
uv run ruff format --check . # formatting
uv run mypy app tests        # type checking
uv run pytest                # tests
```

To fix formatting instead of only reporting it:

```bash
uv run ruff format .
```

## Adding a dependency

```bash
uv add <package>             # runtime
uv add --dev <package>       # development only
```

Both update `pyproject.toml` and `uv.lock`. **Commit the lock file** — it is
what keeps every machine on the same versions.

## Structure

```
backend/
├── app/
│   ├── config.py        settings read from environment variables
│   ├── main.py          creates the app and registers the routers
│   └── api/             one module per group of endpoints
├── tests/
└── pyproject.toml       dependencies and tool configuration
```

## Configuration

Every value that differs between a laptop and a server lives in `app/config.py`
and is read from the environment. Never hardcode a URL, port or password.

| Variable | Default |
|---|---|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/caselaw` |
| `ENVIRONMENT` | `development` |

`.env.example` is versioned as a template. The real `.env` is ignored by git.
