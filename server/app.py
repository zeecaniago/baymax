from __future__ import annotations

import re
from copy import deepcopy
from datetime import date as DateType
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

app = FastAPI(
    title="Baymax API",
    version="0.1.0",
    description="Minimal dummy API surface based on README.md.",
)


class ParseExpenseRequest(BaseModel):
    raw_text: str = Field(..., min_length=1)
    household_id: str | None = None


class ExpenseDraft(BaseModel):
    amount: float
    description: str
    category: str | None = None
    flags: list[str] = Field(default_factory=list)
    goal_candidates: list[str] = Field(default_factory=list)
    notes: str | None = None


class CreateExpenseRequest(BaseModel):
    amount: float
    description: str
    category: str | None = None
    flags: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    notes: str | None = None
    date: DateType | None = None
    user_id: str | None = None


class UpdateExpenseRequest(BaseModel):
    amount: float | None = None
    description: str | None = None
    category: str | None = None
    flags: list[str] | None = None
    goals: list[str] | None = None
    notes: str | None = None
    date: DateType | None = None


class SetBudgetRequest(BaseModel):
    amount: float = Field(..., ge=0)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    cycle: str = "current"


class AskResponse(BaseModel):
    answer: str
    cycle: str
    supporting_data: dict


_DUMMY_BUDGETS = {
    "cycle": "current",
    "cycle_label": "Jun 26–Jul 25",
    "currency": "USD",
    "categories": [
        {
            "name": "groceries",
            "budget_amount": 400.0,
            "spent": 403.0,
            "remaining": -3.0,
            "expense_count": 15,
            "average_amount": 26.87,
            "largest_expenses": [
                {"description": "Costco", "amount": 91.0},
                {"description": "Whole Foods", "amount": 64.0},
                {"description": "Trader Joe's", "amount": 58.0},
            ],
        },
        {
            "name": "transport",
            "budget_amount": 150.0,
            "spent": 48.75,
            "remaining": 101.25,
            "expense_count": 3,
            "average_amount": 16.25,
            "largest_expenses": [
                {"description": "Train reload", "amount": 18.5},
                {"description": "Bus pass top-up", "amount": 16.25},
                {"description": "Parking meter", "amount": 14.0},
            ],
        },
        {
            "name": "eating out",
            "budget_amount": None,
            "spent": 105.0,
            "remaining": None,
            "expense_count": 6,
            "average_amount": 17.5,
            "largest_expenses": [
                {"description": "Sushi lunch", "amount": 28.0},
                {"description": "Pizza night", "amount": 24.0},
                {"description": "Coffee run", "amount": 19.0},
            ],
        },
    ],
    "totals": {"budgeted": 550.0, "spent": 451.75, "remaining": 98.25},
}

_DUMMY_GOALS = {
    "goal-resilient-kid": {
        "id": "goal-resilient-kid",
        "name": "Raise a strong, resilient kid",
        "target_amount": None,
        "target_date": None,
        "is_open_ended": True,
        "cycle_contributions": 90.0,
        "total_contributions": 890.0,
        "remaining_to_target": None,
        "cycle_expense_count": 2,
        "total_expense_count": 14,
        "since": "Mar 2026",
        "cycle_entries": [
            {"description": "karate class", "amount": 50.0},
            {"description": "books", "amount": 40.0},
        ],
    },
    "goal-emergency-fund": {
        "id": "goal-emergency-fund",
        "name": "Emergency Fund",
        "target_amount": 10000,
        "target_date": None,
        "is_open_ended": True,
        "cycle_contributions": 125.0,
        "total_contributions": 2750.0,
        "remaining_to_target": 7250.0,
        "cycle_expense_count": 3,
        "total_expense_count": 17,
        "since": "Jan 2026",
        "cycle_entries": [
            {"description": "paycheck transfer", "amount": 75.0},
            {"description": "bonus sweep", "amount": 50.0},
        ],
    },
    "goal-japan-trip": {
        "id": "goal-japan-trip",
        "name": "Japan Trip",
        "target_amount": 4000,
        "target_date": "2027-05-01",
        "is_open_ended": False,
        "cycle_contributions": 220.0,
        "total_contributions": 980.0,
        "remaining_to_target": 3020.0,
        "cycle_expense_count": 2,
        "total_expense_count": 6,
        "since": "Apr 2026",
        "cycle_entries": [
            {"description": "flight deposit", "amount": 200.0},
            {"description": "passport renewal", "amount": 20.0},
        ],
    },
}

_DUMMY_EXPENSES = [
    {
        "id": "exp-1",
        "household_id": "household-1",
        "user_id": "user-1",
        "cycle": "current",
        "amount": 45.00,
        "description": "Groceries at corner market",
        "category": "groceries",
        "flags": ["one-off"],
        "goals": [],
        "notes": None,
        "date": "2026-07-03",
    },
    {
        "id": "exp-2",
        "household_id": "household-1",
        "user_id": "user-2",
        "cycle": "current",
        "amount": 18.50,
        "description": "Train reload",
        "category": "transport",
        "flags": [],
        "goals": [],
        "notes": "Monthly commute top-up",
        "date": "2026-07-02",
    },
]


