from __future__ import annotations

from typing import Optional

from ..db import DEFAULT_HOUSEHOLD_ID, connection, initialize_database


def list_all(household_id: str = DEFAULT_HOUSEHOLD_ID) -> list[dict]:
    initialize_database()
    with connection() as db:
        rows = db.execute(
            "SELECT id, name FROM goals WHERE household_id = ? ORDER BY rowid",
            (household_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get(goal_id: str, household_id: str = DEFAULT_HOUSEHOLD_ID) -> Optional[dict]:
    initialize_database()
    with connection() as db:
        row = db.execute(
            "SELECT id, name FROM goals WHERE household_id = ? AND id = ?",
            (household_id, goal_id),
        ).fetchone()
    return dict(row) if row else None


def resolve(value: str, household_id: str = DEFAULT_HOUSEHOLD_ID) -> Optional[dict]:
    normalized = " ".join(value.strip().split()).lower()
    return next(
        (
            goal
            for goal in list_all(household_id)
            if normalized in {goal["id"].lower(), goal["name"].lower()}
        ),
        None,
    )
