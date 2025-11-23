import json
import os
import re
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

import google.generativeai as genai
from flask import Flask, jsonify, request, g
from flask_cors import CORS
from .db import init_pool, get_connection, reset_pool
from psycopg import IsolationLevel
from dotenv import load_dotenv
import bcrypt
import jwt
from functools import wraps
import threading
import time
import hashlib
from typing import Any
try:
    from .cache import cache_get, cache_set, cache_invalidate, cache_memo, cache_metrics
except ImportError:
    # Fallback no-op implementations if cache module missing
    def cache_get(key):
        return None
    def cache_set(key, value, ttl):
        return None
    def cache_invalidate(prefix):
        return None
    def cache_memo(key, ttl, fn):
        return fn()


def _make_access_token(payload: dict) -> str:
    secret = os.getenv("SECRET_KEY", "changeme")
    to_encode = dict(payload)
    to_encode.setdefault("exp", (datetime.utcnow() + timedelta(hours=1)))
    return jwt.encode(to_encode, secret, algorithm="HS256")


def requires_auth(role: str | None = None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                return jsonify({"error": "Missing or invalid Authorization header"}), 401
            token = auth.split(" ", 1)[1].strip()
            secret = os.getenv("SECRET_KEY", "changeme")
            try:
                claims = jwt.decode(token, secret, algorithms=["HS256"])  # type: ignore
            except Exception as e:
                return jsonify({"error": f"Invalid token: {e}"}), 401
            if role and claims.get("role") != role:
                return jsonify({"error": "Forbidden"}), 403
            # Optionally attach claims to request context (not used currently)
            request.user = claims  # type: ignore
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def create_app() -> Flask:
    # Load env from .env for local dev
    load_dotenv()

    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*"}})

    # Compression (gzip/brotli) optional via env ENABLE_COMPRESSION=1
    if os.getenv("ENABLE_COMPRESSION") == "1":
        try:
            from flask_compress import Compress
            Compress(app)
        except Exception:
            pass

    # Observability: optional timing middleware controlled by LOG_TIMING=1
    if os.getenv("LOG_TIMING") == "1":
        try:
            SLOW_REQUEST_MS = int(os.getenv("SLOW_REQUEST_MS", "500"))
        except Exception:
            SLOW_REQUEST_MS = 500
        try:
            SLOW_DB_MS = int(os.getenv("SLOW_DB_MS", "400"))
        except Exception:
            SLOW_DB_MS = 400

        @app.before_request
        def _timing_start():  # type: ignore
            try:
                g._req_start = time.perf_counter()
                g.db_time_ms = 0.0
            except Exception:
                pass

        @app.after_request
        def _timing_end(resp):  # type: ignore
            try:
                start = getattr(g, "_req_start", None)
                if start is not None:
                    dur_ms = (time.perf_counter() - start) * 1000.0
                    db_ms = float(getattr(g, "db_time_ms", 0.0) or 0.0)
                    resp.headers["X-Request-Duration"] = f"{dur_ms:.2f}ms"
                    resp.headers["X-DB-Time"] = f"{db_ms:.2f}ms"
                    # Server-Timing compatible header for browsers/clients
                    resp.headers["Server-Timing"] = f"app;dur={dur_ms:.2f}, db;dur={db_ms:.2f}"
                    # Slow request logging
                    if dur_ms >= SLOW_REQUEST_MS:
                        app.logger.warning(
                            "SLOW_REQUEST method=%s path=%s status=%s dur_ms=%.2f db_ms=%.2f",
                            request.method,
                            request.path,
                            getattr(resp, "status_code", 0),
                            dur_ms,
                            db_ms,
                        )
                    # High DB time logging
                    if db_ms >= SLOW_DB_MS:
                        app.logger.warning(
                            "SLOW_DB method=%s path=%s status=%s db_ms=%.2f total_ms=%.2f",
                            request.method,
                            request.path,
                            getattr(resp, "status_code", 0),
                            db_ms,
                            dur_ms,
                        )
            except Exception:
                pass
            return resp

    # Initialize DB pool early (will no-op if DATABASE_URL missing)
    try:
        init_pool()
    except Exception:
        # In dev without DB, health still works
        pass

    # Optional index bootstrap (controlled by RUN_INDEX_BOOTSTRAP=1)
    if os.getenv("RUN_INDEX_BOOTSTRAP") == "1":
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # Enable pg_trgm for faster ILIKE searches
                    cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
                    # Trigram indexes for product search related columns
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_products_name_trgm ON Products USING gin (name gin_trgm_ops)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_products_manufacturer_trgm ON Products USING gin (manufacturer gin_trgm_ops)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_skus_package_size_trgm ON Product_SKUs USING gin (package_size gin_trgm_ops)")
                    # Partial index excluding cancelled orders for dashboard aggregates
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_not_cancelled ON Orders(order_date) WHERE status <> 'cancelled'")
                    # FEFO batch selection optimization (only batches with stock)
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_batches_sku_expiry_qoh ON Inventory_Batches (sku_id, expiry_date) WHERE quantity_on_hand > 0")
                    # Pricing rule indexes to optimize discount subquery pattern
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_pricing_rules_sku_minqty ON Pricing_Rules (sku_id, min_quantity) WHERE customer_id IS NULL AND sku_id IS NOT NULL")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_pricing_rules_cust_minqty ON Pricing_Rules (customer_id, min_quantity) WHERE sku_id IS NULL AND customer_id IS NOT NULL")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_pricing_rules_sku_cust_minqty ON Pricing_Rules (sku_id, customer_id, min_quantity) WHERE sku_id IS NOT NULL AND customer_id IS NOT NULL")
                    # Inventory summary table + maintenance functions/triggers
                    cur.execute("""
                    CREATE TABLE IF NOT EXISTS Inventory_Summary (
                        sku_id INT PRIMARY KEY REFERENCES Product_SKUs(sku_id) ON DELETE CASCADE,
                        total_on_hand BIGINT NOT NULL DEFAULT 0,
                        earliest_expiry DATE
                    )
                    """)
                    # Refresh function (recomputes one sku's summary or deletes if no batches remain)
                    cur.execute("""
                    CREATE OR REPLACE FUNCTION inventory_summary_refresh(p_sku_id INT) RETURNS VOID AS $$
                    DECLARE
                        v_count INT;
                    BEGIN
                        SELECT COUNT(*) INTO v_count FROM Inventory_Batches WHERE sku_id = p_sku_id;
                        IF v_count = 0 THEN
                            DELETE FROM Inventory_Summary WHERE sku_id = p_sku_id;
                            RETURN;
                        END IF;
                        WITH agg AS (
                            SELECT sku_id,
                                   COALESCE(SUM(quantity_on_hand),0) AS total_on_hand,
                                   MIN(expiry_date) FILTER (WHERE quantity_on_hand > 0) AS earliest_expiry
                            FROM Inventory_Batches
                            WHERE sku_id = p_sku_id
                            GROUP BY sku_id
                        )
                        INSERT INTO Inventory_Summary(sku_id,total_on_hand,earliest_expiry)
                        SELECT sku_id,total_on_hand,earliest_expiry FROM agg
                        ON CONFLICT (sku_id) DO UPDATE SET
                          total_on_hand = EXCLUDED.total_on_hand,
                          earliest_expiry = EXCLUDED.earliest_expiry;
                    END; $$ LANGUAGE plpgsql;
                    """)
                    # Trigger function
                    cur.execute("""
                    CREATE OR REPLACE FUNCTION trg_inventory_batches_refresh() RETURNS trigger AS $$
                    BEGIN
                        IF TG_OP = 'DELETE' THEN
                            PERFORM inventory_summary_refresh(OLD.sku_id);
                        ELSE
                            PERFORM inventory_summary_refresh(NEW.sku_id);
                        END IF;
                        RETURN NULL;
                    END; $$ LANGUAGE plpgsql;
                    """)
                    # Attach triggers (idempotent by name)
                    cur.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_trigger WHERE tgname = 'inventory_batches_refresh_ai'
                        ) THEN
                            EXECUTE 'CREATE TRIGGER inventory_batches_refresh_ai AFTER INSERT ON Inventory_Batches FOR EACH ROW EXECUTE FUNCTION trg_inventory_batches_refresh()';
                        END IF;
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_trigger WHERE tgname = 'inventory_batches_refresh_au'
                        ) THEN
                            EXECUTE 'CREATE TRIGGER inventory_batches_refresh_au AFTER UPDATE ON Inventory_Batches FOR EACH ROW EXECUTE FUNCTION trg_inventory_batches_refresh()';
                        END IF;
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_trigger WHERE tgname = 'inventory_batches_refresh_ad'
                        ) THEN
                            EXECUTE 'CREATE TRIGGER inventory_batches_refresh_ad AFTER DELETE ON Inventory_Batches FOR EACH ROW EXECUTE FUNCTION trg_inventory_batches_refresh()';
                        END IF;
                    END; $$;
                    """)
                    # Initial backfill of summary (only for skus not yet present)
                    cur.execute("""
                    INSERT INTO Inventory_Summary(sku_id,total_on_hand,earliest_expiry)
                    SELECT b.sku_id,
                           COALESCE(SUM(b.quantity_on_hand),0) AS total_on_hand,
                           MIN(b.expiry_date) FILTER (WHERE b.quantity_on_hand > 0) AS earliest_expiry
                    FROM Inventory_Batches b
                    GROUP BY b.sku_id
                    ON CONFLICT (sku_id) DO NOTHING
                    """)
                conn.commit()
        except Exception as _e:
            # Non-fatal: continue startup even if index creation fails
            pass

    # Optional dashboard pre-warm thread
    if os.getenv("DASHBOARD_PREWARM") == "1":
        def _compute_dashboard_stats():
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT
                            COALESCE(SUM(oi.quantity_ordered * oi.sale_price),0) AS revenue,
                            COALESCE(SUM(oi.quantity_ordered * (oi.sale_price - b.cost_price)),0) AS profit,
                            COUNT(DISTINCT o.order_id) AS orders
                        FROM Orders o
                        JOIN Order_Items oi ON oi.order_id = o.order_id
                        JOIN Inventory_Batches b ON b.batch_id = oi.batch_id
                        WHERE o.status <> 'cancelled'
                        """
                    )
                    rev_row = cur.fetchone() or (0,0,0)
                    total_revenue, total_profit, total_orders = float(rev_row[0]), float(rev_row[1]), int(rev_row[2])

                    cur.execute("SELECT COUNT(*) FROM Inventory_Batches")
                    total_batches = int(cur.fetchone()[0])

                    cur.execute(
                        "SELECT COUNT(*) FROM Inventory_Batches WHERE expiry_date <= CURRENT_DATE + INTERVAL '30 days' AND quantity_on_hand > 0"
                    )
                    expiring_soon = int(cur.fetchone()[0])

                    cur.execute(
                        "SELECT COUNT(*) FROM Inventory_Batches WHERE quantity_on_hand <= 5"
                    )
                    low_stock_count = int(cur.fetchone()[0])

                    cur.execute(
                        """
                        SELECT
                            DATE(o.order_date) AS day,
                            COALESCE(SUM(oi.quantity_ordered * oi.sale_price),0) AS revenue,
                            COALESCE(SUM(oi.quantity_ordered * (oi.sale_price - b.cost_price)),0) AS profit
                        FROM Orders o
                        JOIN Order_Items oi ON oi.order_id = o.order_id
                        JOIN Inventory_Batches b ON b.batch_id = oi.batch_id
                        WHERE o.order_date >= CURRENT_DATE - INTERVAL '14 days'
                          AND o.status <> 'cancelled'
                        GROUP BY day
                        ORDER BY day ASC
                        """
                    )
                    daily_rows = cur.fetchall()
                    daily = [
                        {"day": r[0].isoformat(), "revenue": float(r[1]), "profit": float(r[2])}
                        for r in daily_rows
                    ]

                    cur.execute(
                        """
                        SELECT
                            DATE_TRUNC('week', o.order_date)::date AS week_start,
                            COALESCE(SUM(oi.quantity_ordered * oi.sale_price),0) AS revenue,
                            COALESCE(SUM(oi.quantity_ordered * (oi.sale_price - b.cost_price)),0) AS profit
                        FROM Orders o
                        JOIN Order_Items oi ON oi.order_id = o.order_id
                        JOIN Inventory_Batches b ON b.batch_id = oi.batch_id
                        WHERE o.order_date >= CURRENT_DATE - INTERVAL '56 days'
                          AND o.status <> 'cancelled'
                        GROUP BY week_start
                        ORDER BY week_start ASC
                        """
                    )
                    week_rows = cur.fetchall()
                    weekly = [
                        {"week_start": r[0].isoformat(), "revenue": float(r[1]), "profit": float(r[2])}
                        for r in week_rows
                    ]

            return {
                "total_revenue": total_revenue,
                "total_profit": total_profit,
                "total_orders": total_orders,
                "total_batches": total_batches,
                "expiring_soon": expiring_soon,
                "low_stock_count": low_stock_count,
                "daily": daily,
                "weekly": weekly,
            }

        def _prewarm_loop():
            interval = int(os.getenv("DASHBOARD_PREWARM_INTERVAL", "60"))
            ttl = int(os.getenv("CACHE_TTL_DASHBOARD", "60"))
            key = "dashboard:v1:stats"
            while True:
                try:
                    stats = _compute_dashboard_stats()
                    cache_set(key, stats, ttl)
                except Exception:
                    pass
                time.sleep(interval)

        t = threading.Thread(target=_prewarm_loop, name="dashboard-prewarm", daemon=True)
        t.start()

    # Optional products pre-warm thread (PRODUCTS_PREWARM=1)
    if os.getenv("PRODUCTS_PREWARM") == "1":
        def _products_prewarm_loop():
            interval = int(os.getenv("PRODUCTS_PREWARM_INTERVAL", "120"))
            ttl = int(os.getenv("CACHE_TTL_PRODUCTS", "30"))
            # Common key variants to pre-populate
            key_specs = [
                {"quantity": 1, "page": 1, "limit": 20, "search": ""},
            ]
            while True:
                for spec in key_specs:
                    customer_id = None
                    page = spec["page"]; limit = spec["limit"]; quantity = spec["quantity"]; search = spec["search"]
                    cache_key = f"products:v1:cid={customer_id}:q={quantity}:page={page}:limit={limit}:search={search}"
                    if cache_get(cache_key) is not None:
                        continue
                    try:
                        with get_connection() as conn:
                            with conn.cursor() as cur:
                                cur.execute(
                                    """
                                    SELECT
                                        p.product_id,
                                        p.name AS product_name,
                                        p.manufacturer,
                                        p.description,
                                        s.sku_id,
                                        s.package_size,
                                        s.unit_type,
                                        s.base_price,
                                        COALESCE(inv.total_on_hand,0) AS total_on_hand,
                                        inv.earliest_expiry,
                                        ROUND(
                                            s.base_price * (1 - COALESCE((
                                                SELECT MAX(r.discount_percentage)
                                                FROM Pricing_Rules r
                                                WHERE (r.sku_id IS NULL OR r.sku_id = s.sku_id)
                                                  AND COALESCE(r.min_quantity, 1) <= %s
                                                  AND (r.customer_id IS NULL OR r.customer_id = %s)
                                            ), 0)/100.0),
                                            2
                                        ) AS effective_price
                                    FROM Products p
                                    JOIN Product_SKUs s ON s.product_id = p.product_id
                                    LEFT JOIN Inventory_Summary inv ON inv.sku_id = s.sku_id
                                    ORDER BY p.product_id, s.sku_id
                                    LIMIT %s OFFSET %s
                                    """,
                                    (quantity, customer_id, limit, 0)
                                )
                                rows = cur.fetchall(); cols = [d[0] for d in cur.description]
                                items = []
                                for row in rows:
                                    rec = dict(zip(cols, row))
                                    try:
                                        if rec.get("base_price") is not None:
                                            rec["base_price"] = float(rec["base_price"])
                                        if rec.get("effective_price") is not None:
                                            rec["effective_price"] = float(rec["effective_price"])
                                        if rec.get("total_on_hand") is not None:
                                            rec["total_on_hand"] = int(rec["total_on_hand"])
                                    except Exception:
                                        pass
                                    items.append(rec)
                                response_body = {
                                    "customer_id": customer_id,
                                    "assumed_quantity_for_pricing": quantity,
                                    "items": items,
                                    "total_items": len(items),
                                    "total_pages": 1,
                                    "current_page": page,
                                    "page_size": limit,
                                    "search": search,
                                }
                                cache_set(cache_key, response_body, ttl)
                    except Exception:
                        pass
                time.sleep(interval)
        tp = threading.Thread(target=_products_prewarm_loop, name="products-prewarm", daemon=True)
        tp.start()

    @app.get("/health")
    def health():
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            db_ok = True
        except Exception:
            db_ok = False
        resp = jsonify({"status": "ok", "db": db_ok})
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return resp

    @app.get("/metrics")
    def metrics():
        # Simple JSON metrics; optionally output Prometheus format if METRICS_PROMETHEUS=1
        m = {
            "cache": cache_metrics(),
        }
        if os.getenv("METRICS_PROMETHEUS") == "1":
            # Plain text exposition for Prometheus scrape
            lines = [
                f"app_cache_hits_total {m['cache']['hits']}",
                f"app_cache_misses_total {m['cache']['misses']}",
                f"app_cache_expired_total {m['cache']['expired']}",
            ]
            return ("\n".join(lines) + "\n", 200, {"Content-Type": "text/plain; version=0.0.4"})
        return jsonify(m)

    @app.get("/api/products")
    def list_products():
        customer_id = request.args.get("customer_id", default=None, type=int)
        quantity = request.args.get("quantity", default=1, type=int)
        if not quantity or quantity <= 0:
            quantity = 1

        page = request.args.get("page", default=1, type=int)
        limit = request.args.get("limit", default=20, type=int)
        if page is None or page <= 0:
            page = 1
        if limit is None or limit <= 0:
            limit = 20
        if limit > 200:
            limit = 200
        offset = (page - 1) * limit

        search = request.args.get("search", default=None, type=str)

        def _build_search_tokens(raw: str) -> tuple[str, list]:
            tokens = [t.strip() for t in re.split(r"\s+", raw) if t.strip()]
            groups: list[str] = []
            params: list = []
            base_fields = [
                "p.name",
                "p.manufacturer",
                "COALESCE(p.description,'')",
                "s.package_size",
                "s.unit_type::text",
                "(p.name || ' ' || s.package_size)",
            ]
            for tok in tokens:
                if len(tok) < 2:
                    continue
                pattern = f"%{tok}%"
                ors_exprs = [f"{f} ILIKE %s" for f in base_fields]
                params.extend([pattern] * len(base_fields))
                if tok.isdigit():
                    ors_exprs.append("CAST(s.sku_id AS TEXT) = %s")
                    params.append(tok)
                    ors_exprs.append("CAST(s.sku_id AS TEXT) ILIKE %s")
                    params.append(pattern)
                groups.append("(" + " OR ".join(ors_exprs) + ")")
            if not groups:
                return "", []
            clause = " AND ".join(groups)
            # Sanity: count placeholders vs params length
            placeholder_count = clause.count("%s")
            if placeholder_count != len(params):
                # Return special clause that will yield empty results and signal mismatch
                return "(1=0)", []
            return clause, params

        search_clause_sql = ""
        search_params: list = []
        if search:
            clause_sql, params = _build_search_tokens(search)
            search_clause_sql = clause_sql
            search_params = params

        # If user provided search but no valid tokens after filtering, return empty set directly
        if search and not search_clause_sql:
            return jsonify({
                "customer_id": customer_id,
                "assumed_quantity_for_pricing": quantity,
                "items": [],
                "total_items": 0,
                "total_pages": 0,
                "current_page": page,
                "page_size": limit,
                "search": search,
                "note": "no valid tokens or placeholder mismatch",
            })

        where_sql = f"WHERE {search_clause_sql}" if search_clause_sql else ""

        sql_items = f"""
        SELECT
            p.product_id,
            p.name AS product_name,
            p.manufacturer,
            p.description,
            s.sku_id,
            s.package_size,
            s.unit_type,
            s.base_price,
            COALESCE(inv.total_on_hand, 0) AS total_on_hand,
            inv.earliest_expiry,
            ROUND(
                s.base_price * (1 - COALESCE((
                    SELECT MAX(r.discount_percentage)
                    FROM Pricing_Rules r
                    WHERE (r.sku_id IS NULL OR r.sku_id = s.sku_id)
                      AND COALESCE(r.min_quantity, 1) <= %s
                      AND (r.customer_id IS NULL OR r.customer_id = %s)
                ), 0)/100.0),
                2
            ) AS effective_price
        FROM Products p
        JOIN Product_SKUs s ON s.product_id = p.product_id
        LEFT JOIN Inventory_Summary inv ON inv.sku_id = s.sku_id
        {where_sql}
        ORDER BY p.product_id, s.sku_id
        LIMIT %s OFFSET %s
        """

        sql_count = f"""
        SELECT COUNT(*)
        FROM Product_SKUs s
        JOIN Products p ON p.product_id = s.product_id
        {where_sql}
        """

        # Parameter order MUST follow appearance in sql_items:
        # 1-2: discount subquery (%s for quantity, %s for customer_id)
        # 3..N: search clause placeholders (if any)
        # Last 2: LIMIT %s OFFSET %s
        params_items = [quantity, customer_id] + list(search_params) + [limit, offset]
        params_count = tuple(search_params)

        def _work():
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql_count, params_count)
                    total_items_row = cur.fetchone()
                    total_items_local = int(total_items_row[0]) if total_items_row else 0
                    # Basic sanity: count placeholders in items query
                    expected_placeholders = sql_items.count('%s')
                    if expected_placeholders != len(params_items):
                        raise ValueError(f"search_param_mismatch: expected {expected_placeholders} params, got {len(params_items)}")
                    cur.execute(sql_items, tuple(params_items))
                    rows_local = cur.fetchall()
                    cols_local = [desc[0] for desc in cur.description]
                    return total_items_local, rows_local, cols_local

        cache_ttl = int(os.getenv("CACHE_TTL_PRODUCTS", "30"))
        cache_key = f"products:v1:cid={customer_id}:q={quantity}:page={page}:limit={limit}:search={search or ''}"
        cached = cache_get(cache_key)
        if cached is not None:
            return jsonify(cached)

        try:
            total_items, rows, cols = _work()
        except Exception as e:
            msg = str(e)
            if (
                "SSL connection has been closed" in msg
                or "server closed the connection unexpectedly" in msg
                or "connection not open" in msg
            ):
                try:
                    reset_pool()
                except Exception:
                    pass
                total_items, rows, cols = _work()
            else:
                return jsonify({"error": msg}), 400

        items: list[dict] = []
        for row in rows:
            rec = dict(zip(cols, row))
            if rec.get("base_price") is not None:
                try:
                    rec["base_price"] = float(rec["base_price"])  # type: ignore
                except Exception:
                    pass
            if rec.get("effective_price") is not None:
                try:
                    rec["effective_price"] = float(rec["effective_price"])  # type: ignore
                except Exception:
                    pass
            if rec.get("total_on_hand") is not None:
                try:
                    rec["total_on_hand"] = int(rec["total_on_hand"])  # type: ignore
                except Exception:
                    pass
            items.append(rec)

        total_pages = (total_items + limit - 1) // limit if limit > 0 else 0
        response_body = {
            "customer_id": customer_id,
            "assumed_quantity_for_pricing": quantity,
            "items": items,
            "total_items": total_items,
            "total_pages": total_pages,
            "current_page": page,
            "page_size": limit,
            "search": search,
        }
        cache_set(cache_key, response_body, cache_ttl)
        resp = jsonify(response_body)
        resp.headers["Cache-Control"] = "private, max-age=30"
        return resp
        

    @app.post("/api/orders")
    @requires_auth()  # any authenticated user
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

        def _work():
            with get_connection() as conn:
                conn.isolation_level = IsolationLevel.SERIALIZABLE
                with conn.cursor() as cur:
                    cur.execute(
                        "CALL sp_PlaceOrder(%s, %s, %s, NULL, NULL, NULL)",
                        (customer_id, batch_id, quantity),
                    )
                    row_local = cur.fetchone()
                conn.commit()
                return row_local

        try:
            row = _work()
        except Exception as e:
            msg = str(e)
            if (
                "SSL connection has been closed" in msg
                or "server closed the connection unexpectedly" in msg
                or "connection not open" in msg
            ):
                try:
                    reset_pool()
                except Exception:
                    pass
                row = _work()
            else:
                if "Insufficient stock" in msg:
                    return jsonify({"error": msg}), 409
                return jsonify({"error": msg}), 400

        if not row or len(row) < 3:
            return jsonify({"error": "Unexpected database response"}), 500

        order_id, order_item_id, sale_price = row[0], row[1], float(row[2])
        # Invalidate caches impacted by inventory and pricing changes due to this order placement
        cache_invalidate("inventory:v1")
        cache_invalidate("dashboard:v1")
        cache_invalidate("products:v1")

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

    # requires_auth and _make_access_token are defined at module scope

    @app.post("/api/admin/add-inventory-nlp")
    @requires_auth(role="admin")
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

            # Lookup SKU by concatenated name with flexible fallback (exact then fuzzy)
            def _db_work():
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        # First: exact match (legacy)
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
                            # Try fuzzy: collapse whitespace/punctuation and ILIKE partials
                            cleaned = re.sub(r"[\s\-_/]+", " ", sku_name).strip()
                            tokens = [t for t in cleaned.split() if t]
                            if not tokens:
                                return None, None, None, "empty_tokens"
                            # Build AND ILIKE conditions
                            conds = " AND ".join(["(p.name || ' ' || s.package_size) ILIKE %s" for _ in tokens])
                            params = [f"%{t}%" for t in tokens]
                            cur.execute(
                                f"""
                                SELECT s.sku_id, s.base_price
                                FROM Product_SKUs s
                                JOIN Products p ON p.product_id = s.product_id
                                WHERE {conds}
                                ORDER BY s.sku_id ASC
                                LIMIT 1
                                """,
                                params,
                            )
                            row = cur.fetchone()
                            if not row:
                                return None, None, None, "no_match"
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
                        return sku_id_local, b_row_local[0], b_row_local[1], None

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

            if result[0] is None and result[1] is None and result[2] is None:
                reason = result[3]
                return jsonify({"error": f"SKU not found for name: {sku_name}", "reason": reason}), 404

            sku_id, batch_id_val, new_qoh, _reason = result

            ai_body = {
                "message": "Inventory batch added",
                "batch_id": int(batch_id_val),
                "sku_id": sku_id,
                "batch_no": batch_no,
                "quantity_added": quantity,
                "new_quantity_on_hand": int(new_qoh),
                "expiry_date": expiry_date.isoformat(),
                "source": model_name,
            }
            cache_invalidate("inventory:v1")
            cache_invalidate("dashboard:v1")
            cache_invalidate("products:v1")
            return jsonify(ai_body), 201
        except Exception as e:
            return jsonify({"error": str(e), "reason": "unhandled_exception"}), 400

    @app.post("/api/login")
    def login():
        try:
            payload = request.get_json(force=True) or {}
            username = payload.get("username")
            password = payload.get("password")
            if not username or not password:
                return jsonify({"error": "Missing username or password"}), 400
            def _work():
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT user_id, username, password_hash, role, customer_id
                            FROM Users
                            WHERE username = %s
                            LIMIT 1
                            """,
                            (username,),
                        )
                        return cur.fetchone()

            try:
                row = _work()
            except Exception as e:
                msg = str(e)
                if (
                    "SSL connection has been closed" in msg
                    or "server closed the connection unexpectedly" in msg
                    or "connection not open" in msg
                ):
                    try:
                        reset_pool()
                    except Exception:
                        pass
                    row = _work()
                else:
                    return jsonify({"error": msg}), 400

            if not row:
                return jsonify({"error": "Invalid credentials"}), 401

            user_id, _uname, stored_hash, role, customer_id = row
            try:
                ok = bcrypt.checkpw(
                    password.encode("utf-8"),
                    (stored_hash if isinstance(stored_hash, bytes) else stored_hash.encode("utf-8")),
                )
            except Exception:
                # In case stored_hash is malformed
                ok = False

            if not ok:
                return jsonify({"error": "Invalid credentials"}), 401

            token = _make_access_token({
                "sub": str(user_id),
                "username": _uname,
                "role": role,
                "customer_id": int(customer_id) if customer_id is not None else None,
            })
            return jsonify({
                "access_token": token,
                "token_type": "Bearer",
            }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.get("/api/my-orders")
    @requires_auth()  # any authenticated user
    def my_orders():
        try:
            claims = getattr(request, "user", {}) or {}
            customer_id = claims.get("customer_id")
            if customer_id is None:
                return jsonify({"error": "No customer_id associated with this user"}), 400
            sql = """
                SELECT o.order_id,
                       o.order_date,
                       o.status,
                       COALESCE(SUM(oi.quantity_ordered),0) AS total_quantity,
                       COALESCE(SUM(oi.quantity_ordered * oi.sale_price),0) AS total_price
                FROM Orders o
                LEFT JOIN Order_Items oi ON oi.order_id = o.order_id
                WHERE o.customer_id = %s
                GROUP BY o.order_id
                ORDER BY o.order_date DESC
            """
            def _work():
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(sql, (customer_id,))
                        rows_local = cur.fetchall()
                        cols_local = [d[0] for d in cur.description]
                        return rows_local, cols_local
            try:
                rows, cols = _work()
            except Exception as e:
                msg = str(e)
                if (
                    "SSL connection has been closed" in msg
                    or "server closed the connection unexpectedly" in msg
                    or "connection not open" in msg
                ):
                    try:
                        reset_pool()
                    except Exception:
                        pass
                    rows, cols = _work()
                else:
                    return jsonify({"error": msg}), 400
            data = []
            for r in rows:
                rec = dict(zip(cols, r))
                # Cast totals to numbers as the UI expects
                if rec.get("total_quantity") is not None:
                    try:
                        rec["total_quantity"] = int(rec["total_quantity"])  # type: ignore
                    except Exception:
                        pass
                if rec.get("total_price") is not None:
                    try:
                        rec["total_price"] = float(rec["total_price"])  # type: ignore
                    except Exception:
                        pass
                data.append(rec)
            return jsonify({"customer_id": customer_id, "orders": data})
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.get("/api/admin/all-orders")
    @requires_auth(role="admin")
    def all_orders():
        try:
            sql = """
                SELECT o.order_id,
                       o.order_date,
                       o.status,
                       o.customer_id,
                       COALESCE(SUM(oi.quantity_ordered),0) AS total_quantity,
                       COALESCE(SUM(oi.quantity_ordered * oi.sale_price),0) AS total_price
                FROM Orders o
                LEFT JOIN Order_Items oi ON oi.order_id = o.order_id
                GROUP BY o.order_id
                ORDER BY o.order_date DESC
            """
            def _work():
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(sql)
                        rows_local = cur.fetchall()
                        cols_local = [d[0] for d in cur.description]
                        return rows_local, cols_local
            try:
                rows, cols = _work()
            except Exception as e:
                msg = str(e)
                if (
                    "SSL connection has been closed" in msg
                    or "server closed the connection unexpectedly" in msg
                    or "connection not open" in msg
                ):
                    try:
                        reset_pool()
                    except Exception:
                        pass
                    rows, cols = _work()
                else:
                    return jsonify({"error": msg}), 400
            data = []
            for r in rows:
                rec = dict(zip(cols, r))
                if rec.get("total_quantity") is not None:
                    try:
                        rec["total_quantity"] = int(rec["total_quantity"])  # type: ignore
                    except Exception:
                        pass
                if rec.get("total_price") is not None:
                    try:
                        rec["total_price"] = float(rec["total_price"])  # type: ignore
                    except Exception:
                        pass
                data.append(rec)
            return jsonify({"orders": data})
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    # Cart Endpoints (moved before return so they register)

    @app.get("/api/cart")
    @requires_auth()
    def get_cart():
        try:
            claims = getattr(request, "user", {}) or {}
            user_id = int(claims.get("sub"))
            customer_id = claims.get("customer_id")  # may be None for admin accounts

            def _work():
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT cart_id FROM Carts WHERE user_id = %s LIMIT 1",
                            (user_id,),
                        )
                        row = cur.fetchone()
                        if not row:
                            cur.execute(
                                "INSERT INTO Carts(user_id) VALUES (%s) RETURNING cart_id",
                                (user_id,),
                            )
                            row = cur.fetchone()
                            conn.commit()
                        cart_id = int(row[0])
                        cur.execute(
                            """
                            SELECT ci.cart_item_id,
                                   ci.sku_id,
                                   ci.quantity,
                                   p.name AS product_name,
                                   p.manufacturer,
                                   p.description,
                                   s.package_size,
                                   s.unit_type,
                                   s.base_price,
                                   COALESCE(inv.available_stock, 0) AS available_stock,
                                   ROUND(
                                       s.base_price * (1 - COALESCE((
                                           SELECT MAX(r.discount_percentage)
                                           FROM Pricing_Rules r
                                           WHERE (r.sku_id IS NULL OR r.sku_id = s.sku_id)
                                             AND COALESCE(r.min_quantity, 1) <= ci.quantity
                                             AND (%s IS NULL OR r.customer_id IS NULL OR r.customer_id = %s)
                                       ), 0)/100.0), 2
                                   ) AS effective_price
                            FROM Cart_Items ci
                            JOIN Product_SKUs s ON s.sku_id = ci.sku_id
                            JOIN Products p ON p.product_id = s.product_id
                            LEFT JOIN (
                                SELECT b.sku_id, SUM(b.quantity_on_hand) AS available_stock
                                FROM Inventory_Batches b
                                GROUP BY b.sku_id
                            ) inv ON inv.sku_id = ci.sku_id
                            WHERE ci.cart_id = %s
                            ORDER BY ci.cart_item_id
                            """,
                            (customer_id, customer_id, cart_id),
                        )
                        rows = cur.fetchall()
                        cols = [d[0] for d in cur.description]
                        items = []
                        total_quantity = 0
                        total_price = 0.0
                        for r in rows:
                            rec = dict(zip(cols, r))
                            try:
                                rec["base_price"] = float(rec["base_price"])
                            except Exception:
                                pass
                            try:
                                rec["effective_price"] = float(rec["effective_price"])
                            except Exception:
                                pass
                            try:
                                rec["quantity"] = int(rec["quantity"])
                            except Exception:
                                pass
                            if rec.get("available_stock") is not None:
                                try:
                                    rec["available_stock"] = int(rec["available_stock"])
                                except Exception:
                                    pass
                            total_quantity += rec["quantity"]
                            total_price += rec["quantity"] * rec["effective_price"]
                            items.append(rec)
                        return cart_id, items, total_quantity, round(total_price, 2)
            try:
                cart_id, items, total_quantity, total_price = _work()
            except Exception as e:
                msg = str(e)
                if (
                    "SSL connection has been closed" in msg
                    or "server closed the connection unexpectedly" in msg
                    or "connection not open" in msg
                ):
                    try:
                        reset_pool()
                    except Exception:
                        pass
                    cart_id, items, total_quantity, total_price = _work()
                else:
                    return jsonify({"error": msg}), 400
            return jsonify({
                "cart_id": cart_id,
                "items": items,
                "total_items": len(items),
                "total_quantity": total_quantity,
                "estimated_total_price": total_price,
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.post("/api/cart")
    @requires_auth()
    def upsert_cart_item():
        try:
            claims = getattr(request, "user", {}) or {}
            user_id = int(claims.get("sub"))
            customer_id = claims.get("customer_id")
            body = request.get_json(force=True) or {}
            sku_id = body.get("sku_id")
            quantity = body.get("quantity")
            if sku_id is None or quantity is None:
                return jsonify({"error": "Missing sku_id or quantity"}), 400
            try:
                sku_id = int(sku_id); quantity = int(quantity)
            except Exception:
                return jsonify({"error": "sku_id and quantity must be integers"}), 400
            if quantity < 0:
                return jsonify({"error": "quantity must be >= 0"}), 400
            def _work():
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT cart_id FROM Carts WHERE user_id = %s LIMIT 1", (user_id,))
                        row = cur.fetchone()
                        if not row:
                            cur.execute("INSERT INTO Carts(user_id) VALUES (%s) RETURNING cart_id", (user_id,))
                            row = cur.fetchone()
                        cart_id = int(row[0])
                        # Determine available stock for sku
                        cur.execute("SELECT COALESCE(SUM(quantity_on_hand),0) FROM Inventory_Batches WHERE sku_id = %s", (sku_id,))
                        avail_row = cur.fetchone()
                        available = int(avail_row[0]) if avail_row and avail_row[0] is not None else 0
                        if quantity > available:
                            return {"stock_error": True, "available": available, "requested": quantity, "sku_id": sku_id}
                        if quantity == 0:
                            cur.execute("DELETE FROM Cart_Items WHERE cart_id = %s AND sku_id = %s RETURNING cart_item_id", (cart_id, sku_id))
                            deleted = cur.fetchone() is not None
                            conn.commit()
                            return {"removed": deleted, "cart_id": cart_id}
                        cur.execute("UPDATE Cart_Items SET quantity = %s WHERE cart_id = %s AND sku_id = %s RETURNING cart_item_id", (quantity, cart_id, sku_id))
                        row_upd = cur.fetchone()
                        if not row_upd:
                            cur.execute("INSERT INTO Cart_Items(cart_id, sku_id, quantity) VALUES (%s, %s, %s) RETURNING cart_item_id", (cart_id, sku_id, quantity))
                            row_upd = cur.fetchone()
                        cart_item_id = int(row_upd[0])
                        cur.execute(
                            """
                            SELECT ci.cart_item_id,
                                   ci.sku_id,
                                   ci.quantity,
                                   p.name AS product_name,
                                   p.manufacturer,
                                   s.package_size,
                                   s.unit_type,
                                   s.base_price,
                                   %s AS available_stock,
                                   ROUND(
                                       s.base_price * (1 - COALESCE((
                                           SELECT MAX(r.discount_percentage)
                                           FROM Pricing_Rules r
                                           WHERE (r.sku_id IS NULL OR r.sku_id = s.sku_id)
                                             AND COALESCE(r.min_quantity, 1) <= ci.quantity
                                             AND (%s IS NULL OR r.customer_id IS NULL OR r.customer_id = %s)
                                       ), 0)/100.0), 2
                                   ) AS effective_price
                            FROM Cart_Items ci
                            JOIN Product_SKUs s ON s.sku_id = ci.sku_id
                            JOIN Products p ON p.product_id = s.product_id
                            WHERE ci.cart_item_id = %s
                            LIMIT 1
                            """,
                            (available, customer_id, customer_id, cart_item_id),
                        )
                        item_row = cur.fetchone(); cols = [d[0] for d in cur.description]
                        item = dict(zip(cols, item_row)) if item_row else None
                        conn.commit()
                        return {"cart_id": cart_id, "item": item, "removed": False}
            try:
                result = _work()
            except Exception as e:
                msg = str(e)
                if (
                    "SSL connection has been closed" in msg
                    or "server closed the connection unexpectedly" in msg
                    or "connection not open" in msg
                ):
                    try:
                        reset_pool()
                    except Exception:
                        pass
                    result = _work()
                else:
                    return jsonify({"error": msg}), 400
            if isinstance(result, dict) and result.get("stock_error"):
                return jsonify({
                    "error": "Requested quantity exceeds available stock",
                    "sku_id": result.get("sku_id"),
                    "requested": result.get("requested"),
                    "available": result.get("available"),
                }), 409
            return jsonify(result)
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.post("/api/checkout")
    @requires_auth()
    def checkout():
        try:
            claims = getattr(request, "user", {}) or {}
            user_id = int(claims.get("sub"))
            customer_id = claims.get("customer_id")

            def _work():
                with get_connection() as conn:
                    conn.isolation_level = IsolationLevel.SERIALIZABLE
                    with conn.cursor() as cur:
                        # Lock cart
                        cur.execute("SELECT cart_id FROM Carts WHERE user_id = %s LIMIT 1 FOR UPDATE", (user_id,))
                        row = cur.fetchone()
                        if not row:
                            raise ValueError("Cart is empty")
                        cart_id = int(row[0])
                        # Get cart items
                        cur.execute(
                            """
                            SELECT ci.sku_id, ci.quantity, s.base_price
                            FROM Cart_Items ci
                            JOIN Product_SKUs s ON s.sku_id = ci.sku_id
                            WHERE ci.cart_id = %s
                            ORDER BY ci.cart_item_id ASC
                            """,
                            (cart_id,),
                        )
                        cart_items = cur.fetchall()
                        if not cart_items:
                            raise ValueError("Cart is empty")

                        # Create order (use customer_id, not user_id) to ensure it appears in /api/my-orders filtering
                        if customer_id is None:
                            raise ValueError("Customer account required for checkout")
                        cur.execute(
                            "INSERT INTO Orders(customer_id, status) VALUES (%s, 'pending') RETURNING order_id",
                            (customer_id,),
                        )
                        order_id = int(cur.fetchone()[0])

                        total_price = 0.0
                        order_item_rows = 0
                        # Iterate items FEFO
                        for sku_id, qty_needed, base_price in cart_items:
                            qty_needed = int(qty_needed)
                            # Ensure base_price as Decimal for precise monetary calc
                            base_price_dec = Decimal(str(base_price))
                            # Discount for this SKU total quantity
                            cur.execute(
                                """
                                SELECT COALESCE(MAX(discount_percentage),0) AS discount
                                FROM Pricing_Rules
                                WHERE (sku_id IS NULL OR sku_id = %s)
                                  AND (%s IS NULL OR customer_id IS NULL OR customer_id = %s)
                                  AND COALESCE(min_quantity,1) <= %s
                                """,
                                (sku_id, customer_id, customer_id, qty_needed),
                            )
                            disc_row = cur.fetchone()
                            discount_raw = disc_row[0] if disc_row else 0
                            # Normalize discount to int
                            try:
                                discount_int = int(discount_raw)
                            except Exception:
                                discount_int = int(Decimal(str(discount_raw)))
                            effective_price_dec = (base_price_dec * (Decimal(1) - (Decimal(discount_int) / Decimal(100)))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                            effective_price = float(effective_price_dec)

                            # Lock batches ordered by expiry (FEFO)
                            cur.execute(
                                """
                                SELECT batch_id, quantity_on_hand, cost_price
                                FROM Inventory_Batches
                                WHERE sku_id = %s AND quantity_on_hand > 0
                                ORDER BY expiry_date ASC
                                FOR UPDATE
                                """,
                                (sku_id,),
                            )
                            batches = cur.fetchall()
                            total_available = sum(b[1] for b in batches)
                            if total_available < qty_needed:
                                raise ValueError(f"Insufficient stock for sku_id {sku_id}: needed {qty_needed}, available {total_available}")

                            remaining = qty_needed
                            # Enforce minimum margin over cost per batch when recording sale price
                            try:
                                min_margin = Decimal(os.getenv("MIN_PROFIT_MARGIN", "0.015"))
                            except Exception:
                                min_margin = Decimal("0.015")
                            for batch_id, batch_qty, batch_cost in batches:
                                if remaining <= 0:
                                    break
                                take = batch_qty if batch_qty < remaining else remaining
                                # Deduct stock
                                cur.execute(
                                    "UPDATE Inventory_Batches SET quantity_on_hand = quantity_on_hand - %s WHERE batch_id = %s",
                                    (take, batch_id),
                                )
                                # Record order item
                                # Floor sale price to ensure at least min margin over batch cost
                                batch_cost_dec = Decimal(str(batch_cost))
                                floor_price_dec = (batch_cost_dec * (Decimal(1) + min_margin)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                                sale_price_dec = effective_price_dec if effective_price_dec >= floor_price_dec else floor_price_dec
                                sale_price = float(sale_price_dec)
                                cur.execute(
                                    """
                                    INSERT INTO Order_Items(order_id, batch_id, quantity_ordered, sale_price)
                                    VALUES (%s, %s, %s, %s)
                                    RETURNING order_item_id
                                    """,
                                    (order_id, batch_id, take, sale_price),
                                )
                                cur.fetchone()
                                total_price += take * sale_price
                                order_item_rows += 1
                                remaining -= take

                        # Clear cart
                        cur.execute("DELETE FROM Cart_Items WHERE cart_id = %s", (cart_id,))
                        cur.execute("DELETE FROM Carts WHERE cart_id = %s", (cart_id,))
                        conn.commit()
                        return {
                            "order_id": order_id,
                            "status": "pending",
                            "total_price": round(total_price, 2),
                            "order_item_rows": order_item_rows,
                        }

            try:
                result = _work()
            except Exception as e:
                msg = str(e)
                if (
                    "SSL connection has been closed" in msg
                    or "server closed the connection unexpectedly" in msg
                    or "connection not open" in msg
                ):
                    try:
                        reset_pool()
                    except Exception:
                        pass
                    result = _work()
                else:
                    if "Insufficient stock" in msg or "Cart is empty" in msg:
                        return jsonify({"error": msg}), (409 if msg.startswith("Insufficient") else 400)
                    return jsonify({"error": msg}), 400
            return jsonify(result), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.get("/api/admin/inventory")
    @requires_auth(role="admin")
    def admin_inventory_batches():
        try:
            # Query params
            page = request.args.get("page", default=1, type=int)
            limit = request.args.get("limit", default=50, type=int)
            search = (request.args.get("search") or "").strip()
            flt = (request.args.get("filter") or "").strip().lower()  # low-stock|critical|expiring|recent|''

            if page <= 0:
                page = 1
            if limit <= 0 or limit > 200:
                limit = 50

            # Build dynamic WHERE conditions
            conditions = []
            params: list[Any] = []
            if search:
                tokens = [t for t in re.split(r"\s+", search) if t]
                for t in tokens:
                    like = f"%{t}%"
                    conditions.append("((p.name || ' - ' || s.package_size) ILIKE %s OR b.batch_no ILIKE %s)")
                    params.extend([like, like])
            if flt == "low-stock":
                conditions.append("b.quantity_on_hand < 10")
            elif flt == "critical":
                # Match dashboard definition (<=5)
                conditions.append("b.quantity_on_hand <= 5")
            elif flt == "expiring":
                conditions.append("b.expiry_date <= CURRENT_DATE + INTERVAL '30 days' AND b.quantity_on_hand > 0")
            elif flt == "recent":
                conditions.append("b.batch_id > (SELECT COALESCE(MAX(batch_id)-50,0) FROM Inventory_Batches)")

            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

            # Cache key includes query params
            cache_key = f"inventory:v1:search={search}:filter={flt}:page={page}:limit={limit}"
            cache_ttl = int(os.getenv("CACHE_TTL_INVENTORY", "30"))
            cached = cache_get(cache_key)
            if cached is not None:
                # Support conditional request with ETag
                etag_in = request.headers.get("If-None-Match")
                if etag_in and cached.get("etag") == etag_in:
                    return ("", 304, {"ETag": etag_in})
                return jsonify(cached), 200

            def _work():
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        # Count total matching
                        cur.execute(
                            f"""
                            SELECT COUNT(*)
                            FROM Inventory_Batches b
                            JOIN Product_SKUs s ON s.sku_id = b.sku_id
                            JOIN Products p ON p.product_id = s.product_id
                            {where_clause}
                            """,
                            tuple(params),
                        )
                        total_matching = int(cur.fetchone()[0])

                        offset = (page - 1) * limit
                        cur.execute(
                            f"""
                            SELECT 
                                b.batch_id,
                                (p.name || ' - ' || s.package_size) AS sku_name,
                                b.batch_no,
                                b.expiry_date,
                                b.quantity_on_hand,
                                b.cost_price
                            FROM Inventory_Batches b
                            JOIN Product_SKUs s ON s.sku_id = b.sku_id
                            JOIN Products p ON p.product_id = s.product_id
                            {where_clause}
                            ORDER BY sku_name ASC, b.expiry_date ASC
                            LIMIT %s OFFSET %s
                            """,
                            tuple(params + [limit, offset]),
                        )
                        rows = cur.fetchall()
                        cols = [d[0] for d in cur.description]
                        items = []
                        for r in rows:
                            rec = dict(zip(cols, r))
                            if rec.get("quantity_on_hand") is not None:
                                try:
                                    rec["quantity_on_hand"] = int(rec["quantity_on_hand"])  # type: ignore
                                except Exception:
                                    pass
                            if rec.get("cost_price") is not None:
                                try:
                                    rec["cost_price"] = float(rec["cost_price"])  # type: ignore
                                except Exception:
                                    pass
                            if rec.get("expiry_date") is not None:
                                try:
                                    rec["expiry_date"] = rec["expiry_date"].isoformat()  # type: ignore
                                except Exception:
                                    pass
                            items.append(rec)

                        # ETag components
                        cur.execute(
                            f"""
                            SELECT COALESCE(MAX(b.batch_id),0) AS max_id,
                                   COUNT(*) AS cnt,
                                   COALESCE(MAX(b.expiry_date), CURRENT_DATE) AS last_expiry
                            FROM Inventory_Batches b
                            JOIN Product_SKUs s ON s.sku_id = b.sku_id
                            JOIN Products p ON p.product_id = s.product_id
                            {where_clause}
                            """,
                            tuple(params),
                        )
                        meta_row = cur.fetchone() or (0,0,datetime.utcnow().date())
                        max_id, cnt, last_expiry = meta_row
                        etag_source = f"{max_id}:{cnt}:{search}:{flt}:{total_matching}".encode()
                        etag = hashlib.sha1(etag_source).hexdigest()

                        total_pages = (total_matching + limit - 1) // limit if limit > 0 else 0
                        last_modified = (
                            last_expiry.isoformat() + "T00:00:00Z" if hasattr(last_expiry, 'isoformat') else datetime.utcnow().isoformat() + 'Z'
                        )

                        return {
                            "batches": items,
                            "total_batches": total_matching,
                            "total_pages": total_pages,
                            "current_page": page,
                            "page_size": limit,
                            "filter": flt,
                            "search": search,
                            "etag": etag,
                            "last_modified": last_modified,
                        }

            try:
                response_body = _work()
            except Exception as e:
                msg = str(e)
                if (
                    "SSL connection has been closed" in msg
                    or "server closed the connection unexpectedly" in msg
                    or "connection not open" in msg
                ):
                    try:
                        reset_pool()
                    except Exception:
                        pass
                    response_body = _work()
                else:
                    return jsonify({"error": msg}), 400

            cache_set(cache_key, response_body, cache_ttl)
            etag = response_body.get("etag")
            headers = {
                "ETag": etag,
                "Cache-Control": "private, max-age=30",
                "Last-Modified": response_body.get("last_modified", datetime.utcnow().isoformat()+"Z"),
            }
            etag_in = request.headers.get("If-None-Match")
            if etag_in and etag_in == etag:
                return ("", 304, headers)
            return jsonify(response_body), 200, headers
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    # Manual inventory CRUD endpoints
    @app.post("/api/admin/inventory/batches")
    @requires_auth(role="admin")
    def admin_create_inventory_batch():
        try:
            body = request.get_json(force=True) or {}
            sku_name = str(body.get("sku_name") or "").strip()
            sku_id_in = body.get("sku_id")
            batch_no = str(body.get("batch_no") or "").strip()
            quantity = body.get("quantity")
            expiry_date_raw = str(body.get("expiry_date") or "").strip()
            cost_price_override_raw = body.get("cost_price")  # optional user-supplied cost per unit
            if not ((sku_name or sku_id_in is not None) and batch_no and quantity and expiry_date_raw):
                return jsonify({"error": "Missing required fields (sku_id or sku_name, batch_no, quantity, expiry_date)", "reason": "missing_fields"}), 400
            try:
                quantity = int(quantity)
            except Exception:
                return jsonify({"error": "quantity must be integer", "reason": "bad_quantity_type"}), 400
            if quantity <= 0:
                return jsonify({"error": "quantity must be > 0", "reason": "quantity_le_zero"}), 400
            # Parse expiry date. Accept strict ISO (YYYY-MM-DD) and user-entered DD/MM/YYYY for convenience.
            expiry_date = None
            for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                try:
                    expiry_date = datetime.strptime(expiry_date_raw, fmt).date()
                    # If DD/MM/YYYY was provided, convert to ISO semantics already handled by .date()
                    break
                except Exception:
                    pass
            if expiry_date is None:
                return jsonify({"error": "expiry_date must be YYYY-MM-DD", "reason": "bad_expiry_format"}), 400

            def _work():
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        sku_id_local = None
                        base_price = None
                        sku_name_result = sku_name  # preserve original (may be blank if sku_id provided)
                        if sku_id_in is not None:
                            try:
                                sku_id_cast = int(sku_id_in)
                            except Exception:
                                return {"error": "Invalid sku_id format", "reason": "bad_sku_id_format"}
                            cur.execute(
                                """
                                SELECT s.sku_id, s.base_price, (p.name || ' - ' || s.package_size) AS sku_name
                                FROM Product_SKUs s
                                JOIN Products p ON p.product_id = s.product_id
                                WHERE s.sku_id = %s
                                LIMIT 1
                                """,
                                (sku_id_cast,),
                            )
                            row = cur.fetchone()
                            if not row:
                                return {"error": "SKU not found for id", "reason": "sku_id_not_found"}
                            sku_id_local, base_price, sku_name_db = int(row[0]), float(row[1]), row[2]
                            if not sku_name_result:
                                sku_name_result = sku_name_db
                        else:
                            cur.execute(
                                """
                                SELECT s.sku_id, s.base_price, (p.name || ' - ' || s.package_size) AS sku_name
                                FROM Product_SKUs s
                                JOIN Products p ON p.product_id = s.product_id
                                WHERE (p.name || ' ' || s.package_size) = %s
                                LIMIT 1
                                """,
                                (sku_name,),
                            )
                            row = cur.fetchone()
                            if not row:
                                return None
                            sku_id_local, base_price, sku_name_db = int(row[0]), float(row[1]), row[2]
                            sku_name_result = sku_name_db  # ensure canonical formatting with hyphen separator for UI consistency
                        # Determine cost_price: explicit override if provided and valid, else default 60% heuristic
                        cost_price = round(base_price * 0.6, 2)
                        override_used = False
                        if cost_price_override_raw is not None:
                            try:
                                cp_val = float(cost_price_override_raw)
                                if cp_val < 0:
                                    return {"error": "cost_price must be >= 0", "reason": "neg_cost_price"}
                                cost_price = round(cp_val, 2)
                                override_used = True
                            except Exception:
                                return {"error": "cost_price must be numeric", "reason": "bad_cost_price"}
                        cur.execute(
                            # On conflict: increment quantity; preserve existing cost_price unless override provided
                            (
                                "INSERT INTO Inventory_Batches(sku_id, batch_no, expiry_date, quantity_on_hand, cost_price) "
                                "VALUES (%s, %s, %s, %s, %s) "
                                "ON CONFLICT (sku_id, batch_no) DO UPDATE SET "
                                "quantity_on_hand = Inventory_Batches.quantity_on_hand + EXCLUDED.quantity_on_hand" + (
                                    ", cost_price = EXCLUDED.cost_price" if override_used else ""
                                ) + " RETURNING batch_id, quantity_on_hand, cost_price"
                            ),
                            (sku_id_local, batch_no, expiry_date, quantity, cost_price),
                        )
                        b_row = cur.fetchone()
                        conn.commit()
                        return {
                            "message": "Batch upserted",
                            "batch": {
                                "batch_id": int(b_row[0]),
                                "sku_name": sku_name_result,
                                "batch_no": batch_no,
                                "expiry_date": expiry_date.isoformat(),
                                "quantity_on_hand": int(b_row[1]),
                                "cost_price": float(b_row[2]),
                                "override_used": override_used,
                            },
                        }

            try:
                result = _work()
            except Exception as e:
                msg = str(e)
                if (
                    "SSL connection has been closed" in msg
                    or "server closed the connection unexpectedly" in msg
                    or "connection not open" in msg
                ):
                    try:
                        reset_pool()
                    except Exception:
                        pass
                    result = _work()
                else:
                    return jsonify({"error": msg}), 400
            if isinstance(result, dict) and result.get("error"):
                status = 404 if "not found" in result["error"] else 400
                return jsonify(result), status
            if result is None:
                return jsonify({"error": f"SKU not found for name: {sku_name}", "reason": "sku_name_not_found"}), 404
            cache_invalidate("inventory:v1")
            cache_invalidate("dashboard:v1")
            cache_invalidate("products:v1")
            return jsonify(result), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.put("/api/admin/inventory/batches/<int:batch_id>")
    @requires_auth(role="admin")
    def admin_update_inventory_batch(batch_id: int):
        try:
            body = request.get_json(force=True) or {}
            qty = body.get("quantity_on_hand")
            expiry_raw = body.get("expiry_date")
            cost_price = body.get("cost_price")
            if qty is None and expiry_raw is None and cost_price is None:
                return jsonify({"error": "No fields provided for update"}), 400
            updates = []
            params = []
            if qty is not None:
                try:
                    qty = int(qty)
                except Exception:
                    return jsonify({"error": "quantity_on_hand must be integer"}), 400
                if qty < 0:
                    return jsonify({"error": "quantity_on_hand must be >= 0"}), 400
                updates.append("quantity_on_hand = %s")
                params.append(qty)
            if expiry_raw is not None:
                try:
                    dt = datetime.strptime(str(expiry_raw), "%Y-%m-%d").date()
                except Exception:
                    return jsonify({"error": "expiry_date must be YYYY-MM-DD"}), 400
                updates.append("expiry_date = %s")
                params.append(dt)
            if cost_price is not None:
                try:
                    cost_price = float(cost_price)
                except Exception:
                    return jsonify({"error": "cost_price must be number"}), 400
                if cost_price < 0:
                    return jsonify({"error": "cost_price must be >= 0"}), 400
                updates.append("cost_price = %s")
                params.append(cost_price)
            params.append(batch_id)

            def _work():
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            f"UPDATE Inventory_Batches SET {', '.join(updates)} WHERE batch_id = %s RETURNING batch_id, sku_id, batch_no, expiry_date, quantity_on_hand, cost_price"
                            , params,
                        )
                        row = cur.fetchone()
                        if not row:
                            return None
                        cur.execute(
                            """
                            SELECT (p.name || ' - ' || s.package_size) AS sku_name
                            FROM Inventory_Batches b
                            JOIN Product_SKUs s ON s.sku_id = b.sku_id
                            JOIN Products p ON p.product_id = s.product_id
                            WHERE b.batch_id = %s
                            LIMIT 1
                            """,
                            (batch_id,),
                        )
                        sku_row = cur.fetchone()
                        conn.commit()
                        return {
                            "batch": {
                                "batch_id": int(row[0]),
                                "sku_name": sku_row[0] if sku_row else "",
                                "batch_no": row[2],
                                "expiry_date": row[3].isoformat() if row[3] else None,
                                "quantity_on_hand": int(row[4]),
                                "cost_price": float(row[5]),
                            }
                        }

            try:
                result = _work()
            except Exception as e:
                msg = str(e)
                if (
                    "SSL connection has been closed" in msg
                    or "server closed the connection unexpectedly" in msg
                    or "connection not open" in msg
                ):
                    try:
                        reset_pool()
                    except Exception:
                        pass
                    result = _work()
                else:
                    return jsonify({"error": msg}), 400
            if result is None:
                return jsonify({"error": "Batch not found"}), 404
            cache_invalidate("inventory:v1")
            cache_invalidate("dashboard:v1")
            cache_invalidate("products:v1")
            return jsonify(result)
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.delete("/api/admin/inventory/batches/<int:batch_id>")
    @requires_auth(role="admin")
    def admin_delete_inventory_batch(batch_id: int):
        try:
            def _work():
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM Inventory_Batches WHERE batch_id = %s RETURNING batch_id", (batch_id,))
                        row = cur.fetchone()
                        if not row:
                            return None
                        conn.commit()
                        return int(row[0])
            try:
                deleted_id = _work()
            except Exception as e:
                msg = str(e)
                if (
                    "SSL connection has been closed" in msg
                    or "server closed the connection unexpectedly" in msg
                    or "connection not open" in msg
                ):
                    try:
                        reset_pool()
                    except Exception:
                        pass
                    deleted_id = _work()
                else:
                    return jsonify({"error": msg}), 400
            if deleted_id is None:
                return jsonify({"error": "Batch not found"}), 404
            cache_invalidate("inventory:v1")
            cache_invalidate("dashboard:v1")
            cache_invalidate("products:v1")
            return jsonify({"deleted": True, "batch_id": deleted_id})
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    # Product & SKU creation endpoints (admin)
    @app.post("/api/admin/products")
    @requires_auth(role="admin")
    def admin_create_product():
        try:
            body = request.get_json(force=True) or {}
            name = str(body.get("name") or "").strip()
            manufacturer = str(body.get("manufacturer") or "").strip() or None
            description = body.get("description")
            if not name:
                return jsonify({"error": "name is required", "reason": "missing_name"}), 400
            def _work():
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO Products(name, manufacturer, description) VALUES (%s, %s, %s) RETURNING product_id, name, manufacturer, description",
                            (name, manufacturer, description),
                        )
                        row = cur.fetchone()
                        conn.commit()
                        return row
            try:
                row = _work()
            except Exception as e:
                msg = str(e)
                if (
                    "SSL connection has been closed" in msg
                    or "server closed the connection unexpectedly" in msg
                    or "connection not open" in msg
                ):
                    try: reset_pool()
                    except Exception: pass
                    row = _work()
                else:
                    return jsonify({"error": msg}), 400
            product_body = {
                "product_id": int(row[0]),
                "name": row[1],
                "manufacturer": row[2],
                "description": row[3],
            }
            cache_invalidate("products:v1")
            return jsonify(product_body), 201
        except Exception as e:
            return jsonify({"error": str(e), "reason": "unhandled_exception"}), 400

    @app.post("/api/admin/skus")
    @requires_auth(role="admin")
    def admin_create_sku():
        try:
            body = request.get_json(force=True) or {}
            product_id = body.get("product_id")
            package_size = str(body.get("package_size") or "").strip()
            unit_type = str(body.get("unit_type") or "").strip()
            base_price_raw = body.get("base_price")
            if not (product_id and package_size and unit_type and base_price_raw is not None):
                return jsonify({"error": "Missing required fields (product_id, package_size, unit_type, base_price)", "reason": "missing_fields"}), 400
            try:
                product_id = int(product_id)
            except Exception:
                return jsonify({"error": "product_id must be integer", "reason": "bad_product_id"}), 400
            try:
                base_price = float(base_price_raw)
            except Exception:
                return jsonify({"error": "base_price must be numeric", "reason": "bad_base_price"}), 400
            if base_price < 0:
                return jsonify({"error": "base_price must be >= 0", "reason": "neg_base_price"}), 400
            def _work():
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        # validate product exists
                        cur.execute("SELECT product_id FROM Products WHERE product_id = %s", (product_id,))
                        if not cur.fetchone():
                            return {"error": "Product not found", "reason": "product_not_found"}
                        cur.execute(
                            """
                            INSERT INTO Product_SKUs(product_id, package_size, unit_type, base_price)
                            VALUES (%s, %s, %s, %s)
                            RETURNING sku_id, product_id, package_size, unit_type, base_price
                            """,
                            (product_id, package_size, unit_type, base_price),
                        )
                        row = cur.fetchone()
                        conn.commit()
                        return row
            try:
                row = _work()
            except Exception as e:
                msg = str(e)
                if (
                    "SSL connection has been closed" in msg
                    or "server closed the connection unexpectedly" in msg
                    or "connection not open" in msg
                ):
                    try: reset_pool()
                    except Exception: pass
                    row = _work()
                else:
                    return jsonify({"error": msg}), 400
            if isinstance(row, dict) and row.get("error"):
                return jsonify(row), 404
            sku_body = {
                "sku_id": int(row[0]),
                "product_id": int(row[1]),
                "package_size": row[2],
                "unit_type": row[3],
                "base_price": float(row[4]),
            }
            cache_invalidate("products:v1")
            return jsonify(sku_body), 201
        except Exception as e:
            return jsonify({"error": str(e), "reason": "unhandled_exception"}), 400

    @app.post("/api/admin/orders/<int:order_id>/status")
    @requires_auth(role="admin")
    def admin_update_order_status(order_id: int):
        try:
            body = request.get_json(force=True) or {}
            status = (body.get("status") or "").strip().lower()
            allowed = {"pending", "processed", "shipped", "cancelled"}
            if status not in allowed:
                return jsonify({"error": f"Invalid status. Allowed: {sorted(list(allowed))}"}), 400

            def _work():
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE Orders SET status = %s WHERE order_id = %s RETURNING order_id, status",
                            (status, order_id),
                        )
                        row = cur.fetchone()
                        if not row:
                            return None
                        conn.commit()
                        return {"order_id": int(row[0]), "status": row[1]}

            try:
                result = _work()
            except Exception as e:
                msg = str(e)
                if (
                    "SSL connection has been closed" in msg
                    or "server closed the connection unexpectedly" in msg
                    or "connection not open" in msg
                ):
                    try:
                        reset_pool()
                    except Exception:
                        pass
                    result = _work()
                else:
                    return jsonify({"error": msg}), 400
            if result is None:
                return jsonify({"error": "Order not found"}), 404
            cache_invalidate("dashboard:v1")
            return jsonify(result)
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.get("/api/admin/dashboard-stats")
    @requires_auth(role="admin")
    def admin_dashboard_stats():
        try:
            cache_key = "dashboard:v1:stats"
            cache_ttl = int(os.getenv("CACHE_TTL_DASHBOARD", "60"))
            cached = cache_get(cache_key)
            if cached is not None:
                return jsonify(cached)
            def _work():
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        # Total revenue & profit
                        cur.execute(
                            """
                            SELECT
                                COALESCE(SUM(oi.quantity_ordered * oi.sale_price),0) AS revenue,
                                COALESCE(SUM(oi.quantity_ordered * (oi.sale_price - b.cost_price)),0) AS profit,
                                COUNT(DISTINCT o.order_id) AS orders
                            FROM Orders o
                            JOIN Order_Items oi ON oi.order_id = o.order_id
                            JOIN Inventory_Batches b ON b.batch_id = oi.batch_id
                            WHERE o.status <> 'cancelled'
                            """
                        )
                        rev_row = cur.fetchone() or (0,0,0)
                        total_revenue, total_profit, total_orders = float(rev_row[0]), float(rev_row[1]), int(rev_row[2])

                        # Total batches
                        cur.execute("SELECT COUNT(*) FROM Inventory_Batches")
                        total_batches = int(cur.fetchone()[0])

                        # Expiring soon (30 days)
                        cur.execute(
                            "SELECT COUNT(*) FROM Inventory_Batches WHERE expiry_date <= CURRENT_DATE + INTERVAL '30 days' AND quantity_on_hand > 0"
                        )
                        expiring_soon = int(cur.fetchone()[0])

                        # Low stock count (<=5)
                        cur.execute(
                            "SELECT COUNT(*) FROM Inventory_Batches WHERE quantity_on_hand <= 5"
                        )
                        low_stock_count = int(cur.fetchone()[0])

                        # Revenue & profit by day (last 14 days)
                        cur.execute(
                            """
                            SELECT
                                DATE(o.order_date) AS day,
                                COALESCE(SUM(oi.quantity_ordered * oi.sale_price),0) AS revenue,
                                COALESCE(SUM(oi.quantity_ordered * (oi.sale_price - b.cost_price)),0) AS profit
                            FROM Orders o
                            JOIN Order_Items oi ON oi.order_id = o.order_id
                            JOIN Inventory_Batches b ON b.batch_id = oi.batch_id
                            WHERE o.order_date >= CURRENT_DATE - INTERVAL '14 days'
                              AND o.status <> 'cancelled'
                            GROUP BY day
                            ORDER BY day ASC
                            """
                        )
                        daily_rows = cur.fetchall()
                        daily = [
                            {
                                "day": r[0].isoformat(),
                                "revenue": float(r[1]),
                                "profit": float(r[2]),
                            }
                            for r in daily_rows
                        ]

                        # Revenue & profit by ISO week (last 8 weeks)
                        cur.execute(
                            """
                            SELECT
                                DATE_TRUNC('week', o.order_date)::date AS week_start,
                                COALESCE(SUM(oi.quantity_ordered * oi.sale_price),0) AS revenue,
                                COALESCE(SUM(oi.quantity_ordered * (oi.sale_price - b.cost_price)),0) AS profit
                            FROM Orders o
                            JOIN Order_Items oi ON oi.order_id = o.order_id
                            JOIN Inventory_Batches b ON b.batch_id = oi.batch_id
                            WHERE o.order_date >= CURRENT_DATE - INTERVAL '56 days'
                              AND o.status <> 'cancelled'
                            GROUP BY week_start
                            ORDER BY week_start ASC
                            """
                        )
                        week_rows = cur.fetchall()
                        weekly = [
                            {
                                "week_start": r[0].isoformat(),
                                "revenue": float(r[1]),
                                "profit": float(r[2]),
                            }
                            for r in week_rows
                        ]
                        return {
                            "total_revenue": total_revenue,
                            "total_profit": total_profit,
                            "total_orders": total_orders,
                            "total_batches": total_batches,
                            "expiring_soon": expiring_soon,
                            "low_stock_count": low_stock_count,
                            "daily": daily,
                            "weekly": weekly,
                        }
            try:
                stats = _work()
            except Exception as e:
                msg = str(e)
                if (
                    "SSL connection has been closed" in msg
                    or "server closed the connection unexpectedly" in msg
                    or "connection not open" in msg
                ):
                    try:
                        reset_pool()
                    except Exception:
                        pass
                    stats = _work()
                else:
                    return jsonify({"error": msg}), 400
            cache_set(cache_key, stats, cache_ttl)
            r = jsonify(stats)
            r.headers["Cache-Control"] = "private, max-age=60"
            return r
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.get("/api/admin/orders/<int:order_id>/items")
    @requires_auth(role="admin")
    def admin_order_items(order_id: int):
        try:
            def _work():
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        # Ensure order exists
                        cur.execute("SELECT order_id, customer_id, order_date, status FROM Orders WHERE order_id = %s", (order_id,))
                        order_row = cur.fetchone()
                        if not order_row:
                            return None

                        cur.execute(
                            """
                            SELECT 
                                oi.order_item_id,
                                oi.quantity_ordered,
                                oi.sale_price,
                                b.batch_id,
                                b.batch_no,
                                b.cost_price,
                                s.sku_id,
                                s.base_price,
                                (p.name || ' - ' || s.package_size) AS sku_name
                            FROM Order_Items oi
                            JOIN Inventory_Batches b ON b.batch_id = oi.batch_id
                            JOIN Product_SKUs s ON s.sku_id = b.sku_id
                            JOIN Products p ON p.product_id = s.product_id
                            WHERE oi.order_id = %s
                            ORDER BY oi.order_item_id ASC
                            """,
                            (order_id,),
                        )
                        rows = cur.fetchall() or []

                        items = []
                        total_qty = 0
                        total_price = Decimal("0.00")
                        total_profit = Decimal("0.00")
                        for r in rows:
                            (
                                order_item_id,
                                qty,
                                sale_price,
                                batch_id,
                                batch_no,
                                cost_price,
                                sku_id,
                                base_price,
                                sku_name,
                            ) = r
                            qty_i = int(qty)
                            sp = Decimal(str(sale_price))
                            cp = Decimal(str(cost_price))
                            bp = Decimal(str(base_price)) if base_price is not None else Decimal("0")
                            # Compute discount only when sale below base; otherwise compute markup
                            discount_pct = 0.0
                            markup_pct = 0.0
                            if bp > 0:
                                if sp < bp:
                                    discount_pct = float((bp - sp) / bp * Decimal(100))
                                elif sp > bp:
                                    markup_pct = float((sp - bp) / bp * Decimal(100))
                            line_total = sp * qty_i
                            line_profit = (sp - cp) * qty_i
                            total_qty += qty_i
                            total_price += line_total
                            total_profit += line_profit
                            items.append({
                                "order_item_id": int(order_item_id),
                                "sku_id": int(sku_id),
                                "sku_name": sku_name,
                                "batch_id": int(batch_id),
                                "batch_no": batch_no,
                                "quantity": qty_i,
                                "base_price": float(bp),
                                "sale_price": float(sp),
                                "cost_price": float(cp),
                                "discount_pct": round(discount_pct, 2),
                                "markup_pct": round(markup_pct, 2),
                                "line_total": float(line_total),
                                "line_profit": float(line_profit),
                            })

                        result = {
                            "order": {
                                "order_id": int(order_row[0]),
                                "customer_id": int(order_row[1]),
                                "order_date": order_row[2].isoformat() if order_row[2] else None,
                                "status": order_row[3],
                            },
                            "items": items,
                            "totals": {
                                "total_quantity": int(total_qty),
                                "total_price": float(total_price),
                                "total_profit": float(total_profit),
                            }
                        }
                        return result

            try:
                data = _work()
            except Exception as e:
                msg = str(e)
                if (
                    "SSL connection has been closed" in msg
                    or "server closed the connection unexpectedly" in msg
                    or "connection not open" in msg
                ):
                    try:
                        reset_pool()
                    except Exception:
                        pass
                    data = _work()
                else:
                    return jsonify({"error": msg}), 400
            if data is None:
                return jsonify({"error": "Order not found"}), 404
            return jsonify(data)
        except Exception as e:
            return jsonify({"error": str(e)}), 400
    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
