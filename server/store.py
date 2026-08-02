from __future__ import annotations

from copy import deepcopy
from typing import Optional


# These are initial configuration values, not report fixtures. Spending, counts,
# reports, and goal progress are all calculated from EXPENSES below.
DEFAULT_CATEGORY_BUDGETS: dict[str, Optional[float]] = {
    "groceries": 400.0,
    "transport": 150.0,
    "eating out": None,
}
CATEGORY_BUDGETS = deepcopy(DEFAULT_CATEGORY_BUDGETS)

GOAL_DEFINITIONS = {
    "goal-resilient-kid": {
        "id": "goal-resilient-kid",
        "name": "Raise a strong, resilient kid",
        "target_amount": None,
        "target_date": None,
        "is_open_ended": True,
    },
    "goal-emergency-fund": {
        "id": "goal-emergency-fund",
        "name": "Emergency Fund",
        "target_amount": 10000.0,
        "target_date": None,
        "is_open_ended": True,
    },
    "goal-japan-trip": {
        "id": "goal-japan-trip",
        "name": "Japan Trip",
        "target_amount": 4000.0,
        "target_date": "2027-05-01",
        "is_open_ended": False,
    },
}

# This remains process-local until the persistence layer is introduced. Unlike
# the old fixture data, every read endpoint derives its values from this list.
EXPENSES: list[dict] = []


def reset_in_memory_store() -> None:
    """Reset the prototype store. Kept public for isolated API tests."""
    EXPENSES.clear()
    CATEGORY_BUDGETS.clear()
    CATEGORY_BUDGETS.update(deepcopy(DEFAULT_CATEGORY_BUDGETS))
