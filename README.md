## Current Prototype Quickstart

The repo currently contains:

- a dummy FastAPI server in `server/`
- a Python REPL-style CLI in `cli/`

The server is still in-memory only. It returns dummy data and stores created expenses in process memory only. There is no Postgres/MySQL setup yet.

### 1. Install server dependencies

```bash
python3 -m pip install -r server/requirements.txt
```

The CLI currently uses only the Python standard library, so it does not need a separate install step.

### 2. Start the server

In one terminal:

```bash
uvicorn server.app:app --reload
```

That starts the dummy API on `http://127.0.0.1:8000`.

### 3. Start the CLI

In a second terminal, from the repo root:

```bash
python3 -m cli
```

The CLI talks to `http://127.0.0.1:8000` by default. To point it somewhere else:

```bash
BAYMAX_API_URL=http://127.0.0.1:9000 python3 -m cli
```

### 4. Try a few commands

Expense logging now goes through the server:

```text
> $45 groceries
✓ $45.00 — groceries  [Groceries]

> $12 coffee, one-off
✓ $12.00 — coffee  #one-off

> $50 karate class, kid goal
✓ $50.00 — karate class  [Kids]  → Raise a strong, resilient kid
```

Ambiguous goal example:

```text
> $40 books, learning goal
Which goal?
  1. Raise a strong, resilient kid
  2. Get promoted this year
  3. Don't link to a goal
> 1
✓ $40.00 — books  [Kids]  → Raise a strong, resilient kid
```

Other CLI commands still work locally inside the REPL:

```text
> report groceries
Groceries — Jun 26–Jul 25
  $403 of $400 (101%) · 15 expenses · avg $26.87
  Largest: Costco $91, Whole Foods $64, Trader Joe's $58

> set groceries budget to $600
✓ Created [Groceries] — budget $600/cycle

> history
1  report groceries
2  set groceries budget to $600
3  history
```

### Current behavior split

- Expense parsing and creation go through the server.
- Reports, budget commands, and most multi-step REPL state still live in the CLI for now.
- Server data is reset when the server process restarts.

## 1. System Overview

```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│ React Native │   │  React Web  │   │     CLI      │
│ (iOS/Android)│   │  (browser)  │   │ (Node, TTY)  │
└──────┬───────┘   └──────┬──────┘   └──────┬───────┘
       │                  │                  │
       └──────────┬───────┴──────────┬───────┘
                   │      imports     │
                   ▼                  ▼
         ┌─────────────────────────────────┐
         │        Shared Core Package        │
         │  (TS: types, API client,          │
         │   formatting, input-grammar       │
         │   helpers)                        │
         └───────────────┬───────────────────┘
                         │  HTTPS
                         ▼
         ┌───────────────────────┐
         │      API Server         │
         │  (Node/Express or       │
         │   FastAPI)               │
         │                          │
         │  - Auth (household)      │
         │  - Expense CRUD          │
         │  - Budget/Goal logic      │
         │    (cycle & budget math   │
         │     live server-side)     │
         │  - Report queries         │
         └──────┬─────────┬─────────┘
                │         │
                ▼         ▼
       ┌────────────┐  ┌──────────────┐
       │  Postgres   │  │  Claude API   │
       │  (data)     │  │  (NL parsing, │
       │             │  │   Q&A)        │
       └────────────┘  └──────────────┘
```

One backend serves all three clients. Cycle/budget math lives **only** on the server now — with three clients, letting each one compute it locally would risk drift (e.g. CLI and mobile disagreeing on remaining balance). The core package now carries just types, the API client, and formatting — not business logic.

---

## 2. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Mobile | React Native (Expo) | One codebase → both app stores; Expo simplifies build/deploy for a solo dev |
| Web | React (Vite) | Shares types/logic with mobile via the core package |
| CLI | Node + commander (or oclif) | Same language as core package/backend — no third language to maintain; a REPL mode can mirror the chat-thread paradigm in text |
| Shared logic | TypeScript package (`core/`) | Cycle math, budget math, API client, types — written once |
| Backend | Node/Express + TypeScript (recommended) | Same language as frontend/core — one language across the whole stack, less context-switching for a solo build |
| Database | Postgres (via Supabase or Railway) | Relational model fits the domain (expenses ↔ goals ↔ flags are all many-to-many) |
| Auth | Supabase Auth (or simple JWT) | Two-user household; no need to build auth from scratch |
| NLP parsing & Q&A | Claude API | Parses free-text input into structured JSON; answers natural-language questions against report data |
| Push/notifications (later) | Expo push | For budget-overrun alerts, if you want them outside the app |

