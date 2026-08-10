from __future__ import annotations

from typing import Any

from .models import Expense


class CliPresentation:
    """Convert API payloads into the names and text used by the CLI."""

    def _expense_from_parse_response(self, parsed: dict[str, Any]) -> Expense:
        goals = parsed.get("goal_candidates") or []
        goal = parsed.get("goal") or (goals[0] if len(goals) == 1 else None)
        return Expense(
            amount=float(parsed["amount"]),
            description=parsed["description"],
            merchant=self._normalize_merchant_name(parsed.get("merchant")),
            category=self._normalize_api_category(parsed.get("category")),
            flags=list(parsed.get("flags") or []),
            budget_treatment=parsed.get("budget_treatment") or "included",
            goal=goal,
        )

    def _expense_from_created_response(self, payload: dict[str, Any]) -> Expense:
        goals = payload.get("goals") or []
        goal = goals[0] if goals else None
        return Expense(
            amount=float(payload["amount"]),
            description=payload["description"],
            merchant=self._normalize_merchant_name(payload.get("merchant")),
            category=self._normalize_api_category(payload.get("category")),
            flags=list(payload.get("flags") or []),
            budget_treatment=payload.get("budget_treatment") or "included",
            goal=goal,
            expense_id=payload.get("id"),
        )

    def _format_expense(self, expense: Expense) -> str:
        line = f"✓ ${expense.amount:.2f} — {expense.description}"
        return self._append_expense_details(line, expense)

    def _format_update(self, expense: Expense) -> str:
        line = f"✓ updated — ${expense.amount:.2f} — {expense.description}"
        return self._append_expense_details(line, expense)

    def _append_expense_details(self, line: str, expense: Expense) -> str:
        if expense.merchant:
            line += self._format_merchant(expense.merchant)
        if expense.category:
            line += self._format_category(expense.category)
        if expense.flags:
            line += "  " + " ".join(f"!{flag}" for flag in expense.flags)
        if expense.budget_treatment == "excluded":
            line += " · excluded from budget"
        if expense.goal:
            line += f"  → {expense.goal}"
        return line

    def _format_category(self, category: str | None) -> str:
        if not category:
            return ""
        return f"  #{category}"

    def _format_merchant(self, merchant: str) -> str:
        return f"  @{merchant}"

    def _format_currency(self, amount: float) -> str:
        return f"${amount:.2f}".rstrip("0").rstrip(".")

    def _normalize_api_category(self, category: str | None) -> str | None:
        if category is None:
            return None
        return self._normalize_category_name(category)

    def _normalize_category_name(self, raw_category: str) -> str:
        category = " ".join(raw_category.strip().split())
        aliases = {
            "groceries": "Groceries",
            "eating out": "Eating Out",
        }
        return aliases.get(category.lower(), category.title())

    def _normalize_merchant_name(self, merchant: str | None) -> str | None:
        if merchant is None:
            return None
        words = merchant.strip().split()
        if not words:
            return None
        return " ".join(
            word if any(char.isupper() for char in word) else word.capitalize()
            for word in words
        )

    def _find_named_item(
        self,
        items: list[dict[str, Any]] | None,
        name: str,
    ) -> dict[str, Any] | None:
        if not items:
            return None
        normalized_name = name.strip().lower()
        for item in items:
            item_name = item.get("name")
            if isinstance(item_name, str) and item_name.strip().lower() == normalized_name:
                return item
        return None

    def _expense_label(self, count: int) -> str:
        return "expense" if count == 1 else "expenses"
