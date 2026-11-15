from base64 import b64encode
from io import BytesIO

import qrcode
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.database.connection import get_db
from app.models.models import Booking, Event, Ticket, TicketCategory
from app.routes import attendee, decide, staff
from app.schemas import CheckinInput, iso

router = APIRouter(prefix="/api")


def qr_image(data):
    buffer = BytesIO()
    qrcode.make(data).save(buffer, format="PNG")
    return "data:image/png;base64," + b64encode(buffer.getvalue()).decode("ascii")


@router.get("/tickets")
def tickets(user=Depends(attendee), db=Depends(get_db)):
    rows = db.execute(select(Ticket, Event, TicketCategory.name).select_from(Ticket)
                      .join(Event, Ticket.event_id == Event.id).join(Booking, Ticket.booking_id == Booking.id)
                      .join(TicketCategory, Booking.ticket_category_id == TicketCategory.id)
                      .where(Ticket.user_id == user.id).order_by(Ticket.id.desc()))
    return [{"event": event.title, "category": category, "start_time": iso(event.start_time),
             "end_time": iso(event.end_time),
             "status": ticket.status, "qr_code": ticket.qr_code if ticket.status == "valid" else None,
             "qr_image": qr_image(ticket.qr_code) if ticket.status == "valid" else None}
            for ticket, event, category in rows]


@router.post("/staff/checkin")
def checkin(payload: CheckinInput, user=Depends(staff)):
    return decide("TicketAgent", "checkin", user, **payload.model_dump())
