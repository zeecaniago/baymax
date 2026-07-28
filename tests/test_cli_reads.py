from __future__ import annotations

import unittest

from cli.app import BaymaxCli


class FakeReadApiClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.report_response = {
            "cycle": "current",
            "cycle_label": "Jun 26–Jul 25",
            "items": [
                {
                    "name": "groceries",
                    "budget_amount": 400.0,
                    "spent": 403.0,
                    "remaining": -3.0,
                    "expense_count": 15,
                    "average_amount": 26.87,
                    "largest_expenses": [
                        {"description": "Costco", "amount": 91.0},
                        {"description": "Whole Foods", "amount": 64.0},
                        {"description": "Trader Joe's", "amount": 58.0},
                    ],
                }
            ],
        }
        self.budgets_response = {
            "cycle": "current",
            "cycle_label": "Jun 26–Jul 25",
            "categories": [
                {
                    "name": "eating out",
                    "budget_amount": None,
                    "spent": 105.0,
                    "remaining": None,
                }
            ],
        }
        self.goal_response = {
            "id": "goal-resilient-kid",
            "name": "Raise a strong, resilient kid",
            "cycle_contributions": 90.0,
            "cycle_expense_count": 2,
            "total_contributions": 890.0,
            "total_expense_count": 14,
            "since": "Mar 2026",
        }
        self.ask_responses = {
            "how much on groceries this cycle?": {
                "answer": "Groceries: $403.00 of $400.00 (101%) — 15 expenses"
            },
            "what did we put toward the resilient kid goal this cycle?": {
                "answer": "$90.00 across 2 expenses — karate class $50, books $40"
            },
        }

    def get_reports(self, *, report_type: str = "category", cycle: str = "current") -> dict:
        self.calls.append(("get_reports", {"report_type": report_type, "cycle": cycle}))
        return self.report_response

    def get_budgets(self) -> dict:
        self.calls.append(("get_budgets", {}))
        return self.budgets_response

    def get_goal_summary(self, goal_id: str, *, cycle: str = "current") -> dict:
        self.calls.append(("get_goal_summary", {"goal_id": goal_id, "cycle": cycle}))
        return self.goal_response

    def ask(self, question: str, *, cycle: str = "current") -> dict:
        self.calls.append(("ask", {"question": question, "cycle": cycle}))
        return self.ask_responses[question.lower()]


class BaymaxCliReadTests(unittest.TestCase):
    def test_report_groceries_reads_category_report_from_server(self) -> None:
        api = FakeReadApiClient()
        cli = BaymaxCli(api_client=api)

        result = cli.handle("report groceries")

        self.assertEqual(
            api.calls,
            [("get_reports", {"report_type": "category", "cycle": "current"})],
        )
        self.assertEqual(
            result,
            [
                "Groceries — Jun 26–Jul 25",
                "  $403 of $400 (101%) · 15 expenses · avg $26.87",
                "  Largest: Costco $91, Whole Foods $64, Trader Joe's $58",
            ],
        )

    def test_report_goal_reads_goal_summary_from_server(self) -> None:
        api = FakeReadApiClient()
        cli = BaymaxCli(api_client=api)

        result = cli.handle("report goal resilient kid")

        self.assertEqual(
            api.calls,
            [("get_goal_summary", {"goal_id": "goal-resilient-kid", "cycle": "current"})],
        )
        self.assertEqual(
            result,
            [
                "Raise a strong, resilient kid",
                "  This cycle: $90 across 2 expenses",
                "  All-time: $890 across 14 expenses (since Mar 2026)",
            ],
        )

    def test_eating_out_balance_reads_budget_from_server(self) -> None:
        api = FakeReadApiClient()
        cli = BaymaxCli(api_client=api)

        result = cli.handle("what's left in eating out?")

        self.assertEqual(api.calls, [("get_budgets", {})])
        self.assertEqual(result, ["Eating Out doesn't have a budget this cycle."])

    def test_groceries_question_reads_server_answer(self) -> None:
        api = FakeReadApiClient()
        cli = BaymaxCli(api_client=api)

        result = cli.handle("how much on groceries this cycle?")

        self.assertEqual(
            api.calls,
            [("ask", {"question": "how much on groceries this cycle?", "cycle": "current"})],
        )
        self.assertEqual(result, ["Groceries: $403.00 of $400.00 (101%) — 15 expenses"])

    def test_goal_question_reads_server_answer(self) -> None:
        api = FakeReadApiClient()
        cli = BaymaxCli(api_client=api)

        result = cli.handle("what did we put toward the resilient kid goal this cycle?")

        self.assertEqual(
            api.calls,
            [
                (
                    "ask",
                    {
                        "question": "what did we put toward the resilient kid goal this cycle?",
                        "cycle": "current",
                    },
                )
            ],
        )
        self.assertEqual(result, ["$90.00 across 2 expenses — karate class $50, books $40"])


if __name__ == "__main__":
    unittest.main()
