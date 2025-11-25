#!/usr/bin/env python3
"""Quick verification of scale seeding.

Prints counts for key tables and lists any customers lacking user accounts.

Usage:
  export DATABASE_URL=postgresql://...
  python scripts/verify_seeding.py
"""
import os
import psycopg

TABLES = [
    "Customers",
    "Products",
    "Product_SKUs",
    "Inventory_Batches",
    "Users",
    "Orders",
    "Order_Items",
]


def main():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL not set")
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            print("[verify] Table counts:")
            for t in TABLES:
                cur.execute(f"SELECT COUNT(*) FROM {t}")
                print(f"  {t:18s} : {cur.fetchone()[0]}")
            # Missing users
            cur.execute(
                """
                SELECT c.customer_id
                FROM Customers c
                LEFT JOIN Users u ON u.customer_id = c.customer_id
                WHERE u.user_id IS NULL
                ORDER BY c.customer_id
                LIMIT 25
                """
            )
            missing = [r[0] for r in cur.fetchall()]
            cur.execute(
                "SELECT COUNT(*) FROM Customers c LEFT JOIN Users u ON u.customer_id = c.customer_id WHERE u.user_id IS NULL"
            )
            total_missing = cur.fetchone()[0]
            print(f"[verify] Customers without user accounts: {total_missing}")
            if missing:
                print("  Sample IDs:", ", ".join(map(str, missing)))
            else:
                print("  None (all customers have accounts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
