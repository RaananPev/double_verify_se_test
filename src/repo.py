# import logging
# from decimal import Decimal
# from . import db
#
# logger = logging.getLogger(__name__)
#
# def get_balance(account_id: str) -> Decimal:
#     logger.debug("repo.get_balance(%s)", account_id)
#     return db.db_get_balance(account_id)
#
# def deposit(account_id: str, amount: Decimal) -> Decimal:
#     logger.info("repo.deposit(%s, %s)", account_id, amount)
#     return db.db_deposit(account_id, amount)
#
# def withdraw(account_id: str, amount: Decimal) -> Decimal:
#     logger.info("repo.withdraw(%s, %s)", account_id, amount)
#     return db.db_withdraw(account_id, amount)

import logging
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException

from . import db

log = logging.getLogger("repo")

def _q2(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def get_balance(account_id: str) -> Decimal:
    bal = db.get_balance(account_id)
    if bal is None:
        log.info("get_balance: account %s not found", account_id)
        raise HTTPException(status_code=404, detail=f"Account '{account_id}' does not exist")
    log.info("get_balance: account %s got the current balance (%s)", account_id,bal)

    return _q2(bal)

def deposit(account_id: str, amount: Decimal) -> Decimal:
    new_bal = db.deposit(account_id, amount)
    if new_bal is None:
        log.info("deposit: account %s not found", account_id)
        raise HTTPException(status_code=404, detail=f"Account '{account_id}' does not exist")
    log.info("deposit id=%s amount=%s new_balance=%s", account_id, amount, new_balance)
    return _q2(new_bal)

def withdraw(account_id: str, amount: Decimal) -> Decimal:
    # Use atomic conditional update. Distinguish not-found vs insufficient.
    # Call exists() if needed to refine message.
    new_bal, ok = db.withdraw(account_id, amount)
    if ok and new_bal is not None:
        log.info("withdraw id=%s amount=%s new_balance=%s", account_id, amount, new_bal)
        return _q2(new_bal)

    if not db.account_exists(account_id):
        log.info("withdraw: account %s not found", account_id)
        raise HTTPException(status_code=404, detail=f"Account '{account_id}' does not exist")

    # exists but insufficient
    log.info("withdraw: insufficient funds on %s (amount=%s)", account_id, amount)
    raise HTTPException(status_code=400, detail="insufficient funds")


def create_account(account_id: str, initial_balance: Decimal = Decimal("0")) -> Decimal:
    if db.account_exists(account_id):
        raise HTTPException(status_code=409, detail=f"Account '{account_id}' already exists")
    if initial_balance < 0:
        raise HTTPException(status_code=400, detail="Initial balance must be non-negative")
    # insert
    _ = db._c().execute(
        "INSERT INTO accounts(id, balance) VALUES(?, ?)",
        (account_id, str(initial_balance))
    )
    log.info("create_account id=%s initial=%s", account_id, initial_balance)
    return _q2(initial_balance)