# AI Coding Agent Instructions for PharmAssist

Purpose: Enable immediate productive work in this monorepo (Flask API + Next.js client + Postgres). Focus on existing, not aspirational, patterns.

## Architecture Overview
- Single Flask app in `backend/app.py`; all HTTP endpoints are defined inline using closures (`_work()` pattern) for DB calls + retry logic.
- Postgres access via `psycopg_pool` in `backend/db.py`; `get_connection()` yields a raw psycopg connection. Connection reset strategy: on specific transient Neon errors (substring match: "SSL connection has been closed", "server closed the connection unexpectedly", "connection not open") call `reset_pool()` and retry once.
- Concurrency & integrity are delegated to SQL: stored procedure `sp_PlaceOrder` (see `db/procedures.sql`) and explicit `SERIALIZABLE` isolation for `/api/orders` and `/api/checkout` flows. Checkout uses FEFO (earliest expiry first) batch locking with `FOR UPDATE`.
- Pricing logic: discount determined by max applicable rule from `Pricing_Rules` filtered by (sku match or NULL), (customer match or NULL), and quantity threshold; applied as percentage off `base_price`.
- Frontend: Next.js App Router in `csm-veena-frontend/app/` with separate role segments (`admin/`, `customer/`, public routes like `login/`, `catalog/`). Client state handled by React contexts in `context/` (`AuthProvider`, `CartProvider`).
- API client wrapper in `csm-veena-frontend/lib/api.ts` centralizes fetch, JWT header injection, 401 handling (token purge + redirect), and numeric field normalization.

## Core Developer Workflows
- Backend dev server: `python -m backend.app` (port 5000). Ensure `.env` with `DATABASE_URL` & `SECRET_KEY`.
- Frontend dev: `cd csm-veena-frontend && npm install && npm run dev` (port 3000). Set `NEXT_PUBLIC_API_URL` if backend not on default.
- DB init: `psql "$DATABASE_URL" -f db/schema.sql` then (optional) seed via `db/seed.sql`.
- Tests (manual scripts):
  - Login: `python tests/test_login.py`
  - AI inventory (requires `GOOGLE_API_KEY`): `python tests/test_ai_endpoint.py`
  - Concurrency race: set `CONCURRENCY_THREADS`, `CONCURRENCY_ORDER_QTY`, `CONCURRENCY_TARGET_STOCK` then `python tests/test_concurrency.py`.

## Backend Implementation Conventions
- Always wrap DB logic inside a local `_work()` closure; perform one retry on transient connection errors only.
- For endpoints needing transactional guarantees or inventory mutation: set `conn.isolation_level = IsolationLevel.SERIALIZABLE` before cursor work; commit explicitly.
- Normalize numeric JSON fields before `jsonify` (convert `Decimal` / `str` → `float` or `int` as done in `/api/products`, `/api/cart` etc.). Frontend expects numbers, not strings.
- Authentication: `requires_auth(role="admin" | None)` decorator attaches decoded claims to `request.user`. Create tokens via `_make_access_token()` including `exp` 1h default.
- Error pattern: return `jsonify({"error": message}), <status>`; use 409 for stock/quantity conflicts and 401/403 for auth issues.
- Inventory logic: FEFO ordering via `ORDER BY expiry_date ASC FOR UPDATE`; decrement `quantity_on_hand` per batch.

## Frontend Patterns & Conventions
- Role-based navigation after login in `AuthProvider.login()` (admin → `/admin/orders`; customer → `/catalog`). JWT decoded manually; keep HS256 structure stable.
- Price display uses formatting helpers in `lib/utils.ts`; numeric fields pre-normalized by `ApiClient.normalizeNumbers()` when keys match known price/quantity names.
- Cart badge logic lives in `CartProvider` (`refreshCart()` calls `/api/cart` and uses `total_quantity`).
- Protect role-specific pages with `components/auth/protected-route.tsx` (if added) or layout level checks; maintain consistent redirect to `/login` on missing token.

## Adding / Modifying Endpoints (Guidelines)
1. Define route in `backend/app.py` within `create_app()` before return.
2. Use `_work()` closure; no global state other than connection pool.
3. On DB ops: handle transient Neon errors → `reset_pool()` and retry once.
4. Convert numeric output fields to Python numeric types prior to response.
5. Apply `requires_auth(role="admin")` for privileged operations; rely on `request.user` for user/customer context.
6. For multi-step mutations (e.g., stock adjustments) use SERIALIZABLE and explicit locking (`FOR UPDATE`).

## AI / NLP Integration
- Endpoint `/api/admin/add-inventory-nlp` expects `text`; Gemini model chosen via `_choose_gemini_model()` with fallback candidates. JSON parsing via regex fences; ensure keys: `sku_name`, `batch_no`, `quantity`, `expiry_date`. On adding similar AI endpoints, replicate JSON extraction + validation pattern.

## Common Pitfalls to Avoid
- Returning stringified numbers: breaks frontend normalization assumptions.
- Omitting retry on Neon idle disconnect: leads to sporadic 500s; follow substring checks.
- Using user_id instead of customer_id for order creation: breaks `/api/my-orders` filtering.
- Forgetting FEFO batch locking for stock deductions: risks race inconsistencies.

## Quick Reference
- Auth header format: `Authorization: Bearer <token>`.
- Numeric discount formula reference (as in `/api/products` & cart pricing): `effective = base_price * (1 - max_discount/100)` rounded to 2 decimals.
- Transient error substrings (case-sensitive): `SSL connection has been closed`, `server closed the connection unexpectedly`, `connection not open`.

Feedback: Please indicate any unclear sections (e.g., pricing, concurrency, AI parsing) or additional workflows you want documented.
