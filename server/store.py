"""Database lifecycle helpers retained for backwards-compatible tests."""

from __future__ import annotations

from .db import connection, initialize_database


def reset_database() -> None:
    with connection() as db:
        for table in ("expense_flags", "expense_goals", "expenses", "flags", "categories", "goals"):
            db.execute(f"DELETE FROM {table}")
    initialize_database()


reset_in_memory_store = reset_database
