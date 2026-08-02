from __future__ import annotations

from copy import deepcopy
from datetime import date as DateType, datetime, timezone

from fastapi import HTTPException

from .parsing import normalized_name
from .store import CATEGORY_BUDGETS, EXPENSES, GOAL_DEFINITIONS


def cycle_start(value: DateType) -> DateType:
    if value.day >= 26:
        return DateType(value.year, value.month, 26)
    if value.month == 1:
        return DateType(value.year - 1, 12, 26)
    return DateType(value.year, value.month - 1, 26)


def next_cycle_start(start: DateType) -> DateType:
    if start.month == 12:
        return DateType(start.year + 1, 1, 26)
    return DateType(start.year, start.month + 1, 26)


def cycle_bounds(cycle: str) -> tuple[DateType, DateType]:
    if cycle == "current":
        start = cycle_start(datetime.now(timezone.utc).date())
    else:
        try:
            start = cycle_start(DateType.fromisoformat(cycle))
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail="cycle must be 'current' or an ISO date (YYYY-MM-DD)",
            ) from exc
    return start, next_cycle_start(start)


def cycle_label(start: DateType, end_exclusive: DateType) -> str:
    end = end_exclusive.fromordinal(end_exclusive.toordinal() - 1)
    return f"{start.strftime('%b')} {start.day}–{end.strftime('%b')} {end.day}"


def expenses_for_cycle(cycle: str) -> list[dict]:
    start, end_exclusive = cycle_bounds(cycle)
    return [
        expense
        for expense in EXPENSES
        if start <= DateType.fromisoformat(expense["date"]) < end_exclusive
    ]


def known_category_names() -> list[str]:
    names = list(CATEGORY_BUDGETS)
    for expense in EXPENSES:
        category = expense.get("category")
        if category:
            normalized = normalized_name(category)
            if normalized not in names:
                names.append(normalized)
    return names


def category_summary(name: str, expenses: list[dict]) -> dict:
    normalized = normalized_name(name)
    matching_expenses = [
        expense
        for expense in expenses
        if expense.get("category") and normalized_name(expense["category"]) == normalized
    ]
    amounts = [float(expense["amount"]) for expense in matching_expenses]
    spent = round(sum(amounts), 2)
    budget_amount = CATEGORY_BUDGETS.get(normalized)
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


def budget_payload(cycle: str = "current") -> dict:
    start, end_exclusive = cycle_bounds(cycle)
    expenses = expenses_for_cycle(cycle)
    categories = [category_summary(name, expenses) for name in known_category_names()]
    budgeted_categories = [category for category in categories if category["budget_amount"] is not None]
    budgeted = round(sum(float(category["budget_amount"]) for category in budgeted_categories), 2)
    spent = round(sum(float(category["spent"]) for category in budgeted_categories), 2)
    return {
        "cycle": cycle,
        "cycle_label": cycle_label(start, end_exclusive),
        "currency": "USD",
        "categories": categories,
        "totals": {"budgeted": budgeted, "spent": spent, "remaining": round(budgeted - spent, 2)},
    }


def goal_entries(goal: dict, expenses: list[dict]) -> list[dict]:
    goal_names = {normalized_name(goal["id"]), normalized_name(goal["name"])}
    return [
        expense
        for expense in expenses
        if any(normalized_name(goal_name) in goal_names for goal_name in expense.get("goals", []))
    ]


def goal_summary(goal_id: str, cycle: str) -> dict:
    goal = GOAL_DEFINITIONS.get(goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")

    cycle_entries = goal_entries(goal, expenses_for_cycle(cycle))
    all_entries = goal_entries(goal, EXPENSES)
    total_contributions = round(sum(float(expense["amount"]) for expense in all_entries), 2)
    target_amount = goal["target_amount"]
    since = min((expense["date"] for expense in all_entries), default=None)
    start, end_exclusive = cycle_bounds(cycle)
    return {
        **deepcopy(goal),
        "cycle": cycle,
        "cycle_label": cycle_label(start, end_exclusive),
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


def report_payload(report_type: str, cycle: str) -> dict:
    budgets = budget_payload(cycle)
    if report_type == "goal":
        return {
            "type": report_type,
            "cycle": cycle,
            "cycle_label": budgets["cycle_label"],
            "items": [goal_summary(goal_id, cycle) for goal_id in GOAL_DEFINITIONS],
        }
    if report_type == "flag":
        totals: dict[str, dict] = {}
        for expense in expenses_for_cycle(cycle):
            for flag in expense.get("flags", []):
                summary = totals.setdefault(flag, {"flag": flag, "count": 0, "total_amount": 0.0})
                summary["count"] += 1
                summary["total_amount"] = round(summary["total_amount"] + float(expense["amount"]), 2)
        return {
            "type": report_type,
            "cycle": cycle,
            "cycle_label": budgets["cycle_label"],
            "items": list(totals.values()),
        }
    return {
        "type": "category",
        "cycle": cycle,
        "cycle_label": budgets["cycle_label"],
        "items": budgets["categories"],
    }
