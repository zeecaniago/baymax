from __future__ import annotations

from datetime import date as DateType
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class ParseExpenseRequest(BaseModel):
    raw_text: str = Field(..., min_length=1)
    household_id: Optional[str] = None


class ExpenseDraft(BaseModel):
    amount: float
    description: str
    merchant: Optional[str] = None
    category: Optional[str] = None
    goal: Optional[str] = None
    flags: list[str] = Field(default_factory=list)
    budget_treatment: Literal["included", "excluded"] = "included"
    goal_candidates: list[str] = Field(default_factory=list)
    explicit_fields: list[Literal["merchant", "category", "goal"]] = Field(default_factory=list)
    field_sources: dict[str, Literal["explicit", "inferred"]] = Field(default_factory=dict)
    notes: Optional[str] = None


class CreateExpenseRequest(BaseModel):
    amount: float = Field(..., gt=0)
    description: str = Field(..., min_length=1)
    merchant: Optional[str] = None
    category: Optional[str] = None
    flags: list[str] = Field(default_factory=list)
    budget_treatment: Literal["included", "excluded"] = "included"
    goals: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    date: Optional[DateType] = None
    user_id: Optional[str] = None

    @field_validator("description")
    @classmethod
    def description_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("description must not be blank")
        return stripped


class UpdateExpenseRequest(BaseModel):
    amount: Optional[float] = Field(default=None, gt=0)
    description: Optional[str] = None
    merchant: Optional[str] = None
    category: Optional[str] = None
    flags: Optional[list[str]] = None
    budget_treatment: Optional[Literal["included", "excluded"]] = None
    goals: Optional[list[str]] = None
    notes: Optional[str] = None
    date: Optional[DateType] = None

    @field_validator("description")
    @classmethod
    def updated_description_must_not_be_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("description must not be blank")
        return stripped


class SetBudgetRequest(BaseModel):
    amount: float = Field(..., ge=0)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    cycle: str = "current"


class AskResponse(BaseModel):
    answer: str
    cycle: str
    supporting_data: dict
