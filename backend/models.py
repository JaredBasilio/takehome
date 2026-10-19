from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class User(BaseModel):
    user_id: str
    name: str
    role: str  # "agent" | "team_lead" | "head_of_support"
    agent_id: Optional[str] = None
    manages_queue_ids: Optional[List[str]] = None


class NotificationScope(BaseModel):
    agent_ids: Optional[List[str]] = None
    queue_ids: Optional[List[str]] = None


class NotificationConfig(BaseModel):
    config_id: str
    user_id: str
    assigned_to_user_ids: List[str]
    label: str
    event_type: str  # "queue_snapshot" | "agent_state_change" | "adherence_check"
    field: str
    comparator: str  # "gt" | "lt" | "gte" | "lte" | "eq" | "neq"
    value: Any
    value_mode: str = "absolute"  # "absolute" | "pct_of_sla"
    scope: Optional[NotificationScope] = None
    filter: Optional[Dict[str, Any]] = None  # exact-match pre-conditions
    is_shared: bool = False


class CreateConfigRequest(BaseModel):
    label: str
    event_type: str
    field: str
    comparator: str
    value: Any
    value_mode: str = "absolute"
    scope: Optional[NotificationScope] = None
    filter: Optional[Dict[str, Any]] = None


class Notification(BaseModel):
    notification_id: str
    user_id: str
    config_id: str
    config_label: str
    triggered_by_event_id: str
    triggered_at: str
    last_seen_at: str
    message: str
    read: bool = False
    is_shared: bool = False  # came from a lead-pushed config


class NotificationHistoryItem(BaseModel):
    notification_id: str
    user_id: str
    config_id: str
    config_label: str
    triggered_at: str
    resolved_at: str
    resolved_by_event_id: str
    message: str
    is_shared: bool = False
