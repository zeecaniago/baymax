from __future__ import annotations

import unittest

from cli.app import BaymaxCli


class FakeBudgetApiClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []
        self.next_set_response: dict | None = None
        self.next_remove_response: dict | None = None

    def set_budget(self, category: str, amount: float) -> dict:
        self.calls.append(("set_budget", (category, amount), {}))
        if self.next_set_response is None:
            raise AssertionError("set_budget called without a queued response")
        response = self.next_set_response
        self.next_set_response = None
        return response

    def remove_budget(self, category: str) -> dict:
        self.calls.append(("remove_budget", (category,), {}))
        if self.next_remove_response is None:
            raise AssertionError("remove_budget called without a queued response")
        response = self.next_remove_response
        self.next_remove_response = None
        return response


class BaymaxCliBudgetTests(unittest.TestCase):
    def test_set_budget_creates_new_category_via_server(self) -> None:
        api = FakeBudgetApiClient()
        api.next_set_response = {
            "action": "created",
            "category": {"name": "subscriptions", "budget_amount": 30.0},
            "previous_budget": None,
        }
        cli = BaymaxCli(api_client=api)

        result = cli.handle("set subscriptions budget to $30")

        self.assertEqual(api.calls, [("set_budget", ("Subscriptions", 30.0), {})])
        self.assertEqual(result, ["✓ Created [Subscriptions] — budget $30/cycle"])
        self.assertEqual(cli.category_budgets["Subscriptions"], 30.0)

    def test_set_budget_sets_existing_budgetless_category_via_server(self) -> None:
        api = FakeBudgetApiClient()
        api.next_set_response = {
            "action": "set",
            "category": {"name": "eating out", "budget_amount": 150.0},
            "previous_budget": None,
        }
        cli = BaymaxCli(api_client=api)

        result = cli.handle("set eating out budget to $150")

        self.assertEqual(api.calls, [("set_budget", ("Eating Out", 150.0), {})])
        self.assertEqual(result, ["✓ [Eating Out] budget set to $150/cycle"])
        self.assertEqual(cli.category_budgets["Eating Out"], 150.0)

    def test_set_budget_updates_existing_budget_via_server(self) -> None:
        api = FakeBudgetApiClient()
        api.next_set_response = {
            "action": "updated",
            "category": {"name": "groceries", "budget_amount": 600.0},
            "previous_budget": 400.0,
        }
        cli = BaymaxCli(api_client=api)

        result = cli.handle("set groceries budget to $600")

        self.assertEqual(api.calls, [("set_budget", ("Groceries", 600.0), {})])
        self.assertEqual(result, ["✓ [Groceries] budget updated: $600/cycle (was $400/cycle)"])
        self.assertEqual(cli.category_budgets["Groceries"], 600.0)

    def test_remove_budget_handles_missing_category_from_server(self) -> None:
        api = FakeBudgetApiClient()
        api.next_remove_response = {"action": "missing", "category_name": "subscriptions"}
        cli = BaymaxCli(api_client=api)

        result = cli.handle("remove subscriptions budget")

        self.assertEqual(api.calls, [("remove_budget", ("Subscriptions",), {})])
        self.assertEqual(result, ["No category called [Subscriptions] yet."])

    def test_remove_budget_handles_already_removed_budget_from_server(self) -> None:
        api = FakeBudgetApiClient()
        api.next_remove_response = {
            "action": "already_removed",
            "category": {"name": "eating out", "budget_amount": None},
        }
        cli = BaymaxCli(api_client=api)

        result = cli.handle("remove eating out budget")

        self.assertEqual(api.calls, [("remove_budget", ("Eating Out",), {})])
        self.assertEqual(result, ["[Eating Out] doesn't have a budget."])
        self.assertIsNone(cli.category_budgets["Eating Out"])

    def test_remove_budget_removes_existing_budget_via_server(self) -> None:
        api = FakeBudgetApiClient()
        api.next_remove_response = {
            "action": "removed",
            "category": {"name": "groceries", "budget_amount": None},
            "previous_budget": 600.0,
        }
        cli = BaymaxCli(api_client=api)

        result = cli.handle("remove groceries budget")

        self.assertEqual(api.calls, [("remove_budget", ("Groceries",), {})])
        self.assertEqual(result, ["✓ [Groceries] — budget removed (was $600/cycle)"])
        self.assertIsNone(cli.category_budgets["Groceries"])

    def test_budget_suggestion_confirmation_uses_server_budget_write(self) -> None:
        api = FakeBudgetApiClient()
        api.next_set_response = {
            "action": "set",
            "category": {"name": "groceries", "budget_amount": 400.0},
            "previous_budget": 400.0,
        }
        cli = BaymaxCli(api_client=api)

        first = cli.handle("suggest a groceries budget")
        second = cli.handle("yes")

        self.assertEqual(
            first,
            ["Last 3 cycles: $380, $410, $395 — avg $395", "Suggest $400/cycle. Set it?"],
        )
        self.assertEqual(api.calls, [("set_budget", ("Groceries", 400.0), {})])
        self.assertEqual(second, ["✓ [Groceries] budget set to $400/cycle"])
        self.assertEqual(cli.category_budgets["Groceries"], 400.0)


if __name__ == "__main__":
    unittest.main()
