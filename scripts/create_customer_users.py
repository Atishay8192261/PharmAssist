#!/usr/bin/env python3
"""Create user accounts for all customers lacking a login.

Usage:
  export DATABASE_URL=postgresql://...
  python scripts/create_customer_users.py --password defaultpass --role customer

Options:
  --password TEXT       Password to hash for all created users (default: auto random if omitted)
  --dry-run             Show what would be created without writing

Behavior:
  - Skips customers already linked to a Users row.
  - Generates a username pattern: cust_<customer_id>
  - Uses bcrypt (Python) rather than pgcrypto to avoid extension dependency.
"""
import os
import argparse
import secrets
import psycopg
import bcrypt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--password", type=str, default=None)
    ap.add_argument("--role", type=str, default="customer", choices=["customer"])  # only customer accounts
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL not set")

    password = args.password or secrets.token_urlsafe(10)
    # bcrypt hash
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.customer_id
                FROM Customers c
                LEFT JOIN Users u ON u.customer_id = c.customer_id
                WHERE u.user_id IS NULL
                ORDER BY c.customer_id
            """)
            missing = [row[0] for row in cur.fetchall()]
            if not missing:
                print("All customers already have user accounts.")
                return 0
            print(f"Customers needing accounts: {len(missing)}")
            rows_to_insert = []
            for cid in missing:
                username = f"cust_{cid}"
                rows_to_insert.append((cid, username, hashed, args.role))
            if args.dry_run:
                for r in rows_to_insert[:10]:
                    print("DRY-RUN sample:", r)
                print(f"Total rows prepared: {len(rows_to_insert)} (no changes written)")
                return 0
            # Insert using psycopg simple executemany
            cur.executemany(
                "INSERT INTO Users(customer_id, username, password_hash, role) VALUES (%s, %s, %s, %s)",
                rows_to_insert,
            )
        conn.commit()
    print(f"Inserted {len(rows_to_insert)} user accounts. Shared password: {password if args.password else '[random generated hidden]'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
