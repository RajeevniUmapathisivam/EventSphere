from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.database.connection import get_db
from app.models.models import Booking, Event, Notification, Payment, TicketCategory, WaitlistEntry
from app.routes import attendee, decide
from app.schemas import BookingInput, TicketChoice, iso, now

router = APIRouter(prefix="/api")


@router.post("/bookings", status_code=201)
def book(payload: BookingInput, user=Depends(attendee)):
    return decide("BookingAgent", "book", user, **payload.model_dump())


@router.get("/bookings")
def bookings(user=Depends(attendee), db=Depends(get_db)):
    rows = db.execute(select(Booking, Payment, Event, TicketCategory.name).select_from(Booking)
                      .join(Payment).join(Event).join(TicketCategory).where(Booking.user_id == user.id)
                      .order_by(Booking.id.desc()))
    return [{"id": record.id, "reference": record.booking_reference,
             "event": event.title, "category": category, "quantity": record.quantity,
             "status": record.status, "can_cancel": record.status == "paid" and event.start_time > now(),
             "paid": str(payment.amount), "refund": str(payment.refund_amount),
             "payment_reference": payment.transaction_reference}
            for record, payment, event, category in rows]


@router.post("/bookings/{booking_id}/cancel")
def cancel(booking_id: int, user=Depends(attendee)):
    return decide("BookingAgent", "cancel_booking", user, booking_id=booking_id)


@router.post("/waitlist", status_code=201)
def join(payload: TicketChoice, user=Depends(attendee)):
    return decide("WaitlistAgent", "join", user, **payload.model_dump())


@router.get("/waitlist")
def waitlist(user=Depends(attendee), db=Depends(get_db)):
    rows = db.execute(select(WaitlistEntry, Event.title, TicketCategory.name).select_from(WaitlistEntry)
                      .join(Event).join(TicketCategory).where(WaitlistEntry.user_id == user.id)
                      .order_by(WaitlistEntry.id.desc()))
    timestamp = now()
    return [{"event_id": entry.event_id, "ticket_category_id": entry.ticket_category_id, "event": title,
             "category": category, "status": entry.status, "expires_at": iso(entry.expires_at),
             "remaining_ms": max(0, int((entry.expires_at - timestamp).total_seconds() * 1000))
             if entry.status == "offered" and entry.expires_at is not None else None}
            for entry, title, category in rows]


@router.get("/notifications")
def notifications(user=Depends(attendee), db=Depends(get_db)):
    records = db.scalars(select(Notification).where(Notification.user_id == user.id)
                         .order_by(Notification.id.desc()))
    return [{"title": item.title, "message": item.message} for item in records]
