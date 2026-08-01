from __future__ import annotations

import re
from copy import deepcopy
from datetime import date as DateType
from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

app = FastAPI(
    title="Baymax API",
    version="0.1.0",
    description="In-memory API for the Baymax expense-tracking prototype.",
)


class ParseExpenseRequest(BaseModel):
    raw_text: str = Field(..., min_length=1)
    household_id: Optional[str] = None


class ExpenseDraft(BaseModel):
    amount: float
    description: str
    category: Optional[str] = None
    flags: list[str] = Field(default_factory=list)
    goal_candidates: list[str] = Field(default_factory=list)
    notes: Optional[str] = None


class CreateExpenseRequest(BaseModel):
    amount: float
    description: str
    category: Optional[str] = None
    flags: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    date: Optional[DateType] = None
    user_id: Optional[str] = None


class UpdateExpenseRequest(BaseModel):
    amount: Optional[float] = None
    description: Optional[str] = None
    category: Optional[str] = None
    flags: Optional[list[str]] = None
    goals: Optional[list[str]] = None
    notes: Optional[str] = None
    date: Optional[DateType] = None


class SetBudgetRequest(BaseModel):
    amount: float = Field(..., ge=0)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    cycle: str = "current"


class AskResponse(BaseModel):
    answer: str
    cycle: str
    supporting_data: dict


# These are initial configuration values, not report fixtures. Spending, counts,
# reports, and goal progress are all calculated from _EXPENSES below.
_DEFAULT_CATEGORY_BUDGETS: dict[str, Optional[float]] = {
    "groceries": 400.0,
    "transport": 150.0,
    "eating out": None,
}
_CATEGORY_BUDGETS = deepcopy(_DEFAULT_CATEGORY_BUDGETS)

_GOAL_DEFINITIONS = {
    "goal-resilient-kid": {
        "id": "goal-resilient-kid",
        "name": "Raise a strong, resilient kid",
        "target_amount": None,
        "target_date": None,
        "is_open_ended": True,
    },
    "goal-emergency-fund": {
        "id": "goal-emergency-fund",
        "name": "Emergency Fund",
        "target_amount": 10000.0,
        "target_date": None,
        "is_open_ended": True,
    },
    "goal-japan-trip": {
        "id": "goal-japan-trip",
        "name": "Japan Trip",
        "target_amount": 4000.0,
        "target_date": "2027-05-01",
        "is_open_ended": False,
    },
}

# This remains process-local until the persistence layer is introduced. Unlike
# the old fixture data, every read endpoint derives its values from this list.
_EXPENSES: list[dict] = []


def reset_in_memory_store() -> None:
    """Reset the prototype store. Kept public for isolated API tests."""
    _EXPENSES.clear()
    _CATEGORY_BUDGETS.clear()
    _CATEGORY_BUDGETS.update(deepcopy(_DEFAULT_CATEGORY_BUDGETS))


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


def _extract_category(description: str) -> Optional[str]:
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

    for category in sorted(_CATEGORY_BUDGETS, key=len, reverse=True):
        if re.search(rf"(?<!\w){re.escape(category)}(?!\w)", lowered):
            return category

    if re.fullmatch(r"[a-z]+", lowered):
        return _normalized_name(description)
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


def _normalized_name(name: str) -> str:
    return " ".join(name.strip().split()).lower()


def _canonical_goal_name(name: str) -> str:
    normalized = _normalized_name(name)
    for goal in _GOAL_DEFINITIONS.values():
        if normalized in {_normalized_name(goal["id"]), _normalized_name(goal["name"])}:
            return goal["name"]
    return " ".join(name.strip().split())


def _cycle_start(value: DateType) -> DateType:
    if value.day >= 26:
        return DateType(value.year, value.month, 26)
    if value.month == 1:
        return DateType(value.year - 1, 12, 26)
    return DateType(value.year, value.month - 1, 26)


