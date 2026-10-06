# Family Expense Manager - Backend API (Phase 1 to 9)

Production-ready Python FastAPI REST API backend for the Family Expense Manager Android Flutter mobile application.

Managed with **Python 3.14** and **uv**.

---

## Tech Stack
- **Language**: Python 3.14
- **Package & Environment Manager**: `uv`
- **Framework**: FastAPI
- **Database**: PostgreSQL 16/17
- **ORM**: SQLAlchemy 2.x (Async with `asyncpg`, Typed Models, DeclarativeBase)
- **Migrations**: Alembic (Async enabled)
- **Settings & Validation**: Pydantic v2 & `pydantic-settings`
- **Security & Hashes**: `pwdlib[argon2]`, `PyJWT`, `secrets`, `hashlib` (SHA-256)
- **Server**: Uvicorn
- **Testing**: Pytest, `pytest-asyncio`, and `httpx`
- **Containerization**: Docker & Docker Compose

---

## Financial Reporting & Dashboard Architecture (Phase 9)

Phase 9 implements comprehensive financial analytics, reporting, and dashboard feeds powered 100% by PostgreSQL aggregation queries without loading raw transactions into application memory.

### Key Rules & Features:
1. **Consolidated Dashboard (`/api/v1/dashboard`)**:
   - Computes total income, total expenses, net remaining balance, and savings rate.
   - Calculates shared vs. personal expenses via SQL `CASE` expressions.
   - Perspective-aware breakdown: evaluates "My Expenses" vs. "Spouse Expenses" dynamically based on the authenticated caller.
   - Integrates current active budget statuses, warnings, and overall family budget consumption.
   - Unified recent transaction feed combining expenses and incomes sorted chronologically.
2. **Annual Monthly Trend Report (`/api/v1/reports/monthly`)**:
   - Aggregates income, expenses, net savings, and savings rates across months 1 through 12 using `EXTRACT(MONTH FROM ...)` and `SUM()`.
   - Computes annual totals and overall savings rate.
3. **Category Spending & Income Distribution (`/api/v1/reports/categories`)**:
   - Groups transactions by category with total amounts, percentage contributions, and transaction counts.
   - Supports both `type=expense` and `type=income`.
4. **Member Contributions & "Husband vs. Wife" Spending (`/api/v1/reports/members`)**:
   - Compares financial activity across all active family members.
   - Calculates total paid, percentage of total expenses, personal expenses, shared expenses, and income earned per member.
5. **Payment Instrument Distribution (`/api/v1/reports/payment-methods`)**:
   - Aggregates expenses across payment channels (`credit_card`, `cash`, `upi`, `debit_card`, `bank_transfer`, `other`).
6. **Date Range & Temporal Filtering**:
   - All reports support flexible date boundaries: `from_date` / `to_date`, `month` / `year`, or `year` only.
   - Defaults cleanly to current calendar month.
7. **Strict Multi-Tenant Security & Decimal Precision**:
   - All metrics are isolated strictly to the authenticated caller's family.
   - Monetary values use exact `Decimal` precision quantized to two decimal places.

---

## Complete API Reference

### Dashboard (`/api/v1/dashboard`)
| Method | Endpoint | Description | Auth Required | Status Code |
| :--- | :--- | :--- | :---: | :---: |
| `GET` | `/api/v1/dashboard` | Unified financial summary (income, expenses, my/spouse, shared/personal, budget health, recent feed) | **Bearer JWT** | `200 OK` |

### Reports (`/api/v1/reports`)
| Method | Endpoint | Description | Auth Required | Status Code |
| :--- | :--- | :--- | :---: | :---: |
| `GET` | `/api/v1/reports/monthly` | Annual month-by-month financial performance (`?year=`) | **Bearer JWT** | `200 OK` |
| `GET` | `/api/v1/reports/categories` | Category distribution & percentage breakdown (`?type=expense\|income`) | **Bearer JWT** | `200 OK` |
| `GET` | `/api/v1/reports/members` | Member contribution & "Husband vs Wife" spending comparison | **Bearer JWT** | `200 OK` |
| `GET` | `/api/v1/reports/payment-methods` | Breakdown across payment methods (credit card, cash, UPI, etc.) | **Bearer JWT** | `200 OK` |

