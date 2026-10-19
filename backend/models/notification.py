from pydantic import BaseModel
from typing import List, Optional


class Notification(BaseModel):
    """
    A notification produced when a monitored condition is detected.

    The system evaluates rules (referenced by config_id) against an event stream.
    When a rule matches, one Notification is created per recipient (recipient_id).
    While the condition persists, last_seen_at is updated but no new notification
    is fired. When the condition clears, the notification is resolved (status →
    'resolved') and moved to history. Manual dismissals set resolved_by_event_id
    to 'user_dismissed'.

    This model is rule-engine-agnostic: the event stream, rule format, and
    delivery mechanism are all pluggable. Only the lifecycle (active → resolved)
    is enforced here.
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
