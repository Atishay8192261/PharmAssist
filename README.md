# PharmAssist

A web-based CRM and inventory management system for a wholesale pharmaceutical distributor.

## Stack
- Database: Neon (Serverless PostgreSQL)
- Backend: Python 3.10+ with Flask, psycopg 3
- AI: LangChain + LLM API (OpenAI/Gemini)
- Frontend: HTML/CSS/JS (thin client)

## Quick start

1. Create a Neon PostgreSQL database and copy the connection string.
2. Copy `.env.example` to `.env` and set `DATABASE_URL`.
3. Initialize schema:
   - Using psql (optional): `psql "$DATABASE_URL" -f db/schema.sql`
4. Install Python deps and run the API:
   - Create a venv and `pip install -r requirements.txt`
   - `python -m backend.app`

## Environment variables
- DATABASE_URL: Postgres connection string (Neon)
- FLASK_ENV: development | production (optional)
- SECRET_KEY: Flask secret (set in production)
- OPENAI_API_KEY or GOOGLE_API_KEY: for the AI stretch feature (optional for now)

## Project structure
- backend/: Flask app and DB code
- db/: SQL schema, procedures, and seed data
- frontend/: simple browser client (optional)

## Notes
- Stored procedure `sp_PlaceOrder` will implement SERIALIZABLE + SELECT ... FOR UPDATE locking.
- The API is intentionally thin and delegates concurrency to the database layer.

That's a great question. It's critical that the project doesn't just "work," but that it clearly *demonstrates* you've mastered the concepts from the course.

Our plan is built to hit every single one of your professor's requirements. Here’s exactly how we're taking care of them and, more importantly, **how you will show them in your final presentation.**

---

### 1. The Requirement: E-R Model & Relational Design

* **How We're Showing It:** This is your **`db/schema.sql`** file.
* **In Your Demo, You'll Say:** "Here is our logical E-R model, which we implemented in `schema.sql`. We separated `Products` from `Product_SKUs` and `Inventory_Batches` to achieve 3rd Normal Form and prevent data redundancy. For example, a single product like 'Paracetamol' can have multiple `SKUs` (500mg, 100mg), and each `SKU` can have multiple `Batches` with different expiry dates. This design is robust and scalable."

---

### 2. The Requirement: Transactions & Concurrency Control

* **How We're Showing It:** This is the **star of the project**: your **`db/procedures.sql`** file, which contains the `sp_PlaceOrder` stored procedure.
* **In Your Demo, You'll Say:** "The most complex part of a retail system is handling concurrency—what happens when two users try to buy the last item at the same time? We solved this at the database level using a stored procedure that runs in a `SERIALIZABLE` **transaction**.
* **Then you'll show the code and explain:**
    * **`TRANSACTION`**: "This ensures that all steps—checking stock, reducing quantity, and creating the order—happen as one atomic unit. If any part fails, the whole order is rolled back."
    * **`SELECT ... FOR UPDATE`**: "This is the key. When a user tries to buy, this command places a *pessimistic lock* on that specific inventory row. The second user *must wait* until the first user's transaction is finished. This makes it impossible to oversell."

---

### 3. The Requirement: Stored Procedures & Triggers

* **How We're Showing It:** The **`sp_PlaceOrder`** procedure is your primary example.
* **In Your Demo, You'll Say:** "We encapsulated all our critical business logic inside this stored procedure. The Flask API just makes one call: `CALL sp_PlaceOrder(...)`. This is more secure and efficient, as the logic lives right next to the data, and it reduces the number of round-trips between the application and the database."

---

### 4. The Requirement: Query Optimization & Indexes

* **How We're Showing It:** The `GET /api/products` endpoint and the `CREATE INDEX` commands in your `schema.sql`.
* **In Your Demo, You'll Say:** "Our product catalog query is complex, joining 5 tables to show customer-specific pricing and real-time stock.
    1.  **First, we'll run the query with `EXPLAIN ANALYZE` *without* indexes.** You'll show the high "cost" and slow speed.
    2.  **Then, you'll show the `CREATE INDEX` commands** in your `schema.sql`.
    3.  **Finally, you'll run the *same query* again.** You'll show the new, much lower "cost" and faster speed, proving our indexing strategy worked. This is a perfect, visual demo of optimization."

---

### 5. The Requirement: Scale Test Plan

* **How We're Showing It:** This is the *proof* that your concurrency control works.
* **In Your Demo, You'll Say:** "To prove our transaction logic works under pressure, we used a load-testing tool, `JMeter`, for our scale test. We simulated 100 users all trying to order the last 10 units of a single batch at the exact same time.
* **Then, you'll show the results:** "As you can see, only 10 orders succeeded, and the database stock is now 0. Our system did not fail, did not crash, and did not oversell. This proves our concurrency model is correct."

Our entire project is designed around these five key demos. You won't just *tell* your professor you did them; you'll **show** and **prove** them one by one.
