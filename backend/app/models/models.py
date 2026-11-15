from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint

from app.database.connection import Base


class DecisionLock(Base):
    __tablename__ = "decision_lock"
    id = Column(Integer, primary_key=True)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    full_name = Column(String(120), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(30), nullable=False, default="attendee")


class LoginSession(Base):
    __tablename__ = "login_sessions"
    token_hash = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)


class Venue(Base):
    __tablename__ = "venues"
    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    location = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    capacity = Column(Integer, nullable=False)
    image_url = Column(Text)
    hourly_rate = Column(Numeric(10, 2), nullable=False)
    open_for_hire = Column(Boolean, nullable=False)


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    title = Column(String(150), nullable=False)
    category = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    venue_id = Column(Integer, ForeignKey("venues.id"), nullable=False, index=True)
    organiser_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(String(30), nullable=False)


class TicketCategory(Base):
    __tablename__ = "ticket_categories"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    total_quantity = Column(Integer, nullable=False)
    sold_quantity = Column(Integer, default=0, nullable=False)


class Booking(Base):
    __tablename__ = "bookings"
    id = Column(Integer, primary_key=True)
    booking_reference = Column(String(50), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False, index=True)
    ticket_category_id = Column(Integer, ForeignKey("ticket_categories.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    total_amount = Column(Numeric(14, 2), nullable=False)
    status = Column(String(30), nullable=False)


class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), unique=True, nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    transaction_reference = Column(String(100), unique=True, nullable=False)
    refund_amount = Column(Numeric(14, 2), default=0, nullable=False)


class Ticket(Base):
    __tablename__ = "tickets"
    id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False, index=True)
    qr_code = Column(String(255), unique=True, nullable=False)
    status = Column(String(30), nullable=False)


class VenueHireRequest(Base):
    __tablename__ = "venue_hire_requests"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    venue_id = Column(Integer, ForeignKey("venues.id"), nullable=False, index=True)
    requested_date = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    expected_attendees = Column(Integer, nullable=False)
    purpose = Column(Text, nullable=False)
    price = Column(Numeric(14, 2), nullable=False)
    status = Column(String(30), nullable=False)


class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"
    __table_args__ = (UniqueConstraint("user_id", "event_id", "ticket_category_id"),)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False, index=True)
    ticket_category_id = Column(Integer, ForeignKey("ticket_categories.id"), nullable=False, index=True)
    status = Column(String(30), nullable=False)
    expires_at = Column(DateTime)
    joined_at = Column(DateTime, nullable=False)


class AgentMessage(Base):
    __tablename__ = "agent_messages"
    id = Column(Integer, primary_key=True)
    sender = Column(String(80), nullable=False)
    receiver = Column(String(80), nullable=False)
    performative = Column(String(30), nullable=False)
    content = Column(Text, nullable=False)
    conversation_id = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False)


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(180), nullable=False)
    message = Column(Text, nullable=False)


class CheckinLog(Base):
    __tablename__ = "checkin_logs"
    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), unique=True, nullable=False)
    staff_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    checked_in_at = Column(DateTime, nullable=False)
