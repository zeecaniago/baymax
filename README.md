# Baymax

Baymax is a conversational household budget tracker. You log purchases in plain language, optionally attach merchants, categories, goals, and flags, then ask about spending and budgets for the current billing cycle (26th of one month through the 25th of the next).

This repository is a **Python prototype**: a SQLite-backed FastAPI server plus a REPL-style CLI. There is no mobile app, web app, Postgres database, or LLM integration in the tree today.

## What is implemented

| Piece | Role |
| --- | --- |
| `server/` | FastAPI API: rule-based parsing, expense CRUD, budgets, goals, reports, and a small `/ask` surface |
| `cli/` | Interactive Python REPL that calls the API (stdlib HTTP client; no third-party CLI deps) |
| `data/` | Default SQLite location (`data/baymax.db`; gitignored `*.db` files) |
| `tests/` | Unit and FastAPI integration tests |

On first start the server creates the schema and seeds default categories (`groceries` $400, `transport` $150, `eating out` with no budget) and several goals (for example “Raise a strong, resilient kid”, “Emergency Fund”). There is no authentication yet; rows use default household/user ids.

Parsing and Q&A are **rule-based** (`server/rule_interpreter.py` and related modules), not Claude or another LLM. An intent contract in `server/intents.py` is shared so a future LLM interpreter could plug in later without changing execution.

## Quickstart

### 1. Install server dependencies

From the repository root:

```bash
python3 -m pip install -r server/requirements.txt
```

The CLI uses only the Python standard library, so it does not need a separate install. Run commands from the repo root so `python3 -m cli` can import `server` helpers.

### 2. Start the server

```bash
uvicorn server.app:app --reload
```

API: `http://127.0.0.1:8000`  
OpenAPI docs: `http://127.0.0.1:8000/docs`

By default the database is `data/baymax.db`. Override with `BAYMAX_DB_PATH` (useful for isolated runs and tests):

```bash
BAYMAX_DB_PATH=/tmp/baymax-dev.db uvicorn server.app:app --reload
```

To reset local data, stop the server and delete the database file; schema and seed data are recreated on the next start.

### 3. Start the CLI

In a second terminal, from the repo root:

```bash
python3 -m cli
```

Default API URL is `http://127.0.0.1:8000`. Override with:

```bash
BAYMAX_API_URL=http://127.0.0.1:9000 python3 -m cli
```

Type `exit` or `quit` (or Ctrl-C / Ctrl-D) to leave the REPL.

### 4. Example session

Amounts and report totals depend on what you have logged in the running database. Formatting should look like this:

```text
> $45 groceries
✓ $45.00 — groceries  #Groceries

> $45 coffee, m: Fresh Street, c: Groceries
✓ $45.00 — coffee  @Fresh Street  #Groceries

> $12 coffee, one-off
✓ $12.00 — coffee  !one-off · excluded from budget

> $50 karate class, kid goal
✓ $50.00 — karate class  → Raise a strong, resilient kid
```

Ambiguous goals prompt for a choice:

```text
> $40 books, learning goal
Which goal?
  1. Raise a strong, resilient kid
  2. Get promoted this year
  0. Don't link to a goal
> 1
✓ $40.00 — books  → Raise a strong, resilient kid
```

Named fields (`m:`/`merchant:`, `c:`/`category:`, `g:`/`goal:`) are case-insensitive, may appear in any order, and override inference. A purchase needs only an amount and description; category and merchant are optional. The `one-off` flag keeps the expense in history but excludes it from category budget spend.

Corrections and budgets go through the server:

```text
> $18 target
✓ $18.00 — target

> no, that one's for the emergency fund goal
✓ updated — $18.00 — target  → Emergency Fund

> $45 groceries
✓ $45.00 — groceries  #Groceries

> oops, 54 not 45
✓ updated — $54.00 — groceries  #Groceries

> set groceries budget to $600
✓ [Groceries] budget updated: $600/cycle (was $400/cycle)

> remove groceries budget
✓ [Groceries] — budget removed (was $600/cycle)
```

Reads recompute from SQLite (figures change as you log and correct expenses, and survive server restarts):

```text
> report groceries
> report goal resilient kid
> how much on groceries this cycle?
> what's left in eating out?
> what did we spend supporting the resilient kid goal this cycle?
```

Session-only CLI state (not persisted on the server):

```text
> suggest a groceries budget
> no

> history
```

### Behavior split

- **Server:** expense parse/create/correct, reports, goal summaries, budget reads/writes, `/ask` answers, intent interpret/execute.
- **CLI:** REPL UX, goal chooser prompts, budget “suggest … / yes|no” confirmation flow, and in-session `history`.

## Environment variables

| Name | Used by | Purpose |
| --- | --- | --- |
| `BAYMAX_DB_PATH` | server | SQLite file path (default `data/baymax.db`) |
| `BAYMAX_API_URL` | CLI | API base URL (default `http://127.0.0.1:8000`) |

## API surface

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Health |
| `POST` | `/expenses/parse` | Parse expense text into a draft |
| `POST` | `/intents/interpret` | Map supported language to a typed intent |
| `POST` | `/intents/execute` | Execute a validated intent (budget writes need `confirmed: true`) |
| `GET` | `/expenses/suggestions` | Suggest merchants, categories, or goals |
| `POST` | `/expenses` | Save an expense |
| `PATCH` | `/expenses/{expense_id}` | Correct a saved expense |
| `GET` | `/expenses` | List expenses for a cycle (optional `category`) |
| `GET` | `/budgets` | Category budgets and balances |
| `PUT` | `/budgets/{category_name}` | Create or update a category budget |
| `DELETE` | `/budgets/{category_name}` | Remove a category budget |
| `GET` | `/goals/{goal_id}/summary` | Goal-related spending for a cycle |
| `POST` | `/ask` | Answer supported spending questions |
| `GET` | `/reports` | Category, goal, or flag reports (`type=category\|goal\|flag`) |

Cycle query parameter defaults to `current`. Pass an ISO date (for example `?cycle=2026-07-01`) to select the cycle containing that date.

More detail and curl examples: [`server/README.md`](server/README.md). CLI interaction notes: [`cli/README.md`](cli/README.md).

## Project layout

```text
cli/                 REPL client (app facade, command modules, HTTP client)
server/              FastAPI app, routes, parsing, calculations, SQLite + repositories
data/                Default DB directory (`.gitkeep`; `*.db` ignored)
tests/               Unit tests and `tests/integration/` FastAPI tests
.github/workflows/   CI: ruff + pytest (+ coverage artifacts); release tags on merge
pyproject.toml       Ruff / pytest config
requirements-dev.txt pytest, httpx, pre-commit, ruff, …
```

## Development checks

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pip install -r server/requirements.txt
pre-commit install
```

Pre-commit runs `python3 -m ruff check` on staged Python files. Manually:

```bash
python3 -m ruff check cli server tests
python3 -m pytest
```

CI (Python 3.12) installs `requirements-dev.txt`, `cli/requirements.txt`, and `server/requirements.txt`, then runs the same lint and a coverage-enabled pytest pass.

## Not yet / roadmap

The lower half of older README drafts described a multi-client product (React Native, React web, shared TypeScript `core/`, Node CLI, Postgres, Claude for NL, household auth). **None of that is in this repository today.** Plausible next steps implied by the current code and docs:

- Additional clients against the same HTTP API
- Stronger auth / real multi-user households
- Optional LLM interpreter behind the existing intent contract
- Richer persistence (for example Postgres) if SQLite stops being enough

## License

MIT — see [`LICENSE`](LICENSE).
