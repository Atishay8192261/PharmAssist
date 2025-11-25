import os
import time
from contextlib import contextmanager

from dotenv import load_dotenv
from psycopg_pool import ConnectionPool
import socket

DB_DEBUG = os.getenv("DB_DEBUG", "0") == "1"

load_dotenv(override=True)

# Basic normalization / trimming (avoid hidden whitespace causing DNS failures)
raw_db_url = os.getenv("DATABASE_URL")
if raw_db_url is not None:
    raw_db_url = raw_db_url.strip()
    # Remove surrounding quotes if present in .env (dotenv usually strips but double insurance)
    if (raw_db_url.startswith('"') and raw_db_url.endswith('"')) or (raw_db_url.startswith("'") and raw_db_url.endswith("'")):
        raw_db_url = raw_db_url[1:-1]
    # Detect placeholder host patterns and raise early to avoid silent DNS loops
    if raw_db_url.startswith("postgresql://user:pass@host/"):
        print("[DB] ERROR: DATABASE_URL uses placeholder 'user:pass@host'. Update .env or unset conflicting shell var.")
        # Force failure so caller sees explicit misconfiguration
        raise RuntimeError("Invalid placeholder DATABASE_URL; please export real Neon connection string.")
    # Basic host validation: ensure we have '@' and a host portion
    if '@' not in raw_db_url:
        print("[DB] ERROR: DATABASE_URL missing '@' separator. Value:", raw_db_url)
        raise RuntimeError("Malformed DATABASE_URL.")
os.environ["DATABASE_URL"] = raw_db_url or ""

if os.getenv("DB_DEBUG") == "1":
    try:
        import pathlib
        print(f"[DB] cwd={os.getcwd()} .env_exists={pathlib.Path('.env').exists()} DATABASE_URL_present={bool(raw_db_url)} value_preview={repr((raw_db_url or '')[:80])}")
    except Exception:
        pass

DATABASE_URL = os.getenv("DATABASE_URL")
POOL_MIN = int(os.getenv("DB_POOL_MIN", "1"))
POOL_MAX = int(os.getenv("DB_POOL_MAX", "10"))
CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))

def _augment_conninfo(url: str) -> str:
    # Append connect_timeout if not provided already
    if "connect_timeout" in url:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}connect_timeout={CONNECT_TIMEOUT}"

# Initialize the pool if we have a DATABASE_URL; otherwise create lazily later.
if not DATABASE_URL:
    _pool = None
else:
    try:
        _pool = ConnectionPool(conninfo=_augment_conninfo(DATABASE_URL), min_size=POOL_MIN, max_size=POOL_MAX)
    except Exception as e:
        if DB_DEBUG:
            print("[DB] Initial pool creation failed:", e)
        # Defer creation until first use if initial DNS/connect fails
        _pool = None


def init_pool():
    """Ensure the pool is created and open."""
    global _pool
    if not DATABASE_URL:
        return
    if _pool is None:
        if DB_DEBUG:
            print("[DB] init_pool(): creating new pool with conninfo", repr(_augment_conninfo(DATABASE_URL)))
        _pool = ConnectionPool(conninfo=_augment_conninfo(DATABASE_URL), min_size=POOL_MIN, max_size=POOL_MAX)
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
    _pool = ConnectionPool(conninfo=_augment_conninfo(DATABASE_URL), min_size=POOL_MIN, max_size=POOL_MAX)


def get_pool() -> ConnectionPool:
    global _pool
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set in environment")
    if _pool is None:
        if DB_DEBUG:
            print("[DB] get_pool(): creating pool with conninfo", repr(_augment_conninfo(DATABASE_URL)))
        _pool = ConnectionPool(conninfo=_augment_conninfo(DATABASE_URL), min_size=POOL_MIN, max_size=POOL_MAX)
    return _pool


@contextmanager
def get_connection():
    pool = get_pool()
    attempts = 0
    max_attempts = int(os.getenv("DB_TRANSIENT_RETRIES", "5"))
    while True:
        try:
            with pool.connection() as conn:  # type: ignore
                _start = time.perf_counter()
                try:
                    yield conn
                finally:
                    try:
                        from flask import g, has_request_context  # type: ignore
                        if has_request_context():
                            elapsed_ms = (time.perf_counter() - _start) * 1000.0
                            try:
                                g.db_time_ms = (getattr(g, "db_time_ms", 0.0) or 0.0) + elapsed_ms  # type: ignore
                            except Exception:
                                pass
                    except Exception:
                        pass
                return
        except Exception as e:
            msg = str(e)
            if DB_DEBUG:
                try:
                    host_part = None
                    if DATABASE_URL and '@' in DATABASE_URL:
                        host_part = DATABASE_URL.split('@',1)[1].split('/',1)[0]
                    print(f"[DB] Connection attempt {attempts} failed: {msg}; host_part={host_part!r}")
                    if host_part:
                        try:
                            addrs = socket.getaddrinfo(host_part, 5432)
                            print("[DB] getaddrinfo results:", [a[4] for a in addrs])
                        except Exception as rerr:
                            print("[DB] getaddrinfo error:", rerr)
                except Exception:
                    pass
            attempts += 1
            transient_patterns = [
                "SSL connection has been closed",
                "server closed the connection unexpectedly",
                "connection not open",
                "nodename nor servname provided",
                "Temporary failure in name resolution",
            ]
            if any(p in msg for p in transient_patterns) and attempts < max_attempts:
                # Attempt DNS / connection recovery
                try:
                    reset_pool()
                except Exception:
                    pass
                time.sleep(min(1.0, 0.25 * attempts))
                continue
            raise
