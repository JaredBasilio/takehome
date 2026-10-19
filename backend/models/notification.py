from pydantic import BaseModel
from typing import List, Optional


class Notification(BaseModel):
    """
    A notification produced when a monitored condition is detected.

    Stored across two tables: notifications (the shared body — message, config,
    timestamps) and notification_recipients (per-recipient state — read, status,
    resolved_at). This model is a flattened JOIN result for one specific recipient,
    so the API can return a simple list without clients doing any joining.

    Lifecycle: the rule engine fires when a condition is first detected (status →
    'active'). last_seen_at is updated on each subsequent matching event without
    re-firing. When the condition clears, resolve_notification() resolves all
    still-active recipient rows at once. A recipient can also dismiss manually
    (status → 'resolved', resolved_by_event_id = 'user_dismissed'), which only
    affects their own row — other recipients continue to see the notification.

    This model is rule-engine-agnostic: the event stream, rule format, and
    delivery mechanism are all pluggable.
    """
    id: str
    recipient_id: str                      # who receives this notification (user, team, monitor, etc.)
    config_id: str                         # the rule that triggered it
    config_label: str                      # snapshot at fire time; configs can be renamed/deleted
    triggering_event_ids: List[str]        # events that matched the rule; multiple for compound rules
    triggered_at: str                      # when the condition was first detected
    last_seen_at: str                      # updated on each subsequent matching event
    message: str
    read: bool = False
    is_shared: bool = False                # True if the config was pushed to this recipient by another user
    status: str = "active"                 # "active" | "resolved"
    resolved_at: Optional[str] = None
    resolved_by_event_id: Optional[str] = None  # event that cleared it, or "user_dismissed"
