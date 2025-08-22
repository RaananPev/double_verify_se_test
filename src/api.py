
from decimal import Decimal
import logging
from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, StrictInt, StrictFloat, field_validator
from typing import Union

from .repo import get_balance as repo_get_balance
from .repo import deposit as repo_deposit
from .repo import withdraw as repo_withdraw
from .repo import create_account as repo_create_account

log = logging.getLogger("api")
router = APIRouter()

# same account id constraints you use elsewhere
AccountID = Path(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$")

def as_number(d: Decimal) -> float:
    # repo/db already quantize to 2dp; safeguard here anyway
    return float(d)

class Money(BaseModel):
    amount: Union[StrictInt, StrictFloat]
    @field_validator("amount")
    @classmethod
    def positive(cls, v):
        if v <= 0:
            raise ValueError("amount must be > 0")
        return v

class CreateBody(BaseModel):
    # optional initial balance; default 0
    initial_balance: Union[StrictInt, StrictFloat] | None = 0
    @field_validator("initial_balance")
    @classmethod
    def non_negative(cls, v):
        if v is None:
            return 0
        if v < 0:
            raise ValueError("initial_balance must be >= 0")
        return v


@router.get("/")
def root():
    return {"status": "ok", "message": "Welcome to the ATM API", "docs": "/docs"}


@router.get("/health")
def health():
    return {"status": "ok"}


from .domain import as_number  # ensure import

@router.get("/accounts/{account_number}/balance")
def get_balance(account_number: str = AccountID):
    bal = repo_get_balance(account_number)
    if bal is None:
        # not found -> 404
        raise HTTPException(status_code=404, detail=f"Account '{account_number}' does not exist")
    return {"account_number": account_number, "balance": as_number(bal)}

@router.post("/accounts/{account_number}/deposit")
def deposit(account_number: str = AccountID, body: Money = ...):
    new_bal = repo_deposit(account_number, Decimal(str(body.amount)))
    # repo_deposit raises 404 if account missing
    return {"account_number": account_number, "balance": as_number(new_bal)}

@router.post("/accounts/{account_number}/withdraw")
def withdraw(account_number: str = AccountID, body: Money = ...):
    new_bal = repo_withdraw(account_number, Decimal(str(body.amount)))
    # repo_withdraw raises 404 if account missing, 400 if insufficient funds
    return {"account_number": account_number, "balance": as_number(new_bal)}

@router.post("/accounts/{account_number}")
def create_account(account_number: str = AccountID, body: CreateBody = CreateBody()):
    initial = Decimal(str(body.initial_balance or 0))
    try:
        bal = repo_create_account(account_number, initial)
    except HTTPException:
        # let repo raise 409 if exists (your repo/db should do that)
        raise
    log.info("create account id=%s initial=%s -> %s", account_number, initial, bal)
    return {"account_number": account_number, "balance": as_number(bal)}