from pydantic import BaseModel
from typing import List


class UserQueueMembership(BaseModel):
    """
    One row in `user_queue_memberships(user_id, queue_id)`. Modeled as its own
    class so future per-membership attributes (role in the queue, start date,
    capacity weight, etc.) can be added without changing the User shape.
    """
    queue_id: str                          # the queue this user is responsible for


class User(BaseModel):
    """
    A contact-center user. Role determines what rules they can write and which
    queues and agents they can watch. Agents use their user id directly as their
    contact-center agent id (e.g. "a_19"), so event fields like agent_id match
    against user.id with no translation layer.
    """
    id: str
    name: str
    role: str                              # "agent" | "team_lead" | "head_of_support"
    queue_memberships: List[UserQueueMembership] = []  # queues this user manages; empty for agents
