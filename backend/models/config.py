from pydantic import BaseModel
from typing import Any, Dict, List, Optional


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
    filter: Optional[Dict[str, Any]] = None
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
