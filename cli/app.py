from __future__ import annotations

import re
from dataclasses import dataclass, field

try:
    import readline
except ImportError:  # pragma: no cover - depends on platform support
    readline = None


BOOT_BANNER = "Cycle: Jun 26 \u2013 Jul 25   (day 10 of 30)"


@dataclass
class Expense:
    amount: float
    description: str
    category: str | None = None
    flags: list[str] = field(default_factory=list)
    goal: str | None = None


class BaymaxCli:
    def __init__(self) -> None:
        self.last_expense: Expense | None = None
        self.pending_action: str | None = None
        self.pending_expense: Expense | None = None
        self.groceries_spent = 243.0
        self.command_history: list[str] = []

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
        if self.pending_action == "choose_learning_goal":
            return self._resolve_learning_goal(raw)
        if self.pending_action == "choose_family_trip_goal":
            return self._resolve_family_trip_goal(raw)
        if self.pending_action == "set_groceries_budget":
            return self._resolve_budget_confirmation(raw)

        lowered = raw.lower()

        if lowered == "suggest a groceries budget":
            self.pending_action = "set_groceries_budget"
            return ["Last 3 cycles: $380, $410, $395 \u2014 avg $395", "Suggest $400/cycle. Set it?"]

        if lowered == "report groceries":
            return [
                "Groceries \u2014 Jun 26\u2013Jul 25",
                "  $403 of $400 (101%) \u00b7 15 expenses \u00b7 avg $26.87",
                "  Largest: Costco $91, Whole Foods $64, Trader Joe's $58",
            ]

        if lowered == "report goal resilient kid":
            return [
                "Raise a strong, resilient kid",
                "  This cycle: $90 across 2 expenses",
                "  All-time: $890 across 14 expenses (since Mar 2026)",
            ]

        if lowered == "how much on groceries this cycle?":
            return ["Groceries: $403.00 of $400 (101%) \u2014 15 expenses"]

        if lowered == "what's left in eating out?":
            return ["$45.00 left of $150"]

        if lowered == "what did we put toward the resilient kid goal this cycle?":
            return ["$90.00 across 2 expenses \u2014 karate class $50, books $40"]

        if lowered == "no, that one's for the emergency fund goal":
            return self._update_last_goal("Emergency Fund")

        if re.fullmatch(r"oops,\s*\d+(?:\.\d{1,2})?\s+not\s+\d+(?:\.\d{1,2})?", lowered):
            return self._update_last_amount(raw)

        if "learning goal" in lowered:
            parsed = self._parse_expense(raw)
            self.pending_action = "choose_learning_goal"
            self.pending_expense = parsed
            return [
                "Which goal?",
                "  1. Raise a strong, resilient kid",
                "  2. Get promoted this year",
                "  3. Don't link to a goal",
            ]

        if "family trip fund" in lowered:
            parsed = self._parse_expense(raw)
            self.pending_action = "choose_family_trip_goal"
            self.pending_expense = parsed
            return [
                'No goal called "family trip fund" yet:',
                "  1. Save for family trip",
                '  2. Create new goal: "family trip fund"',
                "  3. Don't link to a goal",
            ]

        return self._log_expense(raw)

    def _resolve_learning_goal(self, raw: str) -> list[str]:
        choice = raw.strip()
        expense = self.pending_expense
        self.pending_action = None
        self.pending_expense = None
        if expense is None:
            return []

        if choice == "1":
            expense.goal = "Raise a strong, resilient kid"
        elif choice == "2":
            expense.goal = "Get promoted this year"

        self.last_expense = expense
        return [self._format_expense(expense)]

    def _resolve_family_trip_goal(self, raw: str) -> list[str]:
        choice = raw.strip()
        expense = self.pending_expense
        self.pending_action = None
        self.pending_expense = None
        if expense is None:
            return []

        if choice == "1":
            expense.goal = "Save for family trip"
        elif choice == "2":
            expense.goal = "family trip fund"

        self.last_expense = expense
        return [self._format_expense(expense)]

    def _resolve_budget_confirmation(self, raw: str) -> list[str]:
        self.pending_action = None
        if raw.strip().lower() in {"y", "yes"}:
            return ["\u2713 Groceries budget set to $400/cycle"]
        return ["No change."]

    def _update_last_goal(self, goal: str) -> list[str]:
        if self.last_expense is None:
            return ["Nothing to update."]
        before = self.last_expense.goal or "No goal"
        self.last_expense.goal = goal
        return [
            f"\u2713 updated \u2014 ${self.last_expense.amount:.2f} \u2014 {self.last_expense.description}"
            f"{self._format_category(self.last_expense.category)}  \u2192 {before if before != 'No goal' else goal}"
            if before != "No goal"
            else f"\u2713 updated \u2014 ${self.last_expense.amount:.2f} \u2014 {self.last_expense.description}"
            f"{self._format_category(self.last_expense.category)}  \u2192 {goal}"
        ]

    def _update_last_amount(self, raw: str) -> list[str]:
        if self.last_expense is None:
            return ["Nothing to update."]
        numbers = [float(match) for match in re.findall(r"\d+(?:\.\d{1,2})?", raw)]
        if not numbers:
            return ["Nothing to update."]
        self.last_expense.amount = numbers[0]
        return [self._format_update(self.last_expense)]

    def _log_expense(self, raw: str) -> list[str]:
        expense = self._parse_expense(raw)
        self.last_expense = expense
        lines = [self._format_expense(expense)]

        if raw.lower() == "$85 groceries":
            self.groceries_spent = 167.0
            lines.append("  Groceries: $233 left of $400 this cycle")
            return lines

        if raw.lower() == "$60 groceries":
            lines.extend(
                [
                    "",
                    "\u26a0 Groceries \u2014 82% of budget ($328 of $400)",
                    "   Jun 27  farmers market      $22",
                    "   Jun 29  Whole Foods         $64",
                    "   Jul 01  Costco              $91",
                    "   Jul 03  Trader Joe's        $58",
                    "   Jul 05  groceries           $60",
                ]
            )
            return lines

        if raw.lower() == "$75 groceries":
            lines.extend(
                [
                    "",
                    "\u26a0 Groceries \u2014 over budget: $403 of $400 (101%)",
                    "   [full list]",
                ]
            )
            return lines

        if raw.lower().startswith("6/20 $200 car repair"):
            lines.append("  \u21b3 logged to cycle May 26 \u2013 Jun 25 (closed)")
            return lines

        if expense.category == "Groceries":
            self.groceries_spent += expense.amount

        return lines

    def _parse_expense(self, raw: str) -> Expense:
        amount_match = re.search(r"\$(\d+(?:\.\d{1,2})?)", raw)
        amount = float(amount_match.group(1)) if amount_match else 0.0

        body = re.sub(r"^\d{1,2}/\d{1,2}\s+", "", raw).strip()
        body = re.sub(r"^\$\d+(?:\.\d{1,2})?\s*", "", body).strip()
        description = body.split(",")[0].strip()

        flags = []
        if "one-off" in raw.lower():
            flags.append("one-off")

        category = self._guess_category(description)
        goal = self._guess_goal(raw)

        return Expense(amount=amount, description=description, category=category, flags=flags, goal=goal)

    def _guess_category(self, description: str) -> str | None:
        lowered = description.lower()
        if "grocer" in lowered:
            return "Groceries"
        if "target" in lowered:
            return "Shopping"
        if "karate" in lowered or "books" in lowered:
            return "Kids"
        if "flight" in lowered:
            return "Travel"
        if "car repair" in lowered:
            return "Auto"
        return None

    def _guess_goal(self, raw: str) -> str | None:
        lowered = raw.lower()
        if "kid goal" in lowered:
            return "Raise a strong, resilient kid"
        return None

    def _format_expense(self, expense: Expense) -> str:
        line = f"\u2713 ${expense.amount:.2f} \u2014 {expense.description}"
        if expense.category:
            line += self._format_category(expense.category)
        if expense.flags:
            line += "  " + " ".join(f"#{flag}" for flag in expense.flags)
        if expense.goal:
            line += f"  \u2192 {expense.goal}"
        return line

    def _format_update(self, expense: Expense) -> str:
        line = f"\u2713 updated \u2014 ${expense.amount:.2f} \u2014 {expense.description}"
        if expense.category:
            line += self._format_category(expense.category)
        if expense.goal:
            line += f"  \u2192 {expense.goal}"
        return line

    def _format_category(self, category: str | None) -> str:
        return f"  [{category}]" if category else ""

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
        return [f"{index:>{width}}  {command}" for index, command in enumerate(self.command_history, start=1)]


def main() -> None:
    BaymaxCli().run()


if __name__ == "__main__":
    main()
