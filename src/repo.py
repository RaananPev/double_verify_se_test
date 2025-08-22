from decimal import Decimal
import logging
from fastapi import HTTPException
from . import db

log = logging.getLogger("repo")

def get_balance(account_id: str) -> Decimal | None:
    return db.get_balance(account_id)

def create_account(account_id: str, initial: Decimal) -> Decimal:
    try:
        bal = db.create_account(account_id, initial)
    except Exception as e:
        log.info("create_account conflict id=%s", account_id)
        raise HTTPException(status_code=409, detail=f"Account '{account_id}' already exists") from e
    log.info("create_account id=%s initial=%s", account_id, bal)
    return bal

def deposit(account_id: str, amount: Decimal) -> Decimal:
    new_bal = db.deposit(account_id, amount)
    if new_bal is None:
        log.info("deposit: account %s not found", account_id)
        raise HTTPException(status_code=404, detail=f"Account '{account_id}' does not exist")
    log.info("deposit id=%s amount=%s new_balance=%s", account_id, amount, new_bal)
    return new_bal

def withdraw(account_id: str, amount: Decimal) -> Decimal:
    pre = db.get_balance(account_id)
    if pre is None:
        log.info("withdraw: account %s not found", account_id)
        raise HTTPException(status_code=404, detail=f"Account '{account_id}' does not exist")

    new_bal = db.withdraw(account_id, amount)

    # If DB rolled back for insufficient funds, it returns the *old* balance (pre).
    # Detect that and emit 400.
    if new_bal == pre and amount > pre:
        log.info("withdraw insufficient id=%s amount=%s balance=%s", account_id, amount, pre)
        raise HTTPException(status_code=400, detail="insufficient funds")

    log.info("withdraw id=%s amount=%s new_balance=%s", account_id, amount, new_bal)
    return new_bal