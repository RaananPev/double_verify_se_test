import os
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient

# IMPORTANT: import the app factory, not the module-level app
from src.app import create_app
from src.db import init_db

# ---------- per-session app & DB wiring ----------

@pytest.fixture(scope="session")
def tmp_db_path():
    # Use a temporary file-backed SQLite DB (isolated, persists across connections for one test run)
    with tempfile.TemporaryDirectory() as d:
        tmp_db_path = os.path.join(d, "test.sqlite3")
        os.environ["ATM_DB_PATH"] = tmp_db_path
        yield tmp_db_path  # removed when directory is cleaned up


@pytest.fixture(scope="session")
def app(tmp_db_path):
    # Point the app to the temp DB before creating it
    os.environ["ATM_DB_PATH"] = tmp_db_path
    # If your seed_if_empty() always seeds, and you want a pristine DB, you can optionally disable seeding via:
    # os.environ["ATM_DISABLE_SEED"] = "1"   # only if your seed code respects this env
    init_db()  # ensure schema exists for this DB path
    return create_app()


@pytest.fixture()
def client(app):
    # Fresh client per test for clean state; DB file persists across tests in this session
    return TestClient(app)


# ---------- helpers ----------

def acct() -> str:
    return f"acct_{uuid.uuid4().hex[:12]}"

def create_account(client: TestClient, account_id: str, initial_balance: float | int = 0):
    # ALWAYS send a JSON body so Content-Type: application/json is set.
    payload = {"initial_balance": initial_balance} if initial_balance is not None else {}
    return client.post(f"/accounts/{account_id}", json=payload)  # <-- no "or None"

def get_balance(client: TestClient, a: str) -> float:
    r = client.get(f"/accounts/{a}/balance")
    assert r.status_code == 200
    return r.json()["balance"]

def deposit(client: TestClient, a: str, amount):
    return client.post(f"/accounts/{a}/deposit", json={"amount": amount})

def withdraw(client: TestClient, a: str, amount):
    return client.post(f"/accounts/{a}/withdraw", json={"amount": amount})


# ---------- basic availability ----------

