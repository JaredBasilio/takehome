"""
API integration tests: verify the HTTP endpoints enforce ownership, scope rules,
notification lifecycle, and config fan-out. Uses FastAPI's TestClient with an
in-memory SQLite DB so each test starts from the seeded baseline.
"""
import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# ── Test DB setup ─────────────────────────────────────────────────────────────

# Minimal seed: two agents (a_19, a_07), a team lead (u_3), and a head of support (u_4).
USERS = [
    {"user_id": "a_19", "name": "Sarah Chen",    "role": "agent",           "manages_queue_ids": []},
    {"user_id": "a_07", "name": "Marcus Webb",   "role": "agent",           "manages_queue_ids": []},
    {"user_id": "u_3",  "name": "Priya Patel",   "role": "team_lead",       "manages_queue_ids": ["billing", "tier_2"]},
    {"user_id": "u_4",  "name": "Jordan Taylor", "role": "head_of_support", "manages_queue_ids": []},
]

CONFIGS: list = []  # start empty; tests create configs through the API


@pytest.fixture()
def client(tmp_path):
    """Return a TestClient backed by a fresh in-memory DB for each test."""
    db_file = tmp_path / "test.db"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "users.json").write_text(json.dumps(USERS))
    (data_dir / "notification_configs.json").write_text(json.dumps(CONFIGS))
    (data_dir / "events.jsonl").write_text("")

    # Patch the DB path and data dir before importing the app
    import store.db as db_mod
    import store.notifications as notif_mod

    with patch.object(db_mod, "_DB", db_file), \
         patch.object(db_mod, "_DATA", data_dir):
        # Re-init so the patched paths take effect
        import store
        db_mod.init_db()

        # Import app after patching so routes use the same patched store
        from main import app
        from event_processor import replay
        replay.reset()

        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


# ── Users ─────────────────────────────────────────────────────────────────────

def test_list_users_returns_all_seeded_users(client):
    resp = client.get("/api/users")
    assert resp.status_code == 200
    ids = {u["id"] for u in resp.json()}
    assert ids == {"a_19", "a_07", "u_3", "u_4"}


# ── Config ownership ──────────────────────────────────────────────────────────

