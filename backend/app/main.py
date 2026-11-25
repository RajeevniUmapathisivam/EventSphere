import asyncio
import hmac
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import delete, select

from app.agents import sweep_waitlist
from app.core.config import DEMO_DATA_ENABLED, DEMO_ENABLED, PRODUCTION, ROOT, SWEEP_SECONDS
from app.core.security import hash_password, signed_in_user, verify_password
from app.database.connection import Base, SessionLocal, decision_transaction, engine
from app.demo_data import seed_demo_data
from app.models.models import DecisionLock, LoginSession, User
from app.routes import auth_routes, booking_routes, event_routes, ticket_routes, venue_routes

logger = logging.getLogger(__name__)
FRONTEND = ROOT / "frontend"
DEMO_ACCOUNTS = {
    "admin": ("Arul Selvan", "admin@example.com", "DemoAdmin123!"),
    "staff": ("Meena Tharmalingam", "staff@example.com", "DemoStaff123!"),
    "attendee": ("Kavitha Sivarajah", "attendee@example.com", "DemoAttendee123!"),
}


def initialize():
    Base.metadata.create_all(engine)
    with SessionLocal.begin() as db:
        if db.get(DecisionLock, 1) is None:
            db.add(DecisionLock(id=1))
    if not DEMO_ENABLED:
        return
    with SessionLocal() as db, decision_transaction(db):
        accounts = {}
        for role, (name, email, local_password) in DEMO_ACCOUNTS.items():
            password = os.getenv(f"DEMO_{role.upper()}_PASSWORD", "" if PRODUCTION else local_password)
            if len(password) < 8 or (PRODUCTION and password == local_password):
                raise RuntimeError(f"Set a distinct DEMO_{role.upper()}_PASSWORD of at least 8 characters.")
            existing = db.scalar(select(User).where(User.email == email))
            if existing is None:
                existing = User(full_name=name, email=email, password_hash=hash_password(password), role=role)
                db.add(existing)
            elif existing.role != role:
                raise RuntimeError(f"The demo email {email} belongs to a different role.")
            elif (
                role == "admin"
                and os.getenv("RESET_DEMO_ADMIN_PASSWORD") == "1"
                and not verify_password(password, existing.password_hash)
            ):
                existing.password_hash = hash_password(password)
                db.execute(delete(LoginSession).where(LoginSession.user_id == existing.id))
            accounts[role] = existing
        if DEMO_DATA_ENABLED:
            db.flush()
            seed_demo_data(db, accounts["admin"].id, accounts["attendee"].id)


async def timer(stop):
    while not stop.is_set():
        try:
            await asyncio.to_thread(sweep_waitlist)
        except Exception:
            logger.exception("Waitlist sweep failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=SWEEP_SECONDS)
        except TimeoutError:
            continue


@asynccontextmanager
async def lifespan(_app):
    await asyncio.to_thread(initialize)
    stop = asyncio.Event()
    job = asyncio.create_task(timer(stop))
    try:
        yield
    finally:
        stop.set()
        await job


app = FastAPI(title="EventSphere", lifespan=lifespan)


@app.middleware("http")
async def csrf_protection(request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        token = request.cookies.get("es_csrf", "")
        submitted = request.headers.get("X-CSRF-Token", "")
        if not token or not hmac.compare_digest(token.encode(), submitted.encode()):
            return JSONResponse({"detail": "Reload the page to refresh the security token."}, status_code=403)
    response = await call_next(request)
    if request.url.path.startswith("/api/") or request.url.path.endswith(".html"):
        response.headers["Cache-Control"] = "no-store"
    return response


for routes in (auth_routes, event_routes, booking_routes, venue_routes, ticket_routes):
    app.include_router(routes.router)


@app.get("/health")
def health():
    return {"status": "ok"}


def page(filename, request, role=None):
    if role:
        user = signed_in_user(request)
        if user is None:
            return RedirectResponse("/login.html")
        if user.role != role:
            raise HTTPException(403, "This page requires the " + role + " role.")
    return FileResponse(FRONTEND / filename)


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(FRONTEND / "index.html")


def page_handler(filename, role):
    def handler(request: Request):
        return page(filename, request, role)
    return handler


for filename, role in {
    "index.html": None, "login.html": None, "register.html": None, "event-details.html": None,
    "organiser-dashboard.html": "admin", "staff-dashboard.html": "staff", "attendee-dashboard.html": "attendee",
}.items():
    app.add_api_route("/" + filename, page_handler(filename, role), methods=["GET"], include_in_schema=False)

app.mount("/css", StaticFiles(directory=FRONTEND / "css"), name="css")
app.mount("/js", StaticFiles(directory=FRONTEND / "js"), name="js")
