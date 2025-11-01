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
