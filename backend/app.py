import json
import os
import re
from datetime import datetime

import google.generativeai as genai
from flask import Flask, jsonify, request
from flask_cors import CORS
from .db import init_pool, get_connection, reset_pool
from psycopg import IsolationLevel
from dotenv import load_dotenv


def create_app() -> Flask:
    # Load env from .env for local dev
    load_dotenv()

    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*"}})

    # Initialize DB pool early (will no-op if DATABASE_URL missing)
    try:
        init_pool()
    except Exception:
        # In dev without DB, health still works
        pass

    @app.get("/health")
    def health():
        # simple DB check if possible
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            db_ok = True
        except Exception:
            db_ok = False
        return jsonify({"status": "ok", "db": db_ok})

    @app.get("/api/products")
    def list_products():
        # Query params: customer_id (optional), quantity (optional, defaults to 1 for pricing tiers)
        customer_id = request.args.get("customer_id", default=None, type=int)
        quantity = request.args.get("quantity", default=1, type=int)
        if not quantity or quantity <= 0:
            quantity = 1

        sql = """
        SELECT
            p.product_id,
            p.name AS product_name,
            p.manufacturer,
            p.description,
            s.sku_id,
            s.package_size,
            s.unit_type,
            s.base_price,
            COALESCE(st.total_on_hand, 0) AS total_on_hand,
            st.earliest_expiry,
            ROUND(s.base_price * (1 - COALESCE(d.discount_percentage, 0)/100.0), 2) AS effective_price
        FROM Products p
        JOIN Product_SKUs s ON s.product_id = p.product_id
        LEFT JOIN (
            SELECT b.sku_id,
                   SUM(b.quantity_on_hand) AS total_on_hand,
                   MIN(b.expiry_date) FILTER (WHERE b.quantity_on_hand > 0) AS earliest_expiry
            FROM Inventory_Batches b
            GROUP BY b.sku_id
        ) st ON st.sku_id = s.sku_id
        LEFT JOIN LATERAL (
            SELECT COALESCE(MAX(r.discount_percentage), 0) AS discount_percentage
            FROM Pricing_Rules r
            WHERE (r.sku_id IS NULL OR r.sku_id = s.sku_id)
              AND COALESCE(r.min_quantity, 1) <= %s
              AND (r.customer_id IS NULL OR r.customer_id = %s)
        ) d ON TRUE
        ORDER BY p.product_id, s.sku_id
        """

        params = (quantity, customer_id)

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    rows = cur.fetchall()
                    cols = [desc[0] for desc in cur.description]

            items = [dict(zip(cols, row)) for row in rows]
            return jsonify({
                "customer_id": customer_id,
                "assumed_quantity_for_pricing": quantity,
                "items": items,
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.post("/api/orders")
    def place_order():
        # Expected JSON: { customer_id: int, batch_id: int, quantity: int }
        try:
            data = request.get_json(force=True) or {}
            customer_id = int(data.get("customer_id"))
            batch_id = int(data.get("batch_id"))
            quantity = int(data.get("quantity"))
        except Exception:
            return jsonify({"error": "Invalid or missing JSON fields: customer_id, batch_id, quantity"}), 400

        if quantity <= 0:
            return jsonify({"error": "quantity must be > 0"}), 400

        try:
            with get_connection() as conn:
                # Manage transaction in Python with SERIALIZABLE isolation
                conn.isolation_level = IsolationLevel.SERIALIZABLE
                with conn.cursor() as cur:
                    # sp_PlaceOrder has OUT params: (o_order_id, o_order_item_id, o_sale_price)
                    cur.execute(
                        "CALL sp_PlaceOrder(%s, %s, %s, NULL, NULL, NULL)",
                        (customer_id, batch_id, quantity),
                    )
                    row = cur.fetchone()
                # Commit on success
                conn.commit()

            if not row or len(row) < 3:
                return jsonify({"error": "Unexpected database response"}), 500

            order_id, order_item_id, sale_price = row[0], row[1], float(row[2])
            return (
                jsonify(
                    {
                        "order_id": order_id,
                        "order_item_id": order_item_id,
                        "sale_price": sale_price,
                        "status": "processed",
                    }
                ),
                201,
            )
        except Exception as e:
            # Translate DB errors (e.g., insufficient stock) to 409 Conflict
            message = str(e)
            if "Insufficient stock" in message:
                return jsonify({"error": message}), 409
            return jsonify({"error": message}), 400

    def _choose_gemini_model():
        # Accept either plain name (gemini-2.5-flash) or full (models/gemini-2.5-flash)
        desired = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
        if desired.startswith("models/"):
            desired = desired.split("/", 1)[1]

        candidates = [desired, "gemini-flash-latest", "gemini-2.0-flash", "gemini-pro-latest"]
        last_err = None
        for name in candidates:
            try:
                m = genai.GenerativeModel(name)
                # Light ping to validate availability without generating content
                try:
                    m.count_tokens("ping")
                except Exception:
                    # Some models may not support countTokens yet; try a minimal dry run
                    pass
                return m, name
            except Exception as e:
                last_err = e
                continue
        raise RuntimeError(f"No supported Gemini model available from candidates: {candidates}. Last error: {last_err}")

    @app.post("/api/admin/add-inventory-nlp")
    def add_inventory_nlp():
        try:
            body = request.get_json(force=True) or {}
            text = body.get("text")
            if not text or not isinstance(text, str):
                return jsonify({"error": "Missing 'text' field in request body"}), 400

            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                return jsonify({"error": "GOOGLE_API_KEY not configured"}), 500

            # Configure and call Gemini API (stable)
            genai.configure(api_key=api_key)
            model, model_name = _choose_gemini_model()

            prompt = (
                "Parse this instruction and return a JSON object with keys: sku_name, batch_no, "
                "quantity, expiry_date. The expiry_date must be ISO YYYY-MM-DD (use the first day "
                "of the month if only month+year are provided). Return ONLY JSON.\n"
                f"Instruction: {text}\n"
                "Example:\n{\n  \"sku_name\": \"Paracetamol 500mg 10-strip\",\n  \"batch_no\": \"P500-A3\",\n  \"quantity\": 100,\n  \"expiry_date\": \"2028-06-01\"\n}"
            )

            response = model.generate_content(prompt)
            ai_text = (getattr(response, "text", None) or "").strip()
            if not ai_text:
                return jsonify({"error": "Empty response from Gemini"}), 502

            # Extract JSON from possible markdown fences
            m = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", ai_text, re.IGNORECASE)
            if m:
                ai_text = m.group(1)
            else:
                m2 = re.search(r"(\{[\s\S]*\})", ai_text)
                ai_text = m2.group(1) if m2 else ai_text

            try:
                parsed = json.loads(ai_text)
            except Exception as e:
                return jsonify({"error": f"Gemini returned invalid JSON: {e}", "raw": ai_text}), 502

            # Validate fields
            for key in ("sku_name", "batch_no", "quantity", "expiry_date"):
                if key not in parsed:
                    return jsonify({"error": f"Missing field from AI output: {key}", "raw": parsed}), 502

            sku_name = str(parsed["sku_name"]).strip()
            batch_no = str(parsed["batch_no"]).strip()
            try:
                quantity = int(parsed["quantity"])
            except Exception:
                return jsonify({"error": "quantity must be an integer"}), 400
            if quantity <= 0:
                return jsonify({"error": "quantity must be > 0"}), 400

            exp_raw = str(parsed["expiry_date"]).strip()
            expiry_date = None
            for fmt in ("%Y-%m-%d", "%B %Y", "%b %Y", "%Y/%m/%d", "%m/%d/%Y"):
                try:
                    dt = datetime.strptime(exp_raw, fmt)
                    if fmt in ("%B %Y", "%b %Y"):
                        dt = dt.replace(day=1)
                    expiry_date = dt.date()
                    break
                except Exception:
                    pass
            if expiry_date is None:
                return jsonify({"error": f"Could not parse expiry_date: {exp_raw}"}), 400

            # Lookup SKU by concatenated name "ProductName package_size" with one retry on SSL/closed errors
            def _db_work():
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT s.sku_id, s.base_price
                            FROM Product_SKUs s
                            JOIN Products p ON p.product_id = s.product_id
                            WHERE (p.name || ' ' || s.package_size) = %s
                            LIMIT 1
                            """,
                            (sku_name,),
                        )
                        row = cur.fetchone()
                        if not row:
                            return None, None, None
                        sku_id_local, base_price = int(row[0]), float(row[1])

                        cost_price = round(base_price * 0.6, 2)
                        cur.execute(
                            """
                            INSERT INTO Inventory_Batches(sku_id, batch_no, expiry_date, quantity_on_hand, cost_price)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (sku_id, batch_no)
                            DO UPDATE SET quantity_on_hand = Inventory_Batches.quantity_on_hand + EXCLUDED.quantity_on_hand
                            RETURNING batch_id, quantity_on_hand
                            """,
                            (sku_id_local, batch_no, expiry_date, quantity, cost_price),
                        )
                        b_row_local = cur.fetchone()
                        conn.commit()
                        return sku_id_local, b_row_local[0], b_row_local[1]

            try:
                result = _db_work()
            except Exception as e:
                msg = str(e)
                if (
                    "SSL connection has been closed" in msg
                    or "server closed the connection unexpectedly" in msg
                    or "connection not open" in msg
                ):
                    # Recreate pool and retry once
                    try:
                        reset_pool()
                    except Exception:
                        pass
                    result = _db_work()
                else:
                    raise

            if result == (None, None, None):
                return jsonify({"error": f"SKU not found for name: {sku_name}"}), 404

            sku_id, batch_id_val, new_qoh = result

            return (
                jsonify(
                    {
                        "message": "Inventory batch added",
                        "batch_id": int(batch_id_val),
                        "sku_id": sku_id,
                        "batch_no": batch_no,
                        "quantity_added": quantity,
                        "new_quantity_on_hand": int(new_qoh),
                        "expiry_date": expiry_date.isoformat(),
                        "source": model_name,
                    }
                ),
                201,
            )
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
