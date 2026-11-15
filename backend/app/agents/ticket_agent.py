from datetime import timedelta
from secrets import token_urlsafe

from sqlalchemy import select

from app.agents.message_bus import agree, refuse
from app.models.models import Booking, CheckinLog, Event, Ticket
from app.schemas import now


class TicketAgent:
    def receive(self, db, message, bus):
        content = message.content
        action = content["action"]
        if action == "issue":
            booking = db.get(Booking, content["booking_id"])
            if booking is None or booking.status != "paid":
                return refuse("Tickets require a paid booking.")
            existing = list(db.scalars(select(Ticket.id).where(Ticket.booking_id == booking.id)))
            if existing:
                return agree(ticket_count=len(existing))
            for _ in range(booking.quantity):
                db.add(Ticket(booking_id=booking.id, user_id=booking.user_id, event_id=booking.event_id,
                              qr_code=token_urlsafe(32), status="valid"))
            return agree(ticket_count=booking.quantity)
        if action == "invalidate":
            tickets = list(db.scalars(select(Ticket).where(Ticket.booking_id == content["booking_id"])))
            for ticket in tickets:
                ticket.status = "cancelled"
            return agree(cancelled=len(tickets))
        if action == "checkin":
            return self.checkin(db, message, bus)
        return refuse("Unknown ticket request.")

    def checkin(self, db, message, bus):
        content = message.content
        ticket = db.scalar(select(Ticket).where(Ticket.qr_code == content["qr_code"]))
        if ticket is None:
            return refuse("Unknown ticket code.")
        if ticket.event_id != content["event_id"]:
            return refuse("This ticket is for another event.")
        if ticket.status == "cancelled":
            return refuse("This ticket was cancelled.")
        if ticket.status == "used":
            return refuse("This ticket has already been used.")
        event = db.get(Event, ticket.event_id)
        timestamp = now()
        if not event.start_time - timedelta(hours=1) <= timestamp < event.end_time:
            return refuse("Check-in is open from one hour before the event until it ends.")
        ticket.status = "used"
        db.add(CheckinLog(ticket_id=ticket.id, staff_id=content["user_id"], checked_in_at=timestamp))
        bus.inform(message, action="checked_in", user_id=ticket.user_id, event=event.title)
        return agree(ticket_id=ticket.id, message="Admit attendee.")
