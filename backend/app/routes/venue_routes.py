from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.database.connection import get_db
from app.models.models import Venue, VenueHireRequest
from app.routes import admin, attendee, decide
from app.schemas import HireDecision, HireInput, VenueInput, iso

router = APIRouter(prefix="/api")


def venues(db, hire_only):
    query = select(Venue)
    if hire_only:
        query = query.where(Venue.open_for_hire.is_(True))
    return [{"id": venue.id, "name": venue.name, "location": venue.location,
             "capacity": venue.capacity, "hourly_rate": str(venue.hourly_rate),
             "description": venue.description, "image_url": venue.image_url,
             "open_for_hire": venue.open_for_hire}
            for venue in db.scalars(query.order_by(Venue.name, Venue.id))]


@router.get("/venues")
def available_venues(user=Depends(attendee), db=Depends(get_db)):
    return venues(db, True)


@router.get("/admin/venues")
def admin_venues(user=Depends(admin), db=Depends(get_db)):
    return venues(db, False)


@router.post("/admin/venues", status_code=201)
def create_venue(payload: VenueInput, user=Depends(admin)):
    return decide("VenueAgent", "save_venue", user, venue=payload.model_dump(mode="json"))


@router.put("/admin/venues/{venue_id}")
def update_venue(venue_id: int, payload: VenueInput, user=Depends(admin)):
    return decide("VenueAgent", "save_venue", user, venue_id=venue_id, venue=payload.model_dump(mode="json"))


def hires(db, user_id=None):
    query = select(VenueHireRequest, Venue.name).join(Venue)
    if user_id is not None:
        query = query.where(VenueHireRequest.user_id == user_id)
    return [{"id": hire.id, "venue": name, "start_time": iso(hire.requested_date),
             "end_time": iso(hire.end_time), "guests": hire.expected_attendees,
             "purpose": hire.purpose, "status": hire.status, "price": str(hire.price)}
            for hire, name in db.execute(query.order_by(VenueHireRequest.id.desc()))]


@router.get("/hires")
def my_hires(user=Depends(attendee), db=Depends(get_db)):
    return hires(db, user.id)


@router.post("/hires")
def hire_venue(payload: HireInput, user=Depends(attendee)):
    return decide("VenueAgent", "hire", user, hire=payload.model_dump(mode="json"))


@router.get("/admin/hires")
def admin_hires(user=Depends(admin), db=Depends(get_db)):
    return hires(db)


@router.post("/admin/hires/{hire_id}/review")
def review_hire(hire_id: int, payload: HireDecision, user=Depends(admin)):
    return decide("VenueAgent", "review_hire", user, hire_id=hire_id, approved=payload.approved)
