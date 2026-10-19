# Intraday Notification System — Agent Overview

A contact-center notification system that lets agents, team leads, and a head of
support define rules that fire alerts when queue or agent events cross a threshold.
The deliverable is a working demo playable in a browser: press Play, watch
notifications appear in each user's inbox in real time, switch users, configure
new rules, and scrub to any point in the event timeline.

---

## What it does

**Users** have one of three roles (agent, team_lead, head_of_support). Role
determines what rules they can write and which queues and agents they can watch.

**Rules** (`notification_configs`) specify:
- which event type to watch (`queue_snapshot`, `agent_state_change`, or `adherence_check`)
- which field to evaluate (`tickets_waiting`, `longest_wait_sec`, `in_violation`, …)
- a comparator and threshold (`gt 10`, `eq true`, `gt 80%` of SLA target)
- an optional scope (which queues or agents) and a filter (exact-match precondition)

**Events** come from `events.jsonl` — 97 events covering ~90 minutes of a busy
morning shift. The backend replays them as a background task at controllable
speeds (slow / normal / fast / instant).

**Notifications** fire when a rule condition is first met. The inbox is a live
view of *currently active* conditions — once the condition clears, the
notification auto-resolves and moves to a History tab with duration tracking. If
several rules match the same event, all of them fire independently.

**Shared configs** let a team lead push a rule to their agents. Each agent gets
their own notification row (independent read state, independent dismiss) even
though the rule body is shared.

---

## Architecture

```
events.jsonl
    │
    ▼
EventProcessor          background task; reads events one at a time at the chosen speed
    │
    ▼
RuleEngine              stateless evaluator + in-memory active-condition tracker
    │
    ├── new_notifs ──▶  store.add_notification()      INSERT into notifications + notification_recipients
    ├── updated    ──▶  store.update_notification_last_seen()
    └── resolved   ──▶  store.resolve_notification()   UPDATE status = 'resolved'
```

### Backend layers

| Layer | File(s) | Responsibility |
|---|---|---|
| Models | `backend/models/` | Pydantic types: `User`, `NotificationConfig`, `ConfigAssignment`, `Notification`, `NotificationRecipient` |
| Store | `backend/store/` | SQLite I/O — one file per domain (`users.py`, `configs.py`, `notifications.py`); `db.py` holds schema + seed loading |
| Rule engine | `backend/rule_engine.py` | Evaluates one event against all configs; maintains `_active` map for stateful events |
| Event processor | `backend/event_processor.py` | Async replay loop; calls `RuleEngine.process_event` and writes results to the store |
| API | `backend/main.py` | FastAPI REST routes; enforces ownership and scope before writing |

### Database (SQLite WAL)

Six tables:

```
users                       id, name, role
user_queue_memberships      user_id, queue_id
notification_configs        id, owner_id, label, event_type, field, comparator, value, …
config_assignments          config_id, recipient_id   ← who receives notifications
notifications               id, config_id, config_label, triggering_event_ids, triggered_at, last_seen_at, message
notification_recipients     notification_id, recipient_id, is_shared, read, status, resolved_at, resolved_by_event_id
```

One `notifications` row is created per rule+entity match. Each recipient gets its
own `notification_recipients` row so read state and dismiss are independent.
`last_seen_at` lives on the shared body (the condition is shared); `read` and
`status` live per recipient.

### Frontend

Vite + React 18 + Mantine v7. Polls `/api/users/{id}/notifications` every 500ms
during replay. Key components:

- **UserSwitcher** — switch the active user; shows unread badge counts
- **NotificationInbox** — live active conditions; mark read, dismiss
- **NotificationHistory** — resolved notifications with duration
- **ConfigEditor** — create/edit/delete/push rules; scope picker constrained by role
- **ReplayControls + TimelineScrubber** — play/pause/speed; seek to any event

---

## Key design decisions

**Inbox = live view only.** A notification visible right now means the problem is
happening right now. Once the condition clears, the notification moves to History
automatically. This avoids alert fatigue from stale entries.

**One notification body, many recipient rows.** A shared config doesn't duplicate
the notification text — it fans out one `notification_recipients` row per
recipient. Future per-recipient attributes (delivery destination, comment, snooze)
belong on `notification_recipients`, not the body.

**Stateful vs discrete events.** Queue snapshots and adherence checks track
state: the same condition staying true across events does not re-fire; it bumps
`last_seen_at` instead. `agent_state_change` is discrete: every match is a fresh
transition and fires a new notification immediately.

**Scope ≠ filter.** `scope` picks which entities (queues, agents) a rule watches.
`filter` is an exact-match precondition on other event fields (e.g. only fire
when `previous_state = "on_call"`). The split can be confusing and merging them
is open.

**Config assignments are a join table.** `config_assignments(config_id, recipient_id)`
is modeled as `List[ConfigAssignment]` on `NotificationConfig` so future
per-assignment attributes (is_enabled, delivery interfaces, priority) can be
added without changing the config shape.

**`config_label` is denormalized.** The rule engine copies the config's label
into `notifications.config_label` at fire time. Renaming or deleting a rule after
the fact doesn't corrupt existing notification records.

**`owner_id` ≠ recipient.** `notification_configs.owner_id` is who created the
rule and can edit or delete it. Priya can own a rule whose `assignments` list is
`[a_19, a_07]` — she creates no notifications for herself.

---

## Running locally

```bash
# Backend (Python 3.9.6 venv)
cd backend
/usr/bin/python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn main:app --port 8000

# Frontend
cd frontend
npm install
npm run dev        # http://localhost:5173
```

If port 8000 is already in use: `lsof -ti:8000 | xargs kill -9`

After any DB schema change: `rm backend/data/app.db` and restart the backend.

## Running tests

```bash
cd backend
.venv/bin/pytest tests/ -v
```

Tests in `tests/test_rule_engine.py` test the rule engine directly with plain
dicts — no DB needed. Tests in `tests/test_api.py` use FastAPI's `TestClient`
with a temporary SQLite DB seeded per test.

---

## Demo personas

| Persona | What to show |
|---|---|
| **Jordan Taylor** (head of support) | SLA at-risk notification at 09:25, breach at 09:30 |
| **Sarah Chen** (agent a_19) | Adherence violation fires at 09:36, auto-resolves at 10:10 |
| **Priya Patel** (team lead) | Push a shared config; switch to Sarah/Marcus to see it appear |
