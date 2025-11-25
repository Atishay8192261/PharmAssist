"""Functional test runner (subset) for PharmAssist.
Assumes backend is running locally. Focus: pricing presence, cart mutation, checkout.
Prerequisites: At least one SKU with stock and a customer user 'pharma1'.
"""
import os, json, requests, random
from dotenv import load_dotenv

API_BASE = os.getenv("API_BASE", "http://localhost:5000")
load_dotenv()

def post(path, payload, token=None):
    h={"Content-Type":"application/json"}
    if token: h["Authorization"] = f"Bearer {token}"
    r=requests.post(f"{API_BASE}{path}", json=payload, headers=h, timeout=25)
    try: data=r.json()
    except Exception: data={"raw":r.text}
    return r.status_code, data

def get(path, token=None):
    h={"Accept":"application/json"}
    if token: h["Authorization"] = f"Bearer {token}"
    r=requests.get(f"{API_BASE}{path}", headers=h, timeout=25)
    try: data=r.json()
    except Exception: data={"raw":r.text}
    return r.status_code, data

# Login customer
status,data=post("/api/login", {"username":"pharma1","password":"test1234"})
if status!=200: raise SystemExit(f"Customer login failed: {status} {data}")
token=data["access_token"]

# Fetch products with quantity parameter to trigger pricing logic attempt
p_status,p_data=get("/api/products?page=1&limit=20&quantity=5", token)
if p_status!=200: raise SystemExit(f"Product list failed: {p_status}")
items=p_data.get("items", [])
if not items: raise SystemExit("No products available for functional test")
print(f"Fetched {len(items)} products.")

# Pick a random SKU
choice=random.choice(items)
sku_id=choice["sku_id"]
print("Chosen SKU", sku_id, "base_price", choice.get("base_price"), "effective_price", choice.get("effective_price"))

# Add to cart (quantity 2)
up_status, up_data=post("/api/cart", {"sku_id": sku_id, "quantity": 2}, token)
if up_status not in (200,201): raise SystemExit(f"Cart upsert failed: {up_status} {up_data}")
print("Cart item added/updated:", json.dumps({k:up_data.get(k) for k in ("removed","cart_id")}, indent=2))

# Fetch cart
c_status, c_data=get("/api/cart", token)
if c_status!=200: raise SystemExit("Cart fetch failed")
print("Cart total_quantity", c_data.get("total_quantity"), "estimated_total_price", c_data.get("estimated_total_price"))

# Checkout
co_status, co_data=post("/api/checkout", {}, token)
if co_status!=201: raise SystemExit(f"Checkout failed: {co_status} {co_data}")
print("Checkout success order_id", co_data.get("order_id"), "total_price", co_data.get("total_price"))

print("Functional subset PASS")
