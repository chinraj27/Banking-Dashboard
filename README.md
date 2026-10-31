# Banking Products Dashboard

A full-stack demo that shows a customer's savings account, credit card, personal loan and
investment on one screen. **All data is mock data.** Nothing connects to a real bank or processes payments.

```
Browser ──► Nginx :80 ──┬──► React app (served by its own nginx container)
                        └──► /api ──► FastAPI ──┬──► PostgreSQL  users, products, transactions, applications
                                                ├──► MongoDB     activity logs, audit logs, product metadata
                                                └──► Redis       response cache, login sessions
```

## What is included

| Area | Details |
|---|---|
| Frontend | React 18 + Vite, React Router, Axios, Recharts. Plain CSS, responsive for desktop, tablet and mobile. |
| Backend | FastAPI, SQLAlchemy 2, Pydantic v2, JWT (PyJWT), bcrypt, Swagger at `/api/docs`. |
| Data | PostgreSQL (8 tables, indexes, foreign keys), MongoDB, Redis. SQL in `backend/sql/schema.sql`. |
| DevOps | Dockerfiles, `docker-compose.yml`, Nginx reverse proxy, GitHub Actions pipeline. |
| Cloud | AWS and Azure guides in `docs/DEPLOYMENT.md`. |
| Tests | 30 backend tests (pytest) and 5 frontend unit tests (Vitest). |

## Run with Docker (Windows PowerShell)

Prerequisite: Docker Desktop, running.

```powershell
cd banking-dashboard
Copy-Item .env.example .env

# Generate a JWT secret and write it into .env
$secret = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 48 | ForEach-Object { [char]$_ })
(Get-Content .env) -replace '^JWT_SECRET=.*', "JWT_SECRET=$secret" | Set-Content .env

docker compose up --build
```

Then open:

- App: <http://localhost>
- API docs (Swagger): <http://localhost/api/docs>
- Health check: <http://localhost/api/health>

Demo logins (created on first start while `SEED_DEMO_DATA=true`):

| Role | Email | Password |
|---|---|---|
| Customer | `demo@bank.com` | `Demo@1234` |
| Admin | `admin@bank.com` | `Admin@1234` |

Useful commands:

```powershell
docker compose ps                    # service status and health
docker compose logs -f backend       # follow API logs
docker compose down                  # stop, keep data
docker compose down -v               # stop and delete all data (fresh start)
```

The `.env` passwords are used when each database container is first created. If you change them later,
run `docker compose down -v` so the databases are recreated.

## Run without Docker (development)

The backend falls back to SQLite plus in-memory Mongo/Redis stand-ins when those URLs are empty,
so you can develop with only Python and Node installed.

```powershell
# Terminal 1: API on http://localhost:8000
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload

# Terminal 2: UI on http://localhost:5173 (proxies /api to :8000)
cd frontend
npm install
npm run dev
```

To use the real databases from your machine, start only those containers
(`docker compose up postgres mongo redis`, after adding `ports:` to them) and set
`DATABASE_URL`, `MONGO_URL` and `REDIS_URL` in `backend/.env`.

## Tests

```powershell
cd backend;  pytest -q          # API, auth, RBAC, filters, caching, masking
cd frontend; npm test           # formatting helpers
cd backend;  ruff check .       # code quality
```

Backend tests need no running services: they use in-memory SQLite and the in-memory Mongo/Redis fallbacks.

## API summary

All responses use `{"success": true, "data": ..., "message": ...}`. Errors use
`{"success": false, "error": {"code": 401, "message": "..."}}`. Everything except register, login and health needs `Authorization: Bearer <token>`.

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/register` | Create a customer account (201) |
| POST | `/api/auth/login` | Returns a JWT and creates a Redis session |
| POST | `/api/auth/logout` | Revokes the session |
| GET | `/api/auth/me` | Current user |
| GET | `/api/products` | List. Query: `category`, `status`, `search`, `sort_by` (`date`/`balance`), `order` |
| GET | `/api/products/category/{category}` | Products in one category |
| GET | `/api/products/{id}` | Details plus Mongo metadata |
| POST | `/api/applications` | Submit a product application (201) |
| GET | `/api/applications` | Your applications |
| GET | `/api/dashboard/stats` | Totals, portfolio breakdown, 6-month cash flow |
| GET | `/api/transactions` | Query: `product_id`, `txn_type`, `limit`, `offset` |
| GET | `/api/activity` | Your recent activity (from MongoDB) |
| GET | `/api/admin/users` | Admin role only |
| GET | `/api/health` | Postgres, Redis and Mongo status |

## How the data stores are used

- **PostgreSQL**: `users`, `banking_products` (one row per product, with a category-specific child row in
  `savings_accounts`, `credit_cards`, `loans` or `investments`), `transactions`, `product_applications`.
- **MongoDB**: `activity_logs` (logins, product views), `audit_logs` (applications), `product_metadata`
  (flexible per-category features and fees, shown on the product detail page).
- **Redis**: caches product lists and dashboard stats for 60 seconds per user (cleared when an application is
  submitted) and stores one key per login session so logout takes effect immediately.

## Security

- Passwords hashed with bcrypt; never returned by any endpoint.
- JWT access tokens (60 minutes by default) plus a Redis session check, so a logged-out token stops working.
- Role-based access: `customer` and `admin`. Customers can only read their own products and transactions.
- All input validated by Pydantic. Queries go through SQLAlchemy bound parameters (no string-built SQL).
- Account and card numbers are masked in every API response (`**** **** **** 3456`).
- Validation errors never echo submitted values. Unexpected errors return a generic 500 message and are logged server-side.
- CORS limited to `CORS_ORIGINS`. Secrets come from environment variables; `.env` is git-ignored.

Known limits of this demo, to address before anything real: the JWT is kept in `localStorage` (an HttpOnly
cookie is safer against XSS); there is no login rate limiting or account lockout; there is no TLS inside the
compose stack (terminate HTTPS at the load balancer or Nginx); and `schema.sql` plus `create_all` is used
instead of a migration tool such as Alembic.

## Project structure

```
banking-dashboard/
├── frontend/            React app (components, pages, services, hooks, utils)
├── backend/
│   ├── app/             api, models, schemas, services, database, core
│   ├── sql/schema.sql   PostgreSQL schema
│   └── tests/
├── nginx/nginx.conf     reverse proxy
├── docs/DEPLOYMENT.md   AWS and Azure
├── .github/workflows/   CI/CD
├── docker-compose.yml
└── .env.example
```

**##Screenshots**
<img width="1920" height="923" alt="LOGIN PAGE" src="https://github.com/user-attachments/assets/b4e69934-cfcf-4a40-a09d-a1a708454e2c" />
<img width="1920" height="922" alt="HOMEPAGE" src="https://github.com/user-attachments/assets/d876d6cf-2bbb-4b2c-91d1-2470446b1904" />
<img width="1920" height="923" alt="DASHBOARD" src="https://github.com/user-attachments/assets/88148f08-3a63-47b1-80f2-bbff0afc7207" />



