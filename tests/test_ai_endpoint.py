import os
import json
import requests
from dotenv import load_dotenv

API_BASE = os.getenv("API_BASE", "http://localhost:5000")


def main():
    load_dotenv()

    # Always log in as admin for this protected admin endpoint
    login = requests.post(
        f"{API_BASE}/api/login",
        json={"username": "admin", "password": "Admin!23"},
        timeout=15,
    )
    token = None
    try:
        token = login.json().get("access_token")
    except Exception:
        token = None

    headers = {"Authorization": f"Bearer {token}"} if token else {}

    payload = {
        "text": "Add 5 units of Paracetamol 500mg 10-strip Batch #P500-ZZ1 expiring January 2029"
    }
    resp = requests.post(
        f"{API_BASE}/api/admin/add-inventory-nlp",
        json=payload,
        headers=headers,
        timeout=30,
    )
    try:
        data = resp.json()
    except Exception:
        data = {"raw": resp.text}
    print("Status:", resp.status_code)
    print("Body:")
    print(json.dumps(data, indent=2, default=str))


if __name__ == "__main__":
    main()
