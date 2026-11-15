import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app import main
from app.database.connection import SessionLocal, connect
from app.models.models import AgentMessage, User, WaitlistEntry
from app.schemas import now


@pytest.fixture
def app(tmp_path, monkeypatch):
    url = os.getenv("EVENTSPHERE_TEST_POSTGRES_URL")
    engine = connect(url or f"sqlite:///{(tmp_path / 'test.sqlite3').as_posix()}")
    schema = "test_" + uuid4().hex
    if url:
        with engine.begin() as conn:
            conn.execute(text("CREATE SCHEMA " + schema))
        binding = engine.execution_options(schema_translate_map={None: schema})
    else:
        binding = engine
    original = SessionLocal.kw["bind"]
    SessionLocal.configure(bind=binding)
    monkeypatch.setattr(main, "engine", binding)
    monkeypatch.setattr(main, "DEMO_ENABLED", True)
    monkeypatch.setattr(main, "DEMO_DATA_ENABLED", False)
    monkeypatch.setattr(main, "SWEEP_SECONDS", 0.05)
    try:
        yield main.app
    finally:
        SessionLocal.configure(bind=original)
        if url:
            with engine.begin() as conn:
                conn.execute(text("DROP SCHEMA " + schema + " CASCADE"))
        engine.dispose()


def future(hours, minutes=0):
    return (datetime.now(timezone.utc) + timedelta(hours=hours, minutes=minutes)).replace(microsecond=0)


def csrf(client):
    session = client.get("/api/auth/session").json()
    return {"X-CSRF-Token": session["csrf_token"]}


def write(client, path, payload=None, method="POST"):
    return client.request(method, path, json=payload, headers=csrf(client))


def sign_in(client, role=None, email=None):
    if role:
        _, email, password = main.DEMO_ACCOUNTS[role]
    else:
        password = "StudentPass123"
    response = write(client, "/api/auth/login", {"email": email, "password": password})
    assert response.status_code == 200, response.text
    return client


def account(client, name):
    email = f"{name}@example.com"
    response = write(client, "/api/auth/register", {
        "full_name": name, "email": email, "password": "StudentPass123", "role": "admin",
    })
    assert response.status_code == 201, response.text
    return sign_in(client, email=email)


def venue(admin, name="Main Hall", capacity=100, open_for_hire=True):
    result = write(admin, "/api/admin/venues", {
        "name": name, "location": "Campus", "capacity": capacity, "hourly_rate": "2500.00",
        "description": "Auditorium", "image_url": "https://example.com/hall.png", "open_for_hire": open_for_hire,
    })
    assert result.status_code == 201, result.text
    return result.json()["venue_id"]


def event(admin, venue_id, start=None, quantity=1, status="published", title="Welcome Workshop", length=1):
    start = start or future(48)
    return write(admin, "/api/admin/events", {
        "title": title, "category": "Workshop", "venue_id": venue_id,
        "start_time": start.isoformat(), "end_time": (start + timedelta(hours=length)).isoformat(),
        "description": "A campus workshop", "ticket_categories": [{"name": "General", "price": "1000.01",
                                                                  "quantity": quantity}], "status": status,
    })


def published(admin, venue_id, **options):
    result = event(admin, venue_id, **options)
    assert result.status_code == 201, result.text
    event_id = result.json()["event_id"]
    category = admin.get(f"/api/events/{event_id}").json()["ticket_categories"][0]
    return {"event_id": event_id, "ticket_category_id": category["id"]}


def book(client, choice, quantity=1):
    return write(client, "/api/bookings", {**choice, "quantity": quantity})


def hire(client, venue_id, start, guests=10, duration=1):
    return write(client, "/api/hires", {"venue_id": venue_id, "requested_date": start.isoformat(),
                                       "expected_attendees": guests, "duration_hours": duration,
                                       "purpose": "Society reception"})


@pytest.fixture
def roles(app):
    with TestClient(app) as admin:
        yield sign_in(admin, "admin"), sign_in(TestClient(app), "attendee"), sign_in(TestClient(app), "staff")


def test_register_hashes_password_and_cannot_elevate_role(app):
    with TestClient(app) as client:
        account(client, "student")
        assert client.get("/api/auth/session").json()["user"]["role"] == "attendee"
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == "student@example.com"))
            assert user.password_hash.startswith("pbkdf2_sha256$")
            assert "StudentPass123" not in user.password_hash


