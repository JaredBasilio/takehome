from pydantic import BaseModel
from typing import Optional


class Notification(BaseModel):
    """
    A notification, active or resolved.

    Active notifications (status='active') appear in the inbox while the condition holds.
    last_seen_at is updated on each subsequent matching event so you can see how long
    the condition has been live.

    Resolved notifications (status='resolved') move to history when the condition clears
    or the user dismisses them. resolved_at and resolved_by_event_id are set at that point
    ('user_dismissed' if dismissed manually).
    """
    id: str
    user_id: str                           # recipient
    config_id: str                         # the rule that triggered it
    config_label: str                      # snapshot at fire time; configs can be renamed/deleted
    triggered_by_event_id: str             # event that first matched the rule
    triggered_at: str                      # when the condition was first detected
    last_seen_at: str                      # updated on each subsequent matching event
    message: str
    read: bool = False
    is_shared: bool = False                # True if the config was pushed by a team lead
    status: str = "active"                 # "active" | "resolved"
    resolved_at: Optional[str] = None
    resolved_by_event_id: Optional[str] = None  # event that cleared it, or "user_dismissed"
