import os
import random
import uuid
from datetime import date, timedelta

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from faker import Faker

# Scale targets (can be overridden via environment variables)
TARGET_CUSTOMERS = int(os.getenv("SCALE_CUSTOMERS", 500))
TARGET_PRODUCTS = int(os.getenv("SCALE_PRODUCTS", 1000))
TARGET_SKUS = int(os.getenv("SCALE_SKUS", 5000))
TARGET_BATCHES = int(os.getenv("SCALE_BATCHES", 20000))
CHUNK_SIZE = int(os.getenv("SCALE_CHUNK_SIZE", 1000))


def chunked(iterable, size):
    for i in range(0, len(iterable), size):
        yield iterable[i : i + size]


def main():
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set in the environment")

    fake = Faker()

    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            print("Seeding large dataset...")

            # 1) Customers
            print(f"Inserting {TARGET_CUSTOMERS} customers...")
            customers = []
            for _ in range(TARGET_CUSTOMERS):
                name = f"{fake.company()} {fake.company_suffix()}"
                address = fake.address().replace("\n", ", ")
                customer_type = random.choice(["Pharmacy", "Hospital"])
                customers.append((name[:255], address, customer_type))

            for batch in chunked(customers, CHUNK_SIZE):
                execute_values(
                    cur,
                    "INSERT INTO Customers(name, address, customer_type) VALUES %s",
                    batch,
                )
            print("Customers inserted.")

            # 2) Products
            print(f"Inserting {TARGET_PRODUCTS} products...")
            products = []
            for i in range(TARGET_PRODUCTS):
                name = f"{fake.unique.lexify(text='Drug-????')} {fake.word()}"
                manufacturer = fake.company()
                description = fake.sentence(nb_words=8)
                products.append((name[:255], manufacturer[:255], description))

            for batch in chunked(products, CHUNK_SIZE):
                execute_values(
                    cur,
                    "INSERT INTO Products(name, manufacturer, description) VALUES %s",
                    batch,
                )
            print("Products inserted.")

            # Fetch product_ids to reference in SKUs
            cur.execute("SELECT product_id FROM Products ORDER BY product_id")
            product_ids = [row[0] for row in cur.fetchall()]

            # 3) Product SKUs
            print(f"Inserting {TARGET_SKUS} product SKUs...")
            package_sizes = ["10-strip", "15-strip", "20-strip", "30-strip", "100-bottle", "50-vial"]
            unit_types = ["tablet", "capsule", "vial", "syrup"]
            skus = []
            for _ in range(TARGET_SKUS):
                product_id = random.choice(product_ids)
                package_size = random.choice(package_sizes)
                unit_type = random.choice(unit_types)
                base_price = round(random.uniform(0.5, 50.0), 2)
                skus.append((product_id, package_size[:100], unit_type[:50], base_price))

            for batch in chunked(skus, CHUNK_SIZE):
                execute_values(
                    cur,
                    """
                    INSERT INTO Product_SKUs(product_id, package_size, unit_type, base_price)
                    VALUES %s
                    """,
                    batch,
                )
            print("SKUs inserted.")

            # Fetch sku_ids to reference in batches
            cur.execute("SELECT sku_id FROM Product_SKUs ORDER BY sku_id")
            sku_ids = [row[0] for row in cur.fetchall()]

            # 4) Inventory Batches
            print(f"Inserting {TARGET_BATCHES} inventory batches...")
            batches = []
            today = date.today()
            for _ in range(TARGET_BATCHES):
                sku_id = random.choice(sku_ids)
                # Use UUID to avoid collisions per SKU for batch_no
                batch_no = f"B-{uuid.uuid4().hex[:10].upper()}"
                expiry_date = today + timedelta(days=random.randint(180, 365 * 3))
                quantity_on_hand = random.randint(0, 500)
                cost_price = round(random.uniform(0.2, 40.0), 2)
                batches.append(
                    (
                        sku_id,
                        batch_no[:100],
                        expiry_date,
                        quantity_on_hand,
                        cost_price,
                    )
                )

            for batch in chunked(batches, CHUNK_SIZE):
                execute_values(
                    cur,
                    """
                    INSERT INTO Inventory_Batches(sku_id, batch_no, expiry_date, quantity_on_hand, cost_price)
                    VALUES %s
                    ON CONFLICT (sku_id, batch_no) DO NOTHING
                    """,
                    batch,
                )
            print("Inventory batches inserted.")

        conn.commit()
    print("Scale data generation complete.")


if __name__ == "__main__":
    main()
