import os, time
import psycopg2
from psycopg2.extras import RealDictCursor


def run(sql, params=(), fetch="all"):
    """Run one statement on a fresh connection. fetch: all | one | None."""
    conn = psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall() if fetch == "all" else cur.fetchone() if fetch == "one" else None
        conn.commit()
        return rows
    finally:
        conn.close()


def init(statements, retries=30, delay=2):
    """Create tables; wait for the database container to accept connections."""
    for attempt in range(1, retries + 1):
        try:
            for s in statements:
                run(s, fetch=None)
            return
        except Exception as exc:  # database still starting
            print(f"[db] not ready ({attempt}/{retries}): {exc}", flush=True)
            time.sleep(delay)
    raise RuntimeError("database never became ready")
