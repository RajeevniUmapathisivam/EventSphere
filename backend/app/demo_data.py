from datetime import timedelta

from sqlalchemy import select

from app.agents import HANDLERS
from app.agents.message_bus import MessageBus, P
from app.agents.message_schema import AgentMessageSchema
from app.models.models import TicketCategory, Venue
from app.schemas import iso, now


def seed_demo_data(db, admin_id, attendee_id):
    if db.scalar(select(Venue.id).limit(1)) is not None:
        return

    bus = MessageBus(db, HANDLERS)

    def run(receiver, action, user_id, **content):
        reply = bus.dispatch(AgentMessageSchema(
            sender="Demo setup", receiver=receiver, performative=P.REQUEST,
            content={"action": action, "user_id": user_id, **content},
        ))
        if reply.performative != P.AGREE:
            raise RuntimeError(f"Demo setup failed: {reply.content}")
        return reply.content

    hall = run("VenueAgent", "save_venue", admin_id, venue={
        "name": "Muthamizh Cultural Hall", "location": "University of Vavuniya, Pampaimadu",
        "description": "A sample campus hall for student performances and society events.",
        "capacity": 120, "hourly_rate": "3500.00", "open_for_hire": True,
    })["venue_id"]
    seminar_room = run("VenueAgent", "save_venue", admin_id, venue={
        "name": "Thiruvalluvar Seminar Room",
        "location": "Faculty of Technological Studies, University of Vavuniya, Pampaimadu",
        "description": "A sample faculty seminar room for workshops and student presentations.",
        "capacity": 80, "hourly_rate": "2500.00", "open_for_hire": True,
    })["venue_id"]

    today = now()
    events = (
        ("Vavuniya Tamil Cultural Evening", "Concert", hall, timedelta(minutes=30), "published",
         "A campus showcase of Tamil music, poetry and student performances.", "750.00", 60, 2),
        ("Vavuniya Student Web Development Workshop", "Workshop", seminar_room, timedelta(days=7), "published",
         "A hands-on campus workshop on building a simple website.", "500.00", 30, 1),
        ("Pampaimadu Student Innovation Forum", "Seminar", seminar_room, timedelta(days=14), "draft",
         "A student forum for sharing practical ideas and campus projects.", "250.00", 40, 0),
    )
    for title, category, venue_id, offset, status, description, price, seats, quantity in events:
        start = today + offset
        event_id = run("VenueAgent", "create_event", admin_id, event={
            "title": title, "category": category, "description": description, "venue_id": venue_id,
            "start_time": iso(start), "end_time": iso(start + timedelta(hours=2)), "status": status,
            "ticket_categories": [{"name": "General Admission", "price": price, "quantity": seats}],
        })["event_id"]
        if quantity:
            category_id = db.scalar(select(TicketCategory.id).where(TicketCategory.event_id == event_id))
            run("BookingAgent", "book", attendee_id, event_id=event_id,
                ticket_category_id=category_id, quantity=quantity)
