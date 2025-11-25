#!/usr/bin/env python3
"""Create user accounts for all customers lacking a login.

Usage:
    export DATABASE_URL=postgresql://...
    python scripts/create_customer_users.py --role customer
    python scripts/create_customer_users.py --password <PASSWORD> --role customer

Options:
    --password TEXT       Shared password for all created users (auto random if omitted)
    --dry-run             Show what would be created without writing

Behavior:
    - Skips customers already linked to a Users row.
    - Generates a username pattern: <prefix><customer_id> (prefix via USER_PREFIX env, default 'cust_').
    - Uses bcrypt (Python) rather than pgcrypto to avoid extension dependency.
Security:
    - Avoid committing real passwords; prefer auto generation and distribute out of band.
"""
import os
import argparse
import secrets
import time
import psycopg
from dotenv import load_dotenv
import bcrypt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--password", type=str, default=None)
    ap.add_argument("--role", type=str, default="customer", choices=["customer"])  # only customer accounts
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    load_dotenv(os.getenv("DOTENV_PATH", ".env"))
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL not set (ensure .env exists or export DATABASE_URL)")

    password = args.password or secrets.token_urlsafe(12)
    # bcrypt hash (cost 12 adequate for scale seeding; adjust with BCRYPT_ROUNDS env)
    rounds = int(os.getenv("BCRYPT_ROUNDS", "12"))
    salt = bcrypt.gensalt(rounds=rounds)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    prefix = os.getenv("USER_PREFIX", "cust_")
    chunk_size = int(os.getenv("USER_CHUNK_SIZE", "1000"))

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
            print(f"Customers needing accounts: {len(missing)} (chunk_size={chunk_size})")
            if args.dry_run:
                sample_rows = []
                for cid in missing[:10]:
                    sample_rows.append((cid, f"{prefix}{cid}", "<bcrypt_hash>", args.role))
                for r in sample_rows:
                    print("DRY-RUN sample:", r)
                print(f"Total rows prepared: {len(missing)} (no changes written) password={(password if args.password else '[auto-generated hidden]')}")
                return 0

            start = time.time()
            total_inserted = 0
            for i in range(0, len(missing), chunk_size):
                subset = missing[i:i+chunk_size]
                rows = []
                for cid in subset:
                    username = f"{prefix}{cid}"
                    rows.append((cid, username, hashed, args.role))
                cur.executemany(
                    "INSERT INTO Users(customer_id, username, password_hash, role) VALUES (%s, %s, %s, %s)",
                    rows,
                )
                total_inserted += len(rows)
                if total_inserted % (chunk_size * 5) == 0:
                    print(f"[progress] Inserted {total_inserted}/{len(missing)} users...")
            elapsed = time.time() - start
            print(f"[timing] User insert elapsed {elapsed:.2f}s; avg {(elapsed/total_inserted):.4f}s/user")
        conn.commit()
    print(f"Inserted {total_inserted} user accounts. Shared password: {password if args.password else '[random generated hidden]'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
