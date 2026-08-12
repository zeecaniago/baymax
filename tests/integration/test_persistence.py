from __future__ import annotations

import pytest

from .helpers import category_from, create_expense

pytestmark = pytest.mark.integration


def test_expense_persists_across_client_reinitialization(client_factory, db_path) -> None:
    with client_factory() as first_client:
        created = create_expense(first_client, amount=32, description="Pantry staples")

    assert db_path.exists()

    with client_factory() as second_client:
        history = second_client.get("/expenses")
        groceries = category_from(second_client.get("/reports"))

    assert history.status_code == 200
    assert history.json()["items"][0]["id"] == created["id"]
    assert history.json()["items"][0]["description"] == "Pantry staples"
    assert groceries["spent"] == 32
    assert groceries["expense_count"] == 1
