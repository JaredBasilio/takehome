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
    """
    A resolved notification, written when a condition clears or a user manually dismisses it.

    Notifications start in the active inbox (Notification). Once the condition is no longer
    true — e.g. the queue drops below the threshold, the agent returns to adherence — the
    notification moves here with a resolved_at timestamp. This lets you look back at what
    happened during a shift ("billing queue was overloaded 09:25–09:40") without cluttering
    the live inbox. Manual dismissals also land here, with resolved_by_event_id = "user_dismissed".
    """
    id: str
    user_id: str
    config_id: str
    config_label: str           # snapshot at fire time; configs can be renamed/deleted
    triggered_at: str
    resolved_at: str
    resolved_by_event_id: str   # event that cleared the condition ("user_dismissed" if manual)
    message: str
    is_shared: bool = False
