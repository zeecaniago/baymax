from __future__ import annotations

from typing import Optional

from ..db import DEFAULT_HOUSEHOLD_ID, connection, initialize_database
from . import categories


def _hydrate(db, row) -> dict:
    expense = dict(row)
    expense["category"] = expense.pop("category_name")
    expense["flags"] = [
        item["name"]
        for item in db.execute(
            "SELECT f.name FROM flags f JOIN expense_flags ef ON ef.flag_id = f.id WHERE ef.expense_id = ? ORDER BY f.id",
            (expense["id"],),
        ).fetchall()
    ]
    expense["goals"] = [
        item["name"]
        for item in db.execute(
            "SELECT g.name FROM goals g JOIN expense_goals eg ON eg.goal_id = g.id WHERE eg.expense_id = ? ORDER BY g.rowid",
            (expense["id"],),
        ).fetchall()
    ]
    return expense


def list_all(household_id: str = DEFAULT_HOUSEHOLD_ID) -> list[dict]:
    initialize_database()
    with connection() as db:
        rows = db.execute(
            """SELECT e.id, e.household_id, e.user_id, e.amount, e.description,
                      e.merchant, c.name AS category_name, e.budget_treatment,
                      e.notes, e.date
               FROM expenses e LEFT JOIN categories c ON c.id = e.category_id
               WHERE e.household_id = ? ORDER BY e.created_at, e.rowid""",
            (household_id,),
        ).fetchall()
        return [_hydrate(db, row) for row in rows]


def get(expense_id: str, household_id: str = DEFAULT_HOUSEHOLD_ID) -> Optional[dict]:
    return next((item for item in list_all(household_id) if item["id"] == expense_id), None)


def _replace_relations(db, expense_id: str, household_id: str, flags: list[str], goal_names: list[str]) -> None:
    db.execute("DELETE FROM expense_flags WHERE expense_id = ?", (expense_id,))
    for flag in flags:
        db.execute("INSERT OR IGNORE INTO flags (household_id, name) VALUES (?, ?)", (household_id, flag))
        flag_id = db.execute(
            "SELECT id FROM flags WHERE household_id = ? AND name = ?", (household_id, flag)
        ).fetchone()["id"]
        db.execute("INSERT INTO expense_flags (expense_id, flag_id) VALUES (?, ?)", (expense_id, flag_id))

    db.execute("DELETE FROM expense_goals WHERE expense_id = ?", (expense_id,))
    for goal_name in goal_names:
        goal = db.execute(
            """SELECT id FROM goals
               WHERE household_id = ? AND (lower(id) = lower(?) OR lower(name) = lower(?))""",
            (household_id, goal_name, goal_name),
        ).fetchone()
        if goal:
            db.execute("INSERT OR IGNORE INTO expense_goals (expense_id, goal_id) VALUES (?, ?)", (expense_id, goal["id"]))


def create(expense: dict) -> dict:
    initialize_database()
    category_id = None
    if expense.get("category"):
        category_id = categories.ensure(expense["category"], expense["household_id"])["id"]
    with connection() as db:
        db.execute(
            """INSERT INTO expenses
               (id, household_id, user_id, amount, description, merchant, category_id,
                budget_treatment, notes, date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                expense["id"], expense["household_id"], expense["user_id"], expense["amount"],
                expense["description"], expense.get("merchant"), category_id,
                expense["budget_treatment"], expense.get("notes"), expense["date"],
            ),
        )
        _replace_relations(db, expense["id"], expense["household_id"], expense["flags"], expense["goals"])
    return get(expense["id"], expense["household_id"])


def update(expense_id: str, updates: dict, household_id: str = DEFAULT_HOUSEHOLD_ID) -> Optional[dict]:
    current = get(expense_id, household_id)
    if current is None:
        return None
    merged = {**current, **updates}
    category_id = None
    if merged.get("category"):
        category_id = categories.ensure(merged["category"], household_id)["id"]
    with connection() as db:
        db.execute(
            """UPDATE expenses SET amount = ?, description = ?, merchant = ?, category_id = ?,
               budget_treatment = ?, notes = ?, date = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ? AND household_id = ?""",
            (merged["amount"], merged["description"], merged.get("merchant"), category_id,
             merged["budget_treatment"], merged.get("notes"), merged["date"], expense_id, household_id),
        )
        _replace_relations(db, expense_id, household_id, merged["flags"], merged["goals"])
    return get(expense_id, household_id)
