"""Baymax API composition and backwards-compatible public entry point."""

from __future__ import annotations

from fastapi import FastAPI

from .calculations import (
    budget_payload as _budget_payload,
    category_summary as _category_summary,
    cycle_bounds as _cycle_bounds,
    cycle_label as _cycle_label,
    cycle_start as _cycle_start,
    expenses_for_cycle as _expenses_for_cycle,
    goal_entries as _goal_entries,
    goal_summary as _goal_summary,
    known_category_names as _known_category_names,
    next_cycle_start as _next_cycle_start,
    report_payload as _report_payload,
)
from .models import (
    AskRequest,
    AskResponse,
    CreateExpenseRequest,
    ExpenseDraft,
    ParseExpenseRequest,
    SetBudgetRequest,
    UpdateExpenseRequest,
)
from .parsing import (
    canonical_goal_name as _canonical_goal_name,
    extract_amount as _extract_amount,
    extract_category as _extract_category,
    extract_description as _extract_description,
    extract_flags as _extract_flags,
    goal_candidates as _goal_candidates,
    normalized_name as _normalized_name,
)
from .routes import (
    ask_question,
    create_expense,
    get_budgets,
    get_goal_summary,
    get_reports,
    list_expenses,
    parse_expense,
    remove_budget,
    root,
    router,
    set_budget,
    update_expense,
)
from .store import (
    CATEGORY_BUDGETS as _CATEGORY_BUDGETS,
    DEFAULT_CATEGORY_BUDGETS as _DEFAULT_CATEGORY_BUDGETS,
    EXPENSES as _EXPENSES,
    GOAL_DEFINITIONS as _GOAL_DEFINITIONS,
    reset_in_memory_store,
)

app = FastAPI(
    title="Baymax API",
    version="0.1.0",
    description="In-memory API for the Baymax expense-tracking prototype.",
)
app.include_router(router)