def _next_cycle_start(start: DateType) -> DateType:
    if start.month == 12:
        return DateType(start.year + 1, 1, 26)
    return DateType(start.year, start.month + 1, 26)


def _cycle_bounds(cycle: str) -> tuple[DateType, DateType]:
    if cycle == "current":
        start = _cycle_start(datetime.now(timezone.utc).date())
    else:
        try:
            start = _cycle_start(DateType.fromisoformat(cycle))
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail="cycle must be 'current' or an ISO date (YYYY-MM-DD)",
            ) from exc
    return start, _next_cycle_start(start)


def _cycle_label(start: DateType, end_exclusive: DateType) -> str:
    end = end_exclusive.fromordinal(end_exclusive.toordinal() - 1)
    return f"{start.strftime('%b')} {start.day}\u2013{end.strftime('%b')} {end.day}"


def _expenses_for_cycle(cycle: str) -> list[dict]:
    start, end_exclusive = _cycle_bounds(cycle)
    return [
        expense
        for expense in _EXPENSES
        if start <= DateType.fromisoformat(expense["date"]) < end_exclusive
    ]


def _known_category_names() -> list[str]:
    names = list(_CATEGORY_BUDGETS)
    for expense in _EXPENSES:
        category = expense.get("category")
        if category:
            normalized = _normalized_name(category)
            if normalized not in names:
                names.append(normalized)
    return names


def _category_summary(name: str, expenses: list[dict]) -> dict:
    normalized = _normalized_name(name)
    matching_expenses = [
        expense
        for expense in expenses
        if expense.get("category") and _normalized_name(expense["category"]) == normalized
    ]
    amounts = [float(expense["amount"]) for expense in matching_expenses]
    spent = round(sum(amounts), 2)
    budget_amount = _CATEGORY_BUDGETS.get(normalized)
    largest = sorted(matching_expenses, key=lambda expense: float(expense["amount"]), reverse=True)[:3]
    return {
        "name": normalized,
        "budget_amount": budget_amount,
        "spent": spent,
        "remaining": None if budget_amount is None else round(budget_amount - spent, 2),
        "expense_count": len(matching_expenses),
        "average_amount": round(spent / len(amounts), 2) if amounts else 0.0,
        "largest_expenses": [
            {"description": expense["description"], "amount": float(expense["amount"])}
            for expense in largest
        ],
    }


def _budget_payload(cycle: str = "current") -> dict:
    start, end_exclusive = _cycle_bounds(cycle)
    expenses = _expenses_for_cycle(cycle)
    categories = [_category_summary(name, expenses) for name in _known_category_names()]
    budgeted_categories = [category for category in categories if category["budget_amount"] is not None]
    budgeted = round(sum(float(category["budget_amount"]) for category in budgeted_categories), 2)
    spent = round(sum(float(category["spent"]) for category in budgeted_categories), 2)
    return {
        "cycle": cycle,
        "cycle_label": _cycle_label(start, end_exclusive),
        "currency": "USD",
        "categories": categories,
        "totals": {"budgeted": budgeted, "spent": spent, "remaining": round(budgeted - spent, 2)},
    }


def _goal_entries(goal: dict, expenses: list[dict]) -> list[dict]:
    goal_names = {_normalized_name(goal["id"]), _normalized_name(goal["name"])}
    return [
        expense
        for expense in expenses
        if any(_normalized_name(goal_name) in goal_names for goal_name in expense.get("goals", []))
    ]


