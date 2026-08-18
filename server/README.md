# Baymax API Server

FastAPI service for the Baymax expense-tracking prototype. It parses and stores
expenses, manages category budgets, and calculates category and goal-related spending reports.

## Run locally

From the repository root, install the server dependencies and start Uvicorn:

```bash
python3 -m pip install -r server/requirements.txt
uvicorn server.app:app --reload
```

The API is available at `http://127.0.0.1:8000`. Interactive OpenAPI docs are
available at `http://127.0.0.1:8000/docs`.

Data is stored in `data/baymax.db` by default. Override the location with
`BAYMAX_DB_PATH`, for example `BAYMAX_DB_PATH=/tmp/baymax.db uvicorn
server.app:app --reload`. Stop the server and delete the database file to reset
local development data; Baymax recreates its schema and seed data on startup.

## API overview

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Service health response |
| `POST` | `/expenses/parse` | Parse natural-language expense text into a draft |
| `POST` | `/intents/interpret` | Convert supported language into a validated semantic intent |
| `POST` | `/intents/execute` | Resolve and deterministically execute a validated intent |
| `GET` | `/expenses/suggestions` | Suggest known merchants, categories, or goals for a named field |
| `POST` | `/expenses` | Save an expense |
| `PATCH` | `/expenses/{expense_id}` | Correct a saved expense |
| `GET` | `/expenses` | List expenses for a cycle, optionally by category |
| `GET` | `/budgets` | Get category budgets and calculated balances |
| `PUT` | `/budgets/{category_name}` | Create or update a category budget |
| `DELETE` | `/budgets/{category_name}` | Remove a category budget |
| `GET` | `/goals/{goal_id}/summary` | Get goal-related spending for a cycle |
| `POST` | `/ask` | Answer supported natural-language spending questions |
| `GET` | `/reports` | Get category, goal, or flag reports |

## Language intent boundary

The rule-based interpreter and any future LLM interpreter share the Pydantic
contract in `server/intents.py`. Intent payloads contain user-facing references
such as `"groceries"` or `"the kid goal"`; `server/entity_resolution.py`
resolves those references against household data before
`server/intent_executor.py` may read or change application state. Financial
calculations and database identifiers are never delegated to the interpreter.

Budget-changing intents require confirmation. Call `/intents/execute` with
`confirmed: true` only after the client has obtained that confirmation;
rapid expense logging and correction retain their existing immediate-write
behavior. Ambiguous and missing references return a clarification result
rather than being guessed.

All read endpoints use the current billing cycle by default: the 26th of one
month through the 25th of the next. Provide an ISO date with `cycle`, such as
`?cycle=2026-07-01`, to query the cycle containing that date.

## Examples

Parse an expense before saving it:

```bash
curl -X POST http://127.0.0.1:8000/expenses/parse \
  -H 'Content-Type: application/json' \
  -d '{"raw_text":"$45 coffee, m: Fresh Street, c: Groceries, g: Healthy Lifestyle"}'
```

Create an expense:

```bash
curl -X POST http://127.0.0.1:8000/expenses \
  -H 'Content-Type: application/json' \
  -d '{"amount":45,"description":"coffee","merchant":"Fresh Street","category":"Groceries","goals":["Healthy Lifestyle"]}'
```

Set a budget and read its remaining balance:

```bash
curl -X PUT http://127.0.0.1:8000/budgets/groceries \
  -H 'Content-Type: application/json' \
  -d '{"amount":400}'

curl http://127.0.0.1:8000/budgets
```

Request a category report:

```bash
curl 'http://127.0.0.1:8000/reports?type=category'
```

## Project layout

- `app.py` creates the FastAPI application and exposes the existing public API.
- `routes.py` contains HTTP endpoint handlers.
- `models.py` defines Pydantic request and response models.
- `parsing.py` contains natural-language parsing and normalization helpers.
- `calculations.py` derives cycle, budget, goal, and report data.
- `db.py` owns SQLite connection, schema initialization, and seed data.
- `repositories/` isolates persistence queries from routes and business logic.
- `store.py` retains the database reset helper used by compatibility tests.

## Progressive purchase capture

Purchases require only an amount and description. Merchant, category, goal,
and budget treatment are optional details that can be added as the user builds
the habit:

- `$45 groceries` infers the familiar Groceries category.
- `$45 coffee fresh street` stores coffee with the Fresh Street merchant but no category.
- `$45 coffee fresh street groceries` adds the trailing category.
- `$45 coffee, m: Fresh Street, c: Groceries, g: Healthy Lifestyle` is the
  unambiguous named-field form. The long forms `merchant:`, `category:`, and
  `goal:` are also accepted, in any order and without case sensitivity.
- Adding `, one-off` sets `budget_treatment` to `excluded`: the purchase stays
  in history but does not reduce that category's budget balance.

`GET /expenses/suggestions?field=g&q=heal` returns `Healthy Lifestyle`; pass a
description as well to rank matches using prior household usage. This endpoint
keeps client autocomplete separate from the expense syntax.

## Prototype limitations

There is no authentication or multi-user behavior yet. Persisted rows retain
default household and user identifiers so those concepts can be introduced
later without changing the expense schema.

## Test

Run the repository test suite from the project root:

```bash
python3 -m pytest
```
