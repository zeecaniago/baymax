from __future__ import annotations

import pytest
from pydantic import ValidationError

from server.intents import (
    CorrectExpenseIntent,
    LogExpenseIntent,
    PeriodReference,
    validate_intent,
)


def test_future_llm_output_validates_against_the_same_contract() -> None:
    intent = validate_intent(
        {
            "schema_version": "1.0",
            "source": "llm",
            "raw_text": "forty five at fresh street for groceries",
            "intent": "log_expense",
            "amount": 45,
            "description": "groceries",
            "merchant_reference": "Fresh Street",
            "category_reference": "groceries",
        }
    )

    assert isinstance(intent, LogExpenseIntent)
    assert intent.source == "llm"
    assert intent.amount == 45


@pytest.mark.parametrize(
    "payload",
    [
        {"intent": "transfer_money", "raw_text": "transfer $50"},
        {
            "intent": "log_expense",
            "raw_text": "$-5 coffee",
            "amount": -5,
            "description": "coffee",
        },
        {
            "intent": "set_budget",
            "raw_text": "set groceries budget",
            "category_reference": "groceries",
        },
        {
            "intent": "correct_expense",
            "raw_text": "correct the last expense",
        },
        {
            "intent": "set_budget",
            "raw_text": "set groceries budget to 500",
            "category_reference": "groceries",
            "amount": 500,
            "requires_confirmation": False,
        },
        {
            "intent": "log_expense",
            "raw_text": "$5 coffee",
            "amount": 5,
            "description": "coffee",
            "invented_field": "must be rejected",
        },
        {
            "intent": "log_expense",
            "raw_text": "$5 coffee",
            "amount": 5,
            "description": "coffee",
            "category_reference": "   ",
        },
    ],
)
def test_invalid_interpreter_output_is_rejected(payload) -> None:
    with pytest.raises(ValidationError):
        validate_intent(payload)


def test_correction_contract_requires_at_least_one_change() -> None:
    with pytest.raises(ValidationError, match="at least one updated field"):
        CorrectExpenseIntent(raw_text="correct the last expense")


def test_explicit_period_requires_a_complete_ordered_range() -> None:
    with pytest.raises(ValidationError, match="requires start_date and end_date"):
        PeriodReference(kind="date_range", start_date="2026-08-01")

    with pytest.raises(ValidationError, match="must not be before"):
        PeriodReference(
            kind="date_range",
            start_date="2026-08-10",
            end_date="2026-08-01",
        )
