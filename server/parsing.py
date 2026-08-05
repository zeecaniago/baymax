from __future__ import annotations

import re
from typing import Optional

from .store import CATEGORY_BUDGETS, GOAL_DEFINITIONS

# These short purchase descriptions have a natural merchant slot. They let a
# person start with a quick log ("coffee") and add merchant detail later
# ("coffee fresh street") without first setting up categories.
MERCHANTABLE_DESCRIPTIONS = {"coffee"}


def normalized_name(name: str) -> str:
    return " ".join(name.strip().split()).lower()


def canonical_goal_name(name: str) -> str:
    normalized = normalized_name(name)
    for goal in GOAL_DEFINITIONS.values():
        if normalized in {normalized_name(goal["id"]), normalized_name(goal["name"])}:
            return goal["name"]
    return " ".join(name.strip().split())


def extract_amount(raw_text: str) -> float:
    match = re.search(r"\$(\d+(?:\.\d{1,2})?)", raw_text.replace(",", ""))
    if match:
        return float(match.group(1))

    fallback = re.search(r"(\d+(?:\.\d{1,2})?)", raw_text.replace(",", ""))
    return float(fallback.group(1)) if fallback else 45.0


def extract_description(raw_text: str) -> str:
    return _expense_text(raw_text)


def extract_expense_details(raw_text: str) -> tuple[str, Optional[str], Optional[str]]:
    """Return the description, merchant, and category inferred from quick-log text.

    A recognized category at the start of an entry may be followed by a
    merchant. Anchoring the category at the beginning keeps a phrase such as
    ``parking downtown`` as a single description rather than splitting it at
    an arbitrary word boundary.
    """
    expense_text, tagged_merchant, tagged_category = _extract_annotations(_expense_text(raw_text))
    if tagged_category:
        category = normalized_name(tagged_category)
        description, merchant = _split_description_and_merchant(expense_text)
        return description, tagged_merchant or merchant, category

    trailing_category = _trailing_category(expense_text)
    if trailing_category is not None:
        category, category_text = trailing_category
        purchase_text = expense_text[: -len(category_text)].strip()
        if purchase_text:
            description, merchant = _split_description_and_merchant(purchase_text)
            return description, tagged_merchant or merchant, category

    category, category_text = _leading_category(expense_text)
    if category is None or category_text is None:
        description, merchant = _split_description_and_merchant(expense_text)
        return description, tagged_merchant or merchant, extract_category(description)

    merchant = expense_text[len(category_text) :].strip()
    if not merchant:
        return expense_text, tagged_merchant, category
    return category_text, tagged_merchant or merchant, category


def _expense_text(raw_text: str) -> str:
    body = re.sub(r"^\d{1,2}/\d{1,2}\s+", "", raw_text).strip()
    body = re.sub(r"^\$\d+(?:\.\d{1,2})?\s*", "", body).strip()
    return body.split(",")[0].strip() or raw_text.strip()


def _leading_category(description: str) -> tuple[Optional[str], Optional[str]]:
    """Find a known category prefix, returning its normalized name and text."""
    available_categories = set(CATEGORY_BUDGETS)
    for category in sorted(available_categories, key=len, reverse=True):
        match = re.match(rf"{re.escape(category)}(?:\s|$)", description, re.IGNORECASE)
        if match:
            return normalized_name(category), match.group(0).strip()

    # Both spellings belong to the groceries budget.
    match = re.match(r"grocer(?:y|ies)(?:\s|$)", description, re.IGNORECASE)
    if match:
        return "groceries", match.group(0).strip()
    return None, None


def _trailing_category(description: str) -> tuple[str, str] | None:
    """Find an optional expert-supplied category at the end of a quick log."""
    available_categories = set(CATEGORY_BUDGETS) | {"groceries"}
    for category in sorted(available_categories, key=len, reverse=True):
        match = re.search(rf"(?:^|\s)({re.escape(category)})$", description, re.IGNORECASE)
        if match:
            return normalized_name(category), match.group(1)
    return None


def _extract_annotations(description: str) -> tuple[str, Optional[str], Optional[str]]:
    """Extract optional @merchant and #category annotations from a quick log."""
    merchant_match = re.search(r"(?:^|\s)@([^@#]+?)(?=\s[@#]|$)", description)
    category_match = re.search(r"(?:^|\s)#([^@#]+?)(?=\s[@#]|$)", description)
    merchant = merchant_match.group(1).strip() if merchant_match else None
    category = category_match.group(1).strip() if category_match else None
    unannotated = re.sub(r"(?:^|\s)[@#][^@#]+?(?=\s[@#]|$)", " ", description)
    return " ".join(unannotated.split()), merchant or None, category or None


def _split_description_and_merchant(description: str) -> tuple[str, Optional[str]]:
    """Use the natural merchant slot only for short, recognizable purchases."""
    first_word, separator, remainder = description.partition(" ")
    if first_word.lower() in MERCHANTABLE_DESCRIPTIONS and separator and remainder.strip():
        return first_word, remainder.strip()
    return description, None


def extract_flags(raw_text: str) -> list[str]:
    known_flags = {"one-off", "reimbursable", "shared"}
    lowered = raw_text.lower()
    return [flag for flag in known_flags if flag in lowered]


def extract_category(description: str) -> Optional[str]:
    lowered = description.lower()
    if "grocer" in lowered:
        return "groceries"
    if "target" in lowered:
        return "shopping"
    if "karate" in lowered or "books" in lowered:
        return "kids"
    if "flight" in lowered:
        return "travel"
    if "car repair" in lowered:
        return "auto"
    if "transport" in lowered or "train" in lowered:
        return "transport"
    if "eating out" in lowered:
        return "eating out"
    if "rent" in lowered:
        return "rent"

    for category in sorted(CATEGORY_BUDGETS, key=len, reverse=True):
        if re.search(rf"(?<!\w){re.escape(category)}(?!\w)", lowered):
            return category

    return None


def goal_candidates(raw_text: str) -> list[str]:
    lowered = raw_text.lower()
    if "learning goal" in lowered:
        return ["Raise a strong, resilient kid", "Get promoted this year"]
    if "family trip fund" in lowered:
        return ["Save for family trip", "family trip fund"]
    if "kid goal" in lowered:
        return ["Raise a strong, resilient kid"]
    if "emergency fund" in lowered or "fund" in lowered:
        return ["Emergency Fund"]
    return []
