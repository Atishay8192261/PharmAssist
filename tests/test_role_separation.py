import json
import os

import requests
from dotenv import load_dotenv


API_BASE = os.getenv("API_BASE", "http://localhost:5000")


def main() -> None:
    load_dotenv()

    # Log in as customer
    login = requests.post(
        f"{API_BASE}/api/login",
        json={"username": "pharma1", "password": "test1234"},
        timeout=15,
    )
    try:
        token = login.json().get("access_token")
    except Exception:
        token = None

    if not token:
        print("Customer login failed", login.status_code, login.text)
        return

    headers = {"Authorization": f"Bearer {token}"}

    # Call admin-only endpoint with customer token
    resp = requests.get(f"{API_BASE}/api/admin/all-orders", headers=headers, timeout=15)
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text}

    print("Status:", resp.status_code)
    print("Body:")
    print(json.dumps(body, indent=2, default=str))

    if resp.status_code == 403:
        print("Role separation test PASS (customer forbidden on admin endpoint)")
    else:
        print("Role separation test FAIL (expected 403)")


if __name__ == "__main__":
    main()
