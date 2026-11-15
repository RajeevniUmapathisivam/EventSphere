import logging

from app.agents.booking_agent import BookingAgent
from app.agents.message_bus import MessageBus, P
from app.agents.message_schema import AgentMessageSchema
from app.agents.notification_agent import NotificationAgent
from app.agents.ticket_agent import TicketAgent
from app.agents.venue_agent import VenueAgent
from app.agents.waitlist_agent import WaitlistAgent
from app.database.connection import SessionLocal, decision_transaction
from app.models.models import WaitlistEntry
from app.schemas import now

logger = logging.getLogger(__name__)
waitlist = WaitlistAgent()
HANDLERS = {
    "VenueAgent": VenueAgent(),
    "BookingAgent": BookingAgent(),
    "TicketAgent": TicketAgent(),
    "WaitlistAgent": waitlist,
    "NotificationAgent": NotificationAgent(),
}


def request_agent(receiver, action, *, sender="Web", **content):
    envelope = AgentMessageSchema(
        sender=sender, receiver=receiver, performative=P.REQUEST,
        content={"action": action, **content},
    )
    try:
        with SessionLocal() as db, decision_transaction(db):
            return MessageBus(db, HANDLERS).dispatch(envelope)
    except Exception:
        logger.exception("Agent conversation %s rolled back", envelope.conversation_id)
        with SessionLocal() as db, decision_transaction(db):
            return MessageBus(db, HANDLERS).record_failure(envelope)


def sweep_waitlist():
    with SessionLocal() as db:
        # Skip empty timer ticks without taking the write lock or growing the log.
        due = db.scalar(waitlist.due_query(now()).with_only_columns(WaitlistEntry.id).limit(1))
    if due is not None:
        request_agent("WaitlistAgent", "sweep", sender="Timer")
