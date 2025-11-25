"""Pricing discount verification script.
1. Identify a SKU via /api/products.
2. Insert a Pricing_Rules row granting a discount for customer pharma1.
3. Re-fetch products with quantity parameter triggering discount logic.
4. Assert effective_price < base_price and rounded to 2 decimals.
5. Cleanup rule.

Usage:
  source .venv/bin/activate && python scripts/test_pricing_discount.py
"""
import os, requests, psycopg
from decimal import Decimal
from dotenv import load_dotenv

API_BASE = os.getenv("API_BASE", "http://localhost:5000")

def main():
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL missing")

    # Login customer 'pharma1'
    r = requests.post(f"{API_BASE}/api/login", json={"username": "pharma1", "password": "test1234"}, timeout=15)
    token = r.json().get("access_token") if r.status_code == 200 else None
    if not token:
        raise SystemExit(f"Customer login failed: {r.status_code} {r.text}")
    headers = {"Authorization": f"Bearer {token}"}

    # Lookup pharma1's customer_id from Users table to ensure correct mapping
    cust_id = None
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT customer_id FROM Users WHERE username=%s LIMIT 1", ("pharma1",))
            row = cur.fetchone()
            if not row or row[0] is None:
                raise SystemExit("pharma1 user not found or missing customer_id")
            cust_id = int(row[0])
    # Fetch products baseline (before inserting rule)
    r0 = requests.get(f"{API_BASE}/api/products?page=1&limit=30&quantity=1&customer_id={cust_id}", headers=headers, timeout=20)
    data0 = r0.json()
    items = data0.get("items", [])
    if not items:
        raise SystemExit("No products found to test pricing")
    sku = items[0]
    sku_id = sku["sku_id"]
    base_price = Decimal(str(sku["base_price"]))

    # Insert pricing rule: 10% discount for this sku + customer when min_quantity <= 5
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM Pricing_Rules WHERE sku_id=%s AND customer_id=%s", (sku_id, cust_id))
            cur.execute(
                "INSERT INTO Pricing_Rules(sku_id, customer_id, min_quantity, discount_percentage) VALUES (%s,%s,%s,%s) RETURNING rule_id",
                (sku_id, cust_id, 2, Decimal("10.00")),
            )
        conn.commit()

    try:
        # Re-fetch with quantity=5 to trigger discount
        r1 = requests.get(f"{API_BASE}/api/products?page=1&limit=30&quantity=5&customer_id={cust_id}", headers=headers, timeout=20)
        data1 = r1.json()
        discounted_item = next((i for i in data1.get("items", []) if i["sku_id"] == sku_id), None)
        if not discounted_item:
            raise SystemExit("SKU not present after discount fetch")
        eff = Decimal(str(discounted_item["effective_price"]))
        if eff >= base_price:
            raise SystemExit(f"Discount not applied: base={base_price} effective={eff}")
        # Verify rounding precision
        if eff.quantize(Decimal("0.01")) != eff:
            raise SystemExit(f"Effective price not rounded to 2 decimals: {eff}")
        print(f"Discount applied successfully base={base_price} effective={eff}")
        print("Pricing discount test PASS")
    finally:
        # Cleanup rule
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM Pricing_Rules WHERE sku_id=%s AND customer_id=%s", (sku_id, cust_id))
            conn.commit()

if __name__ == "__main__":
    main()
