import json
import os

import requests
from dotenv import load_dotenv


API_BASE = os.getenv("API_BASE", "http://localhost:5000")


def _admin_headers() -> dict:
    # Helper to fetch an admin JWT
    login = requests.post(
        f"{API_BASE}/api/login",
        json={"username": "admin", "password": "Admin!23"},
        timeout=15,
    )
    try:
        token = login.json().get("access_token")
    except Exception:
        token = None
    if not token:
        print("Admin login failed", login.status_code, login.text)
        return {}
    return {"Authorization": f"Bearer {token}"}


def main() -> None:
    load_dotenv()
    headers = _admin_headers()
    if not headers:
        return

    # Missing required 'text' field
    bad_payload = {"not_text": "something"}

    resp = requests.post(
        f"{API_BASE}/api/admin/add-inventory-nlp",
        json=bad_payload,
        headers=headers,
        timeout=15,
    )
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text}

    print("Status:", resp.status_code)
    print("Body:")
    print(json.dumps(body, indent=2, default=str))

    if resp.status_code in (400, 422):
        print("NLP validation test PASS (invalid payload rejected)")
    else:
        print("NLP validation test FAIL (expected 400/422)")


if __name__ == "__main__":
    main()
