# from fastapi import FastAPI
#
# app = FastAPI(title="ATM System (server-side only)")
#
# # in-memory accounts store
# accounts: dict[str, float] = {}
#
# @app.get("/health")
# def health():
#     return {"status": "ok"}
#
# @app.get("/accounts/{account_number}/balance")
# def get_balance(account_number: str):
#     balance = accounts.get(account_number, 0.0)  # auto-create with 0.00
#     return {"account_number": account_number, "balance": f"{balance:.2f}"}
#
# from pydantic import BaseModel
#
# class Money(BaseModel):
#     amount: float  # must be > 0
#
# @app.post("/accounts/{account_number}/deposit")
# def deposit(account_number: str, body: Money):
#     if body.amount <= 0:
#         return {"error": "amount must be > 0"}
#     current = accounts.get(account_number, 0.0)
#     new_balance = current + body.amount
#     accounts[account_number] = new_balance
#     return {"account_number": account_number, "balance": f"{new_balance:.2f}"}
#
# @app.post("/accounts/{account_number}/withdraw")
# def withdraw(account_number: str, body: Money):
#     if body.amount <= 0:
#         return {"error": "amount must be > 0"}
#     current = accounts.get(account_number, 0.0)
#     if body.amount > current:
#         return {"error": "insufficient funds", "balance": f"{current:.2f}"}
#     new_balance = current - body.amount
#     accounts[account_number] = new_balance
#     return {"account_number": account_number, "balance": f"{new_balance:.2f}"}


from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, validator, condecimal
from threading import Lock





app = FastAPI(title="ATM System (server-side only)")

accounts: dict[str, Decimal] = {}

lock = Lock()


def q2(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

# Accept numbers or strings; pydantic converts to Decimal and enforces > 0
class Money(BaseModel):
    amount: condecimal(gt=0) = Field(..., description="Positive amount")

    def _validate_amount(cls, v: str) -> str:
        try:
            d = Decimal(v)
        except InvalidOperation as e:
            raise ValueError("amount must be a decimal string") from e
        if d <= 0:
            raise ValueError("amount must be > 0")
        return v

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/accounts/{account_number}/balance")
def get_balance(account_number: str):
    bal = accounts.get(account_number, Decimal("0.00"))
    return {"account_number": account_number, "balance": f"{q2(bal):.2f}"}

@app.post("/accounts/{account_number}/deposit")
def deposit(account_number: str, body: Money):
    amount: Decimal =  body.amount
    with lock:
        bal = accounts.setdefault(account_number, Decimal("0.00"))
        new_bal = bal + amount
        accounts[account_number] = new_bal
    return {"account_number": account_number, "balance": f"{q2(new_bal):.2f}"}


@app.post("/accounts/{account_number}/withdraw")
def withdraw(account_number: str, body: Money):
    amount: Decimal =  body.amount
    with lock:
        bal = accounts.setdefault(account_number, Decimal("0.00"))
        if amount > bal:
            # don't change state on failure
            raise HTTPException(status_code=400, detail="insufficient funds")
        new_bal = bal - amount
        accounts[account_number] = new_bal
    return {"account_number": account_number, "balance": f"{q2(new_bal):.2f}"}