from typing import List, Optional

from .db import _db, _load


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


def get_history(user_id: Optional[str] = None) -> List[dict]:
    with _db() as con:
        if user_id:
            rows = con.execute(
                "SELECT * FROM notification_history WHERE user_id = ?", (user_id,)
            )
        else:
            rows = con.execute("SELECT * FROM notification_history")
        return [_load(r) for r in rows]


def reset_notifications() -> None:
    with _db() as con:
        con.execute("DELETE FROM notifications")
        con.execute("DELETE FROM notification_history")


def bulk_write_seek(active: List[dict], history: List[dict]) -> None:
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
