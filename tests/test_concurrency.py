import os
import threading
import time
from dataclasses import dataclass

import psycopg2
import requests
from dotenv import load_dotenv

API_BASE = os.getenv("API_BASE", "http://localhost:5000")
NUM_THREADS = int(os.getenv("CONCURRENCY_THREADS", 10))
ORDER_QTY = int(os.getenv("CONCURRENCY_ORDER_QTY", 10))
TARGET_STOCK = int(os.getenv("CONCURRENCY_TARGET_STOCK", 50))
REQUEST_TIMEOUT = float(os.getenv("CONCURRENCY_TIMEOUT", 15))


@dataclass
class TargetBatch:
    batch_id: int
    quantity_on_hand: int
    customer_id: int


def find_or_prepare_batch(conn) -> TargetBatch:
    """Find a batch with stock near 50 and set it to exactly TARGET_STOCK for a reproducible test.
    Picks the first customer_id in the DB for ordering.
    """
    with conn.cursor() as cur:
        # Pick a customer to place orders
        cur.execute("SELECT customer_id FROM Customers ORDER BY customer_id LIMIT 1")
        row = cur.fetchone()
        if not row:
            raise RuntimeError("No customers found; seed or generate data first.")
        customer_id = int(row[0])

        # Find a batch with stock near TARGET_STOCK
        cur.execute(
            """
            SELECT batch_id, quantity_on_hand
            FROM Inventory_Batches
            WHERE quantity_on_hand > 0
            ORDER BY ABS(quantity_on_hand - %s), batch_id
            LIMIT 1
            """,
            (TARGET_STOCK,),
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError("No inventory batches with stock found.")
        batch_id, qty = int(row[0]), int(row[1])

        # Normalize stock to TARGET_STOCK to make the expected outcome deterministic
        if qty != TARGET_STOCK:
            cur.execute(
                "UPDATE Inventory_Batches SET quantity_on_hand = %s WHERE batch_id = %s",
                (TARGET_STOCK, batch_id),
            )
            conn.commit()
            qty = TARGET_STOCK
        return TargetBatch(batch_id=batch_id, quantity_on_hand=qty, customer_id=customer_id)


def place_order(batch: TargetBatch, results: list, index: int, start_barrier: threading.Barrier):
    start_barrier.wait()
    try:
        resp = requests.post(
            f"{API_BASE}/api/orders",
            json={
                "customer_id": batch.customer_id,
                "batch_id": batch.batch_id,
                "quantity": ORDER_QTY,
            },
            timeout=REQUEST_TIMEOUT,
        )
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text}
        results[index] = {
            "status": resp.status_code,
            "data": data,
        }
    except Exception as e:
        results[index] = {
            "status": None,
            "error": str(e),
        }


def main():
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL not set in environment")

    with psycopg2.connect(database_url) as conn:
        batch = find_or_prepare_batch(conn)
        print(
            f"Using batch_id={batch.batch_id} with stock={batch.quantity_on_hand}, "
            f"customer_id={batch.customer_id}; each thread orders {ORDER_QTY}."
        )

    # Prepare threads
    results = [None] * NUM_THREADS
    start_barrier = threading.Barrier(NUM_THREADS)
    threads = [
        threading.Thread(target=place_order, args=(batch, results, i, start_barrier))
        for i in range(NUM_THREADS)
    ]

    # Launch
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Summarize
    success = sum(1 for r in results if r and r.get("status") == 201)
    conflict = sum(
        1
        for r in results
        if r and r.get("status") == 409 and "Insufficient stock" in str(r.get("data"))
    )
    others = [r for r in results if r and r.get("status") not in (201, 409)]

    print("\nResults per thread:")
    for i, r in enumerate(results):
        print(f"Thread {i+1:02d}: {r}")

    print(
        f"\nSummary: success={success}, conflicts(Insufficient stock)={conflict}, others={len(others)}"
    )

    expected_success = TARGET_STOCK // ORDER_QTY
    if success == expected_success and conflict == (NUM_THREADS - expected_success) and not others:
        print("Test PASS: Concurrency control prevented the race correctly.")
    else:
        print("Test WARN: Results differ from expectation; check server logs and data state.")


if __name__ == "__main__":
    main()
