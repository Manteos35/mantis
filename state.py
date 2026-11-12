
from pathlib import Path
import sqlite3
import time

DB_PATH = Path(__file__).resolve().parent / "seen_tokens.db"
_FALLBACK_CACHE = set()


def _get_connection() -> sqlite3.Connection:
  conn = sqlite3.connect(str(DB_PATH), timeout=5.0)
  conn.execute("PRAGMA journal_mode=WAL;")
  conn.execute("PRAGMA synchronous=NORMAL;")
  return conn


def init_db() -> None:
  try:
    with _get_connection() as conn:
      conn.execute("""
                CREATE TABLE IF NOT EXISTS seen_tokens (
                    address TEXT PRIMARY KEY,
                    seen_at INTEGER NOT NULL
                )
            """)
      conn.execute(
          "CREATE INDEX IF NOT EXISTS idx_seen_at ON seen_tokens(seen_at);"
      )
  except Exception as e:
    print(f"[STATE] DB initialization error (using memory fallback): {e}")


def is_seen(address: str) -> bool:
  if not address:
    return True
  if address in _FALLBACK_CACHE:
    return True
  try:
    with _get_connection() as conn:
      cursor = conn.execute(
          "SELECT 1 FROM seen_tokens WHERE address = ? LIMIT 1", (address,)
      )
      return cursor.fetchone() is not None
  except Exception as e:
    print(f"[STATE] Read error for {address}: {e}")
    return address in _FALLBACK_CACHE


def mark_seen(address: str) -> bool:
  if not address:
    return False
  _FALLBACK_CACHE.add(address)
  if len(_FALLBACK_CACHE) > 5000:
    _FALLBACK_CACHE.pop()

  now = int(time.time())
  try:
    with _get_connection() as conn:
      conn.execute(
          "INSERT OR REPLACE INTO seen_tokens (address, seen_at) VALUES (?, ?)",
          (address, now),
      )
    return True
  except Exception as e:
    print(f"[STATE] Write error for {address}: {e}")
    return False


def cleanup_old(hours: int = 24) -> int:
  cutoff = int(time.time()) - (hours * 3600)
  try:
    with _get_connection() as conn:
      cursor = conn.execute(
          "DELETE FROM seen_tokens WHERE seen_at < ?", (cutoff,)
      )
      deleted = cursor.rowcount
      if deleted > 0:
        print(f"[STATE] Purged {deleted} expired records (> {hours}h).")
      return deleted
  except Exception as e:
    print(f"[STATE] Cleanup error: {e}")
    return 0



init_db()
