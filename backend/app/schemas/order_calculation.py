from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

MIN_PARTICIPANTS = 2
MAX_PARTICIPANTS = 5


class CalculationParticipantIn(BaseModel):
    user_id: int
    percent: Decimal = Field(gt=0, le=100, max_digits=5, decimal_places=2)


class CalculationIn(BaseModel):
    participants: list[CalculationParticipantIn] = Field(min_length=MIN_PARTICIPANTS, max_length=MAX_PARTICIPANTS)


class CalculationParticipantOut(BaseModel):
    user_id: int
    full_name: str
    percent: Decimal
    amount: Decimal


class CalculationOut(BaseModel):
    is_calculated: bool
    calculated_at: datetime | None
    # Fixed when the calculation was saved; before that the current profit, or
    # None while it isn't final yet (is_ready False).
    profit: Decimal | None
    currency: str
    is_ready: bool
    participants: list[CalculationParticipantOut]
