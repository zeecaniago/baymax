"""Deterministic natural-language interpreter for the Baymax intent contract."""

from __future__ import annotations

import re

from .intents import (
    BaymaxIntent,
    CorrectExpenseIntent,
    IntentAmbiguity,
    LogExpenseIntent,
    PeriodReference,
    QuerySpendingIntent,
    RemoveBudgetIntent,
    ReportIntent,
    SetBudgetIntent,
    ShowHistoryIntent,
    SuggestBudgetIntent,
    UnknownIntent,
)
from .parsing import (
    extract_amount,
    extract_flags,
    parse_expense_input,
    split_named_fields,
)


def _clean_reference(value: str) -> str:
    return value.strip().strip("?.!,").strip()


def _period_for(text: str) -> PeriodReference:
    lowered = text.lower()
    if "last cycle" in lowered or "previous cycle" in lowered:
        return PeriodReference(kind="previous_cycle")
    if "next cycle" in lowered:
        return PeriodReference(kind="next_cycle")
    return PeriodReference(kind="current_cycle")


def _without_period(value: str) -> str:
    return _clean_reference(
        re.sub(
            r"\b(?:this|current|last|previous|next)\s+cycle\b",
            "",
            value,
            flags=re.IGNORECASE,
        )
    )


def _interpret_correction(raw_text: str) -> CorrectExpenseIntent | None:
    lowered = raw_text.lower()
    natural_goal = re.fullmatch(
        r"no,?\s+that one(?:'s| is) for (?:the )?(.+?) goal[.!]?",
        raw_text,
        re.IGNORECASE,
    )
    if natural_goal:
        return CorrectExpenseIntent(
            raw_text=raw_text,
            goal_reference=_clean_reference(natural_goal.group(1)),
        )

    amount_match = re.fullmatch(
        r"(?:oops,?\s*)?(\d+(?:\.\d{1,2})?)\s+not\s+\d+(?:\.\d{1,2})?[.!]?",
        lowered,
    )
    if amount_match:
        return CorrectExpenseIntent(
            raw_text=raw_text,
            amount=float(amount_match.group(1)),
        )

    correction = re.fullmatch(
        r"(?:correct|update)\s+(?:the\s+)?last\s+expense,?\s*(.+)",
        raw_text,
        re.IGNORECASE,
    )
    if correction is None:
        return None

    correction_text = correction.group(1)
    try:
        fields = split_named_fields(correction_text)
    except ValueError:
        return None
    if not fields.values:
        return None
    return CorrectExpenseIntent(
        raw_text=raw_text,
        merchant_reference=fields.values.get("merchant"),
        category_reference=fields.values.get("category"),
        goal_reference=fields.values.get("goal"),
    )


def _interpret_query(raw_text: str) -> QuerySpendingIntent | None:
    period = _period_for(raw_text)

    goal_match = re.fullmatch(
        r"what did (?:we|i) (?:spend supporting|put toward) (?:the )?(.+?) goal(?: this cycle)?\?",
        raw_text,
        re.IGNORECASE,
    )
    if goal_match:
        return QuerySpendingIntent(
            raw_text=raw_text,
            metric="spent",
            period=period,
            goal_reference=_clean_reference(goal_match.group(1)),
        )

    patterns: list[tuple[str, str]] = [
        (r"how much (?:did (?:we|i) spend|have (?:we|i) spent) on (.+?)\??", "spent"),
        (r"how much on (.+?)\??", "spent"),
        (r"what(?:'s| is) left (?:in|for) (.+?)\??", "remaining"),
        (r"how much remains (?:in|for) (.+?)\??", "remaining"),
        (r"how many (?:expenses|purchases) (?:in|for|on) (.+?)\??", "expense_count"),
        (r"what(?:'s| is) the average (?:expense )?(?:in|for|on) (.+?)\??", "average"),
        (r"what (?:were|are) the largest expenses (?:in|for|on) (.+?)\??", "largest_expenses"),
    ]
    for pattern, metric in patterns:
        match = re.fullmatch(pattern, raw_text, re.IGNORECASE)
        if match:
            return QuerySpendingIntent(
                raw_text=raw_text,
                metric=metric,
                period=period,
                category_reference=_without_period(match.group(1)),
            )

    total_match = re.fullmatch(
        r"how much (?:did (?:we|i) spend|have (?:we|i) spent)"
        r"(?: (?:this|current|last|previous) cycle)?\??",
        raw_text,
        re.IGNORECASE,
    )
    if total_match:
        return QuerySpendingIntent(raw_text=raw_text, metric="spent", period=period)
    return None


