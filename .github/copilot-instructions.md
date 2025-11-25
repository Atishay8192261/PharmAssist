## PharmAssist AI Coding Agent Guide
Purpose: Fast onboarding for this Flask + Next.js + Postgres monorepo. Only document what exists.

### Architecture
- Backend: Single Flask app (`backend/app.py`), routes defined inline. Each route encloses DB work in local `_work()` to enable one transient retry.
- DB: `psycopg_pool` in `backend/db.py`; use `get_connection()`. On Neon transient substrings ("SSL connection has been closed", "server closed the connection unexpectedly", "connection not open") call `reset_pool()` then retry once.
- Concurrency: Business integrity pushed into SQL (`db/procedures.sql`), esp. `sp_PlaceOrder` using `SERIALIZABLE` + `SELECT ... FOR UPDATE` FEFO (earliest expiry) batch locking.
- Pricing: Determine max discount from `Pricing_Rules` by SKU/customer match (or NULL wildcard) and quantity threshold; apply percent off `base_price` and round to 2 decimals.
- Frontend: Next.js App Router in `csm-veena-frontend/app/` segmented by role (`admin/`, `customer/`, public). State via `context/auth-context.tsx` & `context/cart-context.tsx`.
- API client: `csm-veena-frontend/lib/api.ts` centralizes fetch, JWT header, 401 purge+redirect, and numeric normalization.

### Core Workflows
- Run backend: `python -m backend.app` (port 5000) with `.env` (`DATABASE_URL`, `SECRET_KEY`).
- Init DB: `psql "$DATABASE_URL" -f db/schema.sql`; seed optional via `db/seed.sql`.
- Frontend dev: `cd csm-veena-frontend && npm install && npm run dev` (port 3000). Set `NEXT_PUBLIC_API_URL` if needed.
- Tests: `python tests/test_login.py`; AI inventory (`GOOGLE_API_KEY`) via `python tests/test_ai_endpoint.py`; concurrency via env vars `CONCURRENCY_THREADS`, `CONCURRENCY_ORDER_QTY`, `CONCURRENCY_TARGET_STOCK` then `python tests/test_concurrency.py`.

### Backend Conventions
- Always wrap DB calls in `_work()`; keep logic local, avoid globals.
- For inventory/order mutations: set `conn.isolation_level = IsolationLevel.SERIALIZABLE` before queries; explicit `commit()`.
- Normalize numbers (Dec/str → float/int) before `jsonify`; mimic `/api/products`, `/api/cart`.
- Auth: `requires_auth(role="admin"|None)` decorates `request.user`; tokens via `_make_access_token()` (1h exp default).
- Errors: `jsonify({"error": msg}), status`. Use 409 for stock conflicts; 401/403 for auth.
- Inventory deduction: FEFO ordering `ORDER BY expiry_date ASC FOR UPDATE`; decrement batch `quantity_on_hand` sequentially.

### Frontend Patterns
- Role redirect after login: admin → `/admin/orders`, customer → `/catalog` inside `AuthProvider.login()`.
- Price formatting in `lib/utils.ts`; rely on numeric fields already normalized by API client.
- Cart badge: `CartProvider.refreshCart()` uses `total_quantity`.
- Protect role pages via layout checks (`admin/layout.tsx`, `customer/layout.tsx`) or `components/auth/protected-route.tsx`.

### Adding an Endpoint
1. Define route in `create_app()` inside `backend/app.py` before return.
2. Implement `_work()` closure wrapping DB usage.
3. On DB failure: if transient substring match → `reset_pool()` then one retry.
4. Convert all numeric response fields to Python numeric types.
5. Add `requires_auth(role="admin")` if privileged; use `request.user` for context.
6. For multi-step inventory/ordering → set SERIALIZABLE + proper `FOR UPDATE` locking.

### OAuth2 (Google) Flow
- Environment vars: `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI`, optional `ADMIN_EMAIL_DOMAIN`, `ADMIN_EMAILS`, `OAUTH_AUTO_CUSTOMER_TYPE`.
- Frontend (Next.js) generates PKCE `code_verifier` & `code_challenge` and redirects user to Google with scope `openid email profile` and `state`.
- Callback page (`/login/google/callback`) reads `code`, validates `state`, posts `{code, code_verifier}` to `/api/oauth/google/exchange`.
- Backend exchanges code for tokens, verifies `id_token` via Google tokeninfo, upserts user (`Users.username = email`).
- Role assignment: match email in `ADMIN_EMAILS` or domain match of `ADMIN_EMAIL_DOMAIN`; else create new `Customers` row (type from `OAUTH_AUTO_CUSTOMER_TYPE`).
- Placeholder bcrypt hash is stored for OAuth users (not used). JWT includes `auth_provider=google_oauth`.
- To revoke/remove: delete user row; future login recreates user.

### Admin vs Customer Concurrency & Safety
- Admin endpoints always guarded by `@requires_auth(role="admin")`.
- Optional separation: deploy admin UI on `admin.<domain>` with stricter CSP & rate limit.
- Rate limiting excludes health/ready; can add specific lower burst for `/api/login` & `/api/oauth/google/exchange`.
- DB pool retry logic covers transient Neon disconnect & DNS issues.

### AI / NLP Pattern
- `/api/admin/add-inventory-nlp`: expects `text`; model chosen via `_choose_gemini_model()`. Parse fenced JSON via regex; validate keys: `sku_name`, `batch_no`, `quantity`, `expiry_date`.

### Pitfalls
- String numbers break frontend normalization.
- Skipping transient retry yields sporadic 500s.
- Using `user_id` instead of `customer_id` breaks `/api/my-orders`.
- Omitting FEFO + locking risks race inconsistencies.

### Quick Reference
- Auth header: `Authorization: Bearer <token>`
- Discount: `effective = base_price * (1 - max_discount/100)` → round(2)
- Transient substrings: exact match list above.

Feedback welcome: request clarifications on pricing, concurrency, AI parsing, or missing workflows.
