import hashlib
import hmac
import secrets

from fastapi import HTTPException, Request

from app.core.config import SESSION_SECONDS
from app.database.connection import SessionLocal
from app.models.models import LoginSession, User
from app.schemas import now

ITERATIONS = 600_000


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest.hex()}"


def verify_password(password, stored):
    scheme, rounds, salt, expected = stored.split("$")
    if scheme != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
    return hmac.compare_digest(digest.hex(), expected)


def session_digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def signed_in_user(request: Request):
    token = request.cookies.get("es_session")
    if not token:
        return None
    with SessionLocal() as db:
        session = db.get(LoginSession, session_digest(token))
        if session and session.expires_at > now():
            return db.get(User, session.user_id)
    return None


def role_required(role):
    def current_user(request: Request):
        user = signed_in_user(request)
        if user is None:
            raise HTTPException(401, "Sign in first.")
        if user.role != role:
            raise HTTPException(403, "This action requires the " + role + " role.")
        return user
    return current_user
