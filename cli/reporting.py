from __future__ import annotations

from typing import Any

from .api import BaymaxApiError

GOAL_IDS = {
    "resilient kid": "goal-resilient-kid",
    "raise a strong, resilient kid": "goal-resilient-kid",
    "healthy lifestyle": "goal-healthy-lifestyle",
    "get promoted this year": "goal-promoted",
    "save for family trip": "goal-family-trip",
    "emergency fund": "goal-emergency-fund",
    "japan trip": "goal-japan-trip",
}


class ReportingCommands:
    """Read-only reports and natural-language questions."""

    def _report_category(self, category_name: str) -> list[str]:
        try:
            report = self.api.get_reports(report_type="category")
        except BaymaxApiError as exc:
            print(exc)
            return []

        category = self._find_named_item(report.get("items"), category_name)
        if category is None:
            return [f"No category called [{self._normalize_category_name(category_name)}] yet."]
        return self._format_category_report(report, category)

    def _report_goal_summary(self, goal_alias: str) -> list[str]:
        normalized_alias = " ".join(goal_alias.strip().lower().split())
        goal_id = GOAL_IDS.get(normalized_alias)
        if goal_id is None:
            return [f"No goal called {goal_alias!r}."]

        try:
            summary = self.api.get_goal_summary(goal_id)
        except BaymaxApiError as exc:
            print(exc)
            return []

        cycle_amount = float(summary.get("cycle_goal_related_spending") or 0.0)
        cycle_count = int(summary.get("cycle_expense_count") or 0)
        entries = summary.get("cycle_entries") or []
        lines = [
            f"{summary['name']} — this cycle",
            f"  {self._format_currency(cycle_amount)} across {cycle_count} {self._expense_label(cycle_count)}",
        ]
        lines.extend(
            f"  {entry['description']}  {self._format_currency(float(entry['amount']))}"
            for entry in entries
        )
        return lines

    def _eating_out_balance(self) -> list[str]:
        try:
            budgets = self.api.get_budgets()
        except BaymaxApiError as exc:
            print(exc)
            return []

        category = self._find_named_item(budgets.get("categories"), "eating out")
        if category is None:
            print("Baymax API didn't return an Eating Out budget.")
            return []

        budget = category.get("budget_amount")
        if budget is None:
            return ["Eating Out doesn't have a budget this cycle."]

        remaining = category.get("remaining")
        if remaining is None:
            remaining = float(budget) - float(category.get("spent") or 0.0)
        return [f"{self._format_currency(float(remaining))} left of {self._format_currency(float(budget))}"]

    def _ask_question(self, question: str) -> list[str]:
        try:
            response = self.api.ask(question)
        except BaymaxApiError as exc:
            print(exc)
            return []

        answer = response.get("answer")
        if not isinstance(answer, str):
            print("Baymax API returned an invalid answer payload.")
            return []
        return [answer]

    def _format_category_report(
        self,
        report: dict[str, Any],
        category: dict[str, Any],
    ) -> list[str]:
        category_name = self._normalize_category_name(category["name"])
        cycle_label = report.get("cycle_label") or report.get("cycle") or "current"
        spent = float(category.get("spent") or 0.0)
        budget = category.get("budget_amount")
        expense_count = int(category.get("expense_count") or 0)
        average_amount = float(category.get("average_amount") or 0.0)
        excluded_spent = float(category.get("excluded_spent") or 0.0)

        if budget is None:
            summary_line = (
                f"  {self._format_currency(spent)} spent · "
                f"{expense_count} {self._expense_label(expense_count)} · "
                f"avg {self._format_currency(average_amount)}"
            )
        else:
            percent = round((spent / float(budget)) * 100) if budget else 0
            summary_line = (
                f"  {self._format_currency(spent)} of {self._format_currency(float(budget))} "
                f"({percent}%) · {expense_count} {self._expense_label(expense_count)} · "
                f"avg {self._format_currency(average_amount)}"
            )

        if excluded_spent:
            summary_line += f" · {self._format_currency(excluded_spent)} excluded"

        lines = [f"{category_name} — {cycle_label}", summary_line]
        largest_expenses = category.get("largest_expenses") or []
        if largest_expenses:
            formatted_largest = ", ".join(
                f"{entry['description']} {self._format_currency(float(entry['amount']))}"
                for entry in largest_expenses
            )
            lines.append(f"  Largest: {formatted_largest}")
        return lines
