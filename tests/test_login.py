import os
import json
import requests
from dotenv import load_dotenv

API_BASE = os.getenv("API_BASE", "http://localhost:5000")


def main():
    load_dotenv()

    def post_login(username: str, password: str):
        r = requests.post(
            f"{API_BASE}/api/login",
            json={"username": username, "password": password},
            timeout=15,
        )
        try:
            data = r.json()
        except Exception:
            data = {"raw": r.text}
        print(f"\nLogin attempt user={username!r}")
        print("Status:", r.status_code)
        print("Body:")
        print(json.dumps(data, indent=2))
        return r.status_code, data

    # Valid admin login
    status, data = post_login("admin", "Admin!23")
    if status == 200 and "access_token" in data:
        print("Admin login PASS")
    else:
        print("Admin login FAIL")

    # Valid customer login
    status, data = post_login("pharma1", "test1234")
    if status == 200 and "access_token" in data:
        print("Customer login PASS")
    else:
        print("Customer login FAIL")

    # Invalid login
    status, data = post_login("admin", "wrongpass")
    if status == 401:
        print("Invalid login correctly rejected")
    else:
        print("Invalid login test FAIL")


if __name__ == "__main__":
    main()
