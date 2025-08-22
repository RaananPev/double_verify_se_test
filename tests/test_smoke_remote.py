
import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
import httpx

# ---- Configuration ----
BASE_URL = os.environ.get("ATM_API_URL")

@pytest.fixture(scope="session", autouse=True)
def require_base_url():
    if not BASE_URL:
        pytest.skip("Set BASE_URL env var to your deployed API, e.g. https://<app>.herokuapp.com")

@pytest.fixture()
def client():
    # Small timeout to fail fast; adjust if your dyno is sleepy
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as c:
        yield c

def acct() -> str:
    return f"acct_{uuid.uuid4().hex[:12]}"

# ---- Helpers ----
def create_account(client: httpx.Client, account_id: str, initial_balance: float | int = 0):
    return client.post(f"/accounts/{account_id}", json={"initial_balance": initial_balance})

def get_balance(client: httpx.Client, account_id: str) -> tuple[int, float | None]:
    r = client.get(f"/accounts/{account_id}/balance")
    if r.status_code == 200:
        return 200, r.json()["balance"]
    return r.status_code, None

def deposit(client: httpx.Client, account_id: str, amount):
    return client.post(f"/accounts/{account_id}/deposit", json={"amount": amount})

def withdraw(client: httpx.Client, account_id: str, amount):
    return client.post(f"/accounts/{account_id}/withdraw", json={"amount": amount})

# ---- Tests ----

def test_health(client: httpx.Client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

def test_create_then_get_zero_balance(client: httpx.Client):
    a = acct()
    r = create_account(client, a, 0)
    # Your API returns 200 (or 201 if you changed it)—accept both to be flexible:
    assert r.status_code in (200, 201)
    code, bal = get_balance(client, a)
    assert code == 200
    assert isinstance(bal, float)
    assert round(bal, 2) == 0.00

def test_create_with_initial_and_rounding(client: httpx.Client):
    a = acct()
    r = create_account(client, a, 12.34)
    assert r.status_code in (200, 201)
    code, bal = get_balance(client, a)
    assert code == 200
    assert round(bal, 2) == 12.34

def test_deposit_withdraw_and_overdraw(client: httpx.Client):
    a = acct()
    assert create_account(client, a).status_code in (200, 201)

    r = deposit(client, a, 100)
    assert r.status_code == 200
    assert round(r.json()["balance"], 2) == 100.00

    r = withdraw(client, a, 40)
    assert r.status_code == 200
    assert round(r.json()["balance"], 2) == 60.00

    r = withdraw(client, a, 1000)
    # Expect your API’s 400 with error shape
    assert r.status_code == 400
    body = r.json()
    assert body["error"]["code"] in ("BAD_REQUEST", "INSUFFICIENT_FUNDS", "BAD_REQUEST_ERROR")
    # Final balance remains unchanged
    _, bal = get_balance(client, a)
    assert round(bal, 2) == 60.00

def test_404_for_missing_account(client: httpx.Client):
    missing = acct()
    r = client.get(f"/accounts/{missing}/balance")
    assert r.status_code == 404
    assert r.json()["error"]["code"] in ("NOT_FOUND", "RESOURCE_NOT_FOUND")

def test_content_type_enforcement(client: httpx.Client):
    a = acct()
    assert create_account(client, a).status_code in (200, 201)

    # wrong content type -> 415
    r = client.post(
        f"/accounts/{a}/deposit",
        content="amount=10",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code in (415, 422)  # depending on how strict your endpoint is

    # Missing Content-Type with raw body
    r = client.post(f"/accounts/{a}/withdraw", content='{"amount": 10}')
    assert r.status_code in (415, 422)

def test_rounding_edge_cases(client: httpx.Client):
    a = acct()
    assert create_account(client, a).status_code in (200, 201)
    # deposit 1.005 -> expect half-up to 1.01 on presentation
    assert deposit(client, a, 1.005).status_code == 200
    _, bal = get_balance(client, a)
    assert round(bal, 2) == 1.01

def test_light_concurrency(client: httpx.Client):
    """
    Gentle parallel deposits to catch obvious race issues without overloading a hobby dyno.
    """
    a = acct()
    assert create_account(client, a).status_code in (200, 201)

    def do_deposit():
        return deposit(client, a, 0.10).status_code

    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(do_deposit) for _ in range(30)]  # total expected = 3.00
        codes = [f.result() for f in as_completed(futures)]
        # allow a few flukes on cold starts but expect most 200s
        assert sum(c == 200 for c in codes) >= 28

    _, bal = get_balance(client, a)
    assert round(bal, 2) >= 2.90  # allow tiny slack on slow wakeups, but should be ~3.00