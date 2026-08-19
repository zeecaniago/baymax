"""Deterministic resolution of intent references against household data."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from .db import DEFAULT_HOUSEHOLD_ID
from .intents import (
    BaymaxIntent,
    CorrectExpenseIntent,
    LogExpenseIntent,
    QuerySpendingIntent,
    RemoveBudgetIntent,
    ReportIntent,
    SetBudgetIntent,
    SuggestBudgetIntent,
)
from .parsing import normalized_name
from .repositories import (
    categories as category_repository,
    expenses as expense_repository,
    goals as goal_repository,
)

EntityKind = Literal["category", "goal", "merchant"]


class EntityCandidate(BaseModel):
    entity_id: Optional[str] = None
    canonical_name: str


class ResolvedReference(BaseModel):
    kind: EntityKind
    reference: str
    status: Literal["resolved", "ambiguous", "not_found"]
    entity_id: Optional[str] = None
    canonical_name: Optional[str] = None
    candidates: list[EntityCandidate] = Field(default_factory=list)
    allow_create: bool = False


class EntityResolutionResult(BaseModel):
    references: dict[str, ResolvedReference] = Field(default_factory=dict)

    @property
    def ready(self) -> bool:
        return all(reference.status == "resolved" for reference in self.references.values())

    @property
    def issues(self) -> list[ResolvedReference]:
        return [
            reference
            for reference in self.references.values()
            if reference.status != "resolved"
        ]


def _resolve_from_candidates(
    kind: EntityKind,
    reference: str,
    candidates: list[EntityCandidate],
    *,
    allow_create: bool = False,
) -> ResolvedReference:
    wanted = normalized_name(reference)
    exact = [
        candidate
        for candidate in candidates
        if wanted
        in {
            normalized_name(candidate.canonical_name),
            normalized_name(candidate.entity_id or ""),
        }
    ]
    if len(exact) == 1:
        match = exact[0]
        return ResolvedReference(
            kind=kind,
            reference=reference,
            status="resolved",
            entity_id=match.entity_id,
            canonical_name=match.canonical_name,
        )

    partial = [
        candidate
        for candidate in candidates
        if wanted in normalized_name(candidate.canonical_name)
        or normalized_name(candidate.canonical_name) in wanted
    ]
    if len(partial) == 1:
        match = partial[0]
        return ResolvedReference(
            kind=kind,
            reference=reference,
            status="resolved",
            entity_id=match.entity_id,
            canonical_name=match.canonical_name,
        )
    if len(partial) > 1:
        return ResolvedReference(
            kind=kind,
            reference=reference,
            status="ambiguous",
            candidates=partial,
        )
    if allow_create:
        canonical_name = (
            normalized_name(reference)
            if kind == "category"
            else " ".join(reference.strip().split())
        )
        return ResolvedReference(
            kind=kind,
            reference=reference,
            status="resolved",
            canonical_name=canonical_name,
            allow_create=True,
        )
    return ResolvedReference(kind=kind, reference=reference, status="not_found")


def resolve_category(
    reference: str,
    *,
    household_id: str = DEFAULT_HOUSEHOLD_ID,
    allow_create: bool = False,
) -> ResolvedReference:
    candidates = [
        EntityCandidate(entity_id=str(category["id"]), canonical_name=category["name"])
        for category in category_repository.list_all(household_id)
    ]
    return _resolve_from_candidates(
        "category",
        reference,
        candidates,
        allow_create=allow_create,
    )


def resolve_goal(
    reference: str,
    *,
    household_id: str = DEFAULT_HOUSEHOLD_ID,
) -> ResolvedReference:
    candidates = [
        EntityCandidate(entity_id=goal["id"], canonical_name=goal["name"])
        for goal in goal_repository.list_all(household_id)
    ]
    return _resolve_from_candidates("goal", reference, candidates)


def resolve_merchant(
    reference: str,
    *,
    household_id: str = DEFAULT_HOUSEHOLD_ID,
    allow_create: bool = True,
) -> ResolvedReference:
    names = {
        str(expense["merchant"]).strip()
        for expense in expense_repository.list_all(household_id)
        if expense.get("merchant")
    }
    candidates = [EntityCandidate(canonical_name=name) for name in sorted(names)]
    return _resolve_from_candidates(
        "merchant",
        reference,
        candidates,
        allow_create=allow_create,
    )


def resolve_intent_entities(
    intent: BaymaxIntent,
    *,
    household_id: str = DEFAULT_HOUSEHOLD_ID,
) -> EntityResolutionResult:
    """Resolve every entity-bearing field without changing application state."""
    references: dict[str, ResolvedReference] = {}

    if isinstance(intent, (LogExpenseIntent, CorrectExpenseIntent)):
        if intent.category_reference:
            references["category"] = resolve_category(
                intent.category_reference,
                household_id=household_id,
                allow_create=True,
            )
        if intent.merchant_reference:
            references["merchant"] = resolve_merchant(
                intent.merchant_reference,
                household_id=household_id,
            )
        if intent.goal_reference:
            references["goal"] = resolve_goal(
                intent.goal_reference,
                household_id=household_id,
            )
        elif isinstance(intent, LogExpenseIntent) and len(intent.goal_candidates) > 1:
            references["goal"] = ResolvedReference(
                kind="goal",
                reference="",
                status="ambiguous",
                candidates=[
                    EntityCandidate(canonical_name=candidate)
                    for candidate in intent.goal_candidates
                ],
            )

    elif isinstance(intent, SetBudgetIntent):
        references["category"] = resolve_category(
            intent.category_reference,
            household_id=household_id,
            allow_create=True,
        )
    elif isinstance(intent, (RemoveBudgetIntent, SuggestBudgetIntent)):
        references["category"] = resolve_category(
            intent.category_reference,
            household_id=household_id,
        )
    elif isinstance(intent, QuerySpendingIntent):
        if intent.category_reference:
            references["category"] = resolve_category(
                intent.category_reference,
                household_id=household_id,
            )
        if intent.merchant_reference:
            references["merchant"] = resolve_merchant(
                intent.merchant_reference,
                household_id=household_id,
                allow_create=False,
            )
        if intent.goal_reference:
            references["goal"] = resolve_goal(
                intent.goal_reference,
                household_id=household_id,
            )
    elif (
        isinstance(intent, ReportIntent)
        and intent.entity_reference
        and intent.report_type in {"category", "goal"}
    ):
        resolver = resolve_goal if intent.report_type == "goal" else resolve_category
        references[intent.report_type] = resolver(
            intent.entity_reference,
            household_id=household_id,
        )

    return EntityResolutionResult(references=references)
