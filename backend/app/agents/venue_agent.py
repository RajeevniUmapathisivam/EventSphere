from datetime import timedelta

from sqlalchemy import select

from app.agents.message_bus import P, agree, refuse
from app.models.models import Event, TicketCategory, Venue, VenueHireRequest
from app.schemas import EventInput, HireInput, VenueInput, iso, now, utc

BUFFER = timedelta(minutes=30)


class VenueAgent:
    def receive(self, db, message, bus):
        content = message.content
        action = content["action"]
        if action == "save_venue":
            return self.save_venue(db, content)
        if action == "create_event":
            return self.create_event(db, content)
        if action == "publish_event":
            return self.publish_event(db, content["event_id"])
        if action == "hire":
            return self.request_hire(db, message, bus)
        if action == "review_hire":
            return self.review_hire(db, message, bus)
        return refuse("Unknown venue request.")

    def save_venue(self, db, content):
        values = VenueInput.model_validate(content["venue"]).model_dump(mode="json")
        venue_id = content.get("venue_id")
        if venue_id is None:
            venue = Venue(**values)
            db.add(venue)
        else:
            venue = db.get(Venue, venue_id)
            if venue is None:
                return refuse("Venue was not found.")
            events = db.scalars(select(Event).where(
                Event.venue_id == venue.id, Event.status != "cancelled", Event.end_time > now(),
            ))
            for event in events:
                if self.ticket_capacity(db, event.id) > values["capacity"]:
                    return refuse("Capacity is below the ticket allocation of an existing event.")
            hires = db.scalars(select(VenueHireRequest).where(
                VenueHireRequest.venue_id == venue.id, VenueHireRequest.status == "confirmed",
                VenueHireRequest.end_time > now(),
            ))
            if any(hire.expected_attendees > values["capacity"] for hire in hires):
                return refuse("Capacity is below the guest count of a confirmed hire.")
            for key, value in values.items():
                setattr(venue, key, value)
        db.flush()
        return agree(venue_id=venue.id)

    def ticket_capacity(self, db, event_id):
        return sum(db.scalars(select(TicketCategory.total_quantity).where(TicketCategory.event_id == event_id)))

    def calendar(self, db, venue_id):
        events = db.execute(select(Event.start_time, Event.end_time).where(
            Event.venue_id == venue_id, Event.status == "published",
        ))
        hires = db.execute(select(VenueHireRequest.requested_date, VenueHireRequest.end_time).where(
            VenueHireRequest.venue_id == venue_id, VenueHireRequest.status == "confirmed",
        ))
        return sorted([*events, *hires])

    def free(self, calendar, start, end):
        return all(end + BUFFER <= booked_start or start >= booked_end + BUFFER
                   for booked_start, booked_end in calendar)

    def event_problem(self, db, venue, start, end, tickets, publish):
        if venue is None:
            return "Venue was not found."
        if start <= now():
            return "Event must start in the future."
        if tickets > venue.capacity:
            return "Total tickets exceed venue capacity."
        if publish and not self.free(self.calendar(db, venue.id), start, end):
            return "Venue calendar clashes with this event or its 30-minute turnaround."
        return None

    def create_event(self, db, content):
        event = EventInput.model_validate(content["event"])
        start, end = utc(event.start_time), utc(event.end_time)
        problem = self.event_problem(
            db, db.get(Venue, event.venue_id), start, end,
            sum(item.quantity for item in event.ticket_categories), event.status == "published",
        )
        if problem:
            return refuse(problem)
        record = Event(title=event.title, category=event.category, description=event.description,
                       venue_id=event.venue_id, organiser_id=content["user_id"],
                       start_time=start, end_time=end, status=event.status)
        db.add(record)
        db.flush()
        for category in event.ticket_categories:
            db.add(TicketCategory(event_id=record.id, name=category.name,
                                  price=category.price, total_quantity=category.quantity))
        return agree(event_id=record.id, status=record.status)

    def publish_event(self, db, event_id):
        event = db.get(Event, event_id)
        if event is None or event.status != "draft":
            return refuse("Only a saved draft can be published.")
        problem = self.event_problem(db, db.get(Venue, event.venue_id), event.start_time,
                                     event.end_time, self.ticket_capacity(db, event.id), True)
        if problem:
            return refuse(problem)
        event.status = "published"
        return agree(event_id=event.id, status=event.status)

    def alternative(self, venue, start, duration):
        return {"venue_id": venue.id, "venue_name": venue.name,
                "start_time": iso(start), "end_time": iso(start + duration),
                "price": str(venue.hourly_rate * (duration // timedelta(hours=1)))}

    def alternatives(self, db, hire, start, duration):
        suitable = list(db.scalars(select(Venue).where(
            Venue.open_for_hire.is_(True), Venue.capacity >= hire.expected_attendees,
        ).order_by(Venue.id)))
        options = []
        for venue in suitable:
            calendar = self.calendar(db, venue.id)
            if venue.id != hire.venue_id and self.free(calendar, start, start + duration):
                options.append(self.alternative(venue, start, duration))
            if len(options) == 3:
                return options
        if not options and suitable:
            venue = next((v for v in suitable if v.id == hire.venue_id), suitable[0])
            candidate = start
            for booked_start, booked_end in self.calendar(db, venue.id):
                if candidate + duration + BUFFER <= booked_start:
                    break
                candidate = max(candidate, booked_end + BUFFER)
            options.append(self.alternative(venue, candidate, duration))
        return options

    def request_hire(self, db, message, bus):
        content = message.content
        hire = HireInput.model_validate(content["hire"])
        start = utc(hire.requested_date)
        duration = timedelta(hours=hire.duration_hours)
        venue = db.get(Venue, hire.venue_id)
        if start <= now():
            return refuse("Hire must start in the future.")
        if venue is None:
            return refuse("Venue was not found.")
        if not venue.open_for_hire or venue.capacity < hire.expected_attendees:
            reason = "This venue is closed to private hire or has insufficient capacity."
        elif not self.free(self.calendar(db, venue.id), start, start + duration):
            reason = "This time conflicts with the venue calendar or its 30-minute turnaround."
        else:
            reason = None
        if reason:
            options = self.alternatives(db, hire, start, duration)
            if options:
                return P.PROPOSE, {"reason": reason, "alternatives": options}
            return refuse(reason + " No venue can accommodate this group.")
        status = "pending" if hire.expected_attendees > 50 or hire.duration_hours > 6 else "confirmed"
        record = VenueHireRequest(user_id=content["user_id"], venue_id=venue.id, requested_date=start,
                                  end_time=start + duration, expected_attendees=hire.expected_attendees,
                                  purpose=hire.purpose, price=venue.hourly_rate * hire.duration_hours,
                                  status=status)
        db.add(record)
        db.flush()
        bus.inform(message, action="hire_status", user_id=record.user_id, venue=venue.name,
                   status=status, price=str(record.price))
        return agree(hire_id=record.id, status=status, price=str(record.price))

    def review_hire(self, db, message, bus):
        hire = db.get(VenueHireRequest, message.content["hire_id"])
        if hire is None or hire.status != "pending":
            return refuse("Only a hire pending review can be decided.")
        venue = db.get(Venue, hire.venue_id)
        approved = message.content["approved"]
        if approved and (hire.requested_date <= now() or not venue.open_for_hire
                         or hire.expected_attendees > venue.capacity
                         or not self.free(self.calendar(db, venue.id), hire.requested_date, hire.end_time)):
            return refuse("This hire no longer fits the venue calendar or hiring rules. You can reject it.")
        hire.status = "confirmed" if approved else "rejected"
        bus.inform(message, action="hire_status", user_id=hire.user_id, venue=venue.name,
                   status=hire.status, price=str(hire.price))
        return agree(hire_id=hire.id, status=hire.status, price=str(hire.price))
