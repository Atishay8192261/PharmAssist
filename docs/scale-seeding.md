## Scaling Data Seeding (500+ Customers, Products, SKUs, Batches)

Purpose: Create realistic volume for performance/concurrency tests (customers ≥500) and ensure each customer has a login. Uses existing scripts—no schema changes.

### Environment Prerequisites
- `DATABASE_URL` points to Neon database (with `sslmode=require`).
- Virtualenv activated (`python 3.11+`).

### Steps
1. (Optional) Reset schema in a fresh branch or empty database:
   ```bash
   psql "$DATABASE_URL" -f db/schema.sql
   ```
2. Generate scale dataset (customers, products, SKUs, batches). Override counts via env vars:
   ```bash
   export SCALE_CUSTOMERS=500
   export SCALE_PRODUCTS=250      # tune as needed
   export SCALE_SKUS=1500
   export SCALE_BATCHES=8000
   python db/generate_scale_data.py
   ```
3. Create user accounts for customers lacking a login:
   ```bash
   python scripts/create_customer_users.py --password Customer@123
   ```
   - Shared password chosen for convenience; change for production.
4. Verify counts:
   ```bash
   psql "$DATABASE_URL" -c "SELECT COUNT(*) AS customers FROM Customers;"
   psql "$DATABASE_URL" -c "SELECT COUNT(*) AS customer_users FROM Users WHERE role='customer';"
   psql "$DATABASE_URL" -c "SELECT COUNT(*) AS products FROM Products;"
   psql "$DATABASE_URL" -c "SELECT COUNT(*) AS skus FROM Product_SKUs;"
   psql "$DATABASE_URL" -c "SELECT COUNT(*) AS batches FROM Inventory_Batches;"
   ```
5. (Optional) Create a few pricing rules to exercise discount paths:
   ```bash
   psql "$DATABASE_URL" -c "INSERT INTO Pricing_Rules(sku_id, customer_id, min_quantity, discount_percentage) VALUES (NULL, NULL, 10, 3.5);"
   ```
6. Warm cache (optional) using product listing:
   ```bash
   curl -s "http://localhost:5000/api/products?page=1&limit=50&quantity=1" >/dev/null
   ```

### Notes
- Batches may include zero-stock rows; this is intentional for FEFO and low-stock filters.
- `generate_scale_data.py` uses `ON CONFLICT DO NOTHING` for batch uniqueness (sku_id, batch_no). UUID ensures minimal collisions.
- Seeding is idempotent only if underlying tables are truncated first; otherwise counts accumulate.

### Cleanup / Reset
If you need to re-run with different sizes:
```bash
psql "$DATABASE_URL" -c "TRUNCATE Order_Items, Orders, Cart_Items, Carts, Inventory_Batches, Product_SKUs, Products, Users, Customers RESTART IDENTITY CASCADE;"
```
Then repeat steps 2–4.

### Troubleshooting
- Slow insert: reduce `SCALE_BATCHES` or increase `CHUNK_SIZE` (defaults 1000). Larger chunks trade memory for speed.
- Permission errors: ensure Neon user is DB owner.
- Excessive pricing query times: ensure indexes from app bootstrap (set `RUN_INDEX_BOOTSTRAP=1` before starting backend).
