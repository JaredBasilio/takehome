"""
Rule engine tests: verify the conditions under which notifications are created,
updated, resolved, and suppressed. Tests work with plain dicts — no DB required.
"""
import pytest
from rule_engine import RuleEngine


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_config(
    id="cfg_1",
    event_type="queue_snapshot",
    field="tickets_waiting",
    comparator="gt",
    value=10,
    value_mode="absolute",
    scope=None,
    filter=None,
    assignments=None,
    is_shared=False,
    label="Test rule",
):
    return {
        "id": id,
        "owner_id": "u_1",
        "label": label,
        "event_type": event_type,
        "field": field,
        "comparator": comparator,
        "value": value,
        "value_mode": value_mode,
        "scope": scope,
        "filter": filter or {},
        "assignments": assignments or [{"recipient_id": "u_1"}],
        "is_shared": is_shared,
    }


def queue_event(
    queue_id="billing",
    tickets_waiting=20,
    longest_wait_sec=60,
    sla_target_sec=120,
    event_id="evt_001",
    ts="2026-05-26T09:00:00Z",
):
    return {
        "type": "queue_snapshot",
        "event_id": event_id,
        "ts": ts,
        "queue_id": queue_id,
        "tickets_waiting": tickets_waiting,
        "longest_wait_sec": longest_wait_sec,
        "sla_target_sec": sla_target_sec,
    }


def adherence_event(
    agent_id="a_19",
    in_violation=True,
    scheduled_state="available",
    actual_state="on_break",
    queue_ids=None,
    event_id="evt_002",
    ts="2026-05-26T09:05:00Z",
):
    return {
        "type": "adherence_check",
        "event_id": event_id,
        "ts": ts,
        "agent_id": agent_id,
        "in_violation": in_violation,
        "scheduled_state": scheduled_state,
        "actual_state": actual_state,
        "queue_ids": queue_ids or ["billing"],
    }


def state_change_event(
    agent_id="a_19",
    new_state="on_break",
    previous_state="available",
    previous_state_duration_sec=3600,
    queue_ids=None,
    event_id="evt_003",
    ts="2026-05-26T09:10:00Z",
):
    return {
        "type": "agent_state_change",
        "event_id": event_id,
        "ts": ts,
        "agent_id": agent_id,
        "new_state": new_state,
        "previous_state": previous_state,
        "previous_state_duration_sec": previous_state_duration_sec,
        "queue_ids": queue_ids or ["billing"],
    }


# ── Core stateful behaviour ───────────────────────────────────────────────────

def test_condition_met_creates_notification():
    """First time a queue_snapshot exceeds the threshold, a notification fires."""
    engine = RuleEngine()
    config = make_config(field="tickets_waiting", comparator="gt", value=10)
    event = queue_event(tickets_waiting=20)

    new, updated, resolved = engine.process_event(event, [config])

    assert len(new) == 1
    assert updated == []
    assert resolved == []
    n = new[0]
    assert n["config_id"] == "cfg_1"
    assert n["triggered_at"] == event["ts"]
    assert n["last_seen_at"] == event["ts"]
    assert n["recipient_ids"] == ["u_1"]


def test_condition_below_threshold_fires_nothing():
    """When the event value is below the threshold, no notification is created."""
    engine = RuleEngine()
    config = make_config(field="tickets_waiting", comparator="gt", value=10)
    event = queue_event(tickets_waiting=5)

    new, updated, resolved = engine.process_event(event, [config])

    assert new == []
    assert updated == []
    assert resolved == []


def test_active_condition_does_not_refire():
    """A condition that stays true across consecutive events creates only one notification."""
    engine = RuleEngine()
    config = make_config(field="tickets_waiting", comparator="gt", value=10)

    new1, _, _ = engine.process_event(queue_event(tickets_waiting=20, event_id="e1"), [config])
    new2, updated, _ = engine.process_event(queue_event(tickets_waiting=25, event_id="e2"), [config])

    assert len(new1) == 1
    assert new2 == []                         # no second notification
    assert len(updated) == 1                  # last_seen_at is bumped instead
    assert updated[0]["last_seen_at"] == queue_event(event_id="e2")["ts"]