def _extract_amount(raw_text: str) -> float:
    match = re.search(r"\$(\d+(?:\.\d{1,2})?)", raw_text.replace(",", ""))
    if match:
        return float(match.group(1))

    fallback = re.search(r"(\d+(?:\.\d{1,2})?)", raw_text.replace(",", ""))
    return float(fallback.group(1)) if fallback else 45.0


def _extract_description(raw_text: str) -> str:
    body = re.sub(r"^\d{1,2}/\d{1,2}\s+", "", raw_text).strip()
    body = re.sub(r"^\$\d+(?:\.\d{1,2})?\s*", "", body).strip()
    return body.split(",")[0].strip() or raw_text.strip()


def _extract_flags(raw_text: str) -> list[str]:
    known_flags = {"one-off", "reimbursable", "shared"}
    lowered = raw_text.lower()
    return [flag for flag in known_flags if flag in lowered]


def _extract_category(description: str) -> str | None:
    lowered = description.lower()
    if "grocer" in lowered:
        return "groceries"
    if "target" in lowered:
        return "shopping"
    if "karate" in lowered or "books" in lowered:
        return "kids"
    if "flight" in lowered:
        return "travel"
    if "car repair" in lowered:
        return "auto"
    if "transport" in lowered or "train" in lowered:
        return "transport"
    if "eating out" in lowered:
        return "eating out"
    if "rent" in lowered:
        return "rent"
    return None


def _goal_candidates(raw_text: str) -> list[str]:
    lowered = raw_text.lower()
    if "learning goal" in lowered:
        return ["Raise a strong, resilient kid", "Get promoted this year"]
    if "family trip fund" in lowered:
        return ["Save for family trip", "family trip fund"]
    if "kid goal" in lowered:
        return ["Raise a strong, resilient kid"]
    if "emergency fund" in lowered or "fund" in lowered:
        return ["Emergency Fund"]
    return []


def _budget_category(name: str) -> dict | None:
    normalized = name.strip().lower()
    for category in _DUMMY_BUDGETS["categories"]:
        if category["name"] == normalized:
            return category
    return None


def _normalized_budget_name(name: str) -> str:
    return " ".join(name.strip().split()).lower()


def _make_budget_category(name: str, budget_amount: float | None) -> dict:
    spent = 0.0
    return {
        "name": _normalized_budget_name(name),
        "budget_amount": budget_amount,
        "spent": spent,
        "remaining": None if budget_amount is None else budget_amount - spent,
        "expense_count": 0,
        "average_amount": 0.0,
        "largest_expenses": [],
    }


def _recalculate_budget_totals() -> None:
    budgeted = 0.0
    spent = 0.0

    for category in _DUMMY_BUDGETS["categories"]:
        budget_amount = category.get("budget_amount")
        category_spent = float(category.get("spent") or 0.0)
        if budget_amount is None:
            category["remaining"] = None
            continue

        budgeted += float(budget_amount)
        spent += category_spent
        category["remaining"] = float(budget_amount) - category_spent

    _DUMMY_BUDGETS["totals"] = {
        "budgeted": budgeted,
        "spent": spent,
        "remaining": budgeted - spent,
    }


def _report_payload(report_type: str, cycle: str) -> dict:
    if report_type == "goal":
        return {"type": report_type, "cycle": cycle, "items": list(_DUMMY_GOALS.values())}
    if report_type == "flag":
        return {
            "type": report_type,
            "cycle": cycle,
            "items": [
                {"flag": "one-off", "count": 1, "total_amount": 45.0},
                {"flag": "shared", "count": 0, "total_amount": 0.0},
            ],
        }
    return {
        "type": "category",
        "cycle": cycle,
        "items": _DUMMY_BUDGETS["categories"],
    }


@app.get("/")
def root() -> dict:
    return {
        "service": "baymax-api",
        "status": "ok",
        "message": "Dummy API surface is running.",
    }


@app.post("/expenses/parse", response_model=ExpenseDraft)
def parse_expense(payload: ParseExpenseRequest) -> ExpenseDraft:
    raw_text = payload.raw_text.strip()
    description = _extract_description(raw_text)
    return ExpenseDraft(
        amount=_extract_amount(raw_text),
        description=description,
        category=_extract_category(description),
        flags=_extract_flags(raw_text),
        goal_candidates=_goal_candidates(raw_text),
        notes="Dummy parse result generated by the API server.",
    )


@app.post("/expenses")
def create_expense(payload: CreateExpenseRequest) -> dict:
    expense = {
        "id": f"exp-{uuid4().hex[:8]}",
        "household_id": "household-1",
        "user_id": payload.user_id or "user-1",
        "cycle": "current",
        "amount": payload.amount,
        "description": payload.description,
        "category": payload.category,
        "flags": payload.flags,
        "goals": payload.goals,
        "notes": payload.notes,
        "date": str(payload.date or datetime.now(timezone.utc).date()),
    }
    _DUMMY_EXPENSES.append(expense)
    return expense


