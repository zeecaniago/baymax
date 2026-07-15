from __future__ import annotations

import re
from copy import deepcopy
from datetime import date as DateType
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


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    cycle: str = "current"


class AskResponse(BaseModel):
    answer: str
    cycle: str
    supporting_data: dict


_DUMMY_BUDGETS = {
    "cycle": "current",
    "currency": "USD",
    "categories": [
        {"name": "groceries", "budget_amount": 500, "spent": 182.40, "remaining": 317.60},
        {"name": "transport", "budget_amount": 150, "spent": 48.75, "remaining": 101.25},
        {"name": "eating out", "budget_amount": 200, "spent": 63.10, "remaining": 136.90},
    ],
    "totals": {"budgeted": 850, "spent": 294.25, "remaining": 555.75},
}

_DUMMY_GOALS = {
    "goal-emergency-fund": {
        "id": "goal-emergency-fund",
        "name": "Emergency Fund",
        "target_amount": 10000,
        "target_date": None,
        "is_open_ended": True,
        "cycle_contributions": 125,
        "total_contributions": 2750,
        "remaining_to_target": 7250,
    },
    "goal-japan-trip": {
        "id": "goal-japan-trip",
        "name": "Japan Trip",
        "target_amount": 4000,
        "target_date": "2027-05-01",
        "is_open_ended": False,
        "cycle_contributions": 220,
        "total_contributions": 980,
        "remaining_to_target": 3020,
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
        "date": str(payload.date or DateType.today()),
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


@app.get("/goals/{goal_id}/summary")
def get_goal_summary(goal_id: str, cycle: str = Query(default="current")) -> dict:
    goal = _DUMMY_GOALS.get(goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    response = deepcopy(goal)
    response["cycle"] = cycle
    return response


@app.post("/ask", response_model=AskResponse)
def ask_question(payload: AskRequest) -> AskResponse:
    return AskResponse(
        answer=(
            "You have spent $294.25 across budgeted categories this cycle, "
            "with $555.75 remaining."
        ),
        cycle=payload.cycle,
        supporting_data={
            "question": payload.question,
            "budget_totals": _DUMMY_BUDGETS["totals"],
            "top_category": "groceries",
        },
    )


@app.get("/reports")
def get_reports(
    type: Literal["category", "goal", "flag"] = Query(default="category"),
    cycle: str = Query(default="current"),
) -> dict:
    return _report_payload(type, cycle)
