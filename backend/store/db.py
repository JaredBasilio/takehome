import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

_DB = Path(__file__).parent.parent / "data" / "app.db"
_DATA = Path(__file__).parent.parent / "data"


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
    for key in ("value", "scope", "filter", "triggering_event_ids"):
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
                role TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS user_queue_memberships (
                user_id TEXT NOT NULL,
                queue_id TEXT NOT NULL,
                PRIMARY KEY (user_id, queue_id)
            );
            CREATE TABLE IF NOT EXISTS notification_configs (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
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
            CREATE TABLE IF NOT EXISTS config_assignments (
                config_id TEXT NOT NULL,
                recipient_id TEXT NOT NULL,
                PRIMARY KEY (config_id, recipient_id)
            );
            CREATE TABLE IF NOT EXISTS notifications (
                id TEXT PRIMARY KEY,
                config_id TEXT NOT NULL,
                config_label TEXT NOT NULL,
                triggering_event_ids TEXT NOT NULL,
                triggered_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                message TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS notification_recipients (
                notification_id TEXT NOT NULL REFERENCES notifications(id),
                recipient_id TEXT NOT NULL,
                is_shared INTEGER NOT NULL DEFAULT 0,
                read INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'active',
                resolved_at TEXT,
                resolved_by_event_id TEXT,
                PRIMARY KEY (notification_id, recipient_id)
            );
            CREATE INDEX IF NOT EXISTS idx_notif_config ON notifications(config_id);
            CREATE INDEX IF NOT EXISTS idx_notif_recip ON notification_recipients(recipient_id, status);
        """)

        if con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            users = json.loads((_DATA / "users.json").read_text())
            con.executemany(
                "INSERT INTO users VALUES (?,?,?)",
                [(u["user_id"], u["name"], u["role"]) for u in users],
            )
            con.executemany(
                "INSERT INTO user_queue_memberships VALUES (?,?)",
                [
                    (u["user_id"], q)
                    for u in users
                    for q in (u.get("manages_queue_ids") or [])
                ],
            )

        if con.execute("SELECT COUNT(*) FROM notification_configs").fetchone()[0] == 0:
            configs = json.loads((_DATA / "notification_configs.json").read_text())
            con.executemany(
                "INSERT INTO notification_configs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                [(c["config_id"], c["user_id"], c["label"],
                  c["event_type"], c["field"], c["comparator"],
                  json.dumps(c["value"]), c.get("value_mode", "absolute"),
                  json.dumps(c.get("scope")), json.dumps(c.get("filter")),
                  int(c.get("is_shared", False))) for c in configs],
            )
            con.executemany(
                "INSERT INTO config_assignments VALUES (?,?)",
                [
                    (c["config_id"], uid)
                    for c in configs
                    for uid in c["assigned_to_recipient_ids"]
                ],
            )