def test_condition_clearing_resolves_notification():
    """When a stateful condition drops below the threshold, the notification auto-resolves."""
    engine = RuleEngine()
    config = make_config(field="tickets_waiting", comparator="gt", value=10)

    engine.process_event(queue_event(tickets_waiting=20, event_id="e1", ts="T1"), [config])
    _, _, resolved = engine.process_event(queue_event(tickets_waiting=3, event_id="e2", ts="T2"), [config])

    assert len(resolved) == 1
    r = resolved[0]
    assert r["resolved_at"] == "T2"
    assert r["resolved_by_event_id"] == "e2"


def test_retrigger_after_clear_creates_new_notification():
    """After a condition clears and fires again, a brand-new notification is created."""
    engine = RuleEngine()
    config = make_config(field="tickets_waiting", comparator="gt", value=10)

    new1, _, _ = engine.process_event(queue_event(tickets_waiting=20, event_id="e1"), [config])
    engine.process_event(queue_event(tickets_waiting=3, event_id="e2"), [config])   # clears
    new3, _, _ = engine.process_event(queue_event(tickets_waiting=20, event_id="e3"), [config])

    assert len(new1) == 1
    assert len(new3) == 1
    assert new1[0]["id"] != new3[0]["id"]    # different notification objects


# ── Discrete events ───────────────────────────────────────────────────────────

def test_discrete_event_always_fires():
    """agent_state_change is discrete — every matching event fires a fresh notification."""
    engine = RuleEngine()
    config = make_config(
        event_type="agent_state_change",
        field="previous_state_duration_sec",
        comparator="gt",
        value=1800,
    )

    new1, _, _ = engine.process_event(state_change_event(previous_state_duration_sec=3600, event_id="e1"), [config])
    new2, _, _ = engine.process_event(state_change_event(previous_state_duration_sec=3600, event_id="e2"), [config])

    assert len(new1) == 1
    assert len(new2) == 1                     # second event also fires
    assert new1[0]["id"] != new2[0]["id"]


def test_discrete_event_below_threshold_fires_nothing():
    engine = RuleEngine()
    config = make_config(
        event_type="agent_state_change",
        field="previous_state_duration_sec",
        comparator="gt",
        value=1800,
    )
    new, _, _ = engine.process_event(state_change_event(previous_state_duration_sec=60), [config])
    assert new == []


# ── Scope filtering ───────────────────────────────────────────────────────────

def test_queue_scope_filters_unmatched_queue():
    """A queue_snapshot for a queue not in scope should be ignored."""
    engine = RuleEngine()
    config = make_config(scope={"queue_ids": ["billing"], "agent_ids": None})
    event = queue_event(queue_id="tier_2", tickets_waiting=50)

    new, _, _ = engine.process_event(event, [config])
    assert new == []


def test_queue_scope_matches_correct_queue():
    engine = RuleEngine()
    config = make_config(scope={"queue_ids": ["billing"], "agent_ids": None})
    event = queue_event(queue_id="billing", tickets_waiting=50)

    new, _, _ = engine.process_event(event, [config])
    assert len(new) == 1


def test_agent_scope_filters_unmatched_agent():
    """An adherence_check for an agent not in scope should be ignored."""
    engine = RuleEngine()
    config = make_config(
        event_type="adherence_check",
        field="in_violation",
        comparator="eq",
        value=True,
        scope={"agent_ids": ["a_19"], "queue_ids": None},
    )
    event = adherence_event(agent_id="a_07", in_violation=True)

    new, _, _ = engine.process_event(event, [config])
    assert new == []


def test_no_scope_matches_all_queues():
    """A config with no scope watches every queue."""
    engine = RuleEngine()
    config = make_config(scope=None)

    new1, _, _ = engine.process_event(queue_event(queue_id="billing", event_id="e1"), [config])
    new2, _, _ = engine.process_event(queue_event(queue_id="tier_2", event_id="e2"), [config])

    # Each queue gets its own independent notification
    assert len(new1) == 1
    assert len(new2) == 1


# ── Filter preconditions ──────────────────────────────────────────────────────

def test_filter_must_match_for_stateful_event_to_be_evaluated():
    """A stateful event that fails the filter is skipped entirely (not resolved)."""
    engine = RuleEngine()
    config = make_config(
        event_type="adherence_check",
        field="in_violation",
        comparator="eq",
        value=True,
        filter={"scheduled_state": "available"},
    )
    # Fire once with matching filter
    engine.process_event(
        adherence_event(in_violation=True, scheduled_state="available", event_id="e1"),
        [config],
    )
    # Next event fails filter — should NOT resolve the active notification
    _, _, resolved = engine.process_event(
        adherence_event(in_violation=True, scheduled_state="lunch", event_id="e2"),
        [config],
    )
    assert resolved == []


