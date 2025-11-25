"""Smoke test runner for PharmAssist.
Verifies backend basic endpoints when server is already running on localhost:5000.
Usage:
  source .venv/bin/activate && python scripts/run_smoke.py
"""
import os, json, time, requests
from dotenv import load_dotenv

API_BASE = os.getenv("API_BASE", "http://localhost:5000")
load_dotenv()

def get(path: str, token: str | None = None):
    h = {"Accept": "application/json"}
    if token: h["Authorization"] = f"Bearer {token}"
    r = requests.get(f"{API_BASE}{path}", headers=h, timeout=15)
    try: data = r.json()
    except Exception: data = {"raw": r.text}
    return r.status_code, data

def post(path: str, payload: dict, token: str | None = None):
    h = {"Content-Type": "application/json"}
    if token: h["Authorization"] = f"Bearer {token}"
    r = requests.post(f"{API_BASE}{path}", json=payload, headers=h, timeout=20)
    try: data = r.json()
    except Exception: data = {"raw": r.text}
    return r.status_code, data

results = []

# 1. Ready endpoint
status, data = get("/ready")
results.append(("ready", status, data))

# 2. Admin login
admin_status, admin_data = post("/api/login", {"username": "admin", "password": "Admin!23"}, None)
admin_token = admin_data.get("access_token") if admin_status == 200 else None
results.append(("admin_login", admin_status, {k: admin_data.get(k) for k in ["access_token", "error"] if k in admin_data}))

# 3. Customer login
cust_status, cust_data = post("/api/login", {"username": "pharma1", "password": "test1234"}, None)
cust_token = cust_data.get("access_token") if cust_status == 200 else None
results.append(("customer_login", cust_status, {k: cust_data.get(k) for k in ["access_token", "error"] if k in cust_data}))

# 4. Product list (unauth) page=1
prod_status, prod_data = get("/api/products?page=1&limit=5")
items_count = len(prod_data.get("items", [])) if isinstance(prod_data, dict) else 0
results.append(("products", prod_status, {"items": items_count}))

# 5. Cart fetch (customer auth)
cart_status, cart_data = get("/api/cart", cust_token)
results.append(("cart", cart_status, {"items": cart_data.get("total_items"), "qty": cart_data.get("total_quantity")}))

# 6. Protected admin orders list (admin token)
admin_orders_status, admin_orders_data = get("/api/admin/all-orders", admin_token)
results.append(("admin_orders", admin_orders_status, {"orders": len(admin_orders_data.get("orders", [])) if isinstance(admin_orders_data, dict) else None}))

# Summarize
failures = []
for name, status, info in results:
    ok = 200 <= status < 300
    print(f"\n{name}: status={status} info={json.dumps(info)}")
    if not ok:
        failures.append(name)

print("\nSmoke Summary: PASS" if not failures else f"Smoke Summary: FAIL -> {failures}")
if failures:
    raise SystemExit(1)
