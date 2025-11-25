"""Locust load test for PharmAssist

Simulates concurrent customers performing:
1. Login
2. Browse products (first page + search query)
3. Modify cart (add SKU)
4. Checkout

Environment variables:
- BASE_URL (default http://localhost:5000)
- USERNAME_PREFIX (default cust_) for seeded accounts
- SHARED_PASSWORD (default Customer@123) used during seeding
- PRODUCT_SEARCH_TERM (default 'para')
- CART_SKU_ID (must exist; default 1)

Run:
  locust -f loadtest/locustfile.py --users 50 --spawn-rate 5

Prereq: Seed users via create_customer_users.py.
"""
import os
import random
from locust import HttpUser, task, between

BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")
USERNAME_PREFIX = os.getenv("USERNAME_PREFIX", "cust_")
SHARED_PASSWORD = os.getenv("SHARED_PASSWORD", "Customer@123")
PRODUCT_SEARCH_TERM = os.getenv("PRODUCT_SEARCH_TERM", "para")
CART_SKU_ID = int(os.getenv("CART_SKU_ID", "1"))
MAX_CUSTOMER_ID = int(os.getenv("MAX_CUSTOMER_ID", "500"))  # used for random user selection

class CustomerUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self._login()

    def _login(self):
        cid = random.randint(1, MAX_CUSTOMER_ID)
        username = f"{USERNAME_PREFIX}{cid}"
        with self.client.post(
            f"{BASE_URL}/api/login",
            json={"username": username, "password": SHARED_PASSWORD},
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"login failed {resp.status_code}")
                return
            token = resp.json().get("access_token")
            if not token:
                resp.failure("missing token")
                return
            self.token = token

    def _auth_headers(self):
        return {"Authorization": f"Bearer {getattr(self, 'token', '')}"}

    @task(3)
    def list_products(self):
        self.client.get(
            f"{BASE_URL}/api/products?page=1&limit=20&quantity=1", headers=self._auth_headers()
        )

    @task(1)
    def search_products(self):
        term = PRODUCT_SEARCH_TERM
        self.client.get(
            f"{BASE_URL}/api/products?page=1&limit=20&quantity=1&search={term}",
            headers=self._auth_headers(),
        )

    @task(2)
    def cart_flow(self):
        # Add / update item
        qty = random.randint(1, 3)
        self.client.post(
            f"{BASE_URL}/api/cart",
            json={"sku_id": CART_SKU_ID, "quantity": qty},
            headers=self._auth_headers(),
        )
        # Get cart
        self.client.get(f"{BASE_URL}/api/cart", headers=self._auth_headers())

    @task(1)
    def checkout_flow(self):
        # Ensure at least one item before checkout
        self.client.post(
            f"{BASE_URL}/api/cart",
            json={"sku_id": CART_SKU_ID, "quantity": 1},
            headers=self._auth_headers(),
        )
        self.client.post(f"{BASE_URL}/api/checkout", headers=self._auth_headers())

    @task(1)
    def my_orders(self):
        self.client.get(f"{BASE_URL}/api/my-orders", headers=self._auth_headers())
