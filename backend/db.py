import os
import time
from contextlib import contextmanager

from dotenv import load_dotenv
from psycopg_pool import ConnectionPool

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
POOL_MIN = int(os.getenv("DB_POOL_MIN", "1"))
POOL_MAX = int(os.getenv("DB_POOL_MAX", "10"))

# Initialize the pool if we have a DATABASE_URL; otherwise create lazily later.
if not DATABASE_URL:
    _pool = None
else:
    _pool = ConnectionPool(conninfo=DATABASE_URL, min_size=POOL_MIN, max_size=POOL_MAX)


def init_pool():
    """Ensure the pool is created and open."""
    global _pool
    if not DATABASE_URL:
        return
    if _pool is None:
        _pool = ConnectionPool(conninfo=DATABASE_URL, min_size=POOL_MIN, max_size=POOL_MAX)
    else:
        try:
            _pool.open()  # idempotent
        except Exception:
            pass


def reset_pool():
    """Force recreate the pool to clear any stale/closed connections (e.g., after Neon idle closes)."""
    global _pool
    if not DATABASE_URL:
        return
    try:
        if _pool is not None:
            _pool.close()
    except Exception:
        pass
    _pool = ConnectionPool(conninfo=DATABASE_URL, min_size=POOL_MIN, max_size=POOL_MAX)


def get_pool() -> ConnectionPool:
    global _pool
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set in environment")
    if _pool is None:
        _pool = ConnectionPool(conninfo=DATABASE_URL, min_size=POOL_MIN, max_size=POOL_MAX)
    return _pool


@contextmanager
def get_connection():
    pool = get_pool()
    with pool.connection() as conn:  # type: ignore
        _start = time.perf_counter()
        try:
            yield conn
        finally:
            try:
                # Accumulate DB time into Flask request context if available
                from flask import g, has_request_context  # type: ignore

                if has_request_context():
                    elapsed_ms = (time.perf_counter() - _start) * 1000.0
                    try:
                        g.db_time_ms = (getattr(g, "db_time_ms", 0.0) or 0.0) + elapsed_ms  # type: ignore
                    except Exception:
                        pass
            except Exception:
                # If Flask isn't available or no request context, silently ignore
                pass