@app.patch("/expenses/{expense_id}")
def update_expense(expense_id: str, payload: UpdateExpenseRequest) -> dict:
    for expense in _DUMMY_EXPENSES:
        if expense["id"] == expense_id:
            updates = payload.model_dump(exclude_unset=True)
            if "date" in updates and updates["date"] is not None:
                updates["date"] = str(updates["date"])
            expense.update(updates)
            return expense
    raise HTTPException(status_code=404, detail="Expense not found")


@app.get("/expenses")
def list_expenses(
    cycle: str = Query(default="current"),
    category: str | None = Query(default=None),
) -> dict:
    expenses = [expense for expense in _DUMMY_EXPENSES if expense["cycle"] == cycle]
    if category:
        expenses = [expense for expense in expenses if expense["category"] == category]
    return {"cycle": cycle, "count": len(expenses), "items": deepcopy(expenses)}


@app.get("/budgets")
def get_budgets() -> dict:
    return deepcopy(_DUMMY_BUDGETS)


@app.put("/budgets/{category_name}")
def set_budget(category_name: str, payload: SetBudgetRequest) -> dict:
    normalized_name = _normalized_budget_name(category_name)
    category = _budget_category(normalized_name)

    if category is None:
        category = _make_budget_category(normalized_name, payload.amount)
        _DUMMY_BUDGETS["categories"].append(category)
        action = "created"
        previous_budget = None
    else:
        previous_budget = category.get("budget_amount")
        action = "set" if previous_budget is None or previous_budget == payload.amount else "updated"
        category["budget_amount"] = payload.amount

    _recalculate_budget_totals()
    return {
        "action": action,
        "category": deepcopy(category),
        "previous_budget": previous_budget,
    }


@app.delete("/budgets/{category_name}")
def remove_budget(category_name: str) -> dict:
    normalized_name = _normalized_budget_name(category_name)
    category = _budget_category(normalized_name)
    if category is None:
        return {"action": "missing", "category_name": normalized_name}

    previous_budget = category.get("budget_amount")
    if previous_budget is None:
        return {"action": "already_removed", "category": deepcopy(category)}

    category["budget_amount"] = None
    _recalculate_budget_totals()
    return {
        "action": "removed",
        "category": deepcopy(category),
        "previous_budget": previous_budget,
    }


@app.get("/goals/{goal_id}/summary")
def get_goal_summary(goal_id: str, cycle: str = Query(default="current")) -> dict:
    goal = _DUMMY_GOALS.get(goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    response = deepcopy(goal)
    response["cycle"] = cycle
    response["cycle_label"] = _DUMMY_BUDGETS["cycle_label"]
    return response


@app.post("/ask", response_model=AskResponse)
def ask_question(payload: AskRequest) -> AskResponse:
    question = payload.question.strip()
    lowered = question.lower()

    if lowered == "how much on groceries this cycle?":
        groceries = _budget_category("groceries")
        if groceries is None:
            raise HTTPException(status_code=500, detail="Groceries summary unavailable")
        budget_amount = groceries.get("budget_amount")
        spent = float(groceries.get("spent") or 0.0)
        count = int(groceries.get("expense_count") or 0)
        if budget_amount is None:
            answer = f"Groceries: ${spent:.2f} — {count} expenses"
        else:
            percent = round((spent / float(budget_amount)) * 100) if budget_amount else 0
            answer = (
                f"Groceries: ${spent:.2f} of ${float(budget_amount):.2f} ({percent}%)"
                f" — {count} expenses"
            )
        return AskResponse(
            answer=answer,
            cycle=payload.cycle,
            supporting_data={
                "question": question,
                "category": "groceries",
                "spent": spent,
                "budget_amount": budget_amount,
                "expense_count": count,
            },
        )

    if lowered == "what did we put toward the resilient kid goal this cycle?":
        goal = deepcopy(_DUMMY_GOALS["goal-resilient-kid"])
        entries = goal.get("cycle_entries") or []
        details = ", ".join(
            f"{entry['description']} ${float(entry['amount']):.0f}" for entry in entries
        )
        answer = (
            f"${float(goal['cycle_contributions']):.2f} across "
            f"{int(goal['cycle_expense_count'])} expenses — {details}"
        )
        return AskResponse(
            answer=answer,
            cycle=payload.cycle,
            supporting_data={
                "question": question,
                "goal_id": goal["id"],
                "goal_name": goal["name"],
                "cycle_contributions": goal["cycle_contributions"],
                "cycle_entries": entries,
            },
        )

    totals = _DUMMY_BUDGETS["totals"]
    return AskResponse(
        answer=(
            f"You have spent ${float(totals['spent']):.2f} across budgeted categories this cycle, "
            f"with ${float(totals['remaining']):.2f} remaining."
        ),
        cycle=payload.cycle,
        supporting_data={
            "question": question,
            "budget_totals": totals,
            "top_category": "groceries",
        },
    )


@app.get("/reports")
def get_reports(
    type: Literal["category", "goal", "flag"] = Query(default="category"),
    cycle: str = Query(default="current"),
) -> dict:
    return _report_payload(type, cycle)
