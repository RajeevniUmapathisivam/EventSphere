
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
from uuid import uuid4


class Performative(str, Enum):
    REQUEST = "REQUEST"
    AGREE = "AGREE"
    REFUSE = "REFUSE"
    PROPOSE = "PROPOSE"
    INFORM = "INFORM"
    FAILURE = "FAILURE"


class AgentMessageSchema(BaseModel):
    sender: str
    receiver: str
    performative: Performative
    content: dict[str, Any]
    conversation_id: str = Field(
        default_factory=lambda: str(uuid4())
    )
