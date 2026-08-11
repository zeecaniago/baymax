from __future__ import annotations

import sqlite3
import unittest
from datetime import timedelta

from server import app as baymax_api
from server.db import database_path, initialize_database
from server.repositories import categories, expenses, goals


class PersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        baymax_api.reset_database()

    def tearDown(self) -> None:
        baymax_api.reset_database()

    def _date(self):
        start, _ = baymax_api._cycle_bounds("current")
        return start + timedelta(days=1)

    def test_expense_correction_and_relationships_survive_reinitialization(self) -> None:
        created = baymax_api.create_expense(
            baymax_api.CreateExpenseRequest(
                amount=45,
                description="Gift basket",
                category="Groceries",
                flags=["one-off"],
                goals=["Healthy Lifestyle"],
                date=self._date(),
            )
        )
        baymax_api.update_expense(created["id"], baymax_api.UpdateExpenseRequest(amount=54))

        initialize_database()
        persisted = expenses.get(created["id"])
        summary = baymax_api.get_goal_summary("goal-healthy-lifestyle", "current")
        groceries = next(
            item
            for item in baymax_api.get_budgets("current")["categories"]
            if item["name"] == "groceries"
        )

        self.assertEqual(persisted["amount"], 54)
        self.assertEqual(persisted["flags"], ["one-off"])
        self.assertEqual(persisted["goals"], ["Healthy Lifestyle"])
        self.assertEqual(summary["cycle_goal_related_spending"], 54)
        self.assertEqual(groceries["total_spent"], 54)
        self.assertEqual(groceries["spent"], 0)

    def test_budget_and_seed_changes_survive_idempotent_initialization(self) -> None:
        baymax_api.set_budget("groceries", baymax_api.SetBudgetRequest(amount=600))
        initialize_database()
        initialize_database()

        self.assertEqual(categories.get("groceries")["budget_amount"], 600)
        with sqlite3.connect(database_path()) as db:
            category_count = db.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
            goal_count = db.execute("SELECT COUNT(*) FROM goals").fetchone()[0]
        self.assertEqual(category_count, 3)
        self.assertEqual(goal_count, 6)
        self.assertEqual(len(goals.list_all()), 6)


if __name__ == "__main__":
    unittest.main()
