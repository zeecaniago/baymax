from __future__ import annotations

import pytest

from .helpers import category_from, create_expense

pytestmark = pytest.mark.integration


def test_create_expense_is_persisted_through_http(client) -> None:
    created = create_expense(client)

    assert created["id"].startswith("exp-")
    assert created["amount"] == 45
    assert created["description"] == "groceries"
    assert created["category"] == "groceries"

    history = client.get("/expenses")
    assert history.status_code == 200
    assert history.json()["count"] == 1
    assert history.json()["items"] == [created]


def test_explicit_expense_dimensions_are_preserved(client) -> None:
    created = create_expense(
        client,
        description="coffee",
        merchant="Fresh Street",
        category="Groceries",
        goals=["Healthy Lifestyle"],
    )

    assert created["merchant"] == "Fresh Street"
    assert created["category"] == "groceries"
    assert created["goals"] == ["Healthy Lifestyle"]


def test_one_off_remains_in_history_but_not_budget_spend(client) -> None:
    create_expense(client, amount=100, description="Weekly groceries")
    one_off = create_expense(
        client,
        amount=45,
        description="Gift basket",
        flags=["one-off"],
    )

    history = client.get("/expenses")
    groceries = category_from(client.get("/budgets"))

    assert history.json()["count"] == 2
    assert one_off["budget_treatment"] == "excluded"
    assert groceries["spent"] == 100
    assert groceries["total_spent"] == 145
    assert groceries["excluded_spent"] == 45


def test_corrected_expense_updates_report_calculations(client) -> None:
    created = create_expense(client)

    corrected = client.patch(f"/expenses/{created['id']}", json={"amount": 54})
    report = category_from(client.get("/reports", params={"type": "category"}))

    assert corrected.status_code == 200
    assert corrected.json()["amount"] == 54
    assert report["spent"] == 54
    assert report["remaining"] == 346
    assert report["largest_expenses"] == [{"description": "groceries", "amount": 54}]