def test_role_permissions_on_pages_and_apis(roles):
    admin, attendee, staff = roles
    assert attendee.get("/organiser-dashboard.html").status_code == 403
    assert attendee.get("/staff-dashboard.html").status_code == 403
    assert staff.get("/api/admin/messages").status_code == 403
    assert admin.get("/api/staff/events").status_code == 403
    assert write(attendee, "/api/admin/events/1/cancel").status_code == 403
    assert write(attendee, "/api/staff/checkin", {"event_id": 1, "qr_code": "abc"}).status_code == 403


def test_csrf_rejects_missing_and_incorrect_tokens(roles):
    admin, _, _ = roles
    assert admin.post("/api/admin/events/1/cancel").status_code == 403
    assert admin.post("/api/admin/events/1/cancel", headers={"X-CSRF-Token": "wrong"}).status_code == 403
    assert write(admin, "/api/admin/events/1/cancel").status_code == 409


def test_venue_edit_and_capacity_rules(roles):
    admin, attendee, _ = roles
    venue_id = venue(admin, capacity=10)
    assert event(admin, venue_id, quantity=11).status_code == 409
    published(admin, venue_id, quantity=9)
    info = admin.get("/api/admin/venues").json()[0]
    assert info["image_url"] == "https://example.com/hall.png"
    assert write(admin, f"/api/admin/venues/{venue_id}", {**info, "capacity": 5}, "PUT").status_code == 409
    result = write(admin, f"/api/admin/venues/{venue_id}", {**info, "open_for_hire": False, "hourly_rate": "900"}, "PUT")
    assert result.status_code == 200
    assert attendee.get("/api/venues").json() == []
    assert admin.get("/api/admin/venues").json()[0]["hourly_rate"] == "900.00"


def test_draft_publish_and_turnaround_buffer(roles):
    admin, _, _ = roles
    venue_id = venue(admin)
    start = future(48)
    published(admin, venue_id, start=start)
    assert event(admin, venue_id, start=start + timedelta(hours=1, minutes=29)).status_code == 409
    draft = event(admin, venue_id, start=start, status="draft").json()["event_id"]
    assert admin.get(f"/api/events/{draft}").status_code == 404
    assert write(admin, f"/api/admin/events/{draft}/publish").status_code == 409
    ready = event(admin, venue_id, start=start + timedelta(hours=1, minutes=30), status="draft").json()["event_id"]
    assert write(admin, f"/api/admin/events/{ready}/publish").status_code == 200
    assert len(admin.get("/api/events").json()) == 2


def test_last_seat_concurrent_bookings(app, roles):
    admin, first, _ = roles
    second = account(TestClient(app), "second")
    choice = published(admin, venue(admin))
    barrier = Barrier(2)

    def compete(client):
        barrier.wait(timeout=5)
        return book(client, choice).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(compete, (first, second))) == [201, 409]
    dashboard = admin.get("/api/admin/events").json()[0]
    assert dashboard["sold"] == 1 and dashboard["net_revenue"] == "1000.01"


def test_booking_limit_payment_and_unique_qr(roles):
    admin, attendee, _ = roles
    choice = published(admin, venue(admin), quantity=10)
    assert book(attendee, choice, 7).status_code == 409
    result = book(attendee, choice, 2)
    assert result.status_code == 201, result.text
    assert result.json()["payment_reference"].startswith("SIM-")
    records = attendee.get("/api/tickets").json()
    assert len(records) == 2
    assert len({record["qr_code"] for record in records}) == 2
    assert all(len(record["qr_code"]) >= 40 and record["qr_image"].startswith("data:image/png;base64,")
               for record in records)


def test_double_checkin_and_wrong_event(roles):
    admin, attendee, staff = roles
    venue_id = venue(admin)
    choice = published(admin, venue_id, start=future(0, 30))
    another = published(admin, venue_id, start=future(5))
    assert book(attendee, choice).status_code == 201
    token = attendee.get("/api/tickets").json()[0]["qr_code"]
    data = {"event_id": choice["event_id"], "qr_code": token}
    wrong = write(staff, "/api/staff/checkin", {**data, "event_id": another["event_id"]})
    assert wrong.status_code == 409 and "another event" in wrong.json()["detail"]
    assert write(staff, "/api/staff/checkin", data).status_code == 200
    duplicate = write(staff, "/api/staff/checkin", data)
    assert duplicate.status_code == 409 and "already been used" in duplicate.json()["detail"]
    assert next(row for row in admin.get("/api/admin/events").json()
                if row["id"] == choice["event_id"])["checkins"] == 1


