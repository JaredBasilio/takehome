# Intraday Notification System (Assembled take-home)

Contact-center notification system: agents, team leads, and a head of support set up rules that fire notifications from queue and agent events. The deliverable is a working demo that you present in an interview. Interviewers will look at product thinking, tradeoffs, ease of use, system design, code quality, and where AI was or wasn't used.

## Source material (gitignored, in `.context/`)
- `.context/attachments/*/Take-Home Assignment.pdf`: the assignment brief
- `.context/attachments/*/events.jsonl`: the event stream (`queue_snapshot`, `agent_state_change`, `adherence_check`)
- `.context/attachments/*/pasted_text_*.txt`: the author's design notes. **This is the source of truth for product and data-model decisions.**
- `.context/plans/intraday-notification-system-implementation-plan.md`: the original draft plan. The code under `backend/` and `frontend/` has since been built and is now the reference.

## Decisions
- Stack: Python backend (FastAPI) and a React + TypeScript + Mantine frontend.
- Storage: JSON files only. No DB and no Docker, because the time budget is 2 days.
- Out of scope: real delivery (Slack, email, etc.), CI/CD, and auth.
- Roles are nested: head of support ⊇ team lead ⊇ agent. A rule is `event + comparator + value`.
- Everyone is a `User` with a role, and the role can change. A `user_notifications` join table links users to configs so configs can be shared later.
- Notification `metadata` stays a free-form dict. Don't turn it into typed columns.
- If several rules match, **fire all of them**. Don't dedupe across rules, but make each notification's source clear.
- **Within a single rule, a condition that stays active does not re-fire.** This is a business decision. The user went back and forth (fire once → re-notify on a cadence → fire once), and the final answer is: the original notification stays in the user's inbox, so a repeat isn't needed. Track active conditions per `(config_id, entity)`, where the entity is `queue_id` for queue snapshots and `agent_id` for agent and adherence events. The first match creates one notification with status `active`. While the condition still holds, don't create new notifications. You can update a `last_seen_at` on the existing one to show it's still live. When the condition clears, the tracker resets.
- **The inbox is a live view of active conditions only.** A later event for the same entity that no longer matches the rule resolves the notification and removes it from the inbox. For example, `adherence_check` with `in_violation=false`, or a `queue_snapshot` back under the threshold. If a user sees a notification, the problem is happening right now. Mark it `resolved` with a `resolved_at` instead of deleting it.
- Formerly open questions, now settled by the implementation (change them only if the user asks): (a) resolved notifications move to a separate history log (`notification_history.json`, shown in a History tab with durations); (b) a re-trigger after the condition clears creates a **new** notification and does not reopen the old one.
- Stateful vs. discrete events: `queue_snapshot` and `adherence_check` are stateful (tracked and auto-resolved). `agent_state_change` is discrete: every match creates a fresh notification and nothing auto-resolves it. For stateful events, a failed rule *filter* (e.g. a different queue) skips the event instead of resolving the notification.
- The active-condition tracker key is `(config_id, entity, user_id)`, so a shared config tracks state separately for each recipient. The tracker lives in memory in `RuleEngine` and is cleared on replay reset.
- Demo playback is implemented as an async background task with speeds `slow` / `normal` / `fast` / `instant` (`SPEED_DELAYS` in `event_processor.py`).
- The SLA threshold is configurable. A rule value can be absolute (e.g. `longest_wait_sec > 150`) or a percentage of SLA (e.g. 80% of the snapshot's own `sla_target_sec`).
- Shared configs are in scope: a team lead can push a config to their agents. Notifications from a shared config land in **each agent's own feed**. Agents **cannot opt out** and **cannot edit** a shared config. It is read-only for them and labeled as coming from their lead.
- The UI must let you switch between users to see each user's feed.

## Layout & running
- `backend/` (FastAPI, **Python 3.9**, so use `typing.List`/`Optional` and not `list[...]` or `X | None`): `main.py` has the REST endpoints, `rule_engine.py` handles evaluation and the active-condition tracker, `event_processor.py` handles replay, `store.py` handles JSON I/O, `models.py` holds the Pydantic models. All data, including the copied `events.jsonl`, lives in `backend/data/`. These files are tracked in git, and running replay rewrites `notifications.json` and `notification_history.json`. Check `git status` before committing so demo-run state doesn't land in a PR by accident.
- `frontend/` (Vite + React 18 + Mantine v7): `src/api.ts` is the API client, and `src/components/` holds UserSwitcher, NotificationInbox, NotificationHistory, ConfigEditor, and ReplayControls. Vite proxies `/api` → `localhost:8000`. The inbox polls every 500ms during replay.
- Run: `cd backend && .venv/bin/uvicorn main:app --port 8000` and `cd frontend && npm run dev` (port 5173).
- Venv setup: build it with `/usr/bin/python3 -m venv .venv` (system 3.9.6). The `python3` on PATH fails to build the pinned `pydantic-core` wheel. 3.11–3.13 aren't installed.
- "Address already in use" on 8000 usually means a backend from an earlier session is still running. Reuse it, or run `lsof -ti:8000 | xargs kill -9` before restarting.
- Demo personas: Jordan Taylor (SLA at-risk → breach), Sarah Chen (adherence violation that auto-resolves), Priya Patel (lead pushing a shared config to agents).

## Git / PRs
- The work is a Graphite stack on `JaredBasilio/takehome`, in this order (branches prefixed `JaredBasilio/`): `main` → `intra-notification-take-home` (CLAUDE.md, .gitignore, requirements, seed data + events) → `backend-models` (`models.py`) → `backend-store` (`store.py`) → `backend-rule-engine` (`rule_engine.py`) → `backend-event-processor` (`event_processor.py`) → `backend-api` (`main.py`) → `frontend`. One backend module per branch/PR, so each PR stays small enough to review on its own.
- To change a layer, check out its branch, stage specific files (not `-a`), run `gt modify`, then `gt submit --stack`. That restacks the branches above it.

## Working style
- Discuss the product (personas, rule model, noise/dedup, severity) before writing or finalizing implementation plans. Don't jump straight to a plan.
- Keep the scope demo-sized. The goal is "enough that the picture is clear," not production completeness.