### Budgets (`/api/v1/budgets`)
| Method | Endpoint | Description | Auth Required | Status Code |
| :--- | :--- | :--- | :---: | :---: |
| `GET` | `/api/v1/budgets` | List family budgets with SQL-aggregated spending (`?month=&year=&category_id=`) | **Bearer JWT** | `200 OK` |
| `POST` | `/api/v1/budgets` | Create monthly category budget allocation | **Bearer JWT** | `201 Created` |
| `GET` | `/api/v1/budgets/{id}` | Retrieve single budget with real-time spending & warning status | **Bearer JWT** | `200 OK` |
| `PUT` | `/api/v1/budgets/{id}` | Update budget allocation or target period | **Bearer JWT** | `200 OK` |
| `DELETE` | `/api/v1/budgets/{id}` | Delete monthly budget | **Bearer JWT** | `200 OK` |

### Categories (`/api/v1/categories`)
| Method | Endpoint | Description | Auth Required | Status Code |
| :--- | :--- | :--- | :---: | :---: |
| `GET` | `/api/v1/categories` | List categories accessible to family (defaults + custom, filterable by `?type=`) | **Bearer JWT** | `200 OK` |
| `POST` | `/api/v1/categories` | Create new custom category for the active family | **Bearer JWT** | `201 Created` |
| `PUT` | `/api/v1/categories/{id}` | Update existing custom family category | **Bearer JWT** | `200 OK` |
| `DELETE` | `/api/v1/categories/{id}` | Delete unused custom family category | **Bearer JWT** | `200 OK` |

### Income (`/api/v1/income`)
| Method | Endpoint | Description | Auth Required | Status Code |
| :--- | :--- | :--- | :---: | :---: |
| `GET` | `/api/v1/income` | List family income (paginated, filtered, sorted) | **Bearer JWT** | `200 OK` |
| `POST` | `/api/v1/income` | Record a new income entry | **Bearer JWT** | `201 Created` |
| `GET` | `/api/v1/income/{id}` | Retrieve single income details | **Bearer JWT** | `200 OK` |
| `PUT` | `/api/v1/income/{id}` | Update existing income record | **Bearer JWT** | `200 OK` |
| `DELETE` | `/api/v1/income/{id}` | Permanently delete income record | **Bearer JWT** | `200 OK` |

### Expenses (`/api/v1/expenses`)
| Method | Endpoint | Description | Auth Required | Status Code |
| :--- | :--- | :--- | :---: | :---: |
| `GET` | `/api/v1/expenses` | List family expenses (paginated, filtered, sorted) | **Bearer JWT** | `200 OK` |
| `POST` | `/api/v1/expenses` | Record a new expense | **Bearer JWT** | `201 Created` |
| `GET` | `/api/v1/expenses/{id}` | Retrieve single expense details | **Bearer JWT** | `200 OK` |
| `PUT` | `/api/v1/expenses/{id}` | Update existing expense | **Bearer JWT** | `200 OK` |
| `DELETE` | `/api/v1/expenses/{id}` | Permanently delete expense | **Bearer JWT** | `200 OK` |

### Families (`/api/v1/families`)
| Method | Endpoint | Description | Auth Required | Status Code |
| :--- | :--- | :--- | :---: | :---: |
| `POST` | `/api/v1/families` | Create household (Creator = OWNER) | **Bearer JWT** | `201 Created` |
| `GET` | `/api/v1/families/current` | Get active family details | **Bearer JWT** | `200 OK` |
| `PUT` | `/api/v1/families/current` | Update family settings (OWNER only) | **Bearer JWT** | `200 OK` |
| `POST` | `/api/v1/families/invite` | Invite spouse/member (OWNER only) | **Bearer JWT** | `201 Created` |
| `POST` | `/api/v1/families/invite/accept` | Accept invitation using token | **Bearer JWT** | `200 OK` |
| `GET` | `/api/v1/families/members` | List family members | **Bearer JWT** | `200 OK` |

### Authentication (`/api/v1/auth`) & Users (`/api/v1/users`)
| Method | Endpoint | Description | Auth Required | Status Code |
| :--- | :--- | :--- | :---: | :---: |
| `POST` | `/api/v1/auth/register` | Register new user account | No | `201 Created` |
| `POST` | `/api/v1/auth/login` | Authenticate email & password | No | `200 OK` |
| `POST` | `/api/v1/auth/refresh` | Rotate and issue new tokens | No | `200 OK` |
| `POST` | `/api/v1/auth/logout` | Revoke active refresh token | No | `200 OK` |
| `GET` | `/api/v1/users/me` | Fetch authenticated profile | **Bearer JWT** | `200 OK` |
| `PUT` | `/api/v1/users/me` | Update authenticated profile | **Bearer JWT** | `200 OK` |

---

## Quickstart & Verification

```bash
# 1. Install dependencies
make install

# 2. Run Database Migrations
make migrate

# 3. Seed Default System Categories (Safe & Repeatable)
make seed

# 4. Run Test Suite (80 tests)
make test

# 5. Start Development Server
make dev
```
