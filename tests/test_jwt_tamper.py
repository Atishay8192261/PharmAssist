import json
import os

import requests
from dotenv import load_dotenv


API_BASE = os.getenv("API_BASE", "http://localhost:5000")


def _tamper_token(token: str) -> str:
    # JWT format: header.payload.signature – we flip one char in signature
    parts = token.split(".")
    if len(parts) != 3:
        return token + "x"
    sig = parts[2]
    if not sig:
        return token + "x"
    # Flip last character deterministically
    last = sig[-1]
    new_last = "a" if last != "a" else "b"
    tampered_sig = sig[:-1] + new_last
    parts[2] = tampered_sig
    return ".".join(parts)


def main() -> None:
    load_dotenv()

    # Log in as customer to get a valid JWT
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

    bad_token = _tamper_token(token)

    headers = {"Authorization": f"Bearer {bad_token}"}

    # Hit a simple protected endpoint (cart)
    resp = requests.get(f"{API_BASE}/api/cart", headers=headers, timeout=15)
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text}

    print("Status:", resp.status_code)
    print("Body:")
    print(json.dumps(body, indent=2, default=str))

    if resp.status_code == 401:
        print("JWT tamper test PASS (invalid token rejected)")
    else:
        print("JWT tamper test FAIL (expected 401)")


if __name__ == "__main__":
    main()
