"""Typed language contract shared by rule-based and future LLM interpreters.

The models in this module deliberately contain user-facing references rather
than trusted database identifiers.  Entity resolution and command execution
happen in later, deterministic stages.
"""

from __future__ import annotations

from datetime import date as DateType
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

SCHEMA_VERSION = "1.0"


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PeriodReference(ContractModel):
    kind: Literal["current_cycle", "previous_cycle", "next_cycle", "date_range"] = (
        "current_cycle"
    )
    start_date: Optional[DateType] = None
    end_date: Optional[DateType] = None

    @model_validator(mode="after")
    def validate_explicit_range(self) -> PeriodReference:
        if self.kind == "date_range":
            if self.start_date is None or self.end_date is None:
                raise ValueError("date_range requires start_date and end_date")
            if self.end_date < self.start_date:
                raise ValueError("end_date must not be before start_date")
        elif self.start_date is not None or self.end_date is not None:
            raise ValueError("cycle periods cannot include explicit dates")
        return self


class IntentAmbiguity(ContractModel):
    field: str
    reason: str
    candidates: list[str] = Field(default_factory=list)


class IntentBase(ContractModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    source: Literal["rules", "llm"] = "rules"
    raw_text: str = Field(..., min_length=1)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    ambiguities: list[IntentAmbiguity] = Field(default_factory=list)
    requires_confirmation: bool = False


class LogExpenseIntent(IntentBase):
    intent: Literal["log_expense"] = "log_expense"
    amount: float = Field(..., gt=0)
    description: str = Field(..., min_length=1)
    merchant_reference: Optional[str] = Field(default=None, min_length=1)
    category_reference: Optional[str] = Field(default=None, min_length=1)
    goal_reference: Optional[str] = Field(default=None, min_length=1)
    goal_candidates: list[str] = Field(default_factory=list)
    flags: list[Literal["one-off", "reimbursable", "shared"]] = Field(
        default_factory=list
    )
    budget_treatment: Literal["included", "excluded"] = "included"
    purchase_date: Optional[DateType] = None
    explicit_fields: list[Literal["merchant", "category", "goal"]] = Field(
        default_factory=list
    )
    field_sources: dict[str, Literal["explicit", "inferred"]] = Field(
        default_factory=dict
    )


class CorrectExpenseIntent(IntentBase):
    intent: Literal["correct_expense"] = "correct_expense"
    expense_reference: Literal["last_expense"] = "last_expense"
    amount: Optional[float] = Field(default=None, gt=0)
    description: Optional[str] = Field(default=None, min_length=1)
    merchant_reference: Optional[str] = Field(default=None, min_length=1)
    category_reference: Optional[str] = Field(default=None, min_length=1)
    goal_reference: Optional[str] = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def require_an_update(self) -> CorrectExpenseIntent:
        updates = (
            self.amount,
            self.description,
            self.merchant_reference,
            self.category_reference,
            self.goal_reference,
        )
        if all(value is None for value in updates):
            raise ValueError("a correction requires at least one updated field")
        return self


class QuerySpendingIntent(IntentBase):
    intent: Literal["query_spending"] = "query_spending"
    metric: Literal[
        "spent",
        "remaining",
        "expense_count",
        "average",
        "largest_expenses",
    ]
    period: PeriodReference = Field(default_factory=PeriodReference)
    category_reference: Optional[str] = Field(default=None, min_length=1)
    merchant_reference: Optional[str] = Field(default=None, min_length=1)
    goal_reference: Optional[str] = Field(default=None, min_length=1)
    flags: list[Literal["one-off", "reimbursable", "shared"]] = Field(
        default_factory=list
    )


class SetBudgetIntent(IntentBase):
    intent: Literal["set_budget"] = "set_budget"
    category_reference: str = Field(..., min_length=1)
    amount: float = Field(..., ge=0)
    period: PeriodReference = Field(default_factory=PeriodReference)
    requires_confirmation: Literal[True] = True


class RemoveBudgetIntent(IntentBase):
    intent: Literal["remove_budget"] = "remove_budget"
    category_reference: str = Field(..., min_length=1)
    requires_confirmation: Literal[True] = True


class SuggestBudgetIntent(IntentBase):
    intent: Literal["suggest_budget"] = "suggest_budget"
    category_reference: str = Field(..., min_length=1)


class ReportIntent(IntentBase):
    intent: Literal["report"] = "report"
    report_type: Literal["category", "goal", "flag"]
    entity_reference: Optional[str] = Field(default=None, min_length=1)
    period: PeriodReference = Field(default_factory=PeriodReference)


class ShowHistoryIntent(IntentBase):
    intent: Literal["show_history"] = "show_history"


class UnknownIntent(IntentBase):
    intent: Literal["unknown"] = "unknown"
    reason: str = Field(..., min_length=1)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


BaymaxIntent = Annotated[
    Union[  # noqa: UP007 - evaluated at runtime on supported Python 3.9
        LogExpenseIntent,
        CorrectExpenseIntent,
        QuerySpendingIntent,
        SetBudgetIntent,
        RemoveBudgetIntent,
        SuggestBudgetIntent,
        ReportIntent,
        ShowHistoryIntent,
        UnknownIntent,
    ],
    Field(discriminator="intent"),
]

INTENT_ADAPTER = TypeAdapter(BaymaxIntent)


class InterpretIntentRequest(ContractModel):
    raw_text: str = Field(..., min_length=1)


def validate_intent(payload: dict) -> BaymaxIntent:
    """Validate output from any interpreter against the shared contract."""
    return INTENT_ADAPTER.validate_python(payload)
