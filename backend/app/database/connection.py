from contextlib import contextmanager

from sqlalchemy import create_engine, event, update
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import DATABASE_URL

Base = declarative_base()


def connect(url):
    sqlite = url.startswith("sqlite:")
    engine = create_engine(
        url, pool_pre_ping=True,
        connect_args={"timeout": 30, "check_same_thread": False} if sqlite else {},
    )
    if sqlite:
        @event.listens_for(engine, "connect")
        def sqlite_settings(connection, _record):
            connection.execute("PRAGMA foreign_keys = ON")
    return engine


engine = connect(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as db:
        yield db


@contextmanager
def decision_transaction(db):
    from app.models.models import DecisionLock

    with db.begin():
        # The first statement acquires PostgreSQL's row lock or SQLite's writer lock.
        db.execute(update(DecisionLock).where(DecisionLock.id == 1).values(id=1))
        yield