def _interpret_expense(raw_text: str) -> BaymaxIntent:
    if not re.match(r"^(?:\d{1,2}/\d{1,2}\s+)?\$?[\d,]+(?:\.\d{1,2})?(?:\s|$)", raw_text):
        return UnknownIntent(raw_text=raw_text, reason="No supported command matched")

    try:
        amount = extract_amount(raw_text)
        parsed = parse_expense_input(raw_text)
    except ValueError as exc:
        return UnknownIntent(raw_text=raw_text, reason=str(exc))

    flags = extract_flags(raw_text)
    ambiguities = []
    if parsed.goal is None and len(parsed.goal_candidates) > 1:
        ambiguities.append(
            IntentAmbiguity(
                field="goal_reference",
                reason="More than one goal matches the supplied reference",
                candidates=parsed.goal_candidates,
            )
        )
    return LogExpenseIntent(
        raw_text=raw_text,
        amount=amount,
        description=parsed.description,
        merchant_reference=parsed.merchant,
        category_reference=parsed.category,
        goal_reference=parsed.goal,
        goal_candidates=parsed.goal_candidates,
        flags=flags,
        budget_treatment="excluded" if "one-off" in flags else "included",
        explicit_fields=parsed.explicit_fields,
        field_sources=parsed.field_sources,
        confidence=0.75 if ambiguities else 1.0,
        ambiguities=ambiguities,
        requires_confirmation=bool(ambiguities),
    )


def interpret_intent(raw_text: str) -> BaymaxIntent:
    """Translate supported current syntax into a validated semantic intent."""
    cleaned = raw_text.strip()
    if not cleaned:
        raise ValueError("raw_text must not be blank")

    if cleaned.lower() == "history":
        return ShowHistoryIntent(raw_text=cleaned)

    correction = _interpret_correction(cleaned)
    if correction is not None:
        return correction

    budget_set = re.fullmatch(
        r"(?:set|change)\s+(.+?)\s+budget\s+to\s+\$?(\d+(?:\.\d{1,2})?)"
        r"(?:\s+(this|current|next)\s+cycle)?[.!]?",
        cleaned,
        re.IGNORECASE,
    )
    if budget_set:
        period_word = budget_set.group(3)
        period = PeriodReference(
            kind="next_cycle" if period_word and period_word.lower() == "next" else "current_cycle"
        )
        return SetBudgetIntent(
            raw_text=cleaned,
            category_reference=_clean_reference(budget_set.group(1)),
            amount=float(budget_set.group(2)),
            period=period,
        )

    budget_remove = re.fullmatch(
        r"(?:remove|delete)\s+(?:the\s+)?(.+?)\s+budget[.!]?",
        cleaned,
        re.IGNORECASE,
    )
    if budget_remove:
        return RemoveBudgetIntent(
            raw_text=cleaned,
            category_reference=_clean_reference(budget_remove.group(1)),
        )

    budget_suggestion = re.fullmatch(
        r"suggest\s+(?:an?\s+)?(.+?)\s+budget[.!]?",
        cleaned,
        re.IGNORECASE,
    )
    if budget_suggestion:
        return SuggestBudgetIntent(
            raw_text=cleaned,
            category_reference=_clean_reference(budget_suggestion.group(1)),
        )

    goal_report = re.fullmatch(r"report\s+goal\s+(.+?)[.!]?", cleaned, re.IGNORECASE)
    if goal_report:
        return ReportIntent(
            raw_text=cleaned,
            report_type="goal",
            entity_reference=_clean_reference(goal_report.group(1)),
        )

    report = re.fullmatch(r"report\s+(.+?)[.!]?", cleaned, re.IGNORECASE)
    if report:
        return ReportIntent(
            raw_text=cleaned,
            report_type="category",
            entity_reference=_clean_reference(report.group(1)),
        )

    query = _interpret_query(cleaned)
    if query is not None:
        return query

    return _interpret_expense(cleaned)
