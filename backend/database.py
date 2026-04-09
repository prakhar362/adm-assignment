"""
database.py
-----------
SQLite connection via SQLAlchemy ORM.
Defines three tables:
  - tickets          : raw incoming support tickets
  - predictions      : ML inference results linked to a ticket
  - routing_decisions: final queue assignment after business-rule layer
"""

from datetime import datetime, timezone
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    Text,
    DateTime,
    ForeignKey,
    event,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    relationship,
    sessionmaker,
    Session,
)

# ---------------------------------------------------------------------------
# Engine & session factory
# ---------------------------------------------------------------------------
DATABASE_URL = "sqlite:///./ticket_routing.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # required for SQLite + threads
    echo=False,
)

# Enable WAL mode and foreign-key enforcement for SQLite
@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, _connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class Ticket(Base):
    """Stores the raw incoming support ticket."""

    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    customer_name = Column(String(255), nullable=False)
    customer_email = Column(String(255), nullable=False)
    subject = Column(String(512), nullable=False)
    description = Column(Text, nullable=False)
    language = Column(String(10), default="en")
    source_channel = Column(String(50), default="api")  # api | email | chat
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # relationships
    prediction = relationship(
        "Prediction", back_populates="ticket", uselist=False, cascade="all, delete-orphan"
    )
    routing_decision = relationship(
        "RoutingDecision", back_populates="ticket", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Ticket id={self.id} subject='{self.subject[:40]}'>"


class Prediction(Base):
    """Stores the ML model's inference output for a ticket."""

    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, unique=True)
    predicted_category = Column(String(100), nullable=False)
    predicted_intent = Column(String(150), nullable=True)
    confidence = Column(Float, nullable=False)
    model_version = Column(String(50), nullable=False)
    inference_time_ms = Column(Float, nullable=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    ticket = relationship("Ticket", back_populates="prediction")

    def __repr__(self) -> str:
        return (
            f"<Prediction ticket_id={self.ticket_id} "
            f"category='{self.predicted_category}' "
            f"confidence={self.confidence:.3f}>"
        )


class RoutingDecision(Base):
    """Stores the final routing/queue assignment after business rules."""

    __tablename__ = "routing_decisions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, unique=True)
    assigned_queue = Column(String(100), nullable=False)
    priority = Column(String(20), nullable=False, default="medium")  # low | medium | high | critical
    escalated = Column(Integer, default=0)  # 0/1 boolean flag
    reason = Column(Text, nullable=True)  # human-readable routing rationale
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    ticket = relationship("Ticket", back_populates="routing_decision")

    def __repr__(self) -> str:
        return (
            f"<RoutingDecision ticket_id={self.ticket_id} "
            f"queue='{self.assigned_queue}' priority='{self.priority}'>"
        )


# ---------------------------------------------------------------------------
# Table creation helper
# ---------------------------------------------------------------------------
def init_db() -> None:
    """Create all tables if they do not exist."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency — yields a DB session and ensures cleanup."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
