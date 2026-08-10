from __future__ import annotations

from .api import BaymaxApiError


class BudgetCommands:
    """Budget recommendation, update, and removal workflows."""

    def _resolve_budget_confirmation(self, raw: str) -> list[str]:
        self.pending_action = None
        category = self.pending_budget_category
        amount = self.pending_budget_amount
        self.pending_budget_category = None
        self.pending_budget_amount = None
        if raw.strip().lower() in {"y", "yes"}:
            if category is None or amount is None:
                return ["Nothing to update."]
            return self._set_category_budget(category, amount)
        return ["No change."]

    def _set_category_budget(self, category: str, amount: float) -> list[str]:
        try:
            response = self.api.set_budget(category, amount)
        except BaymaxApiError as exc:
            print(exc)
            return []

        action = response.get("action")
        payload = response.get("category") or {}
        category_name = self._normalize_api_category(payload.get("name")) or category
        budget_amount = float(payload.get("budget_amount") or amount)
        previous_budget = response.get("previous_budget")

        self.category_budgets[category_name] = budget_amount

        if action == "created":
            return [f"✓ Created [{category_name}] — budget {self._format_currency(budget_amount)}/cycle"]
        if action == "set":
            return [f"✓ [{category_name}] budget set to {self._format_currency(budget_amount)}/cycle"]
        if action == "updated":
            if previous_budget is None:
                print("Baymax API returned an invalid budget update payload.")
                return []
            return [
                (
                    f"✓ [{category_name}] budget updated: "
                    f"{self._format_currency(budget_amount)}/cycle"
                    f" (was {self._format_currency(float(previous_budget))}/cycle)"
                )
            ]

        print("Baymax API returned an invalid budget response.")
        return []

    def _remove_category_budget(self, category: str) -> list[str]:
        try:
            response = self.api.remove_budget(category)
        except BaymaxApiError as exc:
            print(exc)
            return []

        action = response.get("action")
        payload = response.get("category") or {}
        category_name = self._normalize_api_category(payload.get("name")) or category
        previous_budget = response.get("previous_budget")

        if action == "missing":
            return [f"No category called [{category}] yet."]
        if action == "already_removed":
            self.category_budgets[category_name] = None
            return [f"[{category_name}] doesn't have a budget."]
        if action == "removed":
            if previous_budget is None:
                print("Baymax API returned an invalid budget removal payload.")
                return []
            self.category_budgets[category_name] = None
            return [
                (
                    f"✓ [{category_name}] — budget removed"
                    f" (was {self._format_currency(float(previous_budget))}/cycle)"
                )
            ]

        print("Baymax API returned an invalid budget response.")
        return []

    def _budget_for(self, category: str, default: float | None = None) -> float | None:
        return self.category_budgets.get(category, default)
