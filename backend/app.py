from flask import Flask, jsonify, request
from flask_cors import CORS
from .db import init_pool, get_connection
from psycopg import IsolationLevel


def create_app() -> Flask:
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

    # Placeholders for future endpoints
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
              AND (
                    (%s IS NULL AND r.customer_id IS NULL)
                 OR (%s IS NOT NULL AND (r.customer_id IS NULL OR r.customer_id = %s))
              )
        ) d ON TRUE
        ORDER BY p.product_id, s.sku_id
        """

        params = (quantity, customer_id, customer_id, customer_id)

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

    @app.post("/api/admin/add-inventory-nlp")
    def add_inventory_nlp():
        return jsonify({"message": "Not implemented yet"}), 501

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
