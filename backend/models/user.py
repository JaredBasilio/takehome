from pydantic import BaseModel
from typing import List, Optional


class User(BaseModel):
    id: str
    name: str
    role: str  # "agent" | "team_lead" | "head_of_support"
    manages_queue_ids: Optional[List[str]] = None
