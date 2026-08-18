"""Deterministic executor for validated Baymax intents.

This module is the only bridge from the language contract to application
state.  It never asks an interpreter to calculate balances or choose database
identifiers.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from .calculations import (
    budget_payload,
    category_summary,
    cycle_bounds,
    expenses_for_cycle,
    goal_summary,
    report_payload,
)
from .db import DEFAULT_HOUSEHOLD_ID, DEFAULT_USER_ID
from .entity_resolution import EntityResolutionResult, resolve_intent_entities
from .intents import (
    BaymaxIntent,
    ContractModel,
    CorrectExpenseIntent,
    LogExpenseIntent,
    QuerySpendingIntent,
    RemoveBudgetIntent,
    ReportIntent,
    SetBudgetIntent,
    ShowHistoryIntent,
    SuggestBudgetIntent,
    UnknownIntent,
)
from .repositories import (
    categories as category_repository,
    expenses as expense_repository,
)


class IntentExecutionResult(BaseModel):
    status: Literal[
        "executed",
        "confirmation_required",
        "clarification_required",
        "unsupported",
        "not_found",
    ]
    intent: BaymaxIntent
    message: str
    data: dict = Field(default_factory=dict)
    resolution: EntityResolutionResult = Field(default_factory=EntityResolutionResult)


class ExecuteIntentRequest(ContractModel):
    intent: BaymaxIntent
    confirmed: bool = False
    last_expense_id: Optional[str] = None


def _cycle_for_period(kind: str) -> str:
    if kind == "current_cycle":
        return "current"
    start, end_exclusive = cycle_bounds("current")
    if kind == "previous_cycle":
        return str(start - timedelta(days=1))
    if kind == "next_cycle":
        return str(end_exclusive)
    raise ValueError("explicit date ranges are not executable yet")


def _resolved_name(resolution: EntityResolutionResult, field: str) -> Optional[str]:
    reference = resolution.references.get(field)
    return reference.canonical_name if reference else None


def _resolved_id(resolution: EntityResolutionResult, field: str) -> Optional[str]:
    reference = resolution.references.get(field)
    return reference.entity_id if reference else None


def _clarification_message(resolution: EntityResolutionResult) -> str:
    issue = resolution.issues[0]
    if issue.status == "ambiguous":
        choices = ", ".join(candidate.canonical_name for candidate in issue.candidates)
        return f"Which {issue.kind} did you mean? {choices}"
    return f"No {issue.kind} matches {issue.reference!r}."


def _execute_log_expense(
    intent: LogExpenseIntent,
    resolution: EntityResolutionResult,
) -> IntentExecutionResult:
    goal_name = _resolved_name(resolution, "goal")
    expense = {
        "id": f"exp-{uuid4().hex[:8]}",
        "household_id": DEFAULT_HOUSEHOLD_ID,
        "user_id": DEFAULT_USER_ID,
        "amount": intent.amount,
        "description": intent.description,
        "merchant": _resolved_name(resolution, "merchant"),
        "category": _resolved_name(resolution, "category"),
        "flags": list(intent.flags),
        "budget_treatment": intent.budget_treatment,
        "goals": [goal_name] if goal_name else [],
        "notes": None,
        "date": str(intent.purchase_date or datetime.now(timezone.utc).date()),
    }
    created = expense_repository.create(expense)
    return IntentExecutionResult(
        status="executed",
        intent=intent,
        message=f"Logged ${intent.amount:.2f} for {intent.description}.",
        data={"expense": created},
        resolution=resolution,
    )


def _execute_correction(
    intent: CorrectExpenseIntent,
    resolution: EntityResolutionResult,
    last_expense_id: Optional[str],
) -> IntentExecutionResult:
    if last_expense_id is None:
        return IntentExecutionResult(
            status="not_found",
            intent=intent,
            message="There is no last expense to update.",
            resolution=resolution,
        )
    updates = intent.model_dump(
        include={"amount", "description"},
        exclude_none=True,
    )
    merchant = _resolved_name(resolution, "merchant")
    category = _resolved_name(resolution, "category")
    goal = _resolved_name(resolution, "goal")
    if intent.merchant_reference is not None:
        updates["merchant"] = merchant
    if intent.category_reference is not None:
        updates["category"] = category
    if intent.goal_reference is not None:
        updates["goals"] = [goal] if goal else []
    updated = expense_repository.update(last_expense_id, updates)
    if updated is None:
        return IntentExecutionResult(
            status="not_found",
            intent=intent,
            message="The referenced expense no longer exists.",
            resolution=resolution,
        )
    return IntentExecutionResult(
        status="executed",
        intent=intent,
        message="Updated the last expense.",
        data={"expense": updated},
        resolution=resolution,
    )


def _query_message(intent: QuerySpendingIntent, data: dict) -> str:
    if "goal" in data:
        goal = data["goal"]
        entries = ", ".join(
            f"{entry['description']} ${float(entry['amount']):.0f}"
            for entry in goal["cycle_entries"]
        )
        message = (
            f"${float(goal['cycle_goal_related_spending']):.2f} of goal-related spending "
            f"across {int(goal['cycle_expense_count'])} expenses"
        )
        return f"{message} — {entries}" if entries else message

    if "category" in data:
        category = data["category"]
        name = str(category["name"]).title()
        spent = float(category["spent"])
        budget = category["budget_amount"]
        count = int(category["expense_count"])
        if intent.metric == "remaining":
            if budget is None:
                return f"{name} doesn't have a budget this cycle."
            return f"${float(category['remaining']):.2f} left of ${float(budget):.2f}"
        if intent.metric == "expense_count":
            return f"{name}: {count} expenses this cycle."
        if intent.metric == "average":
            return f"{name}: ${float(category['average_amount']):.2f} average expense."
        if intent.metric == "largest_expenses":
            entries = ", ".join(
                f"{entry['description']} ${float(entry['amount']):.2f}"
                for entry in category["largest_expenses"]
            )
            return f"{name}: {entries}" if entries else f"{name}: no expenses this cycle."
        if budget is None:
            return f"{name}: ${spent:.2f} — {count} expenses"
        percent = round((spent / float(budget)) * 100) if budget else 0
        return f"{name}: ${spent:.2f} of ${float(budget):.2f} ({percent}%) — {count} expenses"

    totals = data["budget_totals"]
    return (
        f"You have spent ${float(totals['spent']):.2f} across budgeted categories "
        f"this cycle, with ${float(totals['remaining']):.2f} remaining."
    )


def _execute_query(
    intent: QuerySpendingIntent,
    resolution: EntityResolutionResult,
) -> IntentExecutionResult:
    cycle = _cycle_for_period(intent.period.kind)
    if intent.goal_reference:
        goal_id = _resolved_id(resolution, "goal")
        data = {"goal": goal_summary(str(goal_id), cycle)}
    elif intent.category_reference:
        category_name = str(_resolved_name(resolution, "category"))
        data = {
            "category": category_summary(category_name, expenses_for_cycle(cycle)),
        }
    else:
        data = {"budget_totals": budget_payload(cycle)["totals"]}
    return IntentExecutionResult(
        status="executed",
        intent=intent,
        message=_query_message(intent, data),
        data=data,
        resolution=resolution,
    )


def execute_intent(
    intent: BaymaxIntent,
    *,
    confirmed: bool = False,
    last_expense_id: Optional[str] = None,
) -> IntentExecutionResult:
    """Resolve and execute an intent through deterministic domain functions."""
    resolution = resolve_intent_entities(intent)
    if not resolution.ready:
        return IntentExecutionResult(
            status="clarification_required",
            intent=intent,
            message=_clarification_message(resolution),
            resolution=resolution,
        )

    if intent.requires_confirmation and not confirmed:
        return IntentExecutionResult(
            status="confirmation_required",
            intent=intent,
            message="Please confirm this change before it is applied.",
            resolution=resolution,
        )

    if isinstance(intent, LogExpenseIntent):
        return _execute_log_expense(intent, resolution)
    if isinstance(intent, CorrectExpenseIntent):
        return _execute_correction(intent, resolution, last_expense_id)
    if isinstance(intent, QuerySpendingIntent):
        if intent.period.kind == "date_range":
            return IntentExecutionResult(
                status="unsupported",
                intent=intent,
                message="Explicit date-range queries are not supported yet.",
                resolution=resolution,
            )
        if intent.merchant_reference or intent.flags:
            return IntentExecutionResult(
                status="unsupported",
                intent=intent,
                message="Merchant and flag query filters are not supported yet.",
                resolution=resolution,
            )
        return _execute_query(intent, resolution)
    if isinstance(intent, SetBudgetIntent):
        if intent.period.kind != "current_cycle":
            return IntentExecutionResult(
                status="unsupported",
                intent=intent,
                message="Future-cycle budgets are not persisted by the current data model.",
                resolution=resolution,
            )
        category_name = str(_resolved_name(resolution, "category"))
        previous = category_repository.get(category_name)
        previous_budget = previous["budget_amount"] if previous else None
        category_repository.set_budget(category_name, intent.amount)
        category = category_summary(category_name, expenses_for_cycle("current"))
        return IntentExecutionResult(
            status="executed",
            intent=intent,
            message=f"Set the {category_name} budget to ${intent.amount:.2f}.",
            data={"category": category, "previous_budget": previous_budget},
            resolution=resolution,
        )
    if isinstance(intent, RemoveBudgetIntent):
        category_name = str(_resolved_name(resolution, "category"))
        previous = category_repository.get(category_name)
        previous_budget = previous["budget_amount"] if previous else None
        category_repository.set_budget(category_name, None)
        return IntentExecutionResult(
            status="executed",
            intent=intent,
            message=f"Removed the {category_name} budget.",
            data={"category_name": category_name, "previous_budget": previous_budget},
            resolution=resolution,
        )
    if isinstance(intent, ReportIntent):
        if intent.period.kind == "date_range":
            return IntentExecutionResult(
                status="unsupported",
                intent=intent,
                message="Explicit date-range reports are not supported yet.",
                resolution=resolution,
            )
        cycle = _cycle_for_period(intent.period.kind)
        report = report_payload(intent.report_type, cycle)
        if intent.entity_reference and intent.report_type != "flag":
            resolved_name = _resolved_name(resolution, intent.report_type)
            if intent.report_type == "goal":
                report = goal_summary(str(_resolved_id(resolution, "goal")), cycle)
            else:
                report = next(
                    item for item in report["items"] if item["name"] == resolved_name
                )
        elif intent.entity_reference:
            report = next(
                (
                    item
                    for item in report["items"]
                    if item["flag"] == intent.entity_reference.lower()
                ),
                {"flag": intent.entity_reference.lower(), "count": 0, "total_amount": 0.0},
            )
        return IntentExecutionResult(
            status="executed",
            intent=intent,
            message="Generated the requested report.",
            data={"report": report},
            resolution=resolution,
        )
    if isinstance(intent, SuggestBudgetIntent):
        return IntentExecutionResult(
            status="unsupported",
            intent=intent,
            message="Budget recommendation execution is not server-backed yet.",
            resolution=resolution,
        )
    if isinstance(intent, ShowHistoryIntent):
        return IntentExecutionResult(
            status="unsupported",
            intent=intent,
            message="Command history belongs to the client session.",
            resolution=resolution,
        )
    if isinstance(intent, UnknownIntent):
        return IntentExecutionResult(
            status="unsupported",
            intent=intent,
            message=intent.reason,
            resolution=resolution,
        )
    raise TypeError(f"Unsupported intent type: {type(intent).__name__}")
