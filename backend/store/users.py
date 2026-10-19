from typing import Dict, List

from .db import _db, _load


def get_users() -> List[dict]:
    with _db() as con:
        users = [_load(r) for r in con.execute("SELECT * FROM users")]
        memberships: Dict[str, List[str]] = {}
        for r in con.execute("SELECT user_id, queue_id FROM user_queue_memberships"):
            memberships.setdefault(r["user_id"], []).append(r["queue_id"])
        for u in users:
            u["manages_queue_ids"] = memberships.get(u["id"]) or None
    return users
