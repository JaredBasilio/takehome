from typing import Dict, List

from .db import _db, _load


def get_users() -> List[dict]:
    with _db() as con:
        users = [_load(r) for r in con.execute("SELECT * FROM users")]
        # Group membership rows by user_id, preserving the UserQueueMembership shape
        membership_map: Dict[str, List[dict]] = {}
        for r in con.execute("SELECT user_id, queue_id FROM user_queue_memberships"):
            membership_map.setdefault(r["user_id"], []).append(
                {"queue_id": r["queue_id"]}
            )
        for u in users:
            u["queue_memberships"] = membership_map.get(u["id"], [])
    return users
