# PharmAssist

A B2B pharmaceutical ordering and inventory management platform built to demonstrate solid relational design, transaction safety, pricing logic, and practical AI-assisted ingestion.

## Overview

PharmAssist helps pharmacies and hospitals:
- Browse a product catalog with customer- and quantity-aware pricing.
- Maintain stock by batch with FEFO (First-Expire-First-Out) consumption on checkout.
- Place orders safely under high concurrency.
- Ingest inventory using AI prompts (admin), with validation and DB-backed updates.
- View actionable admin analytics (revenue, profit, low stock, expiring soon).

This project intentionally pushes business integrity into SQL (stored procedures, triggers), with a thin Flask API and a Next.js frontend.

## Tech Stack

- Backend: Flask (Python 3.11), psycopg 3, JWT auth, CORS
- Database: Neon (PostgreSQL) with `SERIALIZABLE` isolation, stored procedures, triggers
- Frontend: Next.js App Router (TypeScript), role-based layouts and contexts
- AI: Google Gemini (Generative AI) for admin NLP inventory ingestion
- Caching: In-memory (optional Redis hooks present)
- Auth: Password + Google OAuth2 (PKCE)

## Architecture

- Backend: Single Flask app with inline routes in [backend/app.py](backend/app.py).
  - DB access via pool in [backend/db.py](backend/db.py).
  - Transient Neon disconnects auto-retry with `reset_pool()`.
  - Admin-only endpoints protected by [`requires_auth(role="admin")`](backend/app.py).
- Database:
  - Schema, indexes, triggers: [db/schema.sql](db/schema.sql).
  - Stored procedures: [db/procedures.sql](db/procedures.sql) including `sp_PlaceOrder`.
  - Seed data: [db/seed.sql](db/seed.sql).
- Frontend: Next.js App Router under [csm-veena-frontend/app/](csm-veena-frontend/app/).
  - Role segmentation: `admin/`, `customer/`, public.
  - State via [`AuthProvider`](csm-veena-frontend/context/auth-context.tsx) and [`CartProvider`](csm-veena-frontend/context/cart-context.tsx).
  - Centralized API client: [`lib/api.ts`](csm-veena-frontend/lib/api.ts).

## Key Features

- Products and Pricing
  - Endpoint: [`GET /api/products`](backend/app.py) with discount rules by SKU/customer/quantity.
  - Max discount computed via `Pricing_Rules`, rounded to 2 decimals.
- Cart and Checkout
  - FEFO consumption: earliest expiry batches locked and decremented in order.
  - SERIALIZABLE isolation and `SELECT ... FOR UPDATE` batch locking.
  - Customer-facing flows: cart, checkout, my orders.
- Orders & Concurrency
  - Stored procedure [`sp_PlaceOrder`](db/procedures.sql) called from [`/api/orders`](backend/app.py).
  - Prevents overselling under simultaneous requests.
- Admin
  - Inventory listing, batch CRUD, dashboard stats: revenue/profit/daily/weekly, low stock, expiring soon.
  - AI NLP ingestion: [`POST /api/admin/add-inventory-nlp`](backend/app.py) parses free text and upserts a batch.
- OAuth2 (Google)
  - PKCE flow via frontend; exchange + verification on backend.

## Database Design Highlights

- Normalized tables: Products → Product_SKUs → Inventory_Batches
- Inventory summary table maintained via triggers for fast catalog rendering.
- Pricing rules precedence: SKU+customer, SKU-only, customer-only, global wildcard.

## Running Locally

### Prerequisites
- Python 3.11+
- Node.js 18+
- Neon PostgreSQL URL with `sslmode=require`

### Environment Variables

Backend (.env):
- DATABASE_URL
- SECRET_KEY
- GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, GOOGLE_OAUTH_REDIRECT_URI
- GOOGLE_API_KEY (for admin AI inventory endpoint)
- Optional: ADMIN_EMAILS or ADMIN_EMAIL_DOMAIN, OAUTH_AUTO_CUSTOMER_TYPE
- Optional tuning: DB_POOL_MAX, PRODUCTS_PREWARM, DASHBOARD_PREWARM

Frontend (`csm-veena-frontend/.env.local`):
- NEXT_PUBLIC_API_URL
- NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID

### Initialize DB

- Apply schema:
  - psql: `psql "$DATABASE_URL" -f db/schema.sql`
  - Or: `python init_db.py`
- (Optional) Procedures:
  - `psql "$DATABASE_URL" -f db/procedures.sql`
- Seed demo data:
  - `psql "$DATABASE_URL" -f db/seed.sql`

### Start Backend

```sh
# In repo root
pip install -r requirements.txt
python -m backend.app
# Backend listens on http://localhost:5000
```

Endpoints to try:
- Login: `POST /api/login`
- Products: `GET /api/products?page=1&limit=20&quantity=5`
- Cart: `GET /api/cart`
- Checkout: `POST /api/checkout`
- Admin: `GET /api/admin/inventory`, `GET /api/admin/dashboard-stats`

### Start Frontend

```sh
cd csm-veena-frontend
npm install
npm run dev
# Frontend at http://localhost:3000
```

Roles:
- Admin: seeded user `admin` / `Admin!23` (see [db/seed.sql](db/seed.sql))
- Customer: `pharma1` / `test1234` (mapped to a real `customer_id`)

## Testing & Load

- Smoke runner: [scripts/run_smoke.py](scripts/run_smoke.py)
- Functional sample: [scripts/run_functional.py](scripts/run_functional.py)
- Concurrency test: [tests/test_concurrency.py](tests/test_concurrency.py)
  - env: `CONCURRENCY_THREADS`, `CONCURRENCY_ORDER_QTY`, `CONCURRENCY_TARGET_STOCK`
- AI admin test: [tests/test_ai_endpoint.py](tests/test_ai_endpoint.py)
- Role separation: [tests/test_role_separation.py](tests/test_role_separation.py)
- Load test: [loadtest/locustfile.py](loadtest/locustfile.py)

Performance tuning tips in [docs/performance-thresholds.md](docs/performance-thresholds.md).

## Implementation Notes

- Transient reconnects: endpoints wrap DB work in `_work()` and retry once when matching Neon error substrings.
- Numeric normalization: all API responses cast numeric fields to real numbers for React rendering (see [`lib/api.ts`](csm-veena-frontend/lib/api.ts)).
- FEFO enforcement: checkout locks batches via `FOR UPDATE` and deducts sequentially.
- Caching: in-memory product/inventory/dashboard cache with invalidation after mutations.

## Folder Guide

- Backend: [backend/app.py](backend/app.py), [backend/db.py](backend/db.py), [backend/oauth.py](backend/oauth.py)
- Frontend: [csm-veena-frontend/app/](csm-veena-frontend/app/), [csm-veena-frontend/components/](csm-veena-frontend/components/), [csm-veena-frontend/lib/api.ts](csm-veena-frontend/lib/api.ts)
- Database: [db/schema.sql](db/schema.sql), [db/procedures.sql](db/procedures.sql), [db/seed.sql](db/seed.sql)
- Docs: [docs/deployment-plan.md](docs/deployment-plan.md), [docs/testing-checklist.md](docs/testing-checklist.md), [docs/scale-seeding.md](docs/scale-seeding.md)

## Roadmap

- Rate limiting for `/api/login` and OAuth exchange
- Redis cache for multi-instance deployments
- More pytest coverage for pricing, FEFO, OAuth edge cases

## Contact

Open to suggestions or collaboration. Feel free to email me at: atishayjain8192261@gmail.com
