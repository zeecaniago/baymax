from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional

from .store import CATEGORY_BUDGETS, EXPENSES, GOAL_DEFINITIONS

# These short purchase descriptions have a natural merchant slot. They let a
# person start with a quick log ("coffee") and add merchant detail later
# ("coffee fresh street") without first setting up categories.
MERCHANTABLE_DESCRIPTIONS = {"coffee"}
KNOWN_FLAGS = {"one-off", "reimbursable", "shared"}
FIELD_ALIASES = {
    "m": "merchant",
    "merchant": "merchant",
    "c": "category",
    "category": "category",
    "g": "goal",
    "goal": "goal",
}
NAMED_FIELD_PATTERN = re.compile(
    r"(?:(?<=^)|(?<=,))\s*(m|merchant|c|category|g|goal)\s*:\s*",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class NamedFields:
    """Structured fields extracted from an expense command.

    Values intentionally remain free text. A comma only starts a new field
    when it is followed by a recognized field name, so names such as
    ``Raise a Strong, Resilient Kid`` stay intact.
    """

    description_text: str
    values: dict[str, str]
    explicit_fields: list[str]


@dataclass(frozen=True)
class ParsedExpenseInput:
    description: str
    merchant: Optional[str]
    category: Optional[str]
    goal: Optional[str]
    goal_candidates: list[str]
    explicit_fields: list[str]
    field_sources: dict[str, str]


def normalized_name(name: str) -> str:
    return " ".join(name.strip().split()).lower()


def display_name(name: str) -> str:
    """Return a compact display value for learned category suggestions."""
    return " ".join(part.capitalize() for part in normalized_name(name).split())


def canonical_goal_name(name: str) -> str:
    normalized = normalized_name(name)
    for goal in GOAL_DEFINITIONS.values():
        if normalized in {normalized_name(goal["id"]), normalized_name(goal["name"])}:
            return goal["name"]
    return " ".join(name.strip().split())


def extract_amount(raw_text: str) -> float:
    """Extract the required expense amount without inventing a default."""
    dollar_match = re.search(r"\$([\d,]+(?:\.\d{1,2})?)", raw_text)
    if dollar_match:
        return float(dollar_match.group(1).replace(",", ""))

    body = re.sub(r"^\s*\d{1,2}/\d{1,2}\s+", "", raw_text)
    fallback = re.match(r"\s*([\d,]+(?:\.\d{1,2})?)(?:\s+|$)", body)
    if fallback:
        return float(fallback.group(1).replace(",", ""))
    raise ValueError("An expense needs an amount, such as $45")


def split_named_fields(text: str) -> NamedFields:
    """Split comma-delimited ``m:``, ``c:``, and ``g:`` fields from text.

    The returned leading text is the description candidate. Repeated fields
    use the final supplied value, matching the usual correction semantics.
    """
    matches = list(NAMED_FIELD_PATTERN.finditer(text))
    if not matches:
        return NamedFields(
            description_text=_without_standalone_flags(text),
            values={},
            explicit_fields=[],
        )

    values: dict[str, str] = {}
    explicit_fields: list[str] = []
    for index, match in enumerate(matches):
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        field = FIELD_ALIASES[match.group(1).lower()]
        value = _without_standalone_flags(text[match.end() : next_start])
        if not value:
            raise ValueError(f"{field} needs a value")
        values[field] = value
        if field not in explicit_fields:
            explicit_fields.append(field)

    return NamedFields(
        description_text=_without_standalone_flags(text[: matches[0].start()]),
        values=values,
        explicit_fields=explicit_fields,
    )


def parse_expense_input(raw_text: str) -> ParsedExpenseInput:
    """Parse structured fields first, then use conservative legacy inference."""
    body = _raw_expense_body(raw_text)
    fields = split_named_fields(body)
    description_text = fields.description_text
    if not description_text:
        raise ValueError("An expense needs a description")

    inference_text = description_text
    description_text = _without_natural_goal_markers(description_text)
    description, inferred_merchant, inferred_category = _infer_expense_details(description_text)
    merchant = fields.values.get("merchant", inferred_merchant)
    category = fields.values.get("category", inferred_category)

    explicit_goal = fields.values.get("goal")
    candidates = [] if explicit_goal else goal_candidates(inference_text)
    goal = canonical_goal_name(explicit_goal) if explicit_goal else None
    if goal is None and len(candidates) == 1:
        goal = candidates[0]

    field_sources: dict[str, str] = {}
    for field, inferred_value in (
        ("merchant", inferred_merchant),
        ("category", inferred_category),
    ):
        if field in fields.values:
            field_sources[field] = "explicit"
        elif inferred_value:
            field_sources[field] = "inferred"
    if explicit_goal:
        field_sources["goal"] = "explicit"
    elif len(candidates) == 1:
        field_sources["goal"] = "inferred"

    return ParsedExpenseInput(
        description=description,
        merchant=merchant,
        category=category,
        goal=goal,
        goal_candidates=candidates,
        explicit_fields=fields.explicit_fields,
        field_sources=field_sources,
    )


def extract_description(raw_text: str) -> str:
    return parse_expense_input(raw_text).description


def extract_expense_details(raw_text: str) -> tuple[str, Optional[str], Optional[str]]:
    """Return the description, merchant, and category for legacy quick logs."""
    return _infer_expense_details(_legacy_expense_text(raw_text))


def _infer_expense_details(expense_text: str) -> tuple[str, Optional[str], Optional[str]]:
    """Infer only values with a clear local or rule-based match."""
    expense_text, tagged_merchant, tagged_category = _extract_annotations(expense_text)
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
    if category is not None and category_text is not None:
        merchant = expense_text[len(category_text) :].strip()
        if not merchant:
            return expense_text, tagged_merchant, category
        return category_text, tagged_merchant or merchant, category

    description, merchant = _split_description_and_merchant(expense_text)
    merchant = tagged_merchant or merchant or _learned_value(description, "merchant")
    category = extract_category(description) or _learned_value(description, "category")
    return description, merchant, category


def _raw_expense_body(raw_text: str) -> str:
    body = re.sub(r"^\s*\d{1,2}/\d{1,2}\s+", "", raw_text).strip()
    amount_match = re.match(r"\$?[\d,]+(?:\.\d{1,2})?(?:\s+|$)", body)
    if not amount_match:
        return body
    return body[amount_match.end() :].strip()


def _legacy_expense_text(raw_text: str) -> str:
    """Keep the older positional grammar intact for non-structured input."""
    body = _raw_expense_body(raw_text)
    return _without_standalone_flags(body.split(",")[0]).strip() or body.strip()


def _without_standalone_flags(value: str) -> str:
    segments = [segment.strip() for segment in value.split(",")]
    retained = [segment for segment in segments if normalized_name(segment) not in KNOWN_FLAGS]
    return ", ".join(segment for segment in retained if segment).strip(" ,")


def _without_natural_goal_markers(value: str) -> str:
    """Keep legacy comma-separated goal hints out of the purchase description."""
    goal_markers = {"kid goal", "learning goal", "family trip fund", "emergency fund goal"}
    segments = [segment.strip() for segment in value.split(",")]
    retained = [segment for segment in segments if normalized_name(segment) not in goal_markers]
    return ", ".join(segment for segment in retained if segment).strip(" ,")


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


def _learned_value(description: str, field: str) -> Optional[str]:
    """Reuse prior household data only when it gives one exact, clear answer."""
    description_name = normalized_name(description)
    matches = {
        str(expense[field]).strip()
        for expense in EXPENSES
        if normalized_name(str(expense.get("description") or "")) == description_name
        and expense.get(field)
    }
    return next(iter(matches)) if len(matches) == 1 else None


def extract_flags(raw_text: str) -> list[str]:
    lowered = raw_text.lower()
    return [
        flag
        for flag in sorted(KNOWN_FLAGS)
        if re.search(rf"(?<!\w){re.escape(flag)}(?!\w)", lowered)
    ]


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
    """Return only high-confidence natural-language goal matches."""
    lowered = normalized_name(raw_text)
    exact_matches = [
        goal["name"]
        for goal in GOAL_DEFINITIONS.values()
        if normalized_name(goal["name"]) in lowered
    ]
    if exact_matches:
        return exact_matches

    if "learning goal" in lowered:
        return ["Raise a strong, resilient kid", "Get promoted this year"]
    if "family trip fund" in lowered:
        return ["Save for family trip", "family trip fund"]
    if "kid goal" in lowered:
        return ["Raise a strong, resilient kid"]
    if "emergency fund" in lowered:
        return ["Emergency Fund"]

    description_name = normalized_name(raw_text)
    learned_goals = {
        goal
        for expense in EXPENSES
        if normalized_name(str(expense.get("description") or "")) == description_name
        for goal in expense.get("goals", [])
    }
    return sorted(learned_goals) if len(learned_goals) == 1 else []


def expense_suggestions(field: str, query: str = "", description: str = "") -> list[str]:
    """Rank known values for future ``m:``, ``c:``, and ``g:`` autocomplete."""
    normalized_field = FIELD_ALIASES.get(field.lower(), field.lower())
    if normalized_field == "merchant":
        candidates = {str(expense["merchant"]).strip() for expense in EXPENSES if expense.get("merchant")}
    elif normalized_field == "category":
        candidates = {display_name(category) for category in CATEGORY_BUDGETS}
        candidates.update(
            display_name(str(expense["category"]))
            for expense in EXPENSES
            if expense.get("category")
        )
    elif normalized_field == "goal":
        candidates = {goal["name"] for goal in GOAL_DEFINITIONS.values()}
    else:
        return []

    query_name = normalized_name(query)
    description_name = normalized_name(description)

    def score(candidate: str) -> tuple[float, str]:
        candidate_name = normalized_name(candidate)
        if not query_name:
            match_score = 1.0
        elif candidate_name.startswith(query_name):
            match_score = 4.0
        elif query_name in candidate_name:
            match_score = 3.0
        else:
            match_score = SequenceMatcher(None, query_name, candidate_name).ratio()

        prior_usage = 0
        for expense in EXPENSES:
            if normalized_name(str(expense.get("description") or "")) != description_name:
                continue
            values = expense.get("goals", []) if normalized_field == "goal" else [expense.get(normalized_field)]
            if any(value and normalized_name(str(value)) == candidate_name for value in values):
                prior_usage += 1
        return (match_score + min(prior_usage, 5) / 10, candidate_name)

    ranked = [candidate for candidate in candidates if not query_name or score(candidate)[0] >= 0.45]
    return sorted(ranked, key=lambda candidate: (-score(candidate)[0], score(candidate)[1]))
