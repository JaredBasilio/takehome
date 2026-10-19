from pydantic import BaseModel


class Notification(BaseModel):
    """A live notification in a user's inbox. Exists while the condition is active."""
    id: str
    user_id: str                # recipient
    config_id: str              # the rule that triggered it
    config_label: str           # snapshot at fire time; configs can be renamed/deleted
    triggered_by_event_id: str  # event that first matched the rule
    triggered_at: str           # when the condition was first detected
    last_seen_at: str           # updated on each subsequent matching event
    message: str
    read: bool = False
    is_shared: bool = False     # True if the config was pushed by a team lead


class NotificationHistoryItem(BaseModel):
    """A resolved notification. Created when the condition clears or the user dismisses it."""
    id: str
    user_id: str
    config_id: str
    config_label: str           # snapshot at fire time; configs can be renamed/deleted
    triggered_at: str
    resolved_at: str
    resolved_by_event_id: str   # event that cleared the condition ("user_dismissed" if manual)
    message: str
    is_shared: bool = False
