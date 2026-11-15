from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, EmailStr, Field, HttpUrl, StringConstraints, model_validator


def now():
    # Store all datetimes as UTC, including in SQLite, which drops timezone metadata.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utc(value):
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def iso(value):
    return value.replace(tzinfo=timezone.utc).isoformat() if value is not None else None


ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=3000)]
Money = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]
Positive = Annotated[int, Field(gt=0, le=100_000)]


class Login(BaseModel):
    email: Annotated[EmailStr, Field(max_length=150)]
    password: Annotated[str, Field(min_length=1, max_length=128)]


class Registration(Login):
    full_name: ShortText
    password: Annotated[str, Field(min_length=8, max_length=128)]


class VenueInput(BaseModel):
    name: Title
    location: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    description: Description
    capacity: Positive
    image_url: HttpUrl | None = None
    hourly_rate: Money
    open_for_hire: bool


class CategoryInput(BaseModel):
    name: ShortText
    price: Money
    quantity: Positive


class EventInput(BaseModel):
    title: Title
    category: ShortText
    venue_id: Positive
    start_time: AwareDatetime
    end_time: AwareDatetime
    description: Description
    ticket_categories: Annotated[list[CategoryInput], Field(min_length=1, max_length=20)]
    status: Literal["draft", "published"]

    @model_validator(mode="after")
    def check_event(self):
        if self.end_time <= self.start_time:
            raise ValueError("End must be after start.")
        names = {item.name.casefold() for item in self.ticket_categories}
        if len(names) != len(self.ticket_categories):
            raise ValueError("Each ticket category needs a distinct name.")
        return self


class TicketChoice(BaseModel):
    event_id: Positive
    ticket_category_id: Positive


class BookingInput(TicketChoice):
    quantity: Annotated[int, Field(strict=True)]


class CheckinInput(BaseModel):
    event_id: Positive
    qr_code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class HireInput(BaseModel):
    venue_id: Positive
    requested_date: AwareDatetime
    duration_hours: Annotated[int, Field(ge=1, le=24)]
    expected_attendees: Positive
    purpose: Description


class HireDecision(BaseModel):
    approved: bool
