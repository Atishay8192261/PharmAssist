import json
import os

import requests
from dotenv import load_dotenv


API_BASE = os.getenv("API_BASE", "http://localhost:5000")


def main() -> None:
    load_dotenv()

    # Simulate frontend callback posting wrong state/verifier to backend exchange
    # Backend expects {code, code_verifier}; we provide dummy values and mismatched state is enforced client-side,
    # but server should still validate and reject invalid exchange deterministically.
    payload = {
        "code": "invalid-code",
        "code_verifier": "invalid-verifier"
    }

    resp = requests.post(f"{API_BASE}/api/oauth/google/exchange", json=payload, timeout=15)
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text}

    print("Status:", resp.status_code)
    print("Body:")
    print(json.dumps(body, indent=2, default=str))

    if resp.status_code in (400, 401):
        print("OAuth state/invalid exchange test PASS (rejected)")
    else:
        print("OAuth state/invalid exchange test FAIL (expected 400/401)")


if __name__ == "__main__":
    main()
