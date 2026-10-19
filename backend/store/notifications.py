import json
from typing import List, Optional

from .db import _db, _load

# Joins notifications (body) with notification_recipients (per-person state).
# n.id is aliased to notification_id so the flat dict matches the NotificationRecipient
# shape — callers use notification_id for API calls (markRead, dismiss) and never
# need to know the underlying join.
_SELECT = """
    SELECT n.id AS notification_id, n.config_id, n.config_label, n.triggering_event_ids,
           n.triggered_at, n.last_seen_at, n.message,
           nr.recipient_id, nr.is_shared, nr.read,
           nr.status, nr.resolved_at, nr.resolved_by_event_id
    FROM notifications n
    JOIN notification_recipients nr ON n.id = nr.notification_id
"""


def _to_recipient(d: dict) -> dict:
    """Convert a flat JOIN row into a NotificationRecipient-shaped dict with nested body."""
    return {
        "notification_id": d["notification_id"],
        "recipient_id": d["recipient_id"],
        "is_shared": d["is_shared"],
        "read": d["read"],
        "status": d["status"],
        "resolved_at": d.get("resolved_at"),
        "resolved_by_event_id": d.get("resolved_by_event_id"),
        "notification": {
            "id": d["notification_id"],
            "config_id": d["config_id"],
            "config_label": d["config_label"],
            "triggering_event_ids": d["triggering_event_ids"],
            "triggered_at": d["triggered_at"],
            "last_seen_at": d["last_seen_at"],
            "message": d["message"],
        },
    }


def get_notifications(user_id: Optional[str] = None) -> List[dict]:
    with _db() as con:
        if user_id:
            rows = con.execute(
                _SELECT + "WHERE nr.recipient_id = ? AND nr.status = 'active'",
                (user_id,),
            )
        else:
            rows = con.execute(_SELECT + "WHERE nr.status = 'active'")
        return [_to_recipient(_load(r)) for r in rows]


def add_notification(notif: dict) -> None:
    """Insert the notification body once, then fan out to each recipient."""
    with _db() as con:
        con.execute(
            "INSERT OR IGNORE INTO notifications VALUES (?,?,?,?,?,?,?)",
            (notif["id"], notif["config_id"], notif["config_label"],
             json.dumps(notif["triggering_event_ids"]),
             notif["triggered_at"], notif["last_seen_at"], notif["message"]),
        )
        con.executemany(
            "INSERT OR IGNORE INTO notification_recipients VALUES (?,?,?,?,?,?,?)",
            [(notif["id"], rid, int(notif.get("is_shared", False)), 0, "active", None, None)
             for rid in notif["recipient_ids"]],
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
            "UPDATE notification_recipients SET read = 1 WHERE notification_id = ? AND recipient_id = ?",
            (notif_id, user_id),
        )
        row = con.execute(
            _SELECT + "WHERE nr.notification_id = ? AND nr.recipient_id = ?",
            (notif_id, user_id),
        ).fetchone()
        return _to_recipient(_load(row)) if row else None


def resolve_notification(notif: dict) -> None:
    """Resolve all still-active recipients when the condition clears."""
    with _db() as con:
        con.execute(
            """UPDATE notification_recipients
               SET status = 'resolved', resolved_at = ?, resolved_by_event_id = ?
               WHERE notification_id = ? AND status = 'active'""",
            (notif.get("resolved_at"), notif.get("resolved_by_event_id"), notif["id"]),
        )


def dismiss_notification(notif_id: str, user_id: str) -> Optional[dict]:
    """Resolve only this recipient's row; others continue to see the notification."""
    with _db() as con:
        row = con.execute(
            _SELECT + "WHERE nr.notification_id = ? AND nr.recipient_id = ? AND nr.status = 'active'",
            (notif_id, user_id),
        ).fetchone()
        if not row:
            return None
        recipient = _to_recipient(_load(row))
        con.execute(
            """UPDATE notification_recipients
               SET status = 'resolved', resolved_at = ?, resolved_by_event_id = 'user_dismissed'
               WHERE notification_id = ? AND recipient_id = ?""",
            (recipient["notification"]["last_seen_at"], notif_id, user_id),
        )
        return recipient


def get_history(user_id: Optional[str] = None) -> List[dict]:
    with _db() as con:
        if user_id:
            rows = con.execute(
                _SELECT + "WHERE nr.recipient_id = ? AND nr.status = 'resolved'",
                (user_id,),
            )
        else:
            rows = con.execute(_SELECT + "WHERE nr.status = 'resolved'")
        return [_to_recipient(_load(r)) for r in rows]


def reset_notifications() -> None:
    with _db() as con:
        con.execute("DELETE FROM notification_recipients")
        con.execute("DELETE FROM notifications")


def bulk_write_seek(active: List[dict], history: List[dict]) -> None:
    """Restore a point-in-time snapshot. active and history items have recipient_ids lists."""
    with _db() as con:
        con.execute("DELETE FROM notification_recipients")
        con.execute("DELETE FROM notifications")

        # Deduplicate notification bodies (multiple recipients share one row)
        seen: dict = {}
        for n in active + history:
            if n["id"] not in seen:
                seen[n["id"]] = n
        con.executemany(
            "INSERT INTO notifications VALUES (?,?,?,?,?,?,?)",
            [(n["id"], n["config_id"], n["config_label"],
              json.dumps(n["triggering_event_ids"]),
              n["triggered_at"], n["last_seen_at"], n["message"])
             for n in seen.values()],
        )

        # Fan out recipient rows
        active_rows = [
            (n["id"], rid, int(n.get("is_shared", False)), int(n.get("read", False)),
             "active", None, None)
            for n in active
            for rid in n["recipient_ids"]
        ]
        history_rows = [
            (h["id"], rid, int(h.get("is_shared", False)), int(h.get("read", False)),
             "resolved", h.get("resolved_at"), h.get("resolved_by_event_id"))
            for h in history
            for rid in h["recipient_ids"]
        ]
        con.executemany(
            "INSERT INTO notification_recipients VALUES (?,?,?,?,?,?,?)",
            active_rows + history_rows,
        )
