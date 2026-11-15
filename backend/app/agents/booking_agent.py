from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select

from app.agents.message_bus import agree, refuse
from app.models.models import Booking, Event, Payment, Ticket, TicketCategory, WaitlistEntry
from app.schemas import now


def held_entries(db, category_id):
    return list(db.scalars(select(WaitlistEntry).where(
        WaitlistEntry.ticket_category_id == category_id, WaitlistEntry.status == "offered",
    )))


class BookingAgent:
    def receive(self, db, message, bus):
        content = message.content
        action = content["action"]
        if action == "book":
            return self.book(db, message, bus)
        if action == "cancel_booking":
            return self.cancel(db, message, bus)
        if action == "cancel_event":
            return self.cancel_event(db, message, bus)
        return refuse("Unknown booking request.")

    def book(self, db, message, bus):
        data = message.content
        event = db.get(Event, data["event_id"])
        category = db.get(TicketCategory, data["ticket_category_id"])
        quantity = data["quantity"]
        if not 1 <= quantity <= 6:
            return refuse("Book between 1 and 6 tickets at a time.")
        if event is None or event.status != "published" or now() >= event.start_time:
            return refuse("Booking is closed for this event.")
        if category is None or category.event_id != event.id:
            return refuse("Select a ticket category for this event.")
        holds = held_entries(db, category.id)
        offer = next((entry for entry in holds if entry.user_id == data["user_id"]
                      and entry.expires_at > now()), None)
        available = category.total_quantity - category.sold_quantity - len(holds)
        if quantity > available + bool(offer):
            return refuse("There are too few tickets available for this request.")
        total = category.price * quantity
        booking = Booking(booking_reference="ES-" + uuid4().hex.upper(), user_id=data["user_id"],
                          event_id=event.id, ticket_category_id=category.id, quantity=quantity,
                          total_amount=total, status="paid")
        db.add(booking)
        category.sold_quantity += quantity
        db.flush()
        payment = Payment(booking_id=booking.id, amount=total, transaction_reference="SIM-" + uuid4().hex.upper())
        db.add(payment)
        if offer:
            bus.send(message, "WaitlistAgent", action="claim", entry_id=offer.id)
        bus.send(message, "TicketAgent", action="issue", booking_id=booking.id)
        bus.inform(message, action="booking_paid", user_id=booking.user_id, event=event.title,
                   reference=payment.transaction_reference)
        return agree(booking_id=booking.id, booking_reference=booking.booking_reference,
                     payment_reference=payment.transaction_reference, amount=str(total))

    def cancel(self, db, message, bus):
        data = message.content
        booking = db.get(Booking, data["booking_id"])
        if booking is None or booking.user_id != data["user_id"]:
            return refuse("Booking was not found.")
        event = db.get(Event, booking.event_id)
        if booking.status != "paid" or now() >= event.start_time:
            return refuse("Only paid bookings before the event starts can be cancelled.")
        used = db.scalar(select(Ticket.id).where(Ticket.booking_id == booking.id, Ticket.status == "used").limit(1))
        if used:
            return refuse("A ticket in this booking has already been used.")
        rate = Decimal("1") if event.start_time - now() >= timedelta(hours=24) else Decimal("0.5")
        refund = self.refund(db, message, bus, booking, event, rate)
        bus.send(message, "WaitlistAgent", action="released", category_id=booking.ticket_category_id)
        return agree(booking_id=booking.id, refund=str(refund))

    def refund(self, db, message, bus, booking, event, rate):
        payment = db.scalar(select(Payment).where(Payment.booking_id == booking.id))
        amount = (payment.amount * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        payment.refund_amount = amount
        booking.status = "cancelled"
        category = db.get(TicketCategory, booking.ticket_category_id)
        category.sold_quantity -= booking.quantity
        bus.send(message, "TicketAgent", action="invalidate", booking_id=booking.id)
        bus.inform(message, action="booking_refunded", user_id=booking.user_id,
                   event=event.title, refund=str(amount))
        return amount

    def cancel_event(self, db, message, bus):
        event = db.get(Event, message.content["event_id"])
        if event is None or event.status != "published":
            return refuse("Only a published event can be cancelled.")
        event.status = "cancelled"
        bookings = list(db.scalars(select(Booking).where(Booking.event_id == event.id, Booking.status == "paid")))
        for booking in bookings:
            self.refund(db, message, bus, booking, event, Decimal("1"))
        bus.send(message, "WaitlistAgent", action="close", event_id=event.id)
        return agree(event_id=event.id, refunded_bookings=len(bookings), status=event.status)
