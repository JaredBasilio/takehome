from pydantic import BaseModel
from typing import List, Optional


class User(BaseModel):
    user_id: str
    name: str
    role: str  # "agent" | "team_lead" | "head_of_support"
    agent_id: Optional[str] = None
    manages_queue_ids: Optional[List[str]] = None
