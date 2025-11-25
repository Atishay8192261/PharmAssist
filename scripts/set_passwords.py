#!/usr/bin/env python3
"""Set or reset passwords for specific users, and optionally ensure an admin.

Usage examples:
  export DATABASE_URL=postgresql://...
  # Set known password for a few test customer users
  python scripts/set_passwords.py --usernames cust_3,cust_4,cust_5 --password Customer!23

  # Ensure an admin user exists (username 'admin') with a password
  python scripts/set_passwords.py --ensure-admin --admin-password Admin!23
"""
import os
import argparse
import psycopg
import bcrypt
from dotenv import load_dotenv


def hash_pw(pw: str, rounds: int = 12) -> str:
    salt = bcrypt.gensalt(rounds=rounds)
    return bcrypt.hashpw(pw.encode("utf-8"), salt).decode("utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--usernames", type=str, default="", help="Comma-separated usernames to set/reset")
    ap.add_argument("--password", type=str, default=None, help="Password to set for listed usernames")
    ap.add_argument("--ensure-admin", action="store_true", help="Ensure an 'admin' user exists")
    ap.add_argument("--admin-password", type=str, default=None, help="Password for admin user if ensuring")
    ap.add_argument("--rounds", type=int, default=int(os.getenv("BCRYPT_ROUNDS", "12")))
    args = ap.parse_args()

    # Load .env automatically for convenience
    load_dotenv(os.getenv("DOTENV_PATH", ".env"))
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL not set (ensure .env exists or export DATABASE_URL)")

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            # Handle customer/usernames updates
            if args.usernames:
                if not args.password:
                    raise SystemExit("--password is required when --usernames is provided")
                usernames = [u.strip() for u in args.usernames.split(",") if u.strip()]
                hpw = hash_pw(args.password, args.rounds)
                for u in usernames:
                    cur.execute(
                        "UPDATE Users SET password_hash=%s WHERE username=%s",
                        (hpw, u),
                    )
                print(f"Updated passwords for {len(usernames)} users.")

            # Ensure admin user if requested
            if args.ensure_admin:
                if not args.admin_password:
                    raise SystemExit("--admin-password is required when --ensure-admin is set")
                cur.execute("SELECT user_id FROM Users WHERE username='admin'")
                row = cur.fetchone()
                hpw = hash_pw(args.admin_password, args.rounds)
                if row:
                    cur.execute(
                        "UPDATE Users SET password_hash=%s, role='admin', customer_id=NULL WHERE username='admin'",
                        (hpw,),
                    )
                    print("Admin user existed; password updated.")
                else:
                    cur.execute(
                        "INSERT INTO Users(customer_id, username, password_hash, role) VALUES (NULL, 'admin', %s, 'admin')",
                        (hpw,),
                    )
                    print("Admin user created.")
        conn.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
