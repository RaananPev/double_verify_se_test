# from decimal import Decimal, ROUND_HALF_UP
# from typing import Union
# from fastapi import Path
# from pydantic import BaseModel, Field, StrictInt, StrictFloat, field_validator
#
# # ---- Account ID validation ----
# AccountID = Path(
#     ...,
#     min_length=1,
#     max_length=64,
#     pattern=r"^[A-Za-z0-9_\-]+$",
#     description="Account identifier (1–64 chars, letters/digits/_/- only)",
# )
#
# # ---- Helpers ----
# def q2(x: Decimal) -> Decimal:
#     return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
#
# def as_number(x: Decimal) -> float:
#     return float(q2(x))
#
# # ---- DTOs ----
# class Money(BaseModel):
#     amount: Union[StrictInt, StrictFloat] = Field(..., description="Positive numeric amount (> 0)")
#
#     @field_validator("amount")
#     @classmethod
#     def _positive(cls, v):
#         if v <= 0:
#             raise ValueError("amount must be > 0")
#         return v


import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Union
from fastapi import Path
from pydantic import BaseModel, Field, StrictInt, StrictFloat, field_validator

logger = logging.getLogger(__name__)

AccountID = Path(
    ...,
    min_length=1,
    max_length=64,
    pattern=r"^[A-Za-z0-9_\-]+$",
    description="Account identifier (1–64 chars, letters/digits/_/- only)",
)

def q2(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def as_number(x: Decimal) -> float:
    return float(q2(x))

class Money(BaseModel):
    amount: Union[StrictInt, StrictFloat] = Field(..., description="Positive numeric amount (> 0)")

    @field_validator("amount")
    @classmethod
    def _positive(cls, v):
        if v <= 0:
            raise ValueError("amount must be > 0")
        return v