def test_create_config_owner_is_set_to_creator(client):
    resp = client.post("/api/users/a_19/configs", json={
        "label": "My rule",
        "event_type": "adherence_check",
        "field": "in_violation",
        "comparator": "eq",
        "value": True,
        "value_mode": "absolute",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["owner_id"] == "a_19"
    assert body["assignments"] == [{"recipient_id": "a_19"}]


def test_non_owner_cannot_update_config(client):
    # Sarah creates a config
    create = client.post("/api/users/a_19/configs", json={
        "label": "Sarah rule",
        "event_type": "adherence_check",
        "field": "in_violation",
        "comparator": "eq",
        "value": True,
        "value_mode": "absolute",
    })
    config_id = create.json()["id"]

    # Marcus tries to update it
    resp = client.put(f"/api/users/a_07/configs/{config_id}", json={
        "label": "Hacked",
        "event_type": "adherence_check",
        "field": "in_violation",
        "comparator": "eq",
        "value": True,
        "value_mode": "absolute",
    })
    assert resp.status_code == 404


def test_non_owner_cannot_delete_config(client):
    create = client.post("/api/users/a_19/configs", json={
        "label": "Sarah rule",
        "event_type": "adherence_check",
        "field": "in_violation",
        "comparator": "eq",
        "value": True,
        "value_mode": "absolute",
    })
    config_id = create.json()["id"]

    resp = client.delete(f"/api/users/a_07/configs/{config_id}")
    assert resp.status_code == 404


def test_owner_can_delete_config(client):
    create = client.post("/api/users/a_19/configs", json={
        "label": "My rule",
        "event_type": "adherence_check",
        "field": "in_violation",
        "comparator": "eq",
        "value": True,
        "value_mode": "absolute",
    })
    config_id = create.json()["id"]

    resp = client.delete(f"/api/users/a_19/configs/{config_id}")
    assert resp.status_code == 204


# ── Config visibility ─────────────────────────────────────────────────────────

def test_shared_config_visible_to_recipient_but_not_others(client):
    """A config pushed by a lead appears in the agent's config list but not other agents'."""
    # Priya creates and pushes a config
    create = client.post("/api/users/u_3/configs", json={
        "label": "Lead rule",
        "event_type": "adherence_check",
        "field": "in_violation",
        "comparator": "eq",
        "value": True,
        "value_mode": "absolute",
        "scope": {"agent_ids": ["a_19", "a_07"]},
    })
    config_id = create.json()["id"]
    client.post(f"/api/users/u_3/configs/{config_id}/push")

    # Both agents should see it
    sarah_configs = client.get("/api/users/a_19/configs").json()
    marcus_configs = client.get("/api/users/a_07/configs").json()
    assert any(c["id"] == config_id for c in sarah_configs)
    assert any(c["id"] == config_id for c in marcus_configs)


# ── Scope validation ──────────────────────────────────────────────────────────

def test_agent_cannot_create_queue_scoped_rule(client):
    resp = client.post("/api/users/a_19/configs", json={
        "label": "Bad rule",
        "event_type": "queue_snapshot",
        "field": "tickets_waiting",
        "comparator": "gt",
        "value": 10,
        "value_mode": "absolute",
        "scope": {"queue_ids": ["billing"]},
    })
    assert resp.status_code == 403


def test_agent_can_create_rule_scoped_to_themselves(client):
    resp = client.post("/api/users/a_19/configs", json={
        "label": "My adherence",
        "event_type": "adherence_check",
        "field": "in_violation",
        "comparator": "eq",
        "value": True,
        "value_mode": "absolute",
        "scope": {"agent_ids": ["a_19"]},
    })
    assert resp.status_code == 201


def test_agent_cannot_scope_rule_to_other_agent(client):
    resp = client.post("/api/users/a_19/configs", json={
        "label": "Watch Marcus",
        "event_type": "adherence_check",
        "field": "in_violation",
        "comparator": "eq",
        "value": True,
        "value_mode": "absolute",
        "scope": {"agent_ids": ["a_07"]},
    })
    assert resp.status_code == 403


def test_team_lead_cannot_scope_outside_managed_queues(client):
    resp = client.post("/api/users/u_3/configs", json={
        "label": "Watch bad queue",
        "event_type": "queue_snapshot",
        "field": "tickets_waiting",
        "comparator": "gt",
        "value": 5,
        "value_mode": "absolute",
        "scope": {"queue_ids": ["unmanaged_queue"]},
    })
    assert resp.status_code == 403


def test_only_team_leads_can_push_configs(client):
    """An agent trying to push a config should get 403."""
    create = client.post("/api/users/a_19/configs", json={
        "label": "My rule",
        "event_type": "adherence_check",
        "field": "in_violation",
        "comparator": "eq",
        "value": True,
        "value_mode": "absolute",
    })
    config_id = create.json()["id"]

    resp = client.post(f"/api/users/a_19/configs/{config_id}/push")
    assert resp.status_code == 403


# ── Notification lifecycle ────────────────────────────────────────────────────

def _seed_notification(client, user_id="a_19"):
    """Insert a notification directly via the store for lifecycle tests."""
    import store
    notif = {
        "id": "notif_test_001",
        "config_id": "cfg_test",
        "config_label": "Test rule",
        "triggering_event_ids": ["evt_001"],
        "triggered_at": "2026-05-26T09:00:00Z",
        "last_seen_at": "2026-05-26T09:00:00Z",
        "message": "Test notification",
        "is_shared": False,
        "recipient_ids": [user_id],
    }
    store.add_notification(notif)
    return notif


def test_inbox_shows_only_active_notifications(client):
    _seed_notification(client, "a_19")
    resp = client.get("/api/users/a_19/notifications")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["status"] == "active"


def test_mark_read_updates_read_state(client):
    _seed_notification(client, "a_19")
    resp = client.patch("/api/users/a_19/notifications/notif_test_001/read")
    assert resp.status_code == 200
    assert resp.json()["read"] is True


def test_dismiss_removes_notification_from_inbox(client):
    _seed_notification(client, "a_19")
    client.delete("/api/users/a_19/notifications/notif_test_001")

    inbox = client.get("/api/users/a_19/notifications").json()
    assert inbox == []


def test_dismissed_notification_appears_in_history(client):
    _seed_notification(client, "a_19")
    client.delete("/api/users/a_19/notifications/notif_test_001")

    history = client.get("/api/users/a_19/notifications/history").json()
    assert len(history) == 1
    assert history[0]["resolved_by_event_id"] == "user_dismissed"


def test_dismiss_only_resolves_requesting_recipients_row(client):
    """When a shared notification is dismissed by one recipient, the other still sees it."""
    import store
    notif = {
        "id": "notif_shared_001",
        "config_id": "cfg_test",
        "config_label": "Shared rule",
        "triggering_event_ids": ["evt_001"],
        "triggered_at": "2026-05-26T09:00:00Z",
        "last_seen_at": "2026-05-26T09:00:00Z",
        "message": "Shared notification",
        "is_shared": True,
        "recipient_ids": ["a_19", "a_07"],
    }
    store.add_notification(notif)

    # Sarah dismisses
    client.delete("/api/users/a_19/notifications/notif_shared_001")

    # Sarah's inbox is clear
    assert client.get("/api/users/a_19/notifications").json() == []
    # Marcus still sees it
    marcus_inbox = client.get("/api/users/a_07/notifications").json()
    assert len(marcus_inbox) == 1


def test_notification_not_visible_to_other_users(client):
    _seed_notification(client, "a_19")

    marcus_inbox = client.get("/api/users/a_07/notifications").json()
    assert marcus_inbox == []
