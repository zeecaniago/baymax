from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

DEFAULT_DB_PATH = Path("data/baymax.db")
DEFAULT_HOUSEHOLD_ID = "household-1"
DEFAULT_USER_ID = "user-1"

DEFAULT_CATEGORIES = {
    "groceries": 400.0,
    "transport": 150.0,
    "eating out": None,
}

DEFAULT_GOALS = {
    "goal-resilient-kid": "Raise a strong, resilient kid",
    "goal-healthy-lifestyle": "Healthy Lifestyle",
    "goal-promoted": "Get promoted this year",
    "goal-family-trip": "Save for family trip",
    "goal-emergency-fund": "Emergency Fund",
    "goal-japan-trip": "Japan Trip",
}


def database_path() -> Path:
    return Path(os.environ.get("BAYMAX_DB_PATH", DEFAULT_DB_PATH))


def connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    db = connect()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def initialize_database() -> None:
    with connection() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                household_id TEXT NOT NULL,
                name TEXT NOT NULL,
                budget_amount REAL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (household_id, name)
            );
            CREATE TABLE IF NOT EXISTS goals (
                id TEXT PRIMARY KEY,
                household_id TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (household_id, name)
            );
            CREATE TABLE IF NOT EXISTS expenses (
                id TEXT PRIMARY KEY,
                household_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                amount REAL NOT NULL,
                description TEXT NOT NULL,
                merchant TEXT,
                category_id INTEGER,
                budget_treatment TEXT NOT NULL,
                notes TEXT,
                date TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories(id)
            );
            CREATE TABLE IF NOT EXISTS flags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                household_id TEXT NOT NULL,
                name TEXT NOT NULL,
                UNIQUE (household_id, name)
            );
            CREATE TABLE IF NOT EXISTS expense_flags (
                expense_id TEXT NOT NULL,
                flag_id INTEGER NOT NULL,
                PRIMARY KEY (expense_id, flag_id),
                FOREIGN KEY (expense_id) REFERENCES expenses(id) ON DELETE CASCADE,
                FOREIGN KEY (flag_id) REFERENCES flags(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS expense_goals (
                expense_id TEXT NOT NULL,
                goal_id TEXT NOT NULL,
                PRIMARY KEY (expense_id, goal_id),
                FOREIGN KEY (expense_id) REFERENCES expenses(id) ON DELETE CASCADE,
                FOREIGN KEY (goal_id) REFERENCES goals(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_expenses_household_date
                ON expenses(household_id, date);
            CREATE INDEX IF NOT EXISTS idx_expenses_category
                ON expenses(category_id);
            """
        )
        for name, budget in DEFAULT_CATEGORIES.items():
            db.execute(
                "INSERT OR IGNORE INTO categories (household_id, name, budget_amount) VALUES (?, ?, ?)",
                (DEFAULT_HOUSEHOLD_ID, name, budget),
            )
        for goal_id, name in DEFAULT_GOALS.items():
            db.execute(
                "INSERT OR IGNORE INTO goals (id, household_id, name) VALUES (?, ?, ?)",
                (goal_id, DEFAULT_HOUSEHOLD_ID, name),
            )


initialize_database()
