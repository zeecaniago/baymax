# Baymax API Server

FastAPI service for the Baymax expense-tracking prototype. It parses and stores
expenses, manages category budgets, and calculates reports and goal progress.

## Run locally

From the repository root, install the server dependencies and start Uvicorn:

```bash
python3 -m pip install -r server/requirements.txt
uvicorn server.app:app --reload
```

The API is available at `http://127.0.0.1:8000`. Interactive OpenAPI docs are
available at `http://127.0.0.1:8000/docs`.

## API overview

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Service health response |
| `POST` | `/expenses/parse` | Parse natural-language expense text into a draft |
| `POST` | `/expenses` | Save an expense |
| `PATCH` | `/expenses/{expense_id}` | Correct a saved expense |
| `GET` | `/expenses` | List expenses for a cycle, optionally by category |
| `GET` | `/budgets` | Get category budgets and calculated balances |
| `PUT` | `/budgets/{category_name}` | Create or update a category budget |
| `DELETE` | `/budgets/{category_name}` | Remove a category budget |
| `GET` | `/goals/{goal_id}/summary` | Get calculated goal progress |
| `POST` | `/ask` | Answer supported natural-language spending questions |
| `GET` | `/reports` | Get category, goal, or flag reports |

All read endpoints use the current billing cycle by default: the 26th of one
month through the 25th of the next. Provide an ISO date with `cycle`, such as
`?cycle=2026-07-01`, to query the cycle containing that date.

## Examples

Parse an expense before saving it:

```bash
curl -X POST http://127.0.0.1:8000/expenses/parse \
  -H 'Content-Type: application/json' \
  -d '{"raw_text":"$45 groceries fresh street, one-off"}'
```

Create an expense:

```bash
curl -X POST http://127.0.0.1:8000/expenses \
  -H 'Content-Type: application/json' \
  -d '{"amount":45,"description":"groceries","merchant":"fresh street","category":"groceries","flags":["one-off"]}'
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
- `store.py` owns the prototype's process-local state and reset helper.

## Prototype limitations

Data is stored only in memory. Restarting the server clears all expenses and
restores the default budgets. There is no authentication or persistent database
yet; `household_id` is accepted on parsing requests for API-shape compatibility
but is not currently used.

## Test

Run the repository test suite from the project root:

```bash
python3 -m unittest discover -s tests -v
```
