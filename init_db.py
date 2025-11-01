import os

import psycopg2
from dotenv import load_dotenv


def main():
    # Load environment variables from .env
    load_dotenv()

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("Error: DATABASE_URL is not set in the environment.")
        return

    try:
        # Connect to the database
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                # Read schema SQL
                schema_path = os.path.join(os.path.dirname(__file__), "db", "schema.sql")
                with open(schema_path, "r", encoding="utf-8") as f:
                    sql = f.read()

                # Execute SQL and commit
                cur.execute(sql)
                conn.commit()

        print("Database initialized successfully!")
    except Exception as e:
        print(f"Error initializing database: {e}")


if __name__ == "__main__":
    main()
