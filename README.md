# Intraday Notification System

A contact-center notification demo. Agents, team leads, and a head of support define rules that fire alerts when queue or agent events cross a threshold. Press Play, watch notifications appear in real time, switch users, and configure new rules.

## Requirements

- Python 3.9.6 (system path: `/usr/bin/python3`)
- Node.js 18+

## Quick start

```bash
make install   # create Python venv + pip install + npm install
make dev       # starts backend on :8000 and frontend on :5173
```

Open [http://localhost:5173](http://localhost:5173).

## Other commands

```bash
make reset     # delete the SQLite DB (required after any schema change)
```

If port 8000 is already in use: `lsof -ti:8000 | xargs kill -9`

## Running tests

```bash
cd backend && .venv/bin/pytest tests/ -v
```

## Demo walkthrough

1. **Press Play** in the replay bar (top right) and pick a speed.
2. Switch to **Jordan Taylor** (head of support) — watch an SLA at-risk alert fire at 09:25, then a breach at 09:30.
3. Switch to **Sarah Chen** (agent) — an adherence violation fires at 09:36 and auto-resolves at 10:10.
4. Switch to **Priya Patel** (team lead) — open Config Editor, push a shared rule to her agents, then switch to Sarah or Marcus to see it land in their inbox.
5. Click the **History** tab to see resolved notifications with durations.
6. Drag the **timeline scrubber** to seek to any point in the event stream.

## Project layout

```
backend/
  main.py              FastAPI routes + scope validation
  rule_engine.py       Evaluates events against configs; tracks active conditions
  event_processor.py   Async replay loop (slow / normal / fast / instant)
  models/              Pydantic types per domain
  store/               SQLite I/O per domain; db.py holds schema + seeding
  data/
    users.json         Seed users (a_19 Sarah, a_07 Marcus, Priya, Jordan)
    notification_configs.json  Seed rules timed to fire during replay
    events.jsonl       97 real-time events covering ~90 min of a busy morning

frontend/
  src/api.ts           Typed API client
  src/components/      UserSwitcher, NotificationInbox, NotificationHistory,
                       ConfigEditor, ReplayControls, TimelineScrubber
```

See `agent.md` for architecture details and design decisions.
