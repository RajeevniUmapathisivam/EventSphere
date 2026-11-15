from fastapi import HTTPException

from app.agents import request_agent
from app.agents.message_bus import P
from app.core.security import role_required

admin = role_required("admin")
staff = role_required("staff")
attendee = role_required("attendee")


def decide(agent, action, user, **data):
    response = request_agent(agent, action, user_id=user.id, **data)
    if response.performative == P.REFUSE:
        raise HTTPException(409, response.content["reason"])
    if response.performative == P.FAILURE:
        raise HTTPException(500, response.content["reason"])
    return {**response.content, "decision": response.performative.value,
            "conversation_id": response.conversation_id}
