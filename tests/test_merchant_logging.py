from __future__ import annotations

import unittest

from cli.app import BaymaxCli
from server import app as baymax_api


class MerchantLoggingTests(unittest.TestCase):
    def setUp(self) -> None:
        baymax_api.reset_in_memory_store()

    def tearDown(self) -> None:
        baymax_api.reset_in_memory_store()

    def test_parser_supports_progressive_purchase_detail(self) -> None:
        beginner = baymax_api.parse_expense(
            baymax_api.ParseExpenseRequest(raw_text="$45 groceries")
        )
        building_habit = baymax_api.parse_expense(
            baymax_api.ParseExpenseRequest(raw_text="$45 coffee fresh street")
        )
        expert = baymax_api.parse_expense(
            baymax_api.ParseExpenseRequest(raw_text="$45 coffee fresh street groceries")
        )
        fresh_street = baymax_api.parse_expense(
            baymax_api.ParseExpenseRequest(raw_text="$45 groceries fresh street")
        )

        self.assertEqual((beginner.description, beginner.merchant, beginner.category), ("groceries", None, "groceries"))
        self.assertEqual(
            (building_habit.description, building_habit.merchant, building_habit.category),
            ("coffee", "fresh street", None),
        )
        self.assertEqual(
            (expert.description, expert.merchant, expert.category),
            ("coffee", "fresh street", "groceries"),
        )
        self.assertEqual(
            (fresh_street.description, fresh_street.merchant, fresh_street.category),
            ("groceries", "fresh street", "groceries"),
        )

    def test_annotations_allow_an_unambiguous_merchant_and_category(self) -> None:
        draft = baymax_api.parse_expense(
            baymax_api.ParseExpenseRequest(raw_text="$45 coffee @fresh street #groceries")
        )
        self.assertEqual(
            (draft.description, draft.merchant, draft.category),
            ("coffee", "fresh street", "groceries"),
        )

    def test_merchant_is_saved_and_rendered_without_forcing_a_category(self) -> None:
        draft = baymax_api.parse_expense(
            baymax_api.ParseExpenseRequest(raw_text="$15 coffee starbuck")
        )
        saved = baymax_api.create_expense(
            baymax_api.CreateExpenseRequest(
                amount=draft.amount,
                description=draft.description,
                merchant=draft.merchant,
                category=draft.category,
                flags=draft.flags,
            )
        )

        expense = BaymaxCli()._expense_from_created_response(saved)

        self.assertEqual((saved["description"], saved["merchant"], saved["category"]), ("coffee", "starbuck", None))
        self.assertEqual(
            BaymaxCli()._format_expense(expense),
            "✓ $15.00 — coffee  [Starbuck]",
        )

    def test_one_off_is_rendered_as_excluded_from_budget(self) -> None:
        draft = baymax_api.parse_expense(
            baymax_api.ParseExpenseRequest(
                raw_text="$15 coffee @fresh street #groceries, one-off"
            )
        )
        saved = baymax_api.create_expense(
            baymax_api.CreateExpenseRequest(
                amount=draft.amount,
                description=draft.description,
                merchant=draft.merchant,
                category=draft.category,
                flags=draft.flags,
                budget_treatment=draft.budget_treatment,
            )
        )

        expense = BaymaxCli()._expense_from_created_response(saved)

        self.assertEqual(draft.budget_treatment, "excluded")
        self.assertEqual(saved["budget_treatment"], "excluded")
        self.assertEqual(
            BaymaxCli()._format_expense(expense),
            "✓ $15.00 — coffee  [Fresh Street] [Groceries]  #one-off · excluded from budget",
        )

    def test_unrecognized_multi_word_descriptions_are_not_split(self) -> None:
        draft = baymax_api.parse_expense(
            baymax_api.ParseExpenseRequest(raw_text="$22 parking downtown")
        )

        self.assertEqual((draft.description, draft.merchant, draft.category), ("parking downtown", None, None))


if __name__ == "__main__":
    unittest.main()
