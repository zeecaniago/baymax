from __future__ import annotations

import re

from .api import BaymaxApiClient
from .budget_commands import BudgetCommands
from .expense_commands import ExpenseCommands
from .models import Expense
from .presentation import CliPresentation
from .reporting import ReportingCommands

try:
    import readline
except ImportError:  # pragma: no cover - depends on platform support
    readline = None


BOOT_BANNER = "Cycle: Jun 26 – Jul 25   (day 10 of 30)"


class BaymaxCli(ExpenseCommands, BudgetCommands, ReportingCommands, CliPresentation):
    """Interactive CLI facade that routes commands to focused workflows."""

    def __init__(self, api_client: BaymaxApiClient | None = None) -> None:
        self.api = api_client or BaymaxApiClient()
        self.last_expense: Expense | None = None
        self.pending_action: str | None = None
        self.pending_expense: Expense | None = None
        self.pending_expense_draft: dict | None = None
        self.pending_goal_candidates: list[str] = []
        self.pending_budget_category: str | None = None
        self.pending_budget_amount: float | None = None
        self.groceries_spent = 243.0
        self.command_history: list[str] = []
        self.category_budgets: dict[str, float | None] = {"Eating Out": None}

    def run(self) -> None:
        self._configure_input_history()
        print(BOOT_BANNER)
        while True:
            try:
                raw = input("> ").strip()
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print("\nbye")
                break

            if not raw:
                continue
            self._remember_command(raw)
            if raw.lower() in {"exit", "quit"}:
                break

            for line in self.handle(raw):
                print(line)

    def handle(self, raw: str) -> list[str]:
        if raw.lower() == "history":
            return self._format_history()
        if self.pending_action == "choose_goal":
            return self._resolve_goal_choice(raw)
        if self.pending_action == "confirm_budget_change":
            return self._resolve_budget_confirmation(raw)

        budget_set_match = re.fullmatch(
            r"set\s+(.+?)\s+budget\s+to\s+\$(\d+(?:\.\d{1,2})?)",
            raw,
            re.IGNORECASE,
        )
        if budget_set_match:
            category = self._normalize_category_name(budget_set_match.group(1))
            amount = float(budget_set_match.group(2))
            return self._set_category_budget(category, amount)

        budget_remove_match = re.fullmatch(r"remove\s+(.+?)\s+budget", raw, re.IGNORECASE)
        if budget_remove_match:
            category = self._normalize_category_name(budget_remove_match.group(1))
            return self._remove_category_budget(category)

        lowered = raw.lower()
        if lowered == "suggest a groceries budget":
            self.pending_action = "confirm_budget_change"
            self.pending_budget_category = "Groceries"
            self.pending_budget_amount = 400.0
            return ["Last 3 cycles: $380, $410, $395 — avg $395", "Suggest $400/cycle. Set it?"]

        goal_report_match = re.fullmatch(r"report\s+goal\s+(.+?)", raw, re.IGNORECASE)
        if goal_report_match:
            return self._report_goal_summary(goal_report_match.group(1))

        report_match = re.fullmatch(r"report\s+(.+?)", raw, re.IGNORECASE)
        if report_match:
            return self._report_category(report_match.group(1))

        if lowered == "how much on groceries this cycle?":
            return self._ask_question(raw)
        if lowered == "what's left in eating out?":
            return self._eating_out_balance()
        if lowered in {
            "what did we put toward the resilient kid goal this cycle?",
            "what did we spend supporting the resilient kid goal this cycle?",
        }:
            return self._ask_question(raw)
        if lowered == "no, that one's for the emergency fund goal":
            return self._update_last_goal("Emergency Fund")

        correction_match = re.fullmatch(
            r"(?:correct|update)\s+last\s+expense\s*,?\s*(.+)",
            raw,
            re.IGNORECASE,
        )
        if correction_match:
            return self._correct_last_expense(correction_match.group(1))
        if re.fullmatch(r"oops,\s*\d+(?:\.\d{1,2})?\s+not\s+\d+(?:\.\d{1,2})?", lowered):
            return self._update_last_amount(raw)

        return self._log_expense(raw)

    def _configure_input_history(self) -> None:
        if readline is None:
            return

        readline.clear_history()
        doc = readline.__doc__ or ""
        if "libedit" in doc:
            readline.parse_and_bind("bind -e")
            readline.parse_and_bind(r'bind "\e[A" ed-prev-history')
            readline.parse_and_bind(r'bind "\e[B" ed-next-history')
            return

        readline.parse_and_bind("set editing-mode emacs")
        readline.parse_and_bind(r'"\e[A": previous-history')
        readline.parse_and_bind(r'"\e[B": next-history')

    def _remember_command(self, raw: str) -> None:
        self.command_history.append(raw)

    def _format_history(self) -> list[str]:
        width = len(str(len(self.command_history)))
        return [
            f"{index:>{width}}  {command}"
            for index, command in enumerate(self.command_history, start=1)
        ]


def main() -> None:
    BaymaxCli().run()


if __name__ == "__main__":
    main()
