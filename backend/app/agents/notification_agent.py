from app.agents.message_bus import P, agree, refuse
from app.models.models import Notification


class NotificationAgent:
    def receive(self, db, message, bus):
        if message.performative != P.INFORM:
            return refuse("Notifications require an INFORM event.")
        data = message.content
        action = data["action"]
        if action == "hire_status":
            title = "Venue hire update"
            detail = f'{data["venue"]}: {data["status"]}. Quoted price LKR {data["price"]}.'
        elif action == "booking_paid":
            title = "Tickets booked"
            detail = f'{data["event"]}. Payment reference {data["reference"]}.'
        elif action == "booking_refunded":
            title = "Booking cancelled"
            detail = f'{data["event"]}. Simulated refund LKR {data["refund"]}.'
        elif action == "checked_in":
            title = "Ticket admitted"
            detail = data["event"]
        elif action == "waitlist_offered":
            title = "Waitlist seat available"
            detail = f'One seat for {data["event"]} is held for you until {data["expires_at"]} (UTC).'
        elif action == "waitlist_expired":
            title = "Waitlist offer expired"
            detail = f'The held seat for {data["event"]} was released.'
        elif action == "waitlist_closed":
            title = "Waitlist closed"
            detail = data["event"]
        else:
            return refuse("This event has no notification rule.")
        db.add(Notification(user_id=data["user_id"], title=title, message=detail))
        return agree(user_id=data["user_id"], title=title)
