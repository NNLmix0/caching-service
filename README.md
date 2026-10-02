# Caching Service

A FastAPI service that builds payloads from two lists of strings. Every string
goes through a "transformer" (a stand-in for a slow external service), the
results are interleaved, and both the transformer results and the finished
payloads are cached in a database. A `cache-cli` tool exercises the service
from the command line.

## Quick start

```bash
docker compose up --build
```

The API listens on http://localhost:8000 (interactive docs at `/docs`). The
SQLite file lives in the `cache-data` volume, so the cache survives restarts.

```bash
curl -X POST http://localhost:8000/payload \
  -H 'Content-Type: application/json' \
  -d '{"list_1": ["first string", "second string", "third string"],
       "list_2": ["other string", "another string", "last string"]}'
# {"id":"f6ef025e-ce8a-4eba-8b14-e963d62d71bb"}

curl http://localhost:8000/payload/f6ef025e-ce8a-4eba-8b14-e963d62d71bb
# {"output":"FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"}
```

## API

| Request | Response |
| --- | --- |
| `POST /payload` with `{"list_1": [...], "list_2": [...]}` | `201` and `{"id": "<uuid>"}` for a new payload, `200` with the same id if this input was seen before |
| `GET /payload/{id}` | `200` and `{"output": "..."}`, `404` for an unknown id |

Invalid requests get `422`: lists of different length, empty lists, non-string
items, or an id that is not a UUID.

## CLI

```
cache-cli [-H|--host URL] [-r|--repeat N] [-i|--input FILE|-] [-j|--json JSON] [-o|--output FILE|-] [-h|--help]
```

| Option | Meaning | Default |
| --- | --- | --- |
| `-H`, `--host` | server URL | `http://localhost:8000` |
| `-r`, `--repeat` | number of iterations | `1` |
| `-i`, `--input` | file with the request body, `-` for stdin | |
| `-j`, `--json` | request body as a JSON string | |
| `-o`, `--output` | file for the results, `-` for stdout | `-` |

Exactly one of `--input` and `--json` is required. Each iteration posts the
body, fetches the payload, and prints one JSON line. `status` shows the cache at
work: `201` when the payload was created, `200` when it was reused.

```bash
cache-cli --repeat 2 --json '{"list_1": ["a", "b"], "list_2": ["c", "d"]}'
# {"status": 201, "id": "874f2c7a-7cf8-4c05-9f9b-ea451d102cd1", "output": "A, C, B, D"}
# {"status": 200, "id": "874f2c7a-7cf8-4c05-9f9b-ea451d102cd1", "output": "A, C, B, D"}

cache-cli --input body.json --output results.jsonl
cat body.json | cache-cli --input -
```

The CLI is installed with the package (see below) and is also available inside
the container:

```bash
docker compose exec api cache-cli --json '{"list_1": ["a"], "list_2": ["b"]}'
```

## Local development

Requires Python 3.12+.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

uvicorn caching_service.api:app  # run the service
pytest                           # unit and integration tests
ruff check . && ruff format --check .
```

The database is configured with `DATABASE_URL` (environment variable or `.env`,
see `.env.example`). It defaults to `sqlite:///./cache.db`.

### Layout

| Path | Contents |
| --- | --- |
| `src/caching_service/transformer.py` | the simulated external service |
| `src/caching_service/service.py` | caching and payload generation |
| `src/caching_service/api.py` | FastAPI endpoints and request validation |
| `src/caching_service/cli.py` | `cache-cli` |
| `src/caching_service/models.py`, `db.py`, `config.py` | tables, session, settings |
| `tests/test_service.py` | unit tests of the caching logic |
| `tests/test_api.py`, `tests/test_cli.py` | integration tests through HTTP and the CLI |

## Decisions and shortcuts

**`-H` for `--host`.** The task assigns `-h` to both `--host` and `--help`.
`-h` stays with help, as users of any command-line tool expect, and the host
gets `-H`.

**Payloads live in the database, not in files.** The task mentions "generated
payloads files". A payload here is a short string that is only ever read back
by id, so it is stored as a row next to the cache; writing it to a file as well
would add a second storage to keep consistent without changing the API.

**A payload is identified by its input.** The payload table stores a SHA-256
hash of the two input lists under a unique constraint. A repeated request is
recognised from the hash alone, without calling the transformer. The trade-off:
inputs that differ but produce the same output (`"a"` and `"A"`) get different
ids.

**Minimising transformer calls.** Strings are de-duplicated within a request,
the cache is read with a single `SELECT ... IN`, and the transformer runs only
for strings that are not cached yet. Strings are cached exactly as received,
with no trimming or case folding, so `"a"` and `"a "` are separate entries.
Cached entries never expire.

**Concurrency.** Unique constraints keep the data correct when two requests
race: the loser's commit fails, and it retries once, now finding the winner's
rows. The cost is that both requests may call the transformer for the same
string; preventing that would need a lock around the transformer call. A second
conflict in a row is treated as an error rather than retried indefinitely.

**Synchronous code.** Endpoints and database access are synchronous and run in
FastAPI's thread pool. A real external transformer would be a reason to go
async; for a local function it would only add complexity.

**SQLite.** It needs no setup and the tests run on the same engine as the
service. The code avoids SQLite-specific SQL, so PostgreSQL should need only a
driver and a different `DATABASE_URL`, but this has not been tested. One thing
would need attention there: the cache uses the raw string as its primary key,
which PostgreSQL limits to about 2.7 kB. On either database, a request with
tens of thousands of distinct strings would exceed the limit on query
parameters; the lookup would then have to be split into batches.

**No migrations.** The two tables are created on startup with `create_all`.
A schema that evolves would call for Alembic.

**The `POST` response.** The task asks for a confirmation message with the
identifier. The body is just `{"id": ...}` and the status code is the
confirmation: `201` when the payload was created, `200` when an existing one
was reused. This also lets the CLI show cache hits.

**Empty lists are rejected.** A payload built from nothing has no meaning, so
it is a validation error instead of an empty output.

**The CLI does not validate the request body.** It checks its own arguments
(URL, repeat count, well-formed JSON) and leaves the body to the server, so it
can also be used to see how the server responds to bad input.

**Unpinned dependencies, no CI.** `pyproject.toml` sets lower bounds only, and
the checks are run locally (verified on Python 3.12 and 3.14). A production
service would have a lock file and a CI workflow running `ruff` and `pytest`.
