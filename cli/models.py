from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Expense:
    """A CLI-friendly view of an expense returned by the API."""

    amount: float
    description: str
    merchant: str | None = None
    category: str | None = None
    flags: list[str] = field(default_factory=list)
    budget_treatment: str = "included"
    goal: str | None = None
    expense_id: str | None = None