If you'd rather avoid Node on the backend, FastAPI (Python) is a fine substitute — you already have Python fluency from the prototype. The tradeoff is just losing type-sharing between backend and core package.

---

## 3. Data Model (Postgres)

```sql
households
  id, created_at

users
  id, household_id (FK), name, email, created_at

-- Free-form, app learns the recurring set. Budget is optional per row.
categories
  id, household_id (FK), name, budget_amount (nullable), created_at

-- Extensible tag system — one row per flag *type*, not hardcoded enum
flags
  id, household_id (FK), name (e.g. "one-off"), created_at

-- Open-ended by default; target is optional
goals
  id, household_id (FK), name, target_amount (nullable), target_date (nullable),
  is_open_ended (bool), created_at

billing_cycles
  id, household_id (FK), start_date, end_date
  -- generated/derived, not user-created; 26th–25th, always recurring

expenses
  id, household_id (FK), user_id (FK), cycle_id (FK),
  amount, description, category_id (nullable FK),
  notes (nullable), date, created_at

-- many-to-many junctions
expense_flags
  expense_id (FK), flag_id (FK)

expense_goals
  expense_id (FK), goal_id (FK)
```

**Design notes:**
- `category_id`, `budget_amount`, goal links, flags are all nullable/optional — "no category" and "no budget" are real states, not migrations-in-waiting.
- `billing_cycles` can be computed on the fly (26th–25th) rather than stored, but storing them makes reporting queries and remaining-balance math simpler — recommend storing, generated lazily when first referenced.
- New flags = new row in `flags`, no schema change. Same for goals and categories.

---

## 4. API Surface (sketch)

```
POST   /expenses/parse        → Claude parses raw text → structured draft (not yet saved)
POST   /expenses               → save a parsed/confirmed expense
PATCH  /expenses/:id           → correction (rollback-and-redo)
GET    /expenses?cycle=current&category=groceries

GET    /budgets                → all categories with budgets + live remaining balance
GET    /goals/:id/summary?cycle=current

POST   /ask                    → natural-language question → Claude reads relevant
                                  data (via tool-call-style queries) → plain-language answer

GET    /reports?type=category|goal|flag&cycle=current
```

`/expenses/parse` and `/ask` are the two endpoints that call out to Claude. Everything else is standard CRUD/query.

---

## 5. NLP Parsing Flow

1. User types: `"$45 groceries, one-off"`
2. App sends raw text + household's known categories/flags/goals (as context) to `/expenses/parse`
3. Server calls Claude with a system prompt describing your input grammar, returns strict JSON:
   ```json
   { "amount": 45, "description": "groceries", "category": "groceries",
     "flags": ["one-off"], "goal_candidates": [] }
   ```
4. Server returns this draft to the client
5. Client shows the confirmation (per your "optimistic execute" model) and calls `POST /expenses` to persist

Corrections follow the same path: re-parse, rollback-and-redo, no confirmation prompt.

---

## 6. Build Sequencing (solo dev)

1. **Data model + core package** — Postgres schema, types, API client as pure TS with tests. No UI yet.
2. **Parsing service** — Claude integration for `/expenses/parse`, validated against real example inputs (including messy/ambiguous ones).
3. **API server** — CRUD endpoints, wired to the schema above.
4. **CLI first** — build the CLI against the real API before either GUI. It's the cheapest surface (no app-store friction, no layout work), it mirrors your existing Python REPL prototype's interaction model, and it's the fastest way to validate parsing reliability and the "optimistic execute" correction flow with real day-to-day use.
5. **Web, then mobile** — reuse core package; should be materially faster since parsing/math/types/API client are already proven by the CLI.
6. **Reports + goals view + Q&A endpoint** — layer on last, since they depend on real logged data to be meaningful to test against.

This order front-loads the riskiest, most novel part (parsing reliability + server-side cycle/budget math) and validates it in the lowest-friction interface before investing in any GUI work.

---

## 7. Open Questions

- Node/Express vs. FastAPI for backend — leaning Node for type-sharing, but Python fluency from the prototype is a real factor.
- Supabase (bundled auth + Postgres) vs. separate Postgres host + custom auth — Supabase saves setup time but adds a vendor dependency.
- Whether `billing_cycles` should be a stored table (recommended above) or computed on demand.
- CLI interaction mode: a persistent REPL (matching your Python prototype and the chat-thread paradigm) vs. one-shot commands (`app log "$45 groceries"`, `app budgets`). A REPL fits the product philosophy better; one-shot commands are more scriptable/composable. Worth deciding once you're building the CLI, since it doesn't block earlier steps.
