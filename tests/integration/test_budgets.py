from __future__ import annotations

import pytest

from .helpers import category_from, create_expense

pytestmark = pytest.mark.integration


def test_budget_can_be_updated_read_and_removed(client) -> None:
    create_expense(client, amount=75)

    updated = client.put("/budgets/groceries", json={"amount": 500})
    groceries = category_from(client.get("/budgets"))

    assert updated.status_code == 200
    assert updated.json()["action"] == "updated"
    assert groceries["budget_amount"] == 500
    assert groceries["spent"] == 75
    assert groceries["remaining"] == 425

    removed = client.delete("/budgets/groceries")
    groceries_without_budget = category_from(client.get("/budgets"))

    assert removed.status_code == 200
    assert removed.json()["action"] == "removed"
    assert groceries_without_budget["budget_amount"] is None
    assert groceries_without_budget["spent"] == 75
    assert groceries_without_budget["remaining"] is None
