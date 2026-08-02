from __future__ import annotations

import unittest

from cli.app import BaymaxCli
from server import app as baymax_api


class MerchantLoggingTests(unittest.TestCase):
    def setUp(self) -> None:
        baymax_api.reset_in_memory_store()

    def tearDown(self) -> None:
        baymax_api.reset_in_memory_store()

    def test_parser_splits_a_trailing_multi_word_merchant_from_a_category(self) -> None:
        fresh_street = baymax_api.parse_expense(
            baymax_api.ParseExpenseRequest(raw_text="$45 groceries fresh street")
        )
        amazon = baymax_api.parse_expense(
            baymax_api.ParseExpenseRequest(raw_text="$55 groceries amazon")
        )
        starbuck = baymax_api.parse_expense(
            baymax_api.ParseExpenseRequest(raw_text="$15 coffee starbuck, one-off")
        )

        self.assertEqual(
            (fresh_street.description, fresh_street.merchant, fresh_street.category),
            ("groceries", "fresh street", "groceries"),
        )
        self.assertEqual(
            (amazon.description, amazon.merchant, amazon.category),
            ("groceries", "amazon", "groceries"),
        )
        self.assertEqual(
            (starbuck.description, starbuck.merchant, starbuck.category, starbuck.flags),
            ("coffee", "starbuck", "coffee", ["one-off"]),
        )

    def test_merchant_is_saved_and_rendered_before_the_category(self) -> None:
        draft = baymax_api.parse_expense(
            baymax_api.ParseExpenseRequest(raw_text="$15 coffee starbuck, one-off")
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

        self.assertEqual(saved["merchant"], "starbuck")
        self.assertEqual(
            BaymaxCli()._format_expense(expense),
            "✓ $15.00 — coffee  [Starbuck] [Coffee]  #one-off",
        )

    def test_unrecognized_multi_word_descriptions_are_not_split(self) -> None:
        draft = baymax_api.parse_expense(
            baymax_api.ParseExpenseRequest(raw_text="$22 parking downtown")
        )

        self.assertEqual((draft.description, draft.merchant, draft.category), ("parking downtown", None, None))


if __name__ == "__main__":
    unittest.main()
