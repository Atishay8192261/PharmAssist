import os
from contextlib import contextmanager

from dotenv import load_dotenv
from psycopg_pool import ConnectionPool

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Initialize the pool if we have a DATABASE_URL; otherwise create lazily later.
if not DATABASE_URL:
    _pool = None
else:
    # Open immediately; avoid relying on non-existent 'opened' attribute
    _pool = ConnectionPool(conninfo=DATABASE_URL, min_size=1, max_size=10)


def init_pool():
    """Ensure the pool is created and open."""
    global _pool
    if not DATABASE_URL:
        return
    if _pool is None:
        _pool = ConnectionPool(conninfo=DATABASE_URL, min_size=1, max_size=10)
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
    _pool = ConnectionPool(conninfo=DATABASE_URL, min_size=1, max_size=10)


def get_pool() -> ConnectionPool:
    global _pool
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set in environment")
    if _pool is None:
        _pool = ConnectionPool(conninfo=DATABASE_URL, min_size=1, max_size=10)
    return _pool


@contextmanager
def get_connection():
    pool = get_pool()
    with pool.connection() as conn:  # type: ignore
        yield conn
