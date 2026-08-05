from __future__ import annotations

from datetime import date as DateType
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ParseExpenseRequest(BaseModel):
    raw_text: str = Field(..., min_length=1)
    household_id: Optional[str] = None


class ExpenseDraft(BaseModel):
    amount: float
    description: str
    merchant: Optional[str] = None
    category: Optional[str] = None
    flags: list[str] = Field(default_factory=list)
    budget_treatment: Literal["included", "excluded"] = "included"
    goal_candidates: list[str] = Field(default_factory=list)
    notes: Optional[str] = None


class CreateExpenseRequest(BaseModel):
    amount: float
    description: str
    merchant: Optional[str] = None
    category: Optional[str] = None
    flags: list[str] = Field(default_factory=list)
    budget_treatment: Literal["included", "excluded"] = "included"
    goals: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    date: Optional[DateType] = None
    user_id: Optional[str] = None


class UpdateExpenseRequest(BaseModel):
    amount: Optional[float] = None
    description: Optional[str] = None
    merchant: Optional[str] = None
    category: Optional[str] = None
    flags: Optional[list[str]] = None
    budget_treatment: Optional[Literal["included", "excluded"]] = None
    goals: Optional[list[str]] = None
    notes: Optional[str] = None
    date: Optional[DateType] = None


class SetBudgetRequest(BaseModel):
    amount: float = Field(..., ge=0)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    cycle: str = "current"


class AskResponse(BaseModel):
    answer: str
    cycle: str
    supporting_data: dict
