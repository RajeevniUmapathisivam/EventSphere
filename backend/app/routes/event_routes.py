import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select

from app.database.connection import get_db
from app.models.models import AgentMessage, Booking, CheckinLog, Event, Payment, Ticket, TicketCategory, Venue, WaitlistEntry
from app.routes import admin, decide, staff
from app.schemas import EventInput, iso, now

router = APIRouter(prefix="/api")


def event_info(event, venue):
    return {"id": event.id, "title": event.title, "category": event.category,
            "venue": venue.name, "location": venue.location, "image_url": venue.image_url,
            "description": event.description, "start_time": iso(event.start_time), "end_time": iso(event.end_time),
            "status": event.status}


@router.get("/events")
def public_events(db=Depends(get_db)):
    rows = db.execute(select(Event, Venue).join(Venue).where(
        Event.status == "published", Event.end_time > now(),
    ).order_by(Event.start_time, Event.id))
    return [event_info(event, venue) for event, venue in rows]


@router.get("/events/{event_id}")
def public_event(event_id: int, db=Depends(get_db)):
    event = db.get(Event, event_id)
    if event is None or event.status != "published":
        raise HTTPException(404, "Published event was not found.")
    categories = list(db.scalars(select(TicketCategory).where(TicketCategory.event_id == event_id)
                                .order_by(TicketCategory.id)))
    holds = dict(db.execute(select(WaitlistEntry.ticket_category_id, func.count()).where(
        WaitlistEntry.event_id == event.id, WaitlistEntry.status == "offered",
    ).group_by(WaitlistEntry.ticket_category_id)).all())
    return {**event_info(event, db.get(Venue, event.venue_id)), "booking_open": event.start_time > now(),
            "ticket_categories": [
                {"id": item.id, "name": item.name, "price": str(item.price),
                 "available": item.total_quantity - item.sold_quantity - holds.get(item.id, 0)}
                for item in categories
            ]}


@router.get("/staff/events")
def staff_events(user=Depends(staff), db=Depends(get_db)):
    return public_events(db)


@router.post("/admin/events", status_code=201)
def create_event(payload: EventInput, user=Depends(admin)):
    return decide("VenueAgent", "create_event", user, event=payload.model_dump(mode="json"))


@router.post("/admin/events/{event_id}/publish")
def publish_event(event_id: int, user=Depends(admin)):
    return decide("VenueAgent", "publish_event", user, event_id=event_id)


@router.post("/admin/events/{event_id}/cancel")
def cancel_event(event_id: int, user=Depends(admin)):
    return decide("BookingAgent", "cancel_event", user, event_id=event_id)


@router.get("/admin/events")
def admin_events(user=Depends(admin), db=Depends(get_db)):
    sales = dict(db.execute(select(TicketCategory.event_id, func.sum(TicketCategory.sold_quantity))
                            .group_by(TicketCategory.event_id)).all())
    allocation = dict(db.execute(select(TicketCategory.event_id, func.sum(TicketCategory.total_quantity))
                                 .group_by(TicketCategory.event_id)).all())
    revenue = dict(db.execute(select(Booking.event_id, func.sum(Payment.amount - Payment.refund_amount))
                              .join(Payment).group_by(Booking.event_id)).all())
    admissions = dict(db.execute(select(Ticket.event_id, func.count()).join(CheckinLog)
                                 .group_by(Ticket.event_id)).all())
    rows = db.execute(select(Event, Venue).join(Venue).order_by(Event.start_time.desc(), Event.id.desc()))
    return [{**event_info(event, venue), "venue_capacity": venue.capacity,
             "ticket_capacity": allocation.get(event.id, 0), "sold": sales.get(event.id, 0),
             "net_revenue": str(revenue.get(event.id, 0)), "checkins": admissions.get(event.id, 0)}
            for event, venue in rows]


@router.get("/admin/messages")
def messages(conversation_id: str | None = None, before_id: int | None = None,
             user=Depends(admin), db=Depends(get_db)):
    query = select(AgentMessage)
    if conversation_id:
        query = query.where(AgentMessage.conversation_id == conversation_id)
    if before_id is not None:
        query = query.where(AgentMessage.id < before_id)
    records = list(db.scalars(query.order_by(AgentMessage.id.desc()).limit(101)))
    return {
        "messages": [
            {"sender": row.sender, "receiver": row.receiver, "performative": row.performative,
             "content": {key: value for key, value in json.loads(row.content).items() if key != "qr_code"},
             "conversation_id": row.conversation_id, "created_at": iso(row.created_at)}
            for row in records[:100]
        ],
        "next_before_id": records[99].id if len(records) > 100 else None,
    }
