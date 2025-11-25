# Testing Checklist

This checklist organizes tests into tiers for PharmAssist (Flask backend + Next.js frontend + Postgres Neon).

## 0. Pre-Test Environment
- .env populated (DATABASE_URL, SECRET_KEY, GOOGLE_OAUTH_*). No placeholder connection string.
- Apply schema & procedures: `psql "$DATABASE_URL" -f db/schema.sql && psql "$DATABASE_URL" -f db/procedures.sql`.
- (Optional) Seed: `python db/generate_scale_data.py` + `python scripts/create_customer_users.py`.
- Admin user present or OAuth admin email configured.

## 1. Smoke Tests (CI on every PR)
Goal: Fail fast for fundamentals.
- Backend starts: `python -m backend.app` (returns 200 on `/ready` within <2s).
- Login password flow: `python tests/test_login.py`.
- Basic product list: single GET `/api/products?page=1&limit=1` returns item.
- Cart empty fetch: GET `/api/cart` returns structure.
- Google OAuth exchange (mock/fake): Use stub test hitting `/api/oauth/google/exchange` with invalid code → 400 deterministic.

## 2. Functional Unit / Integration
- Authentication: valid credentials produce JWT; expired token rejected (manually shorten exp via patch test).
- Pricing: Add a Pricing_Rules row and verify discount applied & rounded to 2 decimals.
- Cart mutations: add, update to zero (removal), checkout creates order with correct totals.
- Admin inventory CRUD: create batch, update quantity_on_hand, delete batch (409 on FEFO conflict not covered here).
- NLP endpoint: `python tests/test_ai_endpoint.py` with valid text → structured JSON keys present.

## 3. Concurrency / Isolation
Purpose: Verify SERIALIZABLE + FEFO locking.
- Run: `CONCURRENCY_THREADS=10 CONCURRENCY_ORDER_QTY=3 CONCURRENCY_TARGET_STOCK=30 python tests/test_concurrency.py`.
Expected:
  - Orders placed until target stock exhausted.
  - No negative stock; no lost updates.
  - Occasional 409 conflicts acceptable (<5%).

## 4. Performance (Reference docs/performance-thresholds.md)
Measure with Locust / custom script after seeding scale data.
Targets (dev indicative):
- P50 product list < 250ms, P95 < 600ms.
- Checkout endpoint P95 < 900ms under 20 concurrent users.
- DB transient error rate < 1% over 10k requests.

## 5. Security & Auth
- Role separation: admin endpoint `/api/admin/all-orders` returns 403 for customer token.
- JWT tamper: modify one char in signature → 401.
- OAuth state mismatch: supply wrong state → 400.
- Input validation: inventory NLP rejects missing required JSON keys.

## 6. Data Integrity
- FEFO: batches with earlier expiry consumed first; verify order item batches order sequence.
- Pricing rules precedence: specific SKU+customer rule overrides wildcard; quantity threshold logic yields correct discount.

## 7. Regression Suite (Nightly)
Combine all above plus:
- Large pagination (page near end) returns correct `total_pages`.
- Expiring soon count in dashboard stats correct for artificially inserted batches.
- Graceful handling of transient DB close (simulate by resetting pool mid-test). Expect auto retry.

## 8. Manual E2E (Release Candidate)
1. Customer login (password) → add product to cart → checkout → view My Orders.
2. Google OAuth login as admin → create product + SKU + batch → view inventory list.
3. Trigger NLP inventory add → verify batch appears.
4. Apply pricing rule → verify discounted cart price.
5. Force conflict scenario: two checkouts for last stock; one succeeds, other 409.

## 9. Tooling / CI Commands
- Install deps: `pip install -r requirements.txt && (cd csm-veena-frontend && npm ci)`.
- Backend tests: `pytest -q` (if added later).
- Frontend build (CI): `npm run build` (ensures Next.js compiles).

## 10. Exit Criteria for Deploy
- All smoke + functional tests pass.
- Concurrency test no integrity violations.
- Performance thresholds met or documented exceptions.
- No critical open security findings.
- Migration delta (if any) applied successfully in staging.

## 11. Future Enhancements
- Add pytest suite wrapping pricing, FEFO, OAuth edge cases.
- Contract tests for API response numeric normalization.
- Add snapshot tests for React components (catalog card, order list).

## Quick Commands Summary
```bash
# Smoke
python tests/test_login.py
# AI endpoint
python tests/test_ai_endpoint.py
# Concurrency
CONCURRENCY_THREADS=10 CONCURRENCY_ORDER_QTY=3 CONCURRENCY_TARGET_STOCK=30 python tests/test_concurrency.py
```

Keep this file updated as new endpoints/features land.