def _goal_summary(goal_id: str, cycle: str) -> dict:
    goal = _GOAL_DEFINITIONS.get(goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")

    cycle_entries = _goal_entries(goal, _expenses_for_cycle(cycle))
    all_entries = _goal_entries(goal, _EXPENSES)
    total_contributions = round(sum(float(expense["amount"]) for expense in all_entries), 2)
    target_amount = goal["target_amount"]
    since = min((expense["date"] for expense in all_entries), default=None)
    start, end_exclusive = _cycle_bounds(cycle)
    return {
        **deepcopy(goal),
        "cycle": cycle,
        "cycle_label": _cycle_label(start, end_exclusive),
        "cycle_contributions": round(sum(float(expense["amount"]) for expense in cycle_entries), 2),
        "total_contributions": total_contributions,
        "remaining_to_target": (
            None if target_amount is None else round(max(target_amount - total_contributions, 0.0), 2)
        ),
        "cycle_expense_count": len(cycle_entries),
        "total_expense_count": len(all_entries),
        "since": DateType.fromisoformat(since).strftime("%b %Y") if since else None,
        "cycle_entries": [
            {"description": expense["description"], "amount": float(expense["amount"])}
            for expense in cycle_entries
        ],
    }


def _report_payload(report_type: str, cycle: str) -> dict:
    budget_payload = _budget_payload(cycle)
    if report_type == "goal":
        return {
            "type": report_type,
            "cycle": cycle,
            "cycle_label": budget_payload["cycle_label"],
            "items": [_goal_summary(goal_id, cycle) for goal_id in _GOAL_DEFINITIONS],
        }
    if report_type == "flag":
        totals: dict[str, dict] = {}
        for expense in _expenses_for_cycle(cycle):
            for flag in expense.get("flags", []):
                summary = totals.setdefault(flag, {"flag": flag, "count": 0, "total_amount": 0.0})
                summary["count"] += 1
                summary["total_amount"] = round(summary["total_amount"] + float(expense["amount"]), 2)
        return {
            "type": report_type,
            "cycle": cycle,
            "cycle_label": budget_payload["cycle_label"],
            "items": list(totals.values()),
        }
    return {
        "type": "category",
        "cycle": cycle,
        "cycle_label": budget_payload["cycle_label"],
        "items": budget_payload["categories"],
    }


@app.get("/")
def root() -> dict:
    return {
        "service": "baymax-api",
        "status": "ok",
        "message": "In-memory expense calculations are running.",
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
        notes="Prototype parse result generated by the API server.",
    )


@app.post("/expenses")
def create_expense(payload: CreateExpenseRequest) -> dict:
    category = _normalized_name(payload.category) if payload.category else None
    if category and category not in _CATEGORY_BUDGETS:
        _CATEGORY_BUDGETS[category] = None

    expense = {
        "id": f"exp-{uuid4().hex[:8]}",
        "household_id": "household-1",
        "user_id": payload.user_id or "user-1",
        "amount": payload.amount,
        "description": payload.description,
        "category": category,
        "flags": [_normalized_name(flag) for flag in payload.flags],
        "goals": [_canonical_goal_name(goal) for goal in payload.goals],
        "notes": payload.notes,
        "date": str(payload.date or datetime.now(timezone.utc).date()),
    }
    _EXPENSES.append(expense)
    return deepcopy(expense)


@app.patch("/expenses/{expense_id}")
def update_expense(expense_id: str, payload: UpdateExpenseRequest) -> dict:
    for expense in _EXPENSES:
        if expense["id"] != expense_id:
            continue

        updates = payload.model_dump(exclude_unset=True)
        if "date" in updates and updates["date"] is not None:
            updates["date"] = str(updates["date"])
        if "category" in updates and updates["category"] is not None:
            updates["category"] = _normalized_name(updates["category"])
            _CATEGORY_BUDGETS.setdefault(updates["category"], None)
        if "flags" in updates and updates["flags"] is not None:
            updates["flags"] = [_normalized_name(flag) for flag in updates["flags"]]
        if "goals" in updates and updates["goals"] is not None:
            updates["goals"] = [_canonical_goal_name(goal) for goal in updates["goals"]]
        expense.update(updates)
        return deepcopy(expense)
    raise HTTPException(status_code=404, detail="Expense not found")


@app.get("/expenses")
def list_expenses(
    cycle: str = Query(default="current"),
    category: Optional[str] = Query(default=None),
) -> dict:
    expenses = _expenses_for_cycle(cycle)
    if category:
        normalized_category = _normalized_name(category)
        expenses = [
            expense
            for expense in expenses
            if expense.get("category") and _normalized_name(expense["category"]) == normalized_category
        ]
    return {"cycle": cycle, "count": len(expenses), "items": deepcopy(expenses)}


@app.get("/budgets")
def get_budgets(cycle: str = Query(default="current")) -> dict:
    return _budget_payload(cycle)


@app.put("/budgets/{category_name}")
def set_budget(category_name: str, payload: SetBudgetRequest) -> dict:
    normalized_name = _normalized_name(category_name)
    if normalized_name not in _CATEGORY_BUDGETS:
        _CATEGORY_BUDGETS[normalized_name] = payload.amount
        action = "created"
        previous_budget = None
    else:
        previous_budget = _CATEGORY_BUDGETS[normalized_name]
        action = "set" if previous_budget is None or previous_budget == payload.amount else "updated"
        _CATEGORY_BUDGETS[normalized_name] = payload.amount

    category = _category_summary(normalized_name, _expenses_for_cycle("current"))
    return {"action": action, "category": category, "previous_budget": previous_budget}


@app.delete("/budgets/{category_name}")
def remove_budget(category_name: str) -> dict:
    normalized_name = _normalized_name(category_name)
    if normalized_name not in _CATEGORY_BUDGETS:
        return {"action": "missing", "category_name": normalized_name}

    previous_budget = _CATEGORY_BUDGETS[normalized_name]
    category = _category_summary(normalized_name, _expenses_for_cycle("current"))
    if previous_budget is None:
        return {"action": "already_removed", "category": category}

    _CATEGORY_BUDGETS[normalized_name] = None
    category = _category_summary(normalized_name, _expenses_for_cycle("current"))
    return {"action": "removed", "category": category, "previous_budget": previous_budget}


@app.get("/goals/{goal_id}/summary")
def get_goal_summary(goal_id: str, cycle: str = Query(default="current")) -> dict:
    return _goal_summary(goal_id, cycle)


@app.post("/ask", response_model=AskResponse)
def ask_question(payload: AskRequest) -> AskResponse:
    question = payload.question.strip()
    lowered = question.lower()
    budget_payload = _budget_payload(payload.cycle)

    if lowered == "how much on groceries this cycle?":
        groceries = next(
            (category for category in budget_payload["categories"] if category["name"] == "groceries"),
            None,
        )
        if groceries is None:
            raise HTTPException(status_code=404, detail="Groceries category not found")
        budget_amount = groceries["budget_amount"]
        spent = float(groceries["spent"])
        count = int(groceries["expense_count"])
        if budget_amount is None:
            answer = f"Groceries: ${spent:.2f} — {count} expenses"
        else:
            percent = round((spent / float(budget_amount)) * 100) if budget_amount else 0
            answer = f"Groceries: ${spent:.2f} of ${float(budget_amount):.2f} ({percent}%) — {count} expenses"
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
        goal = _goal_summary("goal-resilient-kid", payload.cycle)
        details = ", ".join(
            f"{entry['description']} ${float(entry['amount']):.0f}"
            for entry in goal["cycle_entries"]
        )
        answer = (
            f"${float(goal['cycle_contributions']):.2f} across "
            f"{int(goal['cycle_expense_count'])} expenses"
        )
        if details:
            answer += f" — {details}"
        return AskResponse(
            answer=answer,
            cycle=payload.cycle,
            supporting_data={
                "question": question,
                "goal_id": goal["id"],
                "goal_name": goal["name"],
                "cycle_contributions": goal["cycle_contributions"],
                "cycle_entries": goal["cycle_entries"],
            },
        )

    totals = budget_payload["totals"]
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
