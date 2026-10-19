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
    replay.load_events()


# ── Users ─────────────────────────────────────────────────────────────────────

@app.get("/api/users")
def list_users():
    return store.get_users()


# ── Notifications ──────────────────────────────────────────────────────────────

@app.get("/api/users/{user_id}/notifications")
def get_notifications(user_id: str):
    return [n for n in store.get_notifications() if n["user_id"] == user_id]


@app.get("/api/users/{user_id}/notifications/history")
def get_notification_history(user_id: str):
    return [n for n in store.get_history() if n["user_id"] == user_id]


@app.patch("/api/users/{user_id}/notifications/{notif_id}/read")
def mark_read(user_id: str, notif_id: str):
    notifications = store.get_notifications()
    for n in notifications:
        if n["notification_id"] == notif_id and n["user_id"] == user_id:
            n["read"] = True
            store.save_notifications(notifications)
            return n
    raise HTTPException(404, "Notification not found")


@app.delete("/api/users/{user_id}/notifications/{notif_id}")
def dismiss_notification(user_id: str, notif_id: str):
    """Move a notification to history (user-initiated dismiss)."""
    notifications = store.get_notifications()
    target = next(
        (n for n in notifications if n["notification_id"] == notif_id and n["user_id"] == user_id),
        None,
    )
    if not target:
        raise HTTPException(404, "Notification not found")

    remaining = [n for n in notifications if n["notification_id"] != notif_id]
    store.save_notifications(remaining)

    history = store.get_history()
    history.append({
        **target,
        "resolved_at": target["last_seen_at"],
        "resolved_by_event_id": "user_dismissed",
    })
    store.save_history(history)
    return {"status": "dismissed"}


# ── Notification Configs ───────────────────────────────────────────────────────

@app.get("/api/users/{user_id}/configs")
def get_configs(user_id: str):
    configs = store.get_configs()
    # Return configs owned by or assigned to this user
    return [
        c for c in configs
        if c["user_id"] == user_id or user_id in c.get("assigned_to_user_ids", [])
    ]


@app.post("/api/users/{user_id}/configs", status_code=201)
def create_config(user_id: str, req: CreateConfigRequest):
    users = store.get_users()
    user = next((u for u in users if u["user_id"] == user_id), None)
    if not user:
        raise HTTPException(404, "User not found")

    # Enforce role-based scope constraints
    _validate_scope(user, req.scope)

    config = {
        "config_id": f"cfg_{uuid.uuid4().hex[:6]}",
        "user_id": user_id,
        "assigned_to_user_ids": [user_id],
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

    configs = store.get_configs()
    configs.append(config)
    store.save_configs(configs)
    return config


@app.put("/api/users/{user_id}/configs/{config_id}")
def update_config(user_id: str, config_id: str, req: CreateConfigRequest):
    configs = store.get_configs()
    target = next(
        (c for c in configs if c["config_id"] == config_id and c["user_id"] == user_id),
        None,
    )
    if not target:
        raise HTTPException(404, "Config not found")

    users = store.get_users()
    user = next((u for u in users if u["user_id"] == user_id), None)
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
    store.save_configs(configs)
    return target


@app.delete("/api/users/{user_id}/configs/{config_id}", status_code=204)
def delete_config(user_id: str, config_id: str):
    configs = store.get_configs()
    remaining = [
        c for c in configs
        if not (c["config_id"] == config_id and c["user_id"] == user_id)
    ]
    if len(remaining) == len(configs):
        raise HTTPException(404, "Config not found")
    store.save_configs(remaining)


@app.post("/api/users/{user_id}/configs/{config_id}/push")
def push_config_to_agents(user_id: str, config_id: str):
    """Push a team-lead config to all agent users."""
    users = store.get_users()
    owner = next((u for u in users if u["user_id"] == user_id), None)
    if not owner or owner["role"] not in ("team_lead", "head_of_support"):
        raise HTTPException(403, "Only team leads and heads of support can push configs")

    configs = store.get_configs()
    target = next(
        (c for c in configs if c["config_id"] == config_id and c["user_id"] == user_id),
        None,
    )
    if not target:
        raise HTTPException(404, "Config not found")

    agent_user_ids = [u["user_id"] for u in users if u["role"] == "agent"]
    target["assigned_to_user_ids"] = list(
        set(target["assigned_to_user_ids"]) | set(agent_user_ids)
    )
    target["is_shared"] = True
    store.save_configs(configs)
    return target


# ── Replay ─────────────────────────────────────────────────────────────────────

class StartReplayRequest(BaseModel):
    speed: str = "normal"  # "slow" | "normal" | "fast" | "instant"


class SeekRequest(BaseModel):
    index: int


@app.get("/api/replay/events")
def get_replay_events():
    """Return index + timestamp for every event, used to label the timeline scrubber."""
    return [{"index": i, "ts": e["ts"]} for i, e in enumerate(replay.events)]


@app.post("/api/replay/seek")
def seek_replay(req: SeekRequest):
    """Jump to a specific event index, rebuilding notification state instantly."""
    idx = max(0, min(req.index, len(replay.events)))
    replay.reset()

    configs = store.get_configs()
    active: dict = {}
    history: list = []

    for i in range(idx):
        event = replay.events[i]
        new_notifs, updated, resolved = replay._engine.process_event(event, configs)
        for n in new_notifs:
            active[n["notification_id"]] = n
        for n in updated:
            if n["notification_id"] in active:
                active[n["notification_id"]]["last_seen_at"] = n["last_seen_at"]
        for r in resolved:
            history.append(r)
            active.pop(r["notification_id"], None)

    store.save_notifications(list(active.values()))
    store.save_history(history)
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
        agent_id = user.get("agent_id")
        # Agents can only scope to themselves
        if scope.queue_ids:
            raise HTTPException(403, "Agents cannot create queue-scoped rules")
        if scope.agent_ids and scope.agent_ids != [agent_id]:
            raise HTTPException(403, "Agents can only create rules scoped to themselves")
    elif role == "team_lead":
        managed = set(user.get("manages_queue_ids") or [])
        if scope.queue_ids and not set(scope.queue_ids).issubset(managed):
            raise HTTPException(403, "Scope exceeds managed queues")
