from __future__ import annotations

from typing import Optional

from ..db import DEFAULT_HOUSEHOLD_ID, connection, initialize_database


def list_all(household_id: str = DEFAULT_HOUSEHOLD_ID) -> list[dict]:
    initialize_database()
    with connection() as db:
        rows = db.execute(
            "SELECT id, name, budget_amount FROM categories WHERE household_id = ? ORDER BY id",
            (household_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get(name: str, household_id: str = DEFAULT_HOUSEHOLD_ID) -> Optional[dict]:
    initialize_database()
    with connection() as db:
        row = db.execute(
            "SELECT id, name, budget_amount FROM categories WHERE household_id = ? AND name = ?",
            (household_id, name),
        ).fetchone()
    return dict(row) if row else None


def ensure(name: str, household_id: str = DEFAULT_HOUSEHOLD_ID) -> dict:
    initialize_database()
    with connection() as db:
        db.execute(
            "INSERT OR IGNORE INTO categories (household_id, name, budget_amount) VALUES (?, ?, NULL)",
            (household_id, name),
        )
        row = db.execute(
            "SELECT id, name, budget_amount FROM categories WHERE household_id = ? AND name = ?",
            (household_id, name),
        ).fetchone()
    return dict(row)


def set_budget(name: str, amount: Optional[float], household_id: str = DEFAULT_HOUSEHOLD_ID) -> None:
    ensure(name, household_id)
    with connection() as db:
        db.execute(
            "UPDATE categories SET budget_amount = ?, updated_at = CURRENT_TIMESTAMP WHERE household_id = ? AND name = ?",
            (amount, household_id, name),
        )
