# Measuring the project with SonarQube

SonarQube reads the source code. It never runs the system, never connects to
PostgreSQL and never needs the published decisions, so a fresh clone on a
machine with no database analyses fine.

The one exception is the coverage figure. It does not come from SonarQube — it
comes from reports the test suites write, and the backend suite needs a
PostgreSQL to produce a full one. That database is **empty**: the fixtures build
the few rows they need. Running the pipeline is not required, and neither are
the 991,163 decisions.

Measured on this project:

| Database | Backend tests | Coverage reported |
|---|---|---|
| none | 302 run, 433 skipped | 74% |
| empty `caselaw_test` | 735 run | 94% |

## What you need

Docker, and nothing else — the scanner runs in a container. For the backend
coverage you also need `uv`, and for the frontend's, Node.

## 1. Start the server

```bash
docker run -d --name sonarqube -p 9000:9000 sonarqube:community
```

It takes about a minute. Wait for `"status":"UP"`:

```bash
curl -s http://localhost:9000/api/system/status
```

## 2. Create a token

Open <http://localhost:9000>, sign in with `admin` / `admin`, and set a new
password — **at least 12 characters**, or the server refuses it without saying
why on the form. Then *My Account → Security → Generate Token*.

The same thing without the browser:

```bash
curl -u admin:admin -X POST http://localhost:9000/api/users/change_password \
  -d 'login=admin&previousPassword=admin&password=YourNewPassword1'

curl -u admin:YourNewPassword1 -X POST \
  http://localhost:9000/api/user_tokens/generate -d 'name=case-law'
```

## 3. Produce the coverage reports

Skip this to analyse the code alone; SonarQube then reports 0% coverage and
everything else normally.

All three commands run from the repository root, which is what makes the paths
inside the reports resolve for a scanner running in a container.

```bash
# Backend — needs an empty database
docker compose up -d
docker compose exec -T postgres psql -U postgres -c 'CREATE DATABASE caselaw_test'

PYTHONPATH=backend \
TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/caselaw_test \
uv --project backend run python -m pytest backend/tests \
  --cov=backend/app --cov-report=xml:backend/coverage.xml

# Pipeline — no database
PYTHONPATH=pipeline uv --project pipeline run python -m pytest pipeline/tests \
  --cov=pipeline --cov-report=xml:pipeline/coverage.xml

# Frontend — no database
cd frontend && npm ci && npm run test:coverage && cd ..
```

Use the credentials from your `.env` if you changed them from the defaults.

## 4. Analyse

```bash
docker run --rm --network host -v "$(pwd):/usr/src" \
  -e SONAR_HOST_URL=http://localhost:9000 \
  -e SONAR_TOKEN=<the token from step 2> \
  sonarsource/sonar-scanner-cli
```

The result is at <http://localhost:9000/dashboard?id=case-law>.

## What is configured

`sonar-project.properties` at the root declares the three source trees
(`backend/app`, `frontend/src`, `pipeline`), the three test trees, and where the
coverage reports are. Test fixtures are excluded from both: the saved BDJur
pages are captured evidence, not markup anyone wrote, and SonarQube otherwise
reports their missing `lang` attribute as a bug in our code.

`.coveragerc` sets `relative_files`, which is what makes the Python reports
usable. Without it coverage.py writes this machine's absolute paths, the scanner
container cannot find them, and the coverage is dropped — with one line in the
log and no failure.
