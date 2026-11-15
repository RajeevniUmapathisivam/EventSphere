from datetime import timedelta

from sqlalchemy import or_, select

from app.agents.message_bus import agree, refuse
from app.models.models import Event, TicketCategory, WaitlistEntry
from app.schemas import iso, now

HOLD = timedelta(minutes=15)


class WaitlistAgent:
    def receive(self, db, message, bus):
        content = message.content
        action = content["action"]
        if action == "join":
            return self.join(db, content)
        if action == "released":
            return agree(offered=self.offer(db, message, bus, content["category_id"], now()))
        if action == "claim":
            entry = db.get(WaitlistEntry, content["entry_id"])
            if entry is None or entry.status != "offered":
                return refuse("That waitlist hold is unavailable.")
            entry.status, entry.expires_at = "claimed", None
            return agree(entry_id=entry.id)
        if action == "close":
            return agree(closed=self.close(db, message, bus, content["event_id"]))
        if action == "sweep":
            return self.sweep(db, message, bus)
        return refuse("Unknown waitlist request.")

    def active(self):
        return select(WaitlistEntry).where(WaitlistEntry.status.in_(("waiting", "offered")))

    def join(self, db, data):
        event = db.get(Event, data["event_id"])
        category = db.get(TicketCategory, data["ticket_category_id"])
        if event is None or event.status != "published" or event.start_time <= now():
            return refuse("The waitlist is closed for this event.")
        if category is None or category.event_id != event.id:
            return refuse("Select a ticket category for this event.")
        entries = list(db.scalars(self.active().where(WaitlistEntry.ticket_category_id == category.id)))
        if any(entry.user_id == data["user_id"] for entry in entries):
            return refuse("You already have an active waitlist entry.")
        held = sum(entry.status == "offered" for entry in entries)
        if category.total_quantity > category.sold_quantity + held:
            return refuse("Tickets are available to book now.")
        entry = db.scalar(select(WaitlistEntry).where(
            WaitlistEntry.user_id == data["user_id"], WaitlistEntry.ticket_category_id == category.id,
        ))
        if entry is None:
            entry = WaitlistEntry(user_id=data["user_id"], event_id=event.id, ticket_category_id=category.id)
            db.add(entry)
        entry.status, entry.joined_at, entry.expires_at = "waiting", now(), None
        db.flush()
        return agree(entry_id=entry.id, status=entry.status)

    def offer(self, db, message, bus, category_id, timestamp):
        category = db.get(TicketCategory, category_id)
        event = db.get(Event, category.event_id)
        if event.status != "published" or event.start_time <= timestamp:
            return 0
        entries = list(db.scalars(self.active().where(WaitlistEntry.ticket_category_id == category_id)
                                  .order_by(WaitlistEntry.joined_at, WaitlistEntry.id)))
        held = sum(entry.status == "offered" for entry in entries)
        available = category.total_quantity - category.sold_quantity - held
        waiting = [entry for entry in entries if entry.status == "waiting"]
        offered = waiting[:max(0, available)]
        for entry in offered:
            entry.status = "offered"
            entry.expires_at = min(event.start_time, timestamp + HOLD)
            bus.inform(message, action="waitlist_offered", user_id=entry.user_id,
                       event=event.title, expires_at=iso(entry.expires_at))
        return len(offered)

    def due_query(self, timestamp):
        return self.active().join(Event, Event.id == WaitlistEntry.event_id).where(
            or_(WaitlistEntry.expires_at <= timestamp, Event.start_time <= timestamp)
        )

    def sweep(self, db, message, bus):
        timestamp = now()
        due = list(db.scalars(self.due_query(timestamp)))
        categories = set()
        for entry in due:
            event = db.get(Event, entry.event_id)
            action = "waitlist_closed" if event.start_time <= timestamp else "waitlist_expired"
            entry.status, entry.expires_at = "expired", None
            categories.add(entry.ticket_category_id)
            bus.inform(message, action=action, user_id=entry.user_id, event=event.title)
        for category_id in sorted(categories):
            self.offer(db, message, bus, category_id, timestamp)
        return agree(expired=len(due))

    def close(self, db, message, bus, event_id):
        event = db.get(Event, event_id)
        entries = list(db.scalars(self.active().where(WaitlistEntry.event_id == event_id)))
        for entry in entries:
            entry.status, entry.expires_at = "closed", None
            bus.inform(message, action="waitlist_closed", user_id=entry.user_id, event=event.title)
        return len(entries)
