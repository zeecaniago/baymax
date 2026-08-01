from __future__ import annotations

import unittest
from datetime import timedelta

from server import app as baymax_api


class ServerCalculationTests(unittest.TestCase):
    def setUp(self) -> None:
        baymax_api.reset_in_memory_store()

    def tearDown(self) -> None:
        baymax_api.reset_in_memory_store()

    def _current_cycle_date(self):
        start, _ = baymax_api._cycle_bounds("current")
        return start + timedelta(days=1)

    def _category(self, report: dict, name: str) -> dict:
        items = report.get("items") or report["categories"]
        return next(item for item in items if item["name"] == name)

    def test_category_report_and_budget_change_after_create_and_correction(self) -> None:
        expense = baymax_api.create_expense(
            baymax_api.CreateExpenseRequest(
                amount=45.0,
                description="Corner market",
                category="Groceries",
                date=self._current_cycle_date(),
            )
        )
        baymax_api.create_expense(
            baymax_api.CreateExpenseRequest(
                amount=20.0,
                description="Produce stand",
                category="groceries",
                date=self._current_cycle_date(),
            )
        )

        before_correction = self._category(
            baymax_api.get_reports("category", "current"), "groceries"
        )
        self.assertEqual(before_correction["spent"], 65.0)
        self.assertEqual(before_correction["remaining"], 335.0)
        self.assertEqual(before_correction["expense_count"], 2)
        self.assertEqual(before_correction["average_amount"], 32.5)
        self.assertEqual(
            before_correction["largest_expenses"],
            [
                {"description": "Corner market", "amount": 45.0},
                {"description": "Produce stand", "amount": 20.0},
            ],
        )

        baymax_api.update_expense(
            expense["id"], baymax_api.UpdateExpenseRequest(amount=54.0)
        )

        after_correction = self._category(
            baymax_api.get_budgets("current"), "groceries"
        )
        self.assertEqual(after_correction["spent"], 74.0)
        self.assertEqual(after_correction["remaining"], 326.0)
        self.assertEqual(after_correction["expense_count"], 2)

    def test_goal_summary_and_question_are_derived_from_linked_expenses(self) -> None:
        baymax_api.create_expense(
            baymax_api.CreateExpenseRequest(
                amount=50.0,
                description="Karate class",
                category="kids",
                goals=["Raise a strong, resilient kid"],
                date=self._current_cycle_date(),
            )
        )
        baymax_api.create_expense(
            baymax_api.CreateExpenseRequest(
                amount=40.0,
                description="Books",
                category="kids",
                goals=["goal-resilient-kid"],
                date=self._current_cycle_date(),
            )
        )

        summary = baymax_api.get_goal_summary("goal-resilient-kid", "current")

        self.assertEqual(summary["cycle_contributions"], 90.0)
        self.assertEqual(summary["total_contributions"], 90.0)
        self.assertEqual(summary["cycle_expense_count"], 2)
        self.assertEqual(summary["total_expense_count"], 2)
        self.assertEqual(summary["since"], self._current_cycle_date().strftime("%b %Y"))

        answer = baymax_api.ask_question(
            baymax_api.AskRequest(
                question="what did we put toward the resilient kid goal this cycle?"
            )
        )
        self.assertEqual(answer.answer, "$90.00 across 2 expenses — Karate class $50, Books $40")

    def test_backdated_expenses_are_excluded_from_the_current_cycle(self) -> None:
        cycle_start, _ = baymax_api._cycle_bounds("current")
        baymax_api.create_expense(
            baymax_api.CreateExpenseRequest(
                amount=30.0,
                description="Current groceries",
                category="groceries",
                date=cycle_start + timedelta(days=1),
            )
        )
        baymax_api.create_expense(
            baymax_api.CreateExpenseRequest(
                amount=200.0,
                description="Previous-cycle groceries",
                category="groceries",
                date=cycle_start - timedelta(days=1),
            )
        )

        current = self._category(baymax_api.get_budgets("current"), "groceries")
        previous = self._category(
            baymax_api.get_reports("category", (cycle_start - timedelta(days=1)).isoformat()),
            "groceries",
        )

        self.assertEqual(current["spent"], 30.0)
        self.assertEqual(current["expense_count"], 1)
        self.assertEqual(previous["spent"], 200.0)
        self.assertEqual(previous["expense_count"], 1)

    def test_single_word_descriptions_create_reusable_categories(self) -> None:
        coffee_draft = baymax_api.parse_expense(
            baymax_api.ParseExpenseRequest(raw_text="$12 coffee, one-off")
        )
        self.assertEqual(coffee_draft.category, "coffee")

        baymax_api.create_expense(
            baymax_api.CreateExpenseRequest(
                amount=12.0,
                description=coffee_draft.description,
                category=coffee_draft.category,
                date=self._current_cycle_date(),
            )
        )

        coffee_follow_up = baymax_api.parse_expense(
            baymax_api.ParseExpenseRequest(raw_text="$10 coffee beans")
        )
        education_draft = baymax_api.parse_expense(
            baymax_api.ParseExpenseRequest(raw_text="$100 education")
        )
        parking_draft = baymax_api.parse_expense(
            baymax_api.ParseExpenseRequest(raw_text="$22 parking downtown")
        )

        self.assertEqual(coffee_follow_up.category, "coffee")
        self.assertEqual(education_draft.category, "education")
        self.assertIsNone(parking_draft.category)


if __name__ == "__main__":
    unittest.main()