def test_health_ok(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ---------- happy path + persistence ----------

def test_balance_starts_at_zero_and_persists(client: TestClient):
    a = acct()
    r = create_account(client, a)
    assert r.status_code == 200
    # assert r.status_code == 201
    bal = get_balance(client, a)
    assert isinstance(bal, float)
    assert round(bal, 2) == 0.00
    assert Decimal(str(bal)).quantize(Decimal("0.01")) == Decimal("0.00")


# ---------- create account variations ----------

def test_create_account_with_initial_balance(client: TestClient):
    a = acct()
    r = create_account(client, a, initial_balance=12.34)
    # assert r.status_code == 201
    assert r.status_code == 200

    body = r.json()
    assert body["account_number"] == a
    assert round(body["balance"], 2) == 12.34
    assert round(get_balance(client, a), 2) == 12.34


def test_create_existing_account_conflict(client: TestClient):
    a = acct()
    assert create_account(client, a).status_code == 200
    r = create_account(client, a)
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "CONFLICT"


# ---------- deposit/withdraw/overdraw ----------

def test_deposit_and_withdraw_flow_and_overdraw_protection(client: TestClient):
    a = acct()
    assert create_account(client, a).status_code == 200  # used to be 201

    r = deposit(client, a, 100)
    assert r.status_code == 200
    assert isinstance(r.json()["balance"], float)
    assert round(r.json()["balance"], 2) == 100.00

    r = withdraw(client, a, 40)
    assert r.status_code == 200
    assert isinstance(r.json()["balance"], float)
    assert round(r.json()["balance"], 2) == 60.00

    r = withdraw(client, a, 1000)
    assert r.status_code == 400
    body = r.json()
    assert body["error"]["code"] == "BAD_REQUEST"
    assert body["error"]["message"] == "insufficient funds"
    assert round(get_balance(client, a), 2) == 60.00


def test_ops_on_missing_account_404(client: TestClient):
    missing = acct()
    # No create_account call here
    for fn in (get_balance,):
        r = client.get(f"/accounts/{missing}/balance")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "NOT_FOUND"

    for fn in (deposit, withdraw):
        r = fn(client, missing, 1)
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "NOT_FOUND"


# ---------- validation & error handling ----------

@pytest.mark.parametrize(
    "payload",
    [
        {},                             # missing field
        {"amount": 0},                  # zero
        {"amount": -1},                 # negative
        {"amount": "  "},               # whitespace (invalid)
        {"amount": "abc"},              # not a number (invalid)
        None,                           # no JSON body at all
    ],
)
def test_invalid_payloads_return_422_or_415(client: TestClient, payload):
    a = acct()
    assert create_account(client, a).status_code == 200  # used to be 201

    # If payload is None, send without json= to simulate wrong/missing body
    r = client.post(f"/accounts/{a}/deposit", json=payload) if payload is not None \
        else client.post(f"/accounts/{a}/deposit", content="not-json", headers={"Content-Type": "text/plain"})

    if payload is None:
        assert r.status_code == 415  # wrong content-type
    else:
        assert r.status_code == 422  # schema validation


def test_method_not_allowed_and_unknown_paths(client: TestClient):
    a = acct()
    assert create_account(client, a).status_code == 200  # used to be 201
    r = client.get(f"/accounts/{a}/deposit")   # wrong method
    assert r.status_code == 405
    assert client.get("/no/such/path").status_code == 404


# ---------- numeric formatting & rounding ----------

def test_balance_is_number_two_decimals(client: TestClient):
    a = acct()
    assert create_account(client, a).status_code == 200  # used to be 201
    deposit(client, a, 1)
    bal = get_balance(client, a)
    assert isinstance(bal, float)
    assert round(bal, 2) == 1.00
    assert Decimal(str(bal)).quantize(Decimal("0.01")) == Decimal("1.00")


@pytest.mark.parametrize(
    "inputs, expected",
    [
        ([0.01], 0.01),
        ([1.005], 1.01),                  # half-up rounding
        ([0.1] * 10, 1.00),               # cumulative rounding exact to 2dp
        ([2.015, 2.015], 4.03),           # repeated decimals
        ([9999999999999999.99], 9999999999999999.99),
    ],
)
def test_deposit_rounding_and_accumulation(client: TestClient, inputs, expected):
    a = acct()
    assert create_account(client, a).status_code == 200  # used to be 201
    for x in inputs:
        assert deposit(client, a, x).status_code == 200
    result = get_balance(client, a)
    assert isinstance(result, float)
    assert round(result, 2) == expected


def test_multiple_accounts_are_isolated(client: TestClient):
    a1, a2 = acct(), acct()
    assert create_account(client, a1, 0).status_code == 200  # used to be 201
    assert create_account(client, a2, 0).status_code == 200  # used to be 201
    deposit(client, a1, 10)
    deposit(client, a2, 5)
    assert round(get_balance(client, a1), 2) == 10.00
    assert round(get_balance(client, a2), 2) == 5.00


# ---------- concurrency (stress) ----------
def test_many_concurrent_deposits_should_sum_exactly(client: TestClient):
    """
    This test stresses concurrent updates. Your repo/db layer uses SQLite transactions,
    so we keep the parallelism modest.
    """
    a = acct()
    assert create_account(client, a).status_code == 200  # used to be 201

    def do_deposit():
        return deposit(client, a, 0.10).status_code

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(do_deposit) for _ in range(200)]  # total expected = 20.00
        assert all(f.result() == 200 for f in as_completed(futures))

    assert round(get_balance(client, a), 2) == 20.00


# ---------- extra polish: invariants & boundary cases ----------

def test_repeated_get_is_consistent(client: TestClient):
    a = acct()
    assert create_account(client, a).status_code == 200  # used to be 201
    deposit(client, a, 50)
    first = get_balance(client, a)
    for _ in range(10):
        assert get_balance(client, a) == first


def test_many_small_deposits_equal_one_large(client: TestClient):
    a1, a2 = acct(), acct()
    assert create_account(client, a1).status_code == 200  # used to be 201
    assert create_account(client, a2).status_code == 200  # used to be 201
    for _ in range(100):
        deposit(client, a1, 0.01)
    deposit(client, a2, 1.00)
    assert round(get_balance(client, a1), 2) == 1.00
    assert round(get_balance(client, a2), 2) == 1.00


