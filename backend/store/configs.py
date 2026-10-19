import json
from typing import Dict, List

from .db import _db, _load


def get_configs() -> List[dict]:
    with _db() as con:
        configs = [_load(r) for r in con.execute("SELECT * FROM notification_configs")]
        assignments: Dict[str, List[str]] = {}
        for r in con.execute("SELECT config_id, recipient_id FROM config_assignments"):
            assignments.setdefault(r["config_id"], []).append(r["recipient_id"])
        for c in configs:
            c["assigned_to_recipient_ids"] = assignments.get(c["id"], [])
    return configs


def save_config(config: dict) -> None:
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
            [(config["id"], uid) for uid in config.get("assigned_to_recipient_ids", [])],
        )


def delete_config(config_id: str) -> None:
    with _db() as con:
        con.execute("DELETE FROM notification_configs WHERE id = ?", (config_id,))
        con.execute("DELETE FROM config_assignments WHERE config_id = ?", (config_id,))