def test_filter_mismatch_on_discrete_event_suppresses_notification():
    """A discrete event that fails the filter does not fire a notification."""
    engine = RuleEngine()
    config = make_config(
        event_type="agent_state_change",
        field="previous_state_duration_sec",
        comparator="gt",
        value=60,
        filter={"previous_state": "on_call"},
    )
    event = state_change_event(previous_state="available", previous_state_duration_sec=3600)

    new, _, _ = engine.process_event(event, [config])
    assert new == []


# ── pct_of_sla value mode ─────────────────────────────────────────────────────

def test_pct_of_sla_fires_when_threshold_exceeded():
    """80% of a 120s SLA target = 96s. A 100s wait should trigger."""
    engine = RuleEngine()
    config = make_config(
        field="longest_wait_sec",
        comparator="gt",
        value=80,
        value_mode="pct_of_sla",
    )
    event = queue_event(longest_wait_sec=100, sla_target_sec=120)

    new, _, _ = engine.process_event(event, [config])
    assert len(new) == 1


def test_pct_of_sla_does_not_fire_below_threshold():
    """80% of 120s = 96s. A 90s wait should not trigger."""
    engine = RuleEngine()
    config = make_config(
        field="longest_wait_sec",
        comparator="gt",
        value=80,
        value_mode="pct_of_sla",
    )
    event = queue_event(longest_wait_sec=90, sla_target_sec=120)

    new, _, _ = engine.process_event(event, [config])
    assert new == []


# ── Multiple rules and recipients ─────────────────────────────────────────────

def test_multiple_matching_configs_all_fire():
    """When two rules both match the same event, both fire independent notifications."""
    engine = RuleEngine()
    cfg1 = make_config(id="cfg_1", value=10)
    cfg2 = make_config(id="cfg_2", value=5)
    event = queue_event(tickets_waiting=20)

    new, _, _ = engine.process_event(event, [cfg1, cfg2])
    assert len(new) == 2
    assert {n["config_id"] for n in new} == {"cfg_1", "cfg_2"}


def test_multiple_recipients_on_one_config():
    """A config with two recipients fans out recipient_ids to the notification."""
    engine = RuleEngine()
    config = make_config(assignments=[{"recipient_id": "u_1"}, {"recipient_id": "u_2"}])
    event = queue_event(tickets_waiting=20)

    new, _, _ = engine.process_event(event, [config])
    assert len(new) == 1
    assert set(new[0]["recipient_ids"]) == {"u_1", "u_2"}


def test_two_queues_tracked_independently():
    """The same rule watches two queues independently — each gets its own notification."""
    engine = RuleEngine()
    config = make_config(scope=None)  # no queue scope = watches all

    new1, _, _ = engine.process_event(queue_event(queue_id="billing", event_id="e1"), [config])
    new2, _, _ = engine.process_event(queue_event(queue_id="tier_2", event_id="e2"), [config])

    assert len(new1) == 1
    assert len(new2) == 1
    # Clearing billing should not affect tier_2
    _, _, resolved = engine.process_event(queue_event(queue_id="billing", tickets_waiting=0, event_id="e3"), [config])
    assert len(resolved) == 1
    assert resolved[0]["id"] == new1[0]["id"]


def test_reset_clears_active_state():
    """After reset(), a previously active condition fires a fresh notification."""
    engine = RuleEngine()
    config = make_config()
    engine.process_event(queue_event(event_id="e1"), [config])

    engine.reset()

    new, _, _ = engine.process_event(queue_event(event_id="e2"), [config])
    assert len(new) == 1


# ── Event type mismatch ───────────────────────────────────────────────────────

def test_wrong_event_type_is_ignored():
    """A queue_snapshot event should not be evaluated against an adherence_check config."""
    engine = RuleEngine()
    config = make_config(event_type="adherence_check", field="in_violation", comparator="eq", value=True)
    event = queue_event(tickets_waiting=999)

    new, updated, resolved = engine.process_event(event, [config])
    assert new == []
    assert updated == []
    assert resolved == []
