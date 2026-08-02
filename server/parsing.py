from __future__ import annotations

import re
from typing import Optional

from .store import CATEGORY_BUDGETS, GOAL_DEFINITIONS


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
    body = re.sub(r"^\d{1,2}/\d{1,2}\s+", "", raw_text).strip()
    body = re.sub(r"^\$\d+(?:\.\d{1,2})?\s*", "", body).strip()
    return body.split(",")[0].strip() or raw_text.strip()


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

    if re.fullmatch(r"[a-z]+", lowered):
        return normalized_name(description)
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
