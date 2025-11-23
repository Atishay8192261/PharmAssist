#!/usr/bin/env python3
"""Run EXPLAIN (ANALYZE, BUFFERS) for the /api/products queries.

Usage:
  export DATABASE_URL=postgres://...
  python scripts/explain_products.py [--quantity 1] [--customer-id 5] [--search "paracetamol 500"] [--page 1] [--limit 20]

Outputs the execution plan for:
  1. Count query
  2. Items (data) query

Share the output to decide index/materialization strategy.
"""
import argparse
import os
import sys
import psycopg

COUNT_SQL_BASE = """
SELECT COUNT(*)
FROM Product_SKUs s
JOIN Products p ON p.product_id = s.product_id
{where_sql}
""".strip()

ITEMS_SQL_BASE = """
SELECT
    p.product_id,
    p.name AS product_name,
    p.manufacturer,
    p.description,
    s.sku_id,
    s.package_size,
    s.unit_type,
    s.base_price,
    COALESCE(st.total_on_hand, 0) AS total_on_hand,
    st.earliest_expiry,
    ROUND(
        s.base_price * (1 - COALESCE((
            SELECT MAX(r.discount_percentage)
            FROM Pricing_Rules r
            WHERE (r.sku_id IS NULL OR r.sku_id = s.sku_id)
              AND COALESCE(r.min_quantity, 1) <= %s
              AND (r.customer_id IS NULL OR r.customer_id = %s)
        ), 0)/100.0),
        2
    ) AS effective_price
FROM Products p
JOIN Product_SKUs s ON s.product_id = p.product_id
LEFT JOIN (
    SELECT b.sku_id,
           SUM(b.quantity_on_hand) AS total_on_hand,
           MIN(b.expiry_date) FILTER (WHERE b.quantity_on_hand > 0) AS earliest_expiry
    FROM Inventory_Batches b
    GROUP BY b.sku_id
) st ON st.sku_id = s.sku_id
{where_sql}
ORDER BY p.product_id, s.sku_id
LIMIT %s OFFSET %s
""".strip()

SEARCH_FIELDS = [
    "p.name",
    "p.manufacturer",
    "COALESCE(p.description,'')",
    "s.package_size",
    "s.unit_type::text",
    "(p.name || ' ' || s.package_size)",
]


def build_search_clause(raw: str):
    raw = (raw or "").strip()
    if not raw:
        return "", []
    tokens = [t.strip() for t in raw.split() if t.strip()]
    groups = []
    params = []
    for tok in tokens:
        if len(tok) < 2:
            continue
        pattern = f"%{tok}%"
        ors_exprs = [f"{f} ILIKE %s" for f in SEARCH_FIELDS]
        params.extend([pattern] * len(SEARCH_FIELDS))
        if tok.isdigit():
            ors_exprs.append("CAST(s.sku_id AS TEXT) = %s")
            params.append(tok)
            ors_exprs.append("CAST(s.sku_id AS TEXT) ILIKE %s")
            params.append(pattern)
        groups.append("(" + " OR ".join(ors_exprs) + ")")
    if not groups:
        return "", []
    clause = " AND ".join(groups)
    return clause, params


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quantity", type=int, default=1)
    ap.add_argument("--customer-id", type=int, default=None)
    ap.add_argument("--search", type=str, default="")
    ap.add_argument("--page", type=int, default=1)
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set. Set it first, e.g.\n  export DATABASE_URL=postgres://user:pass@host:port/dbname", file=sys.stderr)
        return 2
    if "your_url_here" in db_url:
        print("ERROR: Placeholder DATABASE_URL detected. Replace 'postgres://your_url_here' with the real connection string from your .env / Neon dashboard.", file=sys.stderr)
        return 3

    page = max(args.page, 1)
    limit = max(min(args.limit, 500), 1)
    offset = (page - 1) * limit

    search_clause, search_params = build_search_clause(args.search)
    where_sql = f"WHERE {search_clause}" if search_clause else ""

    count_sql = COUNT_SQL_BASE.format(where_sql=where_sql)
    items_sql = ITEMS_SQL_BASE.format(where_sql=where_sql)

    params_items = [args.quantity, args.customer_id] + search_params + [limit, offset]
    params_count = search_params

    print("=== PARAMETERS ===")
    print(f"quantity={args.quantity} customer_id={args.customer_id} search='{args.search}' limit={limit} offset={offset}")
    print(f"search_params({len(search_params)}): {search_params}")
    print()

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            # Count query plan
            print("=== EXPLAIN ANALYZE COUNT ===")
            cur.execute("EXPLAIN (ANALYZE, BUFFERS, VERBOSE) " + count_sql, params_count)
            for row in cur.fetchall():
                print(row[0])
            print()
            # Items query plan
            print("=== EXPLAIN ANALYZE ITEMS ===")
            cur.execute("EXPLAIN (ANALYZE, BUFFERS, VERBOSE) " + items_sql, params_items)
            for row in cur.fetchall():
                print(row[0])
            print()
            # Quick timing run (without EXPLAIN) for comparison
            print("=== TIMING (data fetch) ===")
            cur.execute(items_sql, params_items)
            rows = cur.fetchall()
            print(f"Fetched {len(rows)} rows.")

    print("Done. Share this output to decide next index/materialization steps.")


if __name__ == "__main__":
    raise SystemExit(main())