def test_checkin_window_and_cancelled_ticket(roles):
    admin, attendee, staff = roles
    choice = published(admin, venue(admin))
    paid = book(attendee, choice).json()
    token = attendee.get("/api/tickets").json()[0]["qr_code"]
    data = {"event_id": choice["event_id"], "qr_code": token}
    assert "one hour" in write(staff, "/api/staff/checkin", data).json()["detail"]
    refund = write(attendee, f"/api/bookings/{paid['booking_id']}/cancel")
    assert refund.json()["refund"] == "1000.01"
    assert "cancelled" in write(staff, "/api/staff/checkin", data).json()["detail"]


def test_refund_policy_and_full_refund_on_event_cancellation(roles):
    admin, attendee, _ = roles
    choice = published(admin, venue(admin), start=future(4), quantity=2)
    first = book(attendee, choice).json()
    second = book(attendee, choice).json()
    assert write(attendee, f"/api/bookings/{first['booking_id']}/cancel").json()["refund"] == "500.01"
    assert write(admin, f"/api/admin/events/{choice['event_id']}/cancel").json()["refunded_bookings"] == 1
    records = {item["id"]: item for item in attendee.get("/api/bookings").json()}
    assert records[second["booking_id"]]["refund"] == "1000.01"
    assert all(ticket["status"] == "cancelled" for ticket in attendee.get("/api/tickets").json())


def test_hire_quote_counterproposal_and_event_conflict(roles):
    admin, attendee, _ = roles
    first = venue(admin, "Hall A")
    second = venue(admin, "Hall B")
    start = future(50)
    confirmed = hire(attendee, first, start, duration=2).json()
    assert confirmed["status"] == "confirmed" and confirmed["price"] == "5000.00"
    assert event(admin, first, start=start + timedelta(hours=2, minutes=29)).status_code == 409
    proposal = hire(attendee, first, start).json()
    assert proposal["decision"] == "PROPOSE" and proposal["reason"]
    assert proposal["alternatives"][0]["venue_id"] == second
    alternative = proposal["alternatives"][0]
    assert hire(attendee, second, datetime.fromisoformat(alternative["start_time"])).json()["status"] == "confirmed"
    later = hire(attendee, first, start).json()["alternatives"][0]
    assert datetime.fromisoformat(later["start_time"]) == start + timedelta(hours=2, minutes=30)


def test_admin_review_can_confirm_reject_and_revalidate(roles):
    admin, attendee, _ = roles
    venue_id = venue(admin)
    start = future(24)
    pending = hire(attendee, venue_id, start, guests=60).json()
    assert pending["status"] == "pending"
    assert write(admin, f"/api/admin/hires/{pending['hire_id']}/review", {"approved": True}).json()["status"] == "confirmed"
    second = hire(attendee, venue_id, start + timedelta(hours=4), guests=65).json()["hire_id"]
    assert hire(attendee, venue_id, start + timedelta(hours=4)).json()["status"] == "confirmed"
    assert write(admin, f"/api/admin/hires/{second}/review", {"approved": True}).status_code == 409
    assert write(admin, f"/api/admin/hires/{second}/review", {"approved": False}).json()["status"] == "rejected"


