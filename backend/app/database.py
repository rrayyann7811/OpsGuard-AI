from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    with SessionLocal() as session:
        yield session


if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def sqlite_options(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
