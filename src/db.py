import os, sqlite3, logging
from contextlib import closing
from decimal import Decimal

log = logging.getLogger("db")

def _db_path() -> str:
    return os.environ.get("ATM_DB_PATH", os.path.join(os.getcwd(), "data", "atm.db"))

_conn = None

def reset_connection():
    """Drop the cached connection so subsequent calls reopen with the current DB_PATH."""
    global _conn
    if _conn is not None:
        try: _conn.close()
        except Exception: pass
    _conn = None

def _ensure_parent_dir(path: str):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

def _open_conn() -> sqlite3.Connection:
    path = _db_path()
    _ensure_parent_dir(path)
    # autocommit; we control BEGIN/COMMIT in ops
    conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def init_db():
    with closing(_open_conn()) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id      TEXT PRIMARY KEY,
                balance TEXT NOT NULL
            )
        """)
    log.info("DB schema ready at %s", _db_path())

def truncate_all():
    with closing(_open_conn()) as conn:
        conn.execute("DELETE FROM accounts")


def seed_if_empty() -> None:
    """Insert demo accounts if the table is empty (used for local dev/demo)."""
    from decimal import Decimal
    with closing(_open_conn()) as conn:
        (n,) = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()
        if n:
            return
        rows = [
            ("12345", str(Decimal("10500.00"))),
            ("777",   str(Decimal("12015.00"))),
            ("a111",  str(Decimal("5040.00"))),
            ("007",   str(Decimal("47000.00"))),
        ]
        conn.executemany("INSERT INTO accounts(id, balance) VALUES(?, ?)", rows)
    log.info("DB seed inserted %d demo accounts", len(rows))


def account_exists(account_id: str) -> bool:
    with closing(_open_conn()) as conn:
        row = conn.execute("SELECT 1 FROM accounts WHERE id=?", (account_id,)).fetchone()
        return row is not None

def get_balance(account_id: str) -> Decimal | None:
    with closing(_open_conn()) as conn:
        row = conn.execute("SELECT balance FROM accounts WHERE id=?", (account_id,)).fetchone()
        return Decimal(row[0]) if row else None

def create_account(account_id: str, initial: Decimal) -> Decimal:
    with closing(_open_conn()) as conn:
        conn.execute("INSERT INTO accounts (id, balance) VALUES (?, ?)", (account_id, str(initial)))
        return initial

def deposit(account_id: str, amount: Decimal) -> Decimal | None:
    """
    Atomically add `amount` to balance.
    Returns new balance, or None if the account doesn't exist.
    """
    with closing(_open_conn()) as conn:
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        try:
            row = cur.execute("SELECT balance FROM accounts WHERE id=?", (account_id,)).fetchone()
            if not row:
                cur.execute("ROLLBACK")
                return None
            old_bal = Decimal(row[0])
            new_bal = old_bal + amount
            cur.execute("UPDATE accounts SET balance=? WHERE id=?", (str(new_bal), account_id))
            cur.execute("COMMIT")
            log.info("db.deposit id=%s amount=%s new=%s", account_id, amount, new_bal)
            return new_bal
        except Exception:
            cur.execute("ROLLBACK")
            raise

def withdraw(account_id: str, amount: Decimal) -> Decimal | None:
    """
        Atomically subtract `amount` from balance.
        Returns:
          - new balance on success
          - None if account is missing
          - old balance (unchanged) if insufficient funds (signal for repo to map to 400)
    """
    with closing(_open_conn()) as conn:
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        try:
            row = cur.execute("SELECT balance FROM accounts WHERE id=?", (account_id,)).fetchone()
            if not row:
                cur.execute("ROLLBACK")
                return None
            old_bal = Decimal(row[0])
            if amount > old_bal:
                cur.execute("ROLLBACK")
                return old_bal  # repo maps to 400
            new_bal = old_bal - amount
            cur.execute("UPDATE accounts SET balance=? WHERE id=?", (str(new_bal), account_id))
            cur.execute("COMMIT")
            log.info("db.withdraw id=%s amount=%s new=%s", account_id, amount, new_bal)
            return new_bal
        except Exception:
            cur.execute("ROLLBACK")
            raise