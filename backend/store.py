import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional

_DB = Path(__file__).parent / "data" / "app.db"
_DATA = Path(__file__).parent / "data"


@contextmanager
def _db():
    con = sqlite3.connect(_DB, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def _load(row) -> dict:
    d = dict(row)
    for key in ("manages_queue_ids", "assigned_to_user_ids", "value", "scope", "filter"):
        if key in d and d[key] is not None:
            try:
                d[key] = json.loads(d[key])
            except (json.JSONDecodeError, TypeError):
                pass
    for key in ("read", "is_shared"):
        if key in d:
            d[key] = bool(d[key])
    return d


def init_db() -> None:
    with _db() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                manages_queue_ids TEXT
            );
            CREATE TABLE IF NOT EXISTS notification_configs (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                assigned_to_user_ids TEXT NOT NULL,
                label TEXT NOT NULL,
                event_type TEXT NOT NULL,
                field TEXT NOT NULL,
                comparator TEXT NOT NULL,
                value TEXT NOT NULL,
                value_mode TEXT NOT NULL DEFAULT 'absolute',
                scope TEXT,
                filter TEXT,
                is_shared INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS notifications (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                config_id TEXT NOT NULL,
                config_label TEXT NOT NULL,
                triggered_by_event_id TEXT NOT NULL,
                triggered_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                message TEXT NOT NULL,
                read INTEGER NOT NULL DEFAULT 0,
                is_shared INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS notification_history (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                config_id TEXT NOT NULL,
                config_label TEXT NOT NULL,
                triggered_by_event_id TEXT NOT NULL,
                triggered_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                message TEXT NOT NULL,
                read INTEGER NOT NULL DEFAULT 0,
                is_shared INTEGER NOT NULL DEFAULT 0,
                resolved_at TEXT,
                resolved_by_event_id TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id);
            CREATE INDEX IF NOT EXISTS idx_hist_user ON notification_history(user_id);
        """)

        if con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            users = json.loads((_DATA / "users.json").read_text())
            con.executemany(
                "INSERT INTO users VALUES (?,?,?,?)",
                [(u["user_id"], u["name"], u["role"],
                  json.dumps(u.get("manages_queue_ids"))) for u in users],
            )

        if con.execute("SELECT COUNT(*) FROM notification_configs").fetchone()[0] == 0:
            configs = json.loads((_DATA / "notification_configs.json").read_text())
            con.executemany(
                "INSERT INTO notification_configs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                [(c["config_id"], c["user_id"],
                  json.dumps(c["assigned_to_user_ids"]), c["label"],
                  c["event_type"], c["field"], c["comparator"],
                  json.dumps(c["value"]), c.get("value_mode", "absolute"),
                  json.dumps(c.get("scope")), json.dumps(c.get("filter")),
                  int(c.get("is_shared", False))) for c in configs],
            )


# ── Users ──────────────────────────────────────────────────────────────────────

def get_users() -> List[dict]:
    with _db() as con:
        return [_load(r) for r in con.execute("SELECT * FROM users")]


# ── Configs ────────────────────────────────────────────────────────────────────

def get_configs() -> List[dict]:
    with _db() as con:
        return [_load(r) for r in con.execute("SELECT * FROM notification_configs")]


def save_config(config: dict) -> None:
    with _db() as con:
        con.execute(
            "INSERT OR REPLACE INTO notification_configs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (config["id"], config["user_id"],
             json.dumps(config["assigned_to_user_ids"]), config["label"],
             config["event_type"], config["field"], config["comparator"],
             json.dumps(config["value"]), config.get("value_mode", "absolute"),
             json.dumps(config.get("scope")), json.dumps(config.get("filter")),
             int(config.get("is_shared", False))),
        )


def delete_config(config_id: str) -> None:
    with _db() as con:
        con.execute("DELETE FROM notification_configs WHERE id = ?", (config_id,))


# ── Active notifications ────────────────────────────────────────────────────────

def get_notifications(user_id: Optional[str] = None) -> List[dict]:
    with _db() as con:
        if user_id:
            rows = con.execute(
                "SELECT * FROM notifications WHERE user_id = ?", (user_id,)
            )
        else:
            rows = con.execute("SELECT * FROM notifications")
        return [_load(r) for r in rows]


def add_notification(notif: dict) -> None:
    with _db() as con:
        con.execute(
            "INSERT OR REPLACE INTO notifications VALUES (?,?,?,?,?,?,?,?,?,?)",
            (notif["id"], notif["user_id"], notif["config_id"],
             notif["config_label"], notif["triggered_by_event_id"],
             notif["triggered_at"], notif["last_seen_at"], notif["message"],
             int(notif.get("read", False)), int(notif.get("is_shared", False))),
        )


def update_notification_last_seen(notif_id: str, last_seen_at: str) -> None:
    with _db() as con:
        con.execute(
            "UPDATE notifications SET last_seen_at = ? WHERE id = ?",
            (last_seen_at, notif_id),
        )


def mark_notification_read(notif_id: str, user_id: str) -> Optional[dict]:
    with _db() as con:
        con.execute(
            "UPDATE notifications SET read = 1 WHERE id = ? AND user_id = ?",
            (notif_id, user_id),
        )
        row = con.execute(
            "SELECT * FROM notifications WHERE id = ?", (notif_id,)
        ).fetchone()
        return _load(row) if row else None


def resolve_notification(notif: dict) -> None:
    """Move a notification from the active inbox to history."""
    with _db() as con:
        con.execute("DELETE FROM notifications WHERE id = ?", (notif["id"],))
        con.execute(
            "INSERT OR REPLACE INTO notification_history VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (notif["id"], notif["user_id"], notif["config_id"],
             notif["config_label"], notif["triggered_by_event_id"],
             notif["triggered_at"], notif["last_seen_at"], notif["message"],
             int(notif.get("read", False)), int(notif.get("is_shared", False)),
             notif.get("resolved_at"), notif.get("resolved_by_event_id")),
        )


def dismiss_notification(notif_id: str, user_id: str) -> Optional[dict]:
    """User-initiated dismiss: move to history."""
    with _db() as con:
        row = con.execute(
            "SELECT * FROM notifications WHERE id = ? AND user_id = ?",
            (notif_id, user_id),
        ).fetchone()
        if not row:
            return None
        notif = _load(row)
        con.execute("DELETE FROM notifications WHERE id = ?", (notif_id,))
        con.execute(
            "INSERT OR REPLACE INTO notification_history VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (notif["id"], notif["user_id"], notif["config_id"],
             notif["config_label"], notif["triggered_by_event_id"],
             notif["triggered_at"], notif["last_seen_at"], notif["message"],
             int(notif.get("read", False)), int(notif.get("is_shared", False)),
             notif["last_seen_at"], "user_dismissed"),
        )
        return notif


# ── History ────────────────────────────────────────────────────────────────────

def get_history(user_id: Optional[str] = None) -> List[dict]:
    with _db() as con:
        if user_id:
            rows = con.execute(
                "SELECT * FROM notification_history WHERE user_id = ?", (user_id,)
            )
        else:
            rows = con.execute("SELECT * FROM notification_history")
        return [_load(r) for r in rows]


# ── Reset / bulk write ─────────────────────────────────────────────────────────

def reset_notifications() -> None:
    with _db() as con:
        con.execute("DELETE FROM notifications")
        con.execute("DELETE FROM notification_history")


def bulk_write_seek(active: List[dict], history: List[dict]) -> None:
    """Replace all active notifications and history in one transaction (used by seek)."""
    with _db() as con:
        con.execute("DELETE FROM notifications")
        con.execute("DELETE FROM notification_history")
        con.executemany(
            "INSERT INTO notifications VALUES (?,?,?,?,?,?,?,?,?,?)",
            [(n["id"], n["user_id"], n["config_id"],
              n["config_label"], n["triggered_by_event_id"],
              n["triggered_at"], n["last_seen_at"], n["message"],
              int(n.get("read", False)), int(n.get("is_shared", False)))
             for n in active],
        )
        con.executemany(
            "INSERT INTO notification_history VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            [(h["id"], h["user_id"], h["config_id"],
              h["config_label"], h["triggered_by_event_id"],
              h["triggered_at"], h["last_seen_at"], h["message"],
              int(h.get("read", False)), int(h.get("is_shared", False)),
              h.get("resolved_at"), h.get("resolved_by_event_id"))
             for h in history],
        )
