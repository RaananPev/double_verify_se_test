# ATM System API

A backend implementation of a simple **ATM System**, built with **FastAPI** and deployed on **Heroku**.  
The service allows users to perform operations on accounts such as **balance retrieval, deposits, and withdrawals**, with robust error handling, middleware enforcement, and automated testing.

Repository: [double_verify_se_test](https://github.com/RaananPev/double_verify_se_test.git)  
Deployed server: [ATM API on Heroku](https://atm-api-8e3e62cb3046.herokuapp.com)

---

## 📌 Assignment Overview

The project was developed as a solution to the Hackerrank **ATM System Mini Project**.  
Requirements included:

- **API Endpoints**:
  - Get balance: `GET /accounts/{account_number}/balance`
  - Withdraw: `POST /accounts/{account_number}/withdraw`
  - Deposit: `POST /accounts/{account_number}/deposit`
  - Account Creation: `POST /accounts/{account_number}` **(Extra Feature)**
 

- **Account model**:
  - `account_number`: unique identifier
  - `balance`: numeric balance of the account

- **Server-side only implementation**  
- **Deployment to a cloud provider (Heroku)**  
- **README documentation with approach, design decisions, and challenges**  

---

## 🛠️ Technologies

- **FastAPI** — framework for high-performance APIs.
- **SQLite** — lightweight database used for persistence.
- **Uvicorn** — ASGI server for local and production execution.
- **Pytest** — unit, integration, and smoke testing.
- **HTTPX** — HTTP client for remote server verification.
- **Heroku** — deployment and public hosting.
- **Logging** — structured logging with correlation IDs for observability.

---

## 📐 System Design & Approach

### 1. API Layer (`src/api.py`)
Implements the business endpoints:
- **Account creation** (`POST /accounts/{account_number}`)
- **Get balance** (`GET /accounts/{account_number}/balance`)
- **Deposit** (`POST /accounts/{account_number}/deposit`)
- **Withdraw** (`POST /accounts/{account_number}/withdraw`)

Each endpoint:
- Returns structured JSON responses.
- Validates input strictly (e.g., rejecting non-JSON requests or invalid account IDs).
- Provides clear error codes (e.g., `NOT_FOUND`, `BAD_REQUEST`, `CONFLICT`).

---

### 2. Application Factory (`src/app.py`)
Encapsulates setup logic:
- **Database Initialization** (`init_db` + `seed_if_empty`)
- **Middlewares**:
  - `EnforceJSONMiddleware`: ensures modifying requests (`POST`, `PUT`, `PATCH`) use `application/json`.
  - `RequestIDMiddleware`: injects an `X-Request-ID` header into each response for traceability.
- **Exception Handling**:
  - Converts FastAPI/Starlette exceptions into a consistent `{"error": {"code": ..., "message": ...}}` format.
  - Validation errors (`422`) and unsupported content types (`415`) are reported clearly.

---

### 3. Database Layer (`src/db.py`)
- SQLite chosen for simplicity and reliability.
- Each account record is stored persistently.
- During **local tests**, a **temporary SQLite file** is created and discarded to isolate test runs.
- In production (Heroku), the DB path is file-backed (`atm.db`).

---

### 4. Logging (`src/logger_config.py`)
- Unified logging with Python’s `logging` module.
- Injects **request IDs** into every log line.
- Startup/shutdown events log lifecycle changes (`🚀 started`, `🛑 stopped`).
- Warnings are logged for validation and error scenarios.
- At midnight, the system automatically rotates logs: the log file for the previous day is archived, and a new one is created for the current day.
- Archived logs are retained for one week before being deleted.
---

## 🚀 Running Locally

### Clone & Install
```bash
git clone https://github.com/RaananPev/double_verify_se_test.git
cd double_verify_se_test
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Run the Server
```bash
uvicorn src.app:app --reload
```

Server will be available at:  
👉 http://127.0.0.1:8000

---
## Default Users (Seed Data)

When the application is initialized, the database is seeded with a few **default accounts**.  
These accounts are created automatically and are useful for testing and demonstration.

| Account Number | Initial Balance |
|----------------|-----------------|
| `12345`        | 10,500.00       |
| `777`          | 12,015.00       |
| `a111`         | 5,040.00        |
| `007`          | 47,000.00       |

## 📖 API Usage Examples

### Create Account
```bash
curl -X POST http://127.0.0.1:8000/accounts/alice \
  -H "Content-Type: application/json" \
  -d '{"initial_balance": 100}'
```

### Get Balance
```bash
curl http://127.0.0.1:8000/accounts/alice/balance
```

### Deposit
```bash
curl -X POST http://127.0.0.1:8000/accounts/alice/deposit \
  -H "Content-Type: application/json" \
  -d '{"amount": 50}'
```

### Withdraw
```bash
curl -X POST http://127.0.0.1:8000/accounts/alice/withdraw \
  -H "Content-Type: application/json" \
  -d '{"amount": 20}'
```

---

## ✅ Testing

### Local Tests (`tests/test_api.py`)
Run against a **temporary SQLite DB** (isolated from development/production).  

Covers:
- Account creation (with and without initial balance)
- Duplicate account conflict handling
- Deposits, withdrawals, and overdraw protection
- Numeric formatting & rounding edge cases
- Account ID validation (length, invalid characters, etc.)
- Error handling for 404, 405, 409, 415, 422
- Concurrency stress test (200 parallel deposits with transaction safety)
- Boundary cases (exact withdrawals, tiny deposits)

Run locally:
```bash
PYTHONPATH=. pytest -q
```

---

### Remote Smoke Tests (`tests/test_smoke_remote.py`)
Run against the **deployed Heroku API**.  

Covers:
- Health check (`/health`)
- Account lifecycle: create, deposit, withdraw, balance checks
- Overdraw protection
- Content-Type enforcement
- Concurrency sanity (parallel deposits on the live API)

Run with:
```bash
export ATM_API_URL="https://atm-api-8e3e62cb3046.herokuapp.com"
PYTHONPATH=. pytest -q
```

> **Note**: If `ATM_API_URL` is not set, remote tests are skipped.

---

## 📦 Deployment

Deployment target: **Heroku** (free dyno).  

**Procfile**:
```text
web: uvicorn src.app:app --host=0.0.0.0 --port=${PORT:-5000}
```

Deploy steps:
```bash
heroku create atm-api
git push heroku main
heroku open
```

Live server: [https://atm-api-8e3e62cb3046.herokuapp.com](https://atm-api-8e3e62cb3046.herokuapp.com)

---

## ⚠️ Challenges & Design Decisions

- **Database vs. In-Memory**  
  SQLite chosen over in-memory Python structures for persistence and durability.  

- **Content-Type Enforcement**  
  Middleware was added to reject non-JSON requests early, simplifying validation logic.  

- **Concurrency**  
  SQLite has limited concurrency handling. Concurrency tests were tuned to modest parallelism to validate transaction correctness without exceeding SQLite’s locking model.  

- **Testing Philosophy**  
  Local tests guarantee correctness in isolation.  
  Remote smoke tests guarantee that the **deployed server works as intended**, not just local code.  

---

## 📎 Submission Info

- **Repository**: [double_verify_se_test](https://github.com/RaananPev/double_verify_se_test.git)  
- **Hosted API**: [https://atm-api-8e3e62cb3046.herokuapp.com](https://atm-api-8e3e62cb3046.herokuapp.com)  
- **README**: This file (detailed explanation, design decisions, challenges, usage, and tests).  
