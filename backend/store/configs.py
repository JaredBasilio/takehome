import json
from typing import Dict, List

from .db import _db, _load


def get_configs() -> List[dict]:
    with _db() as con:
        configs = [_load(r) for r in con.execute("SELECT * FROM notification_configs")]
        # Group assignment rows by config_id, preserving the ConfigAssignment shape
        assignment_map: Dict[str, List[dict]] = {}
        for r in con.execute("SELECT config_id, recipient_id FROM config_assignments"):
            assignment_map.setdefault(r["config_id"], []).append(
                {"recipient_id": r["recipient_id"]}
            )
        for c in configs:
            c["assignments"] = assignment_map.get(c["id"], [])
    return configs


def save_config(config: dict) -> None:
    assignments = config.get("assignments", [])
    # Accept either ConfigAssignment dicts or plain strings (rule engine passes dicts)
    recipient_ids = [
        a["recipient_id"] if isinstance(a, dict) else a for a in assignments
    ]
    with _db() as con:
        con.execute(
            "INSERT OR REPLACE INTO notification_configs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (config["id"], config["owner_id"], config["label"],
             config["event_type"], config["field"], config["comparator"],
             json.dumps(config["value"]), config.get("value_mode", "absolute"),
             json.dumps(config.get("scope")), json.dumps(config.get("filter")),
             int(config.get("is_shared", False))),
        )
        con.execute("DELETE FROM config_assignments WHERE config_id = ?", (config["id"],))
        con.executemany(
            "INSERT INTO config_assignments VALUES (?,?)",
            [(config["id"], rid) for rid in recipient_ids],
        )


def delete_config(config_id: str) -> None:
    with _db() as con:
        con.execute("DELETE FROM notification_configs WHERE id = ?", (config_id,))
        con.execute("DELETE FROM config_assignments WHERE config_id = ?", (config_id,))
