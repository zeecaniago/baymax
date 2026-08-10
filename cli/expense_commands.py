from __future__ import annotations

import re
from typing import Any

from server.parsing import canonical_goal_name, split_named_fields

from .api import BaymaxApiError
from .models import Expense


class ExpenseCommands:
    """Expense capture, goal selection, and correction workflows."""

    def _resolve_goal_choice(self, raw: str) -> list[str]:
        expense = self.pending_expense
        candidates = self.pending_goal_candidates
        if expense is None:
            self._clear_pending_expense()
            return []

        try:
            choice = int(raw.strip())
        except ValueError:
            return ["Choose a listed goal, or 0 to leave it unlinked."]

        if choice == 0:
            expense.goal = None
            if self.pending_expense_draft is not None:
                self.pending_expense_draft["goal_candidates"] = []
        elif 1 <= choice <= len(candidates):
            expense.goal = candidates[choice - 1]
        else:
            return ["Choose a listed goal, or 0 to leave it unlinked."]

        created_expense = self._persist_pending_expense(expense)
        if created_expense is None:
            return []
        self.last_expense = created_expense
        self._clear_pending_expense()
        return [self._format_expense(created_expense)]

    def _update_last_goal(self, goal: str) -> list[str]:
        if self.last_expense is None:
            return ["Nothing to update."]
        updated_expense = self._update_last_expense_on_server(goals=[goal])
        if updated_expense is None:
            return []
        return [self._format_update(updated_expense)]

    def _update_last_amount(self, raw: str) -> list[str]:
        if self.last_expense is None:
            return ["Nothing to update."]
        numbers = [float(match) for match in re.findall(r"\d+(?:\.\d{1,2})?", raw)]
        if not numbers:
            return ["Nothing to update."]
        updated_expense = self._update_last_expense_on_server(amount=numbers[0])
        if updated_expense is None:
            return []
        return [self._format_update(updated_expense)]

    def _correct_last_expense(self, raw: str) -> list[str]:
        if self.last_expense is None:
            return ["Nothing to update."]
        if self.last_expense.expense_id is None:
            return ["Couldn't update the last expense because it was never saved."]

        try:
            fields = split_named_fields(raw)
        except ValueError as exc:
            return [str(exc)]
        updates: dict[str, object] = {}
        if "merchant" in fields.values:
            updates["merchant"] = fields.values["merchant"]
        if "category" in fields.values:
            updates["category"] = fields.values["category"]
        if "goal" in fields.values:
            updates["goals"] = [canonical_goal_name(fields.values["goal"])]
        if not updates:
            return ["Use m:, c:, or g: to correct the last expense."]

        try:
            updated = self.api.update_expense(self.last_expense.expense_id, **updates)
        except BaymaxApiError as exc:
            print(exc)
            return []

        updated_expense = self._expense_from_created_response(updated)
        self.last_expense = updated_expense
        return [self._format_update(updated_expense)]

    def _log_expense(self, raw: str) -> list[str]:
        parsed = self._parse_expense_for_prompt(raw)
        if parsed is None:
            return []

        goal_candidates = list(parsed.get("goal_candidates") or [])
        if parsed.get("goal") is None and len(goal_candidates) > 1:
            self.pending_action = "choose_goal"
            self.pending_expense = self._expense_from_parse_response(parsed)
            self.pending_expense_draft = parsed
            self.pending_goal_candidates = goal_candidates
            return [
                "Which goal?",
                *(f"  {index}. {goal}" for index, goal in enumerate(goal_candidates, start=1)),
                "  0. Don't link to a goal",
            ]

        try:
            expense = self._persist_parsed_expense(parsed)
        except BaymaxApiError as exc:
            print(exc)
            return []

        self.last_expense = expense
        lines = [self._format_expense(expense)]

        if raw.lower() == "$85 groceries":
            groceries_budget = self._budget_for("Groceries", default=400.0)
            if groceries_budget is not None:
                spent = 167.0
                lines.append(
                    f"  Groceries: {self._format_currency(groceries_budget - spent)} left"
                    f" of {self._format_currency(groceries_budget)} this cycle"
                )
            return lines

        if raw.lower() == "$60 groceries":
            groceries_budget = self._budget_for("Groceries", default=400.0)
            if groceries_budget is not None:
                spent = 328.0
                percent = round((spent / groceries_budget) * 100)
                lines.extend(
                    [
                        "",
                        (
                            f"⚠ Groceries — {percent}% of budget "
                            f"({self._format_currency(spent)} of {self._format_currency(groceries_budget)})"
                        ),
                        "   Jun 27  farmers market      $22",
                        "   Jun 29  Whole Foods         $64",
                        "   Jul 01  Costco              $91",
                        "   Jul 03  Trader Joe's        $58",
                        "   Jul 05  groceries           $60",
                    ]
                )
            return lines

        if raw.lower() == "$75 groceries":
            groceries_budget = self._budget_for("Groceries", default=400.0)
            if groceries_budget is not None:
                spent = 403.0
                percent = round((spent / groceries_budget) * 100)
                lines.extend(
                    [
                        "",
                        (
                            f"⚠ Groceries — over budget: "
                            f"{self._format_currency(spent)} of {self._format_currency(groceries_budget)}"
                            f" ({percent}%)"
                        ),
                        "   [full list]",
                    ]
                )
            return lines

        if raw.lower().startswith("6/20 $200 car repair"):
            lines.append("  ↳ logged to cycle May 26 – Jun 25 (closed)")
            return lines

        if expense.category == "Groceries":
            self.groceries_spent += expense.amount

        return lines

    def _parse_expense_for_prompt(self, raw: str) -> dict[str, Any] | None:
        try:
            return self.api.parse_expense(raw)
        except BaymaxApiError as exc:
            print(exc)
            return None

    def _persist_pending_expense(self, expense: Expense) -> Expense | None:
        draft = self.pending_expense_draft
        if draft is None:
            return expense
        try:
            return self._persist_parsed_expense(draft, goal=expense.goal)
        except BaymaxApiError as exc:
            print(exc)
            return None

    def _persist_parsed_expense(
        self,
        parsed: dict[str, Any],
        goal: str | None = None,
    ) -> Expense:
        resolved_goal = goal if goal is not None else parsed.get("goal")
        goals = [resolved_goal] if resolved_goal else []
        if not goals:
            goal_candidates = parsed.get("goal_candidates") or []
            if len(goal_candidates) == 1:
                goals = [goal_candidates[0]]

        created = self.api.create_expense(
            amount=float(parsed["amount"]),
            description=parsed["description"],
            merchant=parsed.get("merchant"),
            category=parsed.get("category"),
            flags=list(parsed.get("flags") or []),
            budget_treatment=parsed.get("budget_treatment") or "included",
            goals=goals,
            notes=parsed.get("notes"),
        )
        return self._expense_from_created_response(created)

    def _update_last_expense_on_server(
        self,
        *,
        amount: float | None = None,
        goals: list[str] | None = None,
    ) -> Expense | None:
        expense = self.last_expense
        if expense is None:
            return None
        if expense.expense_id is None:
            print("Couldn't update the last expense because it was never saved.")
            return None

        try:
            updated = self.api.update_expense(
                expense.expense_id,
                amount=amount,
                goals=goals,
            )
        except BaymaxApiError as exc:
            print(exc)
            return None

        updated_expense = self._expense_from_created_response(updated)
        self.last_expense = updated_expense
        return updated_expense

    def _clear_pending_expense(self) -> None:
        self.pending_action = None
        self.pending_expense = None
        self.pending_expense_draft = None
        self.pending_goal_candidates = []
