import uuid
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import store
from event_processor import replay
from models import CreateConfigRequest, NotificationScope

app = FastAPI(title="Intraday Notification System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    store.init_db()
    replay.load_events()


# ── Users ─────────────────────────────────────────────────────────────────────

@app.get("/api/users")
def list_users():
    return store.get_users()


# ── Notifications ──────────────────────────────────────────────────────────────

@app.get("/api/users/{user_id}/notifications")
def get_notifications(user_id: str):
    return store.get_notifications(user_id)


@app.get("/api/users/{user_id}/notifications/history")
def get_notification_history(user_id: str):
    return store.get_history(user_id)


@app.patch("/api/users/{user_id}/notifications/{notif_id}/read")
def mark_read(user_id: str, notif_id: str):
    notif = store.mark_notification_read(notif_id, user_id)
    if not notif:
        raise HTTPException(404, "Notification not found")
    return notif


@app.delete("/api/users/{user_id}/notifications/{notif_id}")
def dismiss_notification(user_id: str, notif_id: str):
    notif = store.dismiss_notification(notif_id, user_id)
    if not notif:
        raise HTTPException(404, "Notification not found")
    return {"status": "dismissed"}


# ── Notification Configs ───────────────────────────────────────────────────────

@app.get("/api/users/{user_id}/configs")
def get_configs(user_id: str):
    return [
        c for c in store.get_configs()
        if c["user_id"] == user_id or user_id in c.get("assigned_to_recipient_ids", [])
    ]


@app.post("/api/users/{user_id}/configs", status_code=201)
def create_config(user_id: str, req: CreateConfigRequest):
    users = store.get_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        raise HTTPException(404, "User not found")
    _validate_scope(user, req.scope)

    config = {
        "id": f"cfg_{uuid.uuid4().hex[:6]}",
        "user_id": user_id,
        "assigned_to_recipient_ids": [user_id],
        "label": req.label,
        "event_type": req.event_type,
        "field": req.field,
        "comparator": req.comparator,
        "value": req.value,
        "value_mode": req.value_mode,
        "scope": req.scope.model_dump() if req.scope else None,
        "filter": req.filter,
        "is_shared": False,
    }
    store.save_config(config)
    return config


@app.put("/api/users/{user_id}/configs/{config_id}")
def update_config(user_id: str, config_id: str, req: CreateConfigRequest):
    configs = store.get_configs()
    target = next(
        (c for c in configs if c["id"] == config_id and c["user_id"] == user_id),
        None,
    )
    if not target:
        raise HTTPException(404, "Config not found")

    users = store.get_users()
    user = next((u for u in users if u["id"] == user_id), None)
    _validate_scope(user, req.scope)

    target.update({
        "label": req.label,
        "event_type": req.event_type,
        "field": req.field,
        "comparator": req.comparator,
        "value": req.value,
        "value_mode": req.value_mode,
        "scope": req.scope.model_dump() if req.scope else None,
        "filter": req.filter,
    })
    store.save_config(target)
    return target


@app.delete("/api/users/{user_id}/configs/{config_id}", status_code=204)
def delete_config(user_id: str, config_id: str):
    configs = store.get_configs()
    if not any(c["id"] == config_id and c["user_id"] == user_id for c in configs):
        raise HTTPException(404, "Config not found")
    store.delete_config(config_id)


@app.post("/api/users/{user_id}/configs/{config_id}/push")
def push_config_to_agents(user_id: str, config_id: str):
    users = store.get_users()
    owner = next((u for u in users if u["id"] == user_id), None)
    if not owner or owner["role"] not in ("team_lead", "head_of_support"):
        raise HTTPException(403, "Only team leads and heads of support can push configs")

    configs = store.get_configs()
    target = next(
        (c for c in configs if c["id"] == config_id and c["user_id"] == user_id),
        None,
    )
    if not target:
        raise HTTPException(404, "Config not found")

    agent_ids = [u["id"] for u in users if u["role"] == "agent"]
    target["assigned_to_recipient_ids"] = list(
        set(target["assigned_to_recipient_ids"]) | set(agent_ids)
    )
    target["is_shared"] = True
    store.save_config(target)
    return target


# ── Replay ─────────────────────────────────────────────────────────────────────

class StartReplayRequest(BaseModel):
    speed: str = "normal"


class SeekRequest(BaseModel):
    index: int


@app.get("/api/replay/events")
def get_replay_events():
    return [{"index": i, "ts": e["ts"]} for i, e in enumerate(replay.events)]


@app.post("/api/replay/seek")
def seek_replay(req: SeekRequest):
    idx = max(0, min(req.index, len(replay.events)))
    replay.reset()

    configs = store.get_configs()
    active: dict = {}
    history: list = []

    for i in range(idx):
        event = replay.events[i]
        new_notifs, updated, resolved = replay._engine.process_event(event, configs)
        for n in new_notifs:
            active[n["id"]] = n
        for n in updated:
            if n["id"] in active:
                active[n["id"]]["last_seen_at"] = n["last_seen_at"]
        for r in resolved:
            history.append(r)
            active.pop(r["id"], None)

    store.bulk_write_seek(list(active.values()), history)
    replay.current_index = idx
    return replay.to_dict()


@app.post("/api/replay/start")
async def start_replay(req: StartReplayRequest):
    if replay.is_running:
        return replay.to_dict()
    await replay.start(req.speed)
    return replay.to_dict()


@app.post("/api/replay/reset")
def reset_replay():
    replay.reset()
    return replay.to_dict()


@app.get("/api/replay/status")
def replay_status():
    return replay.to_dict()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _validate_scope(user: dict, scope: Optional[NotificationScope]) -> None:
    if not scope or not user:
        return
    role = user.get("role")
    if role == "agent":
        if scope.queue_ids:
            raise HTTPException(403, "Agents cannot create queue-scoped rules")
        if scope.agent_ids and scope.agent_ids != [user["id"]]:
            raise HTTPException(403, "Agents can only create rules scoped to themselves")
    elif role == "team_lead":
        managed = set(user.get("manages_queue_ids") or [])
        if scope.queue_ids and not set(scope.queue_ids).issubset(managed):
            raise HTTPException(403, "Scope exceeds managed queues")
