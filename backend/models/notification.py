from pydantic import BaseModel


class Notification(BaseModel):
    id: str
    user_id: str
    config_id: str
    config_label: str
    triggered_by_event_id: str
    triggered_at: str
    last_seen_at: str
    message: str
    read: bool = False
    is_shared: bool = False


class NotificationHistoryItem(BaseModel):
    id: str
    user_id: str
    config_id: str
    config_label: str
    triggered_at: str
    resolved_at: str
    resolved_by_event_id: str
    message: str
    is_shared: bool = False
