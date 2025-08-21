import re
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from fastapi.testclient import TestClient
from src.main import app, accounts  # import the in-memory store to reset state

client = TestClient(app)


# ---------- helpers ----------
def acct() -> str:
    return f"acct_{uuid.uuid4().hex[:12]}"

def get_balance(a: str):
    r = client.get(f"/accounts/{a}/balance")
    assert r.status_code == 200
    return r.json()["balance"]

def deposit(a: str, amount):
    return client.post(f"/accounts/{a}/deposit", json={"amount": amount})

def withdraw(a: str, amount):
    return client.post(f"/accounts/{a}/withdraw", json={"amount": amount})


# ---------- fixtures ----------
@pytest.fixture(autouse=True)
def clean_state():
    # ensure test isolation; avoids cross-test leakage
    accounts.clear()
    yield
    accounts.clear()


# ---------- basic availability ----------
def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ---------- happy path + persistence ----------
def test_balance_starts_at_zero_and_persists():
    a = acct()
    assert get_balance(a) == "0.00"                # auto-created at 0
    assert deposit(a, "100.50").json()["balance"] == "100.50"
    # another GET later returns same value
    assert get_balance(a) == "100.50"


# ---------- deposit/withdraw/overdraw ----------
def test_deposit_and_withdraw_flow_and_overdraw_protection():
    a = acct()
    r = deposit(a, 100)
    assert r.status_code == 200 and r.json()["balance"] == "100.00"

    r = withdraw(a, 40)
    assert r.status_code == 200 and r.json()["balance"] == "60.00"

    # overdraw returns 400 and does NOT change balance
    r = withdraw(a, 1000)
    assert r.status_code == 400
    assert r.json()["detail"] == "insufficient funds"
    assert get_balance(a) == "60.00"


# ---------- validation & error handling ----------
@pytest.mark.parametrize(
    "payload",
    [
        {},                             # missing field
        {"amount": 0},                  # zero
        {"amount": -1},                 # negative
        {"amount": "  "},               # whitespace
        {"amount": "abc"},              # not a number
        None,                           # no JSON body at all
    ],
)
def test_invalid_payloads_return_422(payload):
    a = acct()
    # If payload is None, send without json= to simulate wrong/missing body
    r = client.post(f"/accounts/{a}/deposit", json=payload) if payload is not None \
        else client.post(f"/accounts/{a}/deposit", content="not-json", headers={"Content-Type": "text/plain"})
    assert r.status_code == 422


def test_method_not_allowed_and_unknown_paths():
    a = acct()
    r = client.get(f"/accounts/{a}/deposit")   # wrong method
    assert r.status_code == 405
    assert client.get("/no/such/path").status_code == 404


# ---------- formatting & rounding ----------
def test_balance_format_is_string_with_two_decimals():
    a = acct()
    deposit(a, 1)
    bal = get_balance(a)
    assert isinstance(bal, str)
    assert re.fullmatch(r"\d+(\.\d{2})", bal)

@pytest.mark.parametrize(
    "inputs, expected",
    [
        (["0.01"], "0.01"),
        (["1.005"], "1.01"),                  # half-up rounding
        (["0.1"] * 10, "1.00"),               # cumulative rounding should be exact
        (["2.015", "2.015"], "4.03"),         # repeated rounding
        (["9999999999999999.99"], "9999999999999999.99"),  # very large but valid
    ],
)
def test_deposit_rounding_and_accumulation(inputs, expected):
    a = acct()
    for x in inputs:
        assert deposit(a, x).status_code == 200
    assert get_balance(a) == expected


def test_multiple_accounts_are_isolated():
    a1, a2 = acct(), acct()
    deposit(a1, 10)
    deposit(a2, 5)
    assert get_balance(a1) == "10.00"
    assert get_balance(a2) == "5.00"


# ---------- concurrency (stress) ----------
def test_many_concurrent_deposits_should_sum_exactly():
    """
    This test stresses concurrent updates. Without a lock around:
        bal = accounts[a]; accounts[a] = bal + amount
    lost updates can occur. Marked xfail to highlight the gap; remove xfail
    after adding a threading.Lock around updates in the app.
    """
    a = acct()

    def do_deposit():
        return deposit(a, "0.10").status_code

    with ThreadPoolExecutor(max_workers=16) as ex:
        futures = [ex.submit(do_deposit) for _ in range(200)]  # total expected = 20.00
        assert all(f.result() == 200 for f in as_completed(futures))

    assert get_balance(a) == "20.00"





# ---------- extra polish: invariants & boundary cases ----------

def test_repeated_get_is_consistent():
    a = acct()
    deposit(a, "50")
    first = get_balance(a)
    for _ in range(10):
        assert get_balance(a) == first


def test_many_small_deposits_equal_one_large():
    a1, a2 = acct(), acct()
    # 100 deposits of 0.01
    for _ in range(100):
        deposit(a1, "0.01")
    # one deposit of 1.00
    deposit(a2, "1.00")
    assert get_balance(a1) == get_balance(a2) == "1.00"


def test_boundary_rounding_to_zero():
    a = acct()
    deposit(a, "0.0001")  # too small, rounds away
    assert get_balance(a) == "0.00"


def test_withdraw_exact_balance_leaves_zero():
    a = acct()
    deposit(a, "42.42")
    r = withdraw(a, "42.42")
    assert r.status_code == 200
    assert r.json()["balance"] == "0.00"


def test_balance_invariant_sum_of_ops():
    a = acct()
    deposits = [10, 20, 30.55]
    withdrawals = [5, 15.55]
    for d in deposits:
        deposit(a, d)
    for w in withdrawals:
        withdraw(a, w)

    expected = sum(deposits) - sum(withdrawals)
    # Use Decimal to compare
    from decimal import Decimal
    bal = Decimal(get_balance(a))
    assert bal == Decimal(str(expected)).quantize(Decimal("0.01"))


def test_account_names_with_special_characters():
    a = "abc-123_X"
    deposit(a, 5)
    assert get_balance(a) == "5.00"



def test_smoke_many_operations_quickly():
    """
    Smoke/performance test: ensure the API can handle a large number of sequential operations
    without drifting balance or slowing down too much.
    """
    a = acct()
    # 10k small deposits
    for _ in range(10_000):
        r = deposit(a, "0.01")
        assert r.status_code == 200

    # final balance should be exactly 100.00 (10,000 * 0.01)
    assert get_balance(a) == "100.00"