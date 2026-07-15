from __future__ import annotations

import unittest

from cli.app import BaymaxCli, Expense


class FakeApiClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.expenses: dict[str, dict] = {}

    def update_expense(self, expense_id: str, **kwargs) -> dict:
        self.calls.append((expense_id, kwargs))
        payload = dict(self.expenses[expense_id])
        payload.update({key: value for key, value in kwargs.items() if value is not None})
        self.expenses[expense_id] = payload
        return payload


class BaymaxCliCorrectionTests(unittest.TestCase):
    def test_amount_correction_patches_last_saved_expense(self) -> None:
        api = FakeApiClient()
        api.expenses["exp-1234"] = {
            "id": "exp-1234",
            "amount": 45.0,
            "description": "groceries",
            "category": "groceries",
            "flags": [],
            "goals": [],
            "notes": None,
        }
        cli = BaymaxCli(api_client=api)
        cli.last_expense = Expense(
            amount=45.0,
            description="groceries",
            category="Groceries",
            expense_id="exp-1234",
        )

        result = cli.handle("oops, 54 not 45")

        self.assertEqual(
            api.calls,
            [("exp-1234", {"amount": 54.0, "goals": None})],
        )
        self.assertEqual(result, ["✓ updated — $54.00 — groceries  [Groceries]"])
        self.assertEqual(cli.last_expense.amount, 54.0)
        self.assertEqual(cli.last_expense.expense_id, "exp-1234")

    def test_goal_correction_patches_last_saved_expense(self) -> None:
        api = FakeApiClient()
        api.expenses["exp-9999"] = {
            "id": "exp-9999",
            "amount": 18.0,
            "description": "target",
            "category": "shopping",
            "flags": [],
            "goals": [],
            "notes": None,
        }
        cli = BaymaxCli(api_client=api)
        cli.last_expense = Expense(
            amount=18.0,
            description="target",
            category="Shopping",
            expense_id="exp-9999",
        )

        result = cli.handle("no, that one's for the emergency fund goal")

        self.assertEqual(
            api.calls,
            [("exp-9999", {"amount": None, "goals": ["Emergency Fund"]})],
        )
        self.assertEqual(result, ["✓ updated — $18.00 — target  [Shopping]  → Emergency Fund"])
        self.assertEqual(cli.last_expense.goal, "Emergency Fund")
        self.assertEqual(cli.last_expense.expense_id, "exp-9999")


if __name__ == "__main__":
    unittest.main()
