from __future__ import annotations

import pytest

from .helpers import category_from, create_expense

pytestmark = pytest.mark.integration


def test_category_report_is_derived_from_persisted_expenses(client) -> None:
    create_expense(client, amount=45, description="Corner market")
    create_expense(client, amount=20, description="Produce stand")

    groceries = category_from(client.get("/reports", params={"type": "category"}))

    assert groceries["spent"] == 65
    assert groceries["remaining"] == 335
    assert groceries["expense_count"] == 2
    assert groceries["average_amount"] == 32.5
    assert groceries["largest_expenses"] == [
        {"description": "Corner market", "amount": 45},
        {"description": "Produce stand", "amount": 20},
    ]


def test_goal_summary_returns_linked_expense_entries(client) -> None:
    create_expense(
        client,
        amount=50,
        description="Workout class",
        goals=["Healthy Lifestyle"],
    )
    create_expense(
        client,
        amount=25,
        description="Running shoes",
        goals=["goal-healthy-lifestyle"],
    )

    response = client.get("/goals/goal-healthy-lifestyle/summary")

    assert response.status_code == 200
    summary = response.json()
    assert summary["cycle_goal_related_spending"] == 75
    assert summary["cycle_expense_count"] == 2
    assert summary["cycle_entries"] == [
        {"description": "Workout class", "amount": 50},
        {"description": "Running shoes", "amount": 25},
    ]


def test_natural_language_question_uses_sandbox_data(client) -> None:
    create_expense(client, amount=45)

    response = client.post(
        "/ask",
        json={"question": "how much on groceries this cycle?"},
    )

    assert response.status_code == 200
    answer = response.json()
    assert answer["answer"] == "Groceries: $45.00 of $400.00 (11%) — 1 expenses"
    assert answer["supporting_data"]["spent"] == 45
    assert answer["supporting_data"]["expense_count"] == 1
