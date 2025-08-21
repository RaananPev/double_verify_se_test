# # # # import logging
# # # # from decimal import Decimal
# # # # from . import db
# # # #
# # # # logger = logging.getLogger(__name__)
# # # #
# # # # def get_balance(account_id: str) -> Decimal:
# # # #     logger.debug("repo.get_balance(%s)", account_id)
# # # #     return db.db_get_balance(account_id)
# # # #
# # # # def deposit(account_id: str, amount: Decimal) -> Decimal:
# # # #     logger.info("repo.deposit(%s, %s)", account_id, amount)
# # # #     return db.db_deposit(account_id, amount)
# # # #
# # # # def withdraw(account_id: str, amount: Decimal) -> Decimal:
# # # #     logger.info("repo.withdraw(%s, %s)", account_id, amount)
# # # #     return db.db_withdraw(account_id, amount)
# # #
# # # import logging
# # # from decimal import Decimal, ROUND_HALF_UP
# # #
# # # from fastapi import HTTPException
# # #
# # # from . import db
# # #
# # # log = logging.getLogger("repo")
# # #
# # # def _q2(x: Decimal) -> Decimal:
# # #     return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
# # #
# # # def get_balance(account_id: str) -> Decimal:
# # #     bal = db.get_balance(account_id)
# # #     if bal is None:
# # #         log.info("get_balance: account %s not found", account_id)
# # #         raise HTTPException(status_code=404, detail=f"Account '{account_id}' does not exist")
# # #     log.info("get_balance: account %s got the current balance (%s)", account_id,bal)
# # #
# # #     return _q2(bal)
# # #
# # # def deposit(account_id: str, amount: Decimal) -> Decimal:
# # #     new_bal = db.deposit(account_id, amount)
# # #     if new_bal is None:
# # #         log.info("deposit: account %s not found", account_id)
# # #         raise HTTPException(status_code=404, detail=f"Account '{account_id}' does not exist")
# # #     log.info("deposit id=%s amount=%s new_balance=%s", account_id, amount, new_balance)
# # #     return _q2(new_bal)
# # #
# # # def withdraw(account_id: str, amount: Decimal) -> Decimal:
# # #     # Use atomic conditional update. Distinguish not-found vs insufficient.
# # #     # Call exists() if needed to refine message.
# # #     new_bal, ok = db.withdraw(account_id, amount)
# # #     if ok and new_bal is not None:
# # #         log.info("withdraw id=%s amount=%s new_balance=%s", account_id, amount, new_bal)
# # #         return _q2(new_bal)
# # #
# # #     if not db.account_exists(account_id):
# # #         log.info("withdraw: account %s not found", account_id)
# # #         raise HTTPException(status_code=404, detail=f"Account '{account_id}' does not exist")
# # #
# # #     # exists but insufficient
# # #     log.info("withdraw: insufficient funds on %s (amount=%s)", account_id, amount)
# # #     raise HTTPException(status_code=400, detail="insufficient funds")
# # #
# # #
# # # def create_account(account_id: str, initial_balance: Decimal = Decimal("0")) -> Decimal:
# # #     if db.account_exists(account_id):
# # #         raise HTTPException(status_code=409, detail=f"Account '{account_id}' already exists")
# # #     if initial_balance < 0:
# # #         raise HTTPException(status_code=400, detail="Initial balance must be non-negative")
# # #     # insert
# # #     _ = db._c().execute(
# # #         "INSERT INTO accounts(id, balance) VALUES(?, ?)",
# # #         (account_id, str(initial_balance))
# # #     )
# # #     log.info("create_account id=%s initial=%s", account_id, initial_balance)
# # #     return _q2(initial_balance)
# #
# #
# # # repo.py
# # #
# # # from decimal import Decimal
# # # import logging
# # # from fastapi import HTTPException
# # # from . import db
# # #
# # # log = logging.getLogger("repo")
# # #
# # # def get_balance(account_id: str) -> Decimal | None:
# # #     return db.get_balance(account_id)
# # #
# # # def create_account(account_id: str, initial: Decimal) -> Decimal:
# # #     bal = db.create_account(account_id, initial)
# # #     log.info("create_account id=%s initial=%s", account_id, bal)
# # #     return bal
# # #
# # # def deposit(account_id: str, amount: Decimal) -> Decimal:
# # #     new_bal = db.deposit(account_id, amount)
# # #     if new_bal is None:
# # #         log.info("deposit: account %s not found", account_id)
# # #         raise HTTPException(status_code=404, detail=f"Account '{account_id}' does not exist")
# # #     log.info("deposit id=%s amount=%s new_balance=%s", account_id, amount, new_bal)  # <-- use new_bal
# # #     return new_bal
# # #
# # # def withdraw(account_id: str, amount: Decimal) -> Decimal:
# # #     new_bal = db.withdraw(account_id, amount)
# # #     if new_bal is None:
# # #         log.info("withdraw: account %s not found", account_id)
# # #         raise HTTPException(status_code=404, detail=f"Account '{account_id}' does not exist")
# # #     log.info("withdraw id=%s amount=%s new_balance=%s", account_id, amount, new_bal)  # <-- use new_bal
# # #     return new_bal
# #
# #
# #
# # from __future__ import annotations
# #
# # from decimal import Decimal
# # import logging
# # from fastapi import HTTPException
# #
# # from . import db
# #
# # log = logging.getLogger("repo")
# #
# #
# # def get_balance(account_id: str) -> Decimal | None:
# #     """Return the current balance, or None if account does not exist."""
# #     return db.get_balance(account_id)
# #
# #
# # def create_account(account_id: str, initial: Decimal) -> Decimal:
# #     """
# #     Create a new account with an initial balance.
# #     Returns the resulting balance.
# #     Raises 409 if the account already exists (if DB layer signals that via None).
# #     """
# #     bal = db.create_account(account_id, initial)
# #     if bal is None:
# #         log.info("create_account conflict id=%s", account_id)
# #         raise HTTPException(status_code=409, detail=f"Account '{account_id}' already exists")
# #     log.info("create_account id=%s initial=%s balance=%s", account_id, initial, bal)
# #     return bal
# #
# #
# # def deposit(account_id: str, amount: Decimal) -> Decimal:
# #     """
# #     Deposit amount and return the updated balance.
# #     Raises 404 if account not found.
# #     """
# #     new_bal = db.deposit(account_id, amount)
# #     if new_bal is None:
# #         log.info("deposit: account %s not found", account_id)
# #         raise HTTPException(status_code=404, detail=f"Account '{account_id}' does not exist")
# #     log.info("deposit id=%s amount=%s new_balance=%s", account_id, amount, new_bal)
# #     return new_bal
# #
# #
# # def withdraw(account_id: str, amount: Decimal) -> Decimal:
# #     """
# #     Withdraw amount and return the updated balance.
# #     Raises 404 if account not found.
# #     Propagate/raise 400 for insufficient funds if your DB layer signals it.
# #     """
# #     new_bal = db.withdraw(account_id, amount)
# #     if new_bal is None:
# #         log.info("withdraw: account %s not found", account_id)
# #         raise HTTPException(status_code=404, detail=f"Account '{account_id}' does not exist")
# #     log.info("withdraw id=%s amount=%s new_balance=%s", account_id, amount, new_bal)
# #     return new_bal
#
# # src/repo.py
# from decimal import Decimal
# import logging
# from fastapi import HTTPException
# from sqlite3 import IntegrityError
#
# from . import db
#
# log = logging.getLogger("repo")
#
# def get_balance(account_id: str) -> Decimal | None:
#     return db.get_balance(account_id)
#
# def create_account(account_id: str, initial: Decimal) -> Decimal:
#     try:
#         bal = db.create_account(account_id, initial)
#     except IntegrityError:
#         log.info("create_account conflict id=%s", account_id)
#         raise HTTPException(status_code=409, detail=f"Account '{account_id}' already exists")
#     log.info("create_account id=%s initial=%s", account_id, bal)
#     return bal
#
# def deposit(account_id: str, amount: Decimal) -> Decimal:
#     new_bal = db.deposit(account_id, amount)
#     if new_bal is None:
#         log.info("deposit: account %s not found", account_id)
#         raise HTTPException(status_code=404, detail=f"Account '{account_id}' does not exist")
#     log.info("deposit id=%s amount=%s new_balance=%s", account_id, amount, new_bal)
#     return new_bal
#
# def withdraw(account_id: str, amount: Decimal) -> Decimal:
#     try:
#         new_bal = db.withdraw(account_id, amount)
#     except ValueError as e:
#         if str(e) == "overdraw":
#             log.info("withdraw overdraw id=%s amount=%s", account_id, amount)
#             raise HTTPException(status_code=400, detail="insufficient funds")
#         raise
#     if new_bal is None:
#         log.info("withdraw: account %s not found", account_id)
#         raise HTTPException(status_code=404, detail=f"Account '{account_id}' does not exist")
#     log.info("withdraw id=%s amount=%s new_balance=%s", account_id, amount, new_bal)
#     return new_bal


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