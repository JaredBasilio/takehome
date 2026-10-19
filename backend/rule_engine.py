import uuid
from typing import Any, Dict, List, Optional, Tuple

# These event types represent ongoing conditions. The same condition staying
# true across multiple events should not re-fire — we track it as "active"
# and only create one notification until the condition clears.
# agent_state_change events are discrete (each one is a unique transition)
# so they don't participate in the active-conditions map.
STATEFUL_EVENT_TYPES = {"queue_snapshot", "adherence_check"}


def _get_entity_key(event: dict, config: dict) -> Optional[str]:
    """Return the entity key for active-condition tracking, or None if out of scope."""
    scope = config.get("scope") or {}
    event_type = event["type"]

    if event_type == "queue_snapshot":
        queue_id = event["queue_id"]
        allowed_queues = scope.get("queue_ids")
        if allowed_queues and queue_id not in allowed_queues:
            return None
        return queue_id

    elif event_type in ("adherence_check", "agent_state_change"):
        agent_id = event.get("agent_id")
        event_queue_ids = event.get("queue_ids") or []

        allowed_agents = scope.get("agent_ids")
        if allowed_agents and agent_id not in allowed_agents:
            return None

        allowed_queues = scope.get("queue_ids")
        if allowed_queues:
            if not any(q in allowed_queues for q in event_queue_ids):
                return None

        return agent_id

    return None


def _check_filter(event: dict, config: dict) -> bool:
    """All filter keys must exactly match the event's fields."""
    filters = config.get("filter") or {}
    return all(event.get(k) == v for k, v in filters.items())


def _evaluate_condition(event: dict, config: dict) -> bool:
    field = config["field"]
    comparator = config["comparator"]
    raw_value = config["value"]
    value_mode = config.get("value_mode", "absolute")

    event_val = event.get(field)
    if event_val is None:
        return False

    if value_mode == "pct_of_sla":
        sla_target = event.get("sla_target_sec") or 1
        threshold = (raw_value / 100.0) * sla_target
    else:
        threshold = raw_value

    ops = {
        "gt": lambda a, b: a > b,
        "lt": lambda a, b: a < b,
        "gte": lambda a, b: a >= b,
        "lte": lambda a, b: a <= b,
        "eq": lambda a, b: a == b,
        "neq": lambda a, b: a != b,
    }
    op = ops.get(comparator)
    return op(event_val, threshold) if op else False


def _generate_message(event: dict, config: dict) -> str:
    event_type = event["type"]
    field = config["field"]
    value_mode = config.get("value_mode", "absolute")

    if event_type == "adherence_check":
        agent_id = event["agent_id"]
        scheduled = event.get("scheduled_state", "?")
        actual = event.get("actual_state", "?")
        return (
            f"Agent {agent_id} is out of adherence — "
            f"scheduled: {scheduled}, actual: {actual}"
        )

    elif event_type == "queue_snapshot":
        queue_id = event["queue_id"]
        sla_target = event.get("sla_target_sec", 1)
        longest_wait = event.get("longest_wait_sec", 0)
        tickets = event.get("tickets_waiting", 0)

        if field == "tickets_waiting":
            return f"{queue_id} queue: {tickets} tickets waiting"
        elif field == "longest_wait_sec":
            pct = round(longest_wait / sla_target * 100) if sla_target else 0
            if value_mode == "pct_of_sla" and config["value"] >= 100:
                return (
                    f"SLA breached in {queue_id}: {longest_wait}s wait "
                    f"({pct}% of {sla_target}s target)"
                )
            elif value_mode == "pct_of_sla":
                return (
                    f"SLA at risk in {queue_id}: {longest_wait}s wait "
                    f"({pct}% of {sla_target}s target)"
                )
            else:
                return f"{queue_id}: longest wait {longest_wait}s exceeds {config['value']}s"
        else:
            return f"{queue_id}: {field} = {event.get(field)}"

    elif event_type == "agent_state_change":
        agent_id = event["agent_id"]
        prev_state = event.get("previous_state", "?")
        duration_sec = event.get("previous_state_duration_sec") or 0
        duration_min = round(duration_sec / 60, 1)
        new_state = event.get("new_state", "?")

        if field == "previous_state_duration_sec":
            return (
                f"Agent {agent_id} was {prev_state} for {duration_min} min "
                f"(now {new_state})"
            )
        elif field == "new_state":
            return f"Agent {agent_id} transitioned to {new_state}"
        else:
            return f"Agent {agent_id}: {field} = {event.get(field)}"

    return config["label"]


class RuleEngine:
    def __init__(self):
        # Maps (config_id, entity_key, user_id) -> active notification dict
        # Only used for STATEFUL_EVENT_TYPES
        self._active: Dict[Tuple[str, str, str], dict] = {}

    def reset(self) -> None:
        self._active = {}

    def process_event(
        self,
        event: dict,
        configs: List[dict],
    ) -> Tuple[List[dict], List[dict], List[dict]]:
        """
        Evaluate one event against all configs.

        Returns:
            new_notifs: notifications to add to the active inbox
            updated_notifs: existing notifications whose last_seen_at changed
            resolved: notifications to move from inbox to history
        """
        new_notifs: List[dict] = []
        updated_notifs: List[dict] = []
        resolved: List[dict] = []

        is_stateful = event["type"] in STATEFUL_EVENT_TYPES

        for config in configs:
            if config["event_type"] != event["type"]:
                continue

            entity_key = _get_entity_key(event, config)
            if entity_key is None:
                continue

            # Filter must pass before we evaluate the condition
            filter_passes = _check_filter(event, config)

            if is_stateful:
                # For stateful events, a filter failure means we skip (don't resolve)
                if not filter_passes:
                    continue
                condition_met = _evaluate_condition(event, config)
            else:
                # For discrete events (agent_state_change), filter failure = not met
                condition_met = filter_passes and _evaluate_condition(event, config)

            for user_id in config["assigned_to_user_ids"]:
                active_key = (config["config_id"], entity_key, user_id)

                if is_stateful:
                    if condition_met:
                        if active_key not in self._active:
                            notif = self._make_notification(event, config, user_id)
                            self._active[active_key] = notif
                            new_notifs.append(notif)
                        else:
                            self._active[active_key]["last_seen_at"] = event["ts"]
                            updated_notifs.append(self._active[active_key])
                    else:
                        if active_key in self._active:
                            notif = self._active.pop(active_key)
                            resolved.append({
                                **notif,
                                "resolved_at": event["ts"],
                                "resolved_by_event_id": event["event_id"],
                            })
                else:
                    # Discrete event: each match is a fresh notification
                    if condition_met:
                        notif = self._make_notification(event, config, user_id)
                        new_notifs.append(notif)

        return new_notifs, updated_notifs, resolved

    def _make_notification(self, event: dict, config: dict, user_id: str) -> dict:
        return {
            "notification_id": f"notif_{uuid.uuid4().hex[:8]}",
            "user_id": user_id,
            "config_id": config["config_id"],
            "config_label": config["label"],
            "triggered_by_event_id": event["event_id"],
            "triggered_at": event["ts"],
            "last_seen_at": event["ts"],
            "message": _generate_message(event, config),
            "read": False,
            "is_shared": config.get("is_shared", False),
        }
