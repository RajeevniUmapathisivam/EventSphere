from datetime import timedelta
from secrets import token_urlsafe

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.core.config import PRODUCTION, SESSION_SECONDS
from app.core.security import hash_password, session_digest, signed_in_user, verify_password
from app.database.connection import SessionLocal
from app.models.models import LoginSession, User
from app.schemas import Login, Registration, now

router = APIRouter(prefix="/api/auth")


def profile(user):
    return {"name": user.full_name, "role": user.role} if user else None


def csrf_cookie(response, token):
    response.set_cookie("es_csrf", token, httponly=True, secure=PRODUCTION, samesite="strict")


@router.get("/session")
def browser_session(request: Request, response: Response):
    token = request.cookies.get("es_csrf")
    if not token:
        token = token_urlsafe(32)
        csrf_cookie(response, token)
    return {"csrf_token": token, "user": profile(signed_in_user(request))}


@router.post("/register", status_code=201)
def register(payload: Registration):
    try:
        with SessionLocal.begin() as db:
            db.add(User(full_name=payload.full_name, email=payload.email.lower(),
                        password_hash=hash_password(payload.password), role="attendee"))
    except IntegrityError as exc:
        raise HTTPException(409, "That email address is already registered.") from exc
    return {"message": "Account created. Sign in to book tickets."}


@router.post("/login")
def login(payload: Login, request: Request, response: Response):
    token = token_urlsafe(32)
    with SessionLocal.begin() as db:
        user = db.scalar(select(User).where(User.email == payload.email.lower()))
        if user is None or not verify_password(payload.password, user.password_hash):
            raise HTTPException(401, "Email or password is incorrect.")
        db.execute(delete(LoginSession).where(LoginSession.expires_at <= now()))
        old = request.cookies.get("es_session")
        if old:
            db.execute(delete(LoginSession).where(LoginSession.token_hash == session_digest(old)))
        db.add(LoginSession(token_hash=session_digest(token), user_id=user.id,
                            expires_at=now() + timedelta(seconds=SESSION_SECONDS)))
    response.set_cookie("es_session", token, max_age=SESSION_SECONDS, httponly=True,
                        secure=PRODUCTION, samesite="strict")
    csrf = token_urlsafe(32)
    csrf_cookie(response, csrf)
    return {"user": profile(user), "csrf_token": csrf}


@router.post("/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get("es_session")
    if token:
        with SessionLocal.begin() as db:
            db.execute(delete(LoginSession).where(LoginSession.token_hash == session_digest(token)))
    response.delete_cookie("es_session", httponly=True, secure=PRODUCTION, samesite="strict")
    response.delete_cookie("es_csrf", httponly=True, secure=PRODUCTION, samesite="strict")
    return {"message": "Signed out."}
