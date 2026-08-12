from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from server.calculations import cycle_bounds


def current_cycle_date() -> str:
    start, _ = cycle_bounds("current")
    return (start + timedelta(days=1)).isoformat()


def create_expense(client: TestClient, **overrides) -> dict:
    payload = {
        "amount": 45,
        "description": "groceries",
        "category": "groceries",
        "date": current_cycle_date(),
        **overrides,
    }
    response = client.post("/expenses", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def category_from(response, name: str = "groceries") -> dict:
    assert response.status_code == 200, response.text
    payload = response.json()
    items = payload.get("items", payload.get("categories"))
    return next(item for item in items if item["name"] == name)
