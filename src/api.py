#
# import logging
# from decimal import Decimal
# from fastapi import APIRouter, HTTPException, Request
# from .domain import AccountID, Money, as_number
# from . import repo
#
# logger = logging.getLogger(__name__)
# router = APIRouter()
#
# @router.get("/health")
# def health():
#     logger.debug("GET /health")
#     return {"status": "ok"}
#
# @router.get("/accounts/{account_number}/balance")
# def get_balance(account_number: str = AccountID):
#     logger.info("GET balance: account=%s", account_number)
#     bal = repo.get_balance(account_number)
#     return {"account_number": account_number, "balance": as_number(bal)}
#
# @router.post("/accounts/{account_number}/deposit")
# def deposit(account_number: str = AccountID, body: Money = ...):
#     logger.info("POST deposit: account=%s amount=%s", account_number, body.amount)
#     amount = Decimal(str(body.amount))
#     new_bal = repo.deposit(account_number, amount)
#     return {"account_number": account_number, "balance": as_number(new_bal)}
#
# @router.post("/accounts/{account_number}/withdraw")
# def withdraw(account_number: str = AccountID, body: Money = ...):
#     logger.info("POST withdraw: account=%s amount=%s", account_number, body.amount)
#     amount = Decimal(str(body.amount))
#     try:
#         new_bal = repo.withdraw(account_number, amount)
#         return {"account_number": account_number, "balance": as_number(new_bal)}
#     except ValueError as e:
#         logger.warning("Withdraw failed: account=%s reason=%s", account_number, str(e))
#         raise HTTPException(status_code=400, detail=str(e))


from typing import Union
from decimal import Decimal

from fastapi import APIRouter, Path
from pydantic import BaseModel, StrictInt, StrictFloat, Field, field_validator

from .repo import get_balance as repo_get_balance, deposit as repo_deposit, withdraw as repo_withdraw,create_account as create

router = APIRouter()

AccountID = Path(
    ...,
    min_length=1,
    max_length=64,
    pattern=r"^[A-Za-z0-9_\-]+$",
    description="Account identifier (1–64 chars, letters/digits/_/- only)",
)

class Money(BaseModel):
    amount: Union[StrictInt, StrictFloat] = Field(..., description="Positive numeric amount (> 0)")
    @field_validator("amount")
    @classmethod
    def _positive(cls, v):
        if v <= 0:
            raise ValueError("amount must be > 0")
        return v

def _as_number(x: Decimal) -> float:
    return float(x)

@router.get("/health")
def health():
    return {"status": "ok"}

@router.get("/accounts/{account_number}/balance")
def get_balance(account_number: str = AccountID):
    bal = repo_get_balance(account_number)      # raises 404 if not found
    return {"account_number": account_number, "balance": _as_number(bal)}

@router.post("/accounts/{account_number}/deposit")
def deposit(account_number: str = AccountID, body: Money = ...):
    new_bal = repo_deposit(account_number, Decimal(str(body.amount)))  # raises 404 if not found
    return {"account_number": account_number, "balance": _as_number(new_bal)}

@router.post("/accounts/{account_number}/withdraw")
def withdraw(account_number: str = AccountID, body: Money = ...):
    new_bal = repo_withdraw(account_number, Decimal(str(body.amount)))  # 404 or 400 as needed
    return {"account_number": account_number, "balance": _as_number(new_bal)}

class CreateAccount(BaseModel):
    initial_balance: Union[StrictInt, StrictFloat] = Field(0, description="Optional starting balance ≥ 0")

    @field_validator("initial_balance")
    @classmethod
    def _nonneg(cls, v):
        if v < 0:
            raise ValueError("initial_balance must be ≥ 0")
        return v


@router.post("/accounts/{account_number}")
def create_account(account_number: str = AccountID, body: CreateAccount = ...):
    new_bal = create(account_number, Decimal(str(body.initial_balance)))
    return {"account_number": account_number, "balance": float(new_bal)}