def test_boundary_rounding_to_zero(client: TestClient):
    a = acct()
    assert create_account(client, a).status_code == 200  # used to be 201
    deposit(client, a, 0.0001)  # rounds away on presentation
    assert round(get_balance(client, a), 2) == 0.00


def test_withdraw_exact_balance_leaves_zero(client: TestClient):
    a = acct()
    assert create_account(client, a).status_code == 200  # used to be 201
    deposit(client, a, 42.42)
    r = withdraw(client, a, 42.42)
    assert r.status_code == 200
    assert isinstance(r.json()["balance"], float)
    assert round(r.json()["balance"], 2) == 0.00


def test_balance_invariant_sum_of_ops(client: TestClient):
    a = acct()
    assert create_account(client, a).status_code == 200  # used to be 201
    deposits = [10, 20, 30.55]
    withdrawals = [5, 15.55]
    for d in deposits:
        deposit(client, a, d)
    for w in withdrawals:
        withdraw(client, a, w)

    expected = sum(deposits) - sum(withdrawals)
    bal = Decimal(str(get_balance(client, a)))
    assert bal == Decimal(str(expected)).quantize(Decimal("0.01"))


def test_account_names_with_special_characters(client: TestClient):
    a = "abc-123_X"
    assert create_account(client, a).status_code == 200  # used to be 201
    deposit(client, a, 5)
    assert round(get_balance(client, a), 2) == 5.00


# ---------- account id validation (refined) ----------

@pytest.mark.parametrize("bad", [
    "a b",              # space
    "abc$",             # punctuation
    "אבי",              # non-ascii
    "x" * 65,           # too long
])
def test_account_id_invalid_422_reachable(client: TestClient, bad):
    # Reaches the route; FastAPI Path validator should 422
    r = client.get(f"/accounts/{bad}/balance")
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "UNPROCESSABLE_ENTITY"


@pytest.mark.parametrize("bad", [
    "",        # empty -> results in // in the path; route won't match
    "a\tb",    # control character -> httpx refuses to build URL
])
def test_account_id_unreachable_url_invalid_or_404(client: TestClient, bad):
    try:
        r = client.get(f"/accounts/{bad}/balance")
    except httpx.InvalidURL:
        return
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["code"] == "NOT_FOUND"


# ---------- strict Content-Type enforcement ----------

def test_deposit_rejects_non_json_content_type(client: TestClient):
    a = acct()
    assert create_account(client, a).status_code == 200  # used to be 201
    r = client.post(
        f"/accounts/{a}/deposit",
        content = "amount=10",  # raw body (intentionally wrong type)
        headers = {"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 415
    body = r.json()
    assert body["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_withdraw_rejects_missing_content_type(client: TestClient):
    a = acct()
    assert create_account(client, a).status_code == 200  # used to be 201
    r = client.post(
        f"/accounts/{a}/withdraw",
        content='{"amount": 10}'  # raw JSON string, but no Content-Type
    )
    assert r.status_code == 415
    body = r.json()
    assert body["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_deposit_accepts_valid_json(client: TestClient):
    a = acct()
    assert create_account(client, a).status_code == 200  # used to be 201
    r = client.post(
        f"/accounts/{a}/deposit",
        json={"amount": 10},  # httpx sets Content-Type: application/json
    )
    assert r.status_code == 200
    assert isinstance(r.json()["balance"], float)
    assert round(r.json()["balance"], 2) == 10.00



import pytest

# @pytest.mark.smoke
# def test_smoke_10k_small_deposits(client: TestClient):
#     """
#     Smoke/performance test: 10,000 deposits of 0.01 should total 100.00.
#     Uses JSON bodies so Content-Type is correct and keeps it sequential to
#     avoid flaky DB lock contention during heavy load.
#     """
#     a = acct()
#     assert create_account(client, a).status_code == 200  # or 201, if you return that
#
#     for _ in range(10_000):
#         r = client.post(f"/accounts/{a}/deposit", json={"amount": 0.01})
#         assert r.status_code == 200
#
#     # final balance must be exact to 2dp
#     assert round(get_balance(client, a), 2) == 100.00

