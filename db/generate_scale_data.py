import os
import random
import uuid
import time
from datetime import date, timedelta

import psycopg
from dotenv import load_dotenv
from faker import Faker

# Scale targets (can be overridden via environment variables)
TARGET_CUSTOMERS = int(os.getenv("SCALE_CUSTOMERS", 500))
TARGET_PRODUCTS = int(os.getenv("SCALE_PRODUCTS", 1000))
TARGET_SKUS = int(os.getenv("SCALE_SKUS", 5000))
TARGET_BATCHES = int(os.getenv("SCALE_BATCHES", 20000))
CHUNK_SIZE = int(os.getenv("SCALE_CHUNK_SIZE", 1000))
APPEND_MODE = os.getenv("SCALE_APPEND", "0") == "1"  # if false, will only fill up to targets


def chunked(iterable, size):
    for i in range(0, len(iterable), size):
        yield iterable[i : i + size]


def main():
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set in the environment")

    fake = Faker()

    start_all = time.time()
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            print("[scale] Starting scale data generation (append_mode=%s)" % APPEND_MODE)

            def existing_count(table):
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                return cur.fetchone()[0]

            # 1) Customers
            t0 = time.time()
            current = existing_count("Customers")
            target_insert = TARGET_CUSTOMERS if APPEND_MODE else max(0, TARGET_CUSTOMERS - current)
            print(f"[scale] Customers existing={current} target_total={TARGET_CUSTOMERS} will_insert={target_insert}")
            if target_insert:
                for _ in range(target_insert // CHUNK_SIZE + (1 if target_insert % CHUNK_SIZE else 0)):
                    remaining = target_insert - existing_count("Customers") if APPEND_MODE else target_insert
                    batch_size = min(CHUNK_SIZE, remaining) if not APPEND_MODE else CHUNK_SIZE
                    if batch_size <= 0:
                        break
                    rows = []
                    for _ in range(batch_size):
                        name = f"{fake.company()} {fake.company_suffix()}"
                        address = fake.address().replace("\n", ", ")
                        customer_type = random.choice(["Pharmacy", "Hospital"])
                        rows.append((name[:255], address, customer_type))
                    cur.executemany(
                        "INSERT INTO Customers(name, address, customer_type) VALUES (%s, %s, %s)",
                        rows,
                    )
                print("[scale] Customers inserted/ensured")
            else:
                print("[scale] Customers already meet/exceed target; skipping")
            print(f"[timing] Customers phase {time.time()-t0:.2f}s")

            # 2) Products
            t0 = time.time()
            current = existing_count("Products")
            target_insert = TARGET_PRODUCTS if APPEND_MODE else max(0, TARGET_PRODUCTS - current)
            print(f"[scale] Products existing={current} target_total={TARGET_PRODUCTS} will_insert={target_insert}")
            if target_insert:
                for _ in range(target_insert // CHUNK_SIZE + (1 if target_insert % CHUNK_SIZE else 0)):
                    remaining = target_insert - existing_count("Products") if APPEND_MODE else target_insert
                    batch_size = min(CHUNK_SIZE, remaining) if not APPEND_MODE else CHUNK_SIZE
                    if batch_size <= 0:
                        break
                    rows = []
                    for _ in range(batch_size):
                        name = f"{fake.unique.lexify(text='Drug-????')} {fake.word()}"
                        manufacturer = fake.company()
                        description = fake.sentence(nb_words=8)
                        rows.append((name[:255], manufacturer[:255], description))
                    cur.executemany(
                        "INSERT INTO Products(name, manufacturer, description) VALUES (%s, %s, %s)",
                        rows,
                    )
                print("[scale] Products inserted/ensured")
            else:
                print("[scale] Products already meet/exceed target; skipping")
            print(f"[timing] Products phase {time.time()-t0:.2f}s")

            # Fetch product_ids
            cur.execute("SELECT product_id FROM Products ORDER BY product_id")
            product_ids = [r[0] for r in cur.fetchall()]

            # 3) Product SKUs
            t0 = time.time()
            current = existing_count("Product_SKUs")
            target_insert = TARGET_SKUS if APPEND_MODE else max(0, TARGET_SKUS - current)
            print(f"[scale] SKUs existing={current} target_total={TARGET_SKUS} will_insert={target_insert}")
            if target_insert:
                package_sizes = ["10-strip", "15-strip", "20-strip", "30-strip", "100-bottle", "50-vial"]
                unit_types = ["tablet", "capsule", "vial", "syrup"]
                for _ in range(target_insert // CHUNK_SIZE + (1 if target_insert % CHUNK_SIZE else 0)):
                    remaining = target_insert - existing_count("Product_SKUs") if APPEND_MODE else target_insert
                    batch_size = min(CHUNK_SIZE, remaining) if not APPEND_MODE else CHUNK_SIZE
                    if batch_size <= 0:
                        break
                    rows = []
                    for _ in range(batch_size):
                        product_id = random.choice(product_ids)
                        package_size = random.choice(package_sizes)
                        unit_type = random.choice(unit_types)
                        base_price = round(random.uniform(0.5, 50.0), 2)
                        rows.append((product_id, package_size[:100], unit_type[:50], base_price))
                    cur.executemany(
                        "INSERT INTO Product_SKUs(product_id, package_size, unit_type, base_price) VALUES (%s, %s, %s, %s)",
                        rows,
                    )
                print("[scale] SKUs inserted/ensured")
            else:
                print("[scale] SKUs already meet/exceed target; skipping")
            print(f"[timing] SKUs phase {time.time()-t0:.2f}s")

            # Fetch sku_ids
            cur.execute("SELECT sku_id FROM Product_SKUs ORDER BY sku_id")
            sku_ids = [r[0] for r in cur.fetchall()]

            # 4) Inventory Batches
            t0 = time.time()
            current = existing_count("Inventory_Batches")
            target_insert = TARGET_BATCHES if APPEND_MODE else max(0, TARGET_BATCHES - current)
            print(f"[scale] Batches existing={current} target_total={TARGET_BATCHES} will_insert={target_insert}")
            if target_insert:
                today = date.today()
                for _ in range(target_insert // CHUNK_SIZE + (1 if target_insert % CHUNK_SIZE else 0)):
                    # We can't easily count inserted so far without re-query cost; just generate fixed chunk sizes.
                    batch_size = min(CHUNK_SIZE, target_insert) if not APPEND_MODE else CHUNK_SIZE
                    if batch_size <= 0:
                        break
                    rows = []
                    for _ in range(batch_size):
                        sku_id = random.choice(sku_ids)
                        batch_no = f"B-{uuid.uuid4().hex[:10].upper()}"
                        expiry_date = today + timedelta(days=random.randint(180, 365 * 3))
                        quantity_on_hand = random.randint(0, 500)
                        cost_price = round(random.uniform(0.2, 40.0), 2)
                        rows.append((sku_id, batch_no[:100], expiry_date, quantity_on_hand, cost_price))
                    cur.executemany(
                        """INSERT INTO Inventory_Batches(sku_id, batch_no, expiry_date, quantity_on_hand, cost_price)
                        VALUES (%s, %s, %s, %s, %s) ON CONFLICT (sku_id, batch_no) DO NOTHING""",
                        rows,
                    )
                    target_insert -= batch_size if not APPEND_MODE else 0
                    if not APPEND_MODE and target_insert <= 0:
                        break
                print("[scale] Batches inserted/ensured")
            else:
                print("[scale] Batches already meet/exceed target; skipping")
            print(f"[timing] Batches phase {time.time()-t0:.2f}s")

        conn.commit()
    print(f"[scale] Complete in {time.time()-start_all:.2f}s")


if __name__ == "__main__":
    main()
