"""Inventory CRUD test script.
Steps:
1. Login as admin.
2. Pick existing sku_id (first from /api/products) or fail.
3. Create batch via /api/admin/inventory/batches (POST) with random batch_no.
4. Update batch quantity_on_hand and cost_price (PUT).
5. Delete batch (DELETE).
6. Assertions on status codes and field presence.

Usage:
  source .venv/bin/activate && python scripts/test_inventory_crud.py
"""
import os, requests, random, string, datetime
from dotenv import load_dotenv

API_BASE = os.getenv("API_BASE", "http://localhost:5000")

def rand_batch():
    return "BTEST-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def fail(msg):
    raise SystemExit(msg)

def main():
    load_dotenv()

    # Admin login
    r = requests.post(f"{API_BASE}/api/login", json={"username": "admin", "password": "Admin!23"}, timeout=15)
    if r.status_code != 200:
        fail(f"Admin login failed {r.status_code} {r.text}")
    token = r.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}

    # Get a sku
    rp = requests.get(f"{API_BASE}/api/products?page=1&limit=10&quantity=1", headers=headers, timeout=20)
    if rp.status_code != 200:
        fail(f"Products fetch failed {rp.status_code}")
    items = rp.json().get("items", [])
    if not items:
        fail("No products to test inventory CRUD")
    sku_id = items[0]["sku_id"]

    # Create batch
    batch_no = rand_batch()
    expiry = (datetime.date.today() + datetime.timedelta(days=365)).isoformat()
    payload = {"sku_id": sku_id, "batch_no": batch_no, "quantity": 5, "expiry_date": expiry, "cost_price": 2.34}
    rc = requests.post(f"{API_BASE}/api/admin/inventory/batches", json=payload, headers=headers, timeout=20)
    if rc.status_code != 201:
        fail(f"Create batch failed {rc.status_code} {rc.text}")
    batch = rc.json().get("batch") or {}
    batch_id = batch.get("batch_id")
    if not batch_id:
        fail("No batch_id returned on create")
    print("Created batch", batch_id, batch_no)

    # Update batch quantity + cost price
    ru = requests.put(f"{API_BASE}/api/admin/inventory/batches/{batch_id}", json={"quantity_on_hand": 9, "cost_price": 2.99}, headers=headers, timeout=20)
    if ru.status_code != 200:
        fail(f"Update batch failed {ru.status_code} {ru.text}")
    ubatch = ru.json().get("batch") or {}
    if ubatch.get("quantity_on_hand") != 9:
        fail(f"Quantity not updated: {ubatch}")
    if abs(ubatch.get("cost_price") - 2.99) > 0.001:
        fail("Cost price not updated")
    print("Updated batch", batch_id)

    # Delete batch
    rd = requests.delete(f"{API_BASE}/api/admin/inventory/batches/{batch_id}", headers=headers, timeout=20)
    if rd.status_code not in (200,204):
        fail(f"Delete batch failed {rd.status_code} {rd.text}")
    print("Deleted batch", batch_id)
    print("Inventory CRUD test PASS")

if __name__ == "__main__":
    main()
