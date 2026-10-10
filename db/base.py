"""SQLAlchemy Base and Database Session Configuration.

Architectural Viva Notes:
1. Shared Declarative Base: Centralizes metadata for both Part A (conversations) and
   Part B (inventory) models while maintaining code isolation.
2. SQLite Concurrency: Configures `check_same_thread=False` to safely handle asynchronous
   FastAPI request worker threads with SQLite.
"""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from core.config import settings

# Engine configuration
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=settings.DEBUG,
)

# Shared sessionmaker
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative Base class for all ORM models across Part A and Part B."""
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all database tables registered with metadata."""
    import db.conversation_models  # noqa: F401
    import db.inventory_models     # noqa: F401
    import db.order_models         # noqa: F401
    Base.metadata.create_all(bind=engine)

