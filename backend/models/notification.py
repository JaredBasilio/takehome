from pydantic import BaseModel
from typing import List, Optional


class Notification(BaseModel):
    """
    The shared body of a notification — created once per rule+entity match,
    regardless of how many recipients are configured. Immutable after creation:
    config_label is copied at fire time so this record stays correct even if the
    rule is renamed or deleted later.

    Stored in the `notifications` table. This model is rule-engine-agnostic: the
    event stream, rule format, and delivery mechanism are all pluggable.
    """
    id: str
    config_id: str                         # the rule that triggered it
    config_label: str                      # snapshot at fire time; configs can be renamed/deleted
    triggering_event_ids: List[str]        # events that matched the rule; multiple for compound rules
    triggered_at: str                      # when the condition was first detected
    last_seen_at: str                      # updated on each subsequent matching event without re-firing
    message: str


class NotificationRecipient(BaseModel):
    """
    Per-recipient state for a notification. One row per (notification, recipient)
    pair in `notification_recipients`, so each person has independent read state,
    status, and room for future per-person attributes (comment, delivery destination,
    snooze, etc.) without affecting other recipients of the same notification.

    Lifecycle: created as 'active' when the condition first fires for this recipient.
    Auto-resolved (status → 'resolved') when the condition clears — all still-active
    rows for the notification are resolved together. A recipient can also dismiss
    manually, which only resolves their own row; other recipients are unaffected.
    A re-trigger after clearing creates a brand-new Notification, not a reopened row.
    """
    notification_id: str                   # FK to Notification; used in API calls (markRead, dismiss)
    recipient_id: str                      # who this state belongs to (user id, team id, monitor id, etc.)
    is_shared: bool = False                # True if the config was pushed to this recipient by another user
    read: bool = False
    status: str = "active"                 # "active" | "resolved"
    resolved_at: Optional[str] = None
    resolved_by_event_id: Optional[str] = None  # event that cleared it, or "user_dismissed"
    notification: Notification             # the shared body; nested so clients need no extra join