def test_waitlist_expires_and_reoffers_without_user_action(app, roles):
    admin, buyer, _ = roles
    first = account(TestClient(app), "first")
    second = account(TestClient(app), "second")
    choice = published(admin, venue(admin))
    paid = book(buyer, choice).json()
    assert write(first, "/api/waitlist", choice).status_code == 201
    assert write(second, "/api/waitlist", choice).status_code == 201
    assert write(buyer, f"/api/bookings/{paid['booking_id']}/cancel").status_code == 200
    first_offer = first.get("/api/waitlist").json()[0]
    assert first_offer["status"] == "offered"
    assert 0 < first_offer["remaining_ms"] <= 15 * 60 * 1000
    waiting = second.get("/api/waitlist").json()[0]
    assert waiting["status"] == "waiting" and waiting["remaining_ms"] is None
    assert book(buyer, choice).status_code == 409
    with SessionLocal.begin() as db:
        offer = db.scalar(select(WaitlistEntry).where(WaitlistEntry.status == "offered"))
        offer.expires_at = now() - timedelta(seconds=1)
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        with SessionLocal() as db:
            statuses = list(db.scalars(select(WaitlistEntry.status).order_by(WaitlistEntry.id)))
        if statuses == ["expired", "offered"]:
            break
        time.sleep(0.05)
    assert statuses == ["expired", "offered"]
    first_expired = first.get("/api/waitlist").json()[0]
    assert first_expired["status"] == "expired" and first_expired["remaining_ms"] is None
    second_offer = second.get("/api/waitlist").json()[0]
    assert second_offer["status"] == "offered" and 0 < second_offer["remaining_ms"] <= 15 * 60 * 1000
    assert book(second, choice).status_code == 201
    claimed = second.get("/api/waitlist").json()[0]
    assert claimed["status"] == "claimed" and claimed["remaining_ms"] is None
    assert any(row["sender"] == "Timer" and row["receiver"] == "WaitlistAgent"
               for row in admin.get("/api/admin/messages").json()["messages"])


def test_notification_routing_and_conversation_trace(roles):
    admin, attendee, _ = roles
    result = book(attendee, published(admin, venue(admin))).json()
    assert attendee.get("/api/notifications").json()[0]["title"] == "Tickets booked"
    trace = admin.get("/api/admin/messages", params={"conversation_id": result["conversation_id"]}).json()["messages"]
    assert len(trace) >= 6
    assert {row["conversation_id"] for row in trace} == {result["conversation_id"]}
    assert any(row["sender"] == "BookingAgent" and row["receiver"] == "TicketAgent" for row in trace)
    assert any(row["sender"] == "BookingAgent" and row["receiver"] == "broadcast"
               and row["performative"] == "INFORM" for row in trace)
    assert any(row["sender"] == "NotificationAgent" for row in trace)


def test_admin_can_read_older_messages_for_a_conversation(roles):
    admin, _, _ = roles
    with SessionLocal.begin() as db:
        db.add_all(AgentMessage(sender="BookingAgent", receiver="TicketAgent", performative="REQUEST",
                                content="{}", conversation_id="test-trace", created_at=now())
                   for _ in range(101))
    first = admin.get("/api/admin/messages", params={"conversation_id": "test-trace"}).json()
    assert len(first["messages"]) == 100
    second = admin.get("/api/admin/messages", params={
        "conversation_id": "test-trace", "before_id": first["next_before_id"],
    }).json()
    assert len(second["messages"]) == 1 and second["next_before_id"] is None


def test_bookings_and_admissions_survive_restart(app):
    with TestClient(app) as client:
        admin = sign_in(client, "admin")
        choice = published(admin, venue(admin), start=future(0, 30))
        sign_in(client, "attendee")
        assert book(client, choice).status_code == 201
        token = client.get("/api/tickets").json()[0]["qr_code"]
        sign_in(client, "staff")
        data = {"event_id": choice["event_id"], "qr_code": token}
        assert write(client, "/api/staff/checkin", data).status_code == 200
    with TestClient(app) as restarted:
        sign_in(restarted, "staff")
        assert "already been used" in write(restarted, "/api/staff/checkin", data).json()["detail"]


def test_demo_data_is_visible_and_does_not_duplicate_on_restart(app, monkeypatch):
    monkeypatch.setattr(main, "DEMO_DATA_ENABLED", True)
    for _ in range(2):
        with TestClient(app) as client:
            sign_in(client, "admin")
            assert len(client.get("/api/admin/venues").json()) == 2
            assert len(client.get("/api/admin/events").json()) == 3
            public = client.get("/api/events").json()
            assert {event["title"] for event in public} == {
                "Vavuniya Tamil Cultural Evening", "Vavuniya Student Web Development Workshop",
            }

            sign_in(client, "attendee")
            bookings = client.get("/api/bookings").json()
            assert len(bookings) == 2 and all(booking["payment_reference"].startswith("SIM-") for booking in bookings)
            tickets = client.get("/api/tickets").json()
            assert len({ticket["qr_code"] for ticket in tickets}) == 3
            assert all(ticket["qr_image"].startswith("data:image/png;base64,") for ticket in tickets)
