#
# import logging
# import sqlite3
# from contextlib import contextmanager
# from decimal import Decimal
# from pathlib import Path
#
# logger = logging.getLogger(__name__)
#
# DATA_DIR = Path(__file__).resolve().parent.parent / "data"
# DATA_DIR.mkdir(parents=True, exist_ok=True)
# DB_PATH = DATA_DIR / "atm.db"
#
# def get_connection() -> sqlite3.Connection:
#     conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, isolation_level=None)
#     conn.row_factory = sqlite3.Row
#     conn.execute("PRAGMA journal_mode=WAL;")
#     conn.execute("PRAGMA synchronous=NORMAL;")
#     return conn
#
# def init_db():
#     logger.info("Initializing database at %s", DB_PATH)
#     with get_connection() as conn:
#         conn.execute("""
#             CREATE TABLE IF NOT EXISTS accounts (
#                 id TEXT PRIMARY KEY,
#                 balance TEXT NOT NULL
#             );
#         """)
#     logger.info("Database initialized")
#
# @contextmanager
# def _tx():
#     conn = get_connection()
#     try:
#         conn.execute("BEGIN IMMEDIATE;")
#         yield conn
#         conn.execute("COMMIT;")
#     except Exception as e:
#         logger.exception("Transaction failed, rolling back: %s", e)
#         try:
#             conn.execute("ROLLBACK;")
#         except Exception:
#             logger.exception("Rollback failed")
#         raise
#     finally:
#         conn.close()
#
# def db_get_balance(account_id: str) -> Decimal:
#     logger.debug("db_get_balance(%s)", account_id)
#     with get_connection() as conn:
#         row = conn.execute("SELECT balance FROM accounts WHERE id = ?", (account_id,)).fetchone()
#         if not row:
#             logger.debug("Account %s not found; returning 0.00", account_id)
#             return Decimal("0.00")
#         return Decimal(row["balance"])
#
# def db_set_balance(conn: sqlite3.Connection, account_id: str, new_balance: Decimal) -> None:
#     conn.execute(
#         "INSERT INTO accounts (id, balance) VALUES (?, ?) "
#         "ON CONFLICT(id) DO UPDATE SET balance = excluded.balance",
#         (account_id, str(new_balance)),
#     )
#
# def db_deposit(account_id: str, amount: Decimal) -> Decimal:
#     logger.info("DB deposit start: account=%s, amount=%s", account_id, amount)
#     with _tx() as conn:
#         row = conn.execute("SELECT balance FROM accounts WHERE id = ?", (account_id,)).fetchone()
#         bal = Decimal(row["balance"]) if row else Decimal("0.00")
#         new_bal = bal + amount
#         db_set_balance(conn, account_id, new_bal)
#         logger.info("DB deposit success: account=%s, old=%s, new=%s", account_id, bal, new_bal)
#         return new_bal
#
# def db_withdraw(account_id: str, amount: Decimal) -> Decimal:
#     logger.info("DB withdraw start: account=%s, amount=%s", account_id, amount)
#     with _tx() as conn:
#         row = conn.execute("SELECT balance FROM accounts WHERE id = ?", (account_id,)).fetchone()
#         bal = Decimal(row["balance"]) if row else Decimal("0.00")
#         if amount > bal:
#             logger.warning("DB withdraw insufficient funds: account=%s, have=%s, need=%s", account_id, bal, amount)
#             raise ValueError("insufficient funds")
#         new_bal = bal - amount
#         db_set_balance(conn, account_id, new_bal)
#         logger.info("DB withdraw success: account=%s, old=%s, new=%s", account_id, bal, new_bal)
#         return new_bal
#
# # ---------- NEW: seed data ----------
# DEFAULT_SEED = [
#     ("12345",  "10500.00"),
#     ("777",    "12015.00"),
#     ("a111",   "5040.00"),
#     ("007",    "47000.00"),
# ]
#
# def seed_if_empty(seed_rows: list[tuple[str, str]] = DEFAULT_SEED) -> bool:
#     """
#     If the accounts table is empty, insert the provided seed rows.
#     Returns True if seeding occurred, False otherwise.
#     """
#     with _tx() as conn:
#         cnt = conn.execute("SELECT COUNT(*) AS c FROM accounts;").fetchone()["c"]
#         if cnt and int(cnt) > 0:
#             logger.info("Seed skipped: accounts table already has %s rows", cnt)
#             return False
#
#         logger.info("Seeding %s account(s) into fresh database", len(seed_rows))
#         conn.executemany(
#             "INSERT INTO accounts (id, balance) VALUES (?, ?)",
#             seed_rows,
#         )
#         logger.info("Seeding completed")
#         return True
import logging
import os
import sqlite3
from decimal import Decimal

DB_PATH = os.environ.get("ATM_DB_PATH", os.path.join(os.getcwd(), "data", "atm.db"))


log = logging.getLogger("db")

def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)  # autocommit
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

_conn = None

def _c() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = get_connection()
    return _conn

def init_db() -> None:
    log.info("db init: %s", DB_PATH)

    _c().execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY,
            balance TEXT NOT NULL
        )
    """)

def seed_if_empty() -> None:

    cur = _c().execute("SELECT COUNT(*) FROM accounts")
    (n,) = cur.fetchone()
    if n:
        return
    # initial demo data – decimal as string for exactness
    rows = [
        ("12345", 10500),
        ("777",   12015.00),
        ("a111",  5040.00),
        ("007",   47000.00),
    ]
    _c().executemany("INSERT INTO accounts(id, balance) VALUES(?, ?)", rows)
    log.info("db seed: inserted %d demo accounts", len(rows))

# --- low-level helpers (no HTTP knowledge here) ---

def account_exists(account_id: str) -> bool:
    cur = _c().execute("SELECT 1 FROM accounts WHERE id = ?", (account_id,))
    return cur.fetchone() is not None

def get_balance(account_id: str) -> Decimal | None:
    cur = _c().execute("SELECT balance FROM accounts WHERE id = ?", (account_id,))
    row = cur.fetchone()
    return Decimal(row[0]) if row else None

def deposit(account_id: str, amount: Decimal) -> Decimal | None:
    # Update only if account exists.
    cur = _c().execute(
        "UPDATE accounts SET balance = (CAST(balance AS REAL) + CAST(? AS REAL)) WHERE id = ?",
        (str(amount), account_id),
    )
    if cur.rowcount == 0:
        return None
    # fetch updated balance
    return get_balance(account_id)

def withdraw(account_id: str, amount: Decimal) -> tuple[Decimal | None, bool]:
    """
    Returns (new_balance, ok).
    - If account doesn't exist -> (None, False)
    - If insufficient funds -> (None, False) but account DOES exist
      (repo layer will differentiate).
    Uses atomic conditional update to avoid race conditions.
    """
    cur = _c().execute(
        """
        UPDATE accounts
           SET balance = (CAST(balance AS REAL) - CAST(? AS REAL))
         WHERE id = ?
           AND CAST(balance AS REAL) >= CAST(? AS REAL)
        """,
        (str(amount), account_id, str(amount)),
    )
    if cur.rowcount == 1:
        return get_balance(account_id), True

    # figure out if it's not found vs insufficient
    if account_exists(account_id):
        return None, False  # insufficient funds
    return None, False      # not found (repo will check and map)