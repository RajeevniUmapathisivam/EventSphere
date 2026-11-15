import json
from collections import deque

from app.agents.message_schema import AgentMessageSchema, Performative
from app.models.models import AgentMessage
from app.schemas import now

P = Performative


def agree(**content):
    return P.AGREE, content


def refuse(reason):
    return P.REFUSE, {"reason": reason}


class MessageBus:
    """Deliver JSON envelopes and persist the whole conversation with its state changes."""

    def __init__(self, db, handlers):
        self.db = db
        self.handlers = handlers
        self.pending = deque()

    def log(self, message):
        payload = message.model_dump_json()
        received = AgentMessageSchema.model_validate_json(payload)
        self.db.add(AgentMessage(
            sender=received.sender, receiver=received.receiver,
            performative=received.performative.value,
            content=json.dumps(received.content), conversation_id=received.conversation_id, created_at=now(),
        ))
        return received

    def send(self, source, receiver, performative=P.REQUEST, **content):
        self.pending.append(AgentMessageSchema(
            sender=source.receiver, receiver=receiver, performative=performative,
            content=content, conversation_id=source.conversation_id,
        ))

    def inform(self, source, **content):
        self.send(source, "broadcast", P.INFORM, **content)

    def dispatch(self, request):
        self.pending.append(request)
        answer = None
        while self.pending:
            message = self.log(self.pending.popleft())
            # NotificationAgent subscribes to the broadcast topic.
            receiver = "NotificationAgent" if message.receiver == "broadcast" else message.receiver
            kind, content = self.handlers[receiver].receive(self.db, message, self)
            if answer is not None and kind != P.AGREE:
                raise RuntimeError(f"{receiver} declined an internal action: {content}")
            reply = self.log(AgentMessageSchema(
                sender=receiver, receiver=message.sender, performative=kind,
                content=content, conversation_id=message.conversation_id,
            ))
            if answer is None:
                answer = reply
        return answer

    def record_failure(self, request):
        self.log(request)
        return self.log(AgentMessageSchema(
            sender=request.receiver, receiver=request.sender, performative=P.FAILURE,
            content={"reason": "The action could not be completed. Please try again."},
            conversation_id=request.conversation_id,
        ))
