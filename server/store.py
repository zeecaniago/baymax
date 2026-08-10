from __future__ import annotations

from copy import deepcopy
from typing import Optional

# These are initial configuration values, not report fixtures. Spending, counts,
# reports, and goal-related spending summaries are all calculated from EXPENSES below.
DEFAULT_CATEGORY_BUDGETS: dict[str, Optional[float]] = {
    "groceries": 400.0,
    "transport": 150.0,
    "eating out": None,
}
CATEGORY_BUDGETS = deepcopy(DEFAULT_CATEGORY_BUDGETS)

# Goals are purposes an expense can support. They deliberately carry no saved
# balance or target amount: Baymax reports linked spending, not goal funding.
GOAL_DEFINITIONS = {
    "goal-resilient-kid": {
        "id": "goal-resilient-kid",
        "name": "Raise a strong, resilient kid",
    },
    "goal-healthy-lifestyle": {
        "id": "goal-healthy-lifestyle",
        "name": "Healthy Lifestyle",
    },
    "goal-promoted": {
        "id": "goal-promoted",
        "name": "Get promoted this year",
    },
    "goal-family-trip": {
        "id": "goal-family-trip",
        "name": "Save for family trip",
    },
    "goal-emergency-fund": {
        "id": "goal-emergency-fund",
        "name": "Emergency Fund",
    },
    "goal-japan-trip": {
        "id": "goal-japan-trip",
        "name": "Japan Trip",
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
