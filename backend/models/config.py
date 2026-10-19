from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class NotificationScope(BaseModel):
    agent_ids: Optional[List[str]] = None
    queue_ids: Optional[List[str]] = None


class ConfigAssignment(BaseModel):
    """
    One assignment of a NotificationConfig to a recipient. Stored as a row in
    `config_assignments(config_id, recipient_id)`. Modeled as its own class so
    future per-assignment attributes can be added without a schema change to
    NotificationConfig (e.g. is_enabled, interfaces, priority, snooze_until).
    """
    recipient_id: str                      # who receives notifications from this config
    # Future: is_enabled: bool = True
    # Future: interfaces: List[str] = ["in_app"]  # delivery channels: "in_app", "slack", "email"
    # Future: priority: str = "normal"


class NotificationConfig(BaseModel):
    id: str
    owner_id: str                          # who created and can edit/delete this config
    assignments: List[ConfigAssignment]    # who receives notifications; one row per recipient in config_assignments
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
