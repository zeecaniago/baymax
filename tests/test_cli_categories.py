from __future__ import annotations

import unittest

from cli.app import BaymaxCli


class FakeCategoryApiClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.report_response = {
            "cycle": "current",
            "cycle_label": "Jul 26–Aug 25",
            "items": [
                {
                    "name": "coffee",
                    "budget_amount": None,
                    "spent": 22.0,
                    "expense_count": 2,
                    "average_amount": 11.0,
                    "largest_expenses": [
                        {"description": "coffee beans", "amount": 12.0},
                        {"description": "coffee", "amount": 10.0},
                    ],
                }
            ],
        }

    def get_reports(self, *, report_type: str = "category", cycle: str = "current") -> dict:
        self.calls.append(("get_reports", {"report_type": report_type, "cycle": cycle}))
        return self.report_response


class BaymaxCliCategoryTests(unittest.TestCase):
    def test_report_category_reads_any_category_from_the_server(self) -> None:
        api = FakeCategoryApiClient()
        cli = BaymaxCli(api_client=api)

        result = cli.handle("report coffee")

        self.assertEqual(api.calls, [("get_reports", {"report_type": "category", "cycle": "current"})])
        self.assertEqual(
            result,
            [
                "Coffee — Jul 26–Aug 25",
                "  $22 spent · 2 expenses · avg $11",
                "  Largest: coffee beans $12, coffee $10",
            ],
        )

    def test_report_unknown_category_does_not_create_an_expense(self) -> None:
        api = FakeCategoryApiClient()
        cli = BaymaxCli(api_client=api)

        result = cli.handle("report education")

        self.assertEqual(api.calls, [("get_reports", {"report_type": "category", "cycle": "current"})])
        self.assertEqual(result, ["No category called [Education] yet."])


if __name__ == "__main__":
    unittest.main()
