from __future__ import annotations

import unittest

from fastapi import HTTPException

from cli.app import BaymaxCli, Expense
from server import app as baymax_api
from server.parsing import expense_suggestions


class DirectExpenseApiClient:
    """Exercise the CLI against the same request models used by the API routes."""

    def parse_expense(self, raw_text: str) -> dict:
        return baymax_api.parse_expense(
            baymax_api.ParseExpenseRequest(raw_text=raw_text)
        ).model_dump()

    def create_expense(self, **payload: object) -> dict:
        return baymax_api.create_expense(baymax_api.CreateExpenseRequest(**payload))

    def update_expense(self, expense_id: str, **payload: object) -> dict:
        return baymax_api.update_expense(
            expense_id,
            baymax_api.UpdateExpenseRequest(**payload),
        )


class ExpenseDimensionTests(unittest.TestCase):
    def setUp(self) -> None:
        baymax_api.reset_in_memory_store()

    def tearDown(self) -> None:
        baymax_api.reset_in_memory_store()

    def test_named_fields_are_optional_case_insensitive_and_order_independent(self) -> None:
        cases = [
            ("$45 coffee", ("coffee", None, None, None)),
            ("$45 coffee, m: Fresh Street", ("coffee", "Fresh Street", None, None)),
            ("$45 coffee, c: Groceries", ("coffee", None, "Groceries", None)),
            ("$45 coffee, g: Healthy Lifestyle", ("coffee", None, None, "Healthy Lifestyle")),
            (
                "$45 coffee, m: Fresh Street, c: Groceries, g: Healthy Lifestyle",
                ("coffee", "Fresh Street", "Groceries", "Healthy Lifestyle"),
            ),
            (
                "$45 coffee, goal: Healthy Lifestyle, merchant: Fresh Street",
                ("coffee", "Fresh Street", None, "Healthy Lifestyle"),
            ),
            ("$45 coffee, M: Fresh Street, C: Groceries", ("coffee", "Fresh Street", "Groceries", None)),
        ]

        for raw_text, expected in cases:
            with self.subTest(raw_text=raw_text):
                draft = baymax_api.parse_expense(baymax_api.ParseExpenseRequest(raw_text=raw_text))
                self.assertEqual(
                    (draft.description, draft.merchant, draft.category, draft.goal),
                    expected,
                )

    def test_multiword_values_and_explicit_fields_override_inference(self) -> None:
        detailed = baymax_api.parse_expense(
            baymax_api.ParseExpenseRequest(
                raw_text="$50 karate class, c: Kids, g: Raise a Strong, Resilient Kid"
            )
        )
        override = baymax_api.parse_expense(
            baymax_api.ParseExpenseRequest(
                raw_text="$45 groceries, g: Healthy Lifestyle, c: Dining Out, m: Fresh Street"
            )
        )

        self.assertEqual(detailed.description, "karate class")
        self.assertEqual(detailed.category, "Kids")
        self.assertEqual(detailed.goal, "Raise a strong, resilient kid")
        self.assertEqual(detailed.explicit_fields, ["category", "goal"])
        self.assertEqual(override.category, "Dining Out")
        self.assertEqual(override.merchant, "Fresh Street")
        self.assertEqual(override.goal, "Healthy Lifestyle")
        self.assertEqual(override.field_sources, {
            "merchant": "explicit",
            "category": "explicit",
            "goal": "explicit",
        })

    def test_modifiers_and_natural_goal_inference_remain_backward_compatible(self) -> None:
        one_off = baymax_api.parse_expense(
            baymax_api.ParseExpenseRequest(raw_text="$12 coffee, one-off")
        )
        natural_goal = baymax_api.parse_expense(
            baymax_api.ParseExpenseRequest(raw_text="$50 karate class, kid goal")
        )

        self.assertEqual((one_off.description, one_off.flags, one_off.budget_treatment), ("coffee", ["one-off"], "excluded"))
        self.assertEqual(natural_goal.description, "karate class")
        self.assertEqual(natural_goal.category, "kids")
        self.assertEqual(natural_goal.goal, "Raise a strong, resilient kid")

    def test_ambiguous_natural_goals_are_not_silently_applied(self) -> None:
        draft = baymax_api.parse_expense(
            baymax_api.ParseExpenseRequest(raw_text="$40 books, learning goal")
        )

        self.assertIsNone(draft.goal)
        self.assertEqual(
            draft.goal_candidates,
            ["Raise a strong, resilient kid", "Get promoted this year"],
        )

    def test_cli_asks_before_saving_an_ambiguous_goal(self) -> None:
        cli = BaymaxCli(api_client=DirectExpenseApiClient())

        prompt = cli.handle("$40 books, learning goal")
        saved = cli.handle("2")

        self.assertEqual(
            prompt,
            [
                "Which goal?",
                "  1. Raise a strong, resilient kid",
                "  2. Get promoted this year",
                "  0. Don't link to a goal",
            ],
        )
        self.assertEqual(
            saved,
            ["✓ $40.00 — books  #Kids  → Get promoted this year"],
        )

    def test_parser_requires_amount_and_description(self) -> None:
        with self.assertRaises(HTTPException):
            baymax_api.parse_expense(baymax_api.ParseExpenseRequest(raw_text="coffee"))
        with self.assertRaises(HTTPException):
            baymax_api.parse_expense(baymax_api.ParseExpenseRequest(raw_text="$45"))

    def test_autocomplete_values_include_known_categories_goals_and_prior_merchants(self) -> None:
        baymax_api.create_expense(
            baymax_api.CreateExpenseRequest(
                amount=45.0,
                description="coffee",
                merchant="Fresh Street",
                category="groceries",
                goals=["Healthy Lifestyle"],
            )
        )

        self.assertEqual(expense_suggestions("merchant", "fre", "coffee"), ["Fresh Street"])
        self.assertIn("Groceries", expense_suggestions("category", "groc"))
        self.assertEqual(expense_suggestions("goal", "heal"), ["Healthy Lifestyle"])
        self.assertEqual(
            baymax_api.get_expense_suggestions("g", "heal", "coffee")["items"],
            ["Healthy Lifestyle"],
        )

    def test_confirmation_distinguishes_the_expense_dimensions(self) -> None:
        formatted = BaymaxCli()._format_expense(
            Expense(
                amount=45.0,
                description="coffee",
                merchant="Fresh Street",
                category="Groceries",
                goal="Healthy Lifestyle",
            )
        )
        self.assertEqual(
            formatted,
            "✓ $45.00 — coffee  @Fresh Street  #Groceries  → Healthy Lifestyle",
        )

    def test_cli_saves_structured_fields_and_corrects_the_last_expense(self) -> None:
        cli = BaymaxCli(api_client=DirectExpenseApiClient())

        created = cli.handle(
            "$45 coffee, m: Fresh Street, c: Groceries, g: Healthy Lifestyle"
        )
        corrected = cli.handle("correct last expense, merchant: Corner Cafe, c: Dining Out")

        self.assertEqual(
            created,
            ["✓ $45.00 — coffee  @Fresh Street  #Groceries  → Healthy Lifestyle"],
        )
        self.assertEqual(
            corrected,
            ["✓ updated — $45.00 — coffee  @Corner Cafe  #Dining Out  → Healthy Lifestyle"],
        )


if __name__ == "__main__":
    unittest.main()
