"""Persistencia con SQLAlchemy 2.0 (SQLite por defecto; cambie USAB_DATABASE_URL para PostgreSQL)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (JSON, BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine,
                        event)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from . import config


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Participant(Base):
    __tablename__ = "participants"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_group: Mapped[str] = mapped_column(String(16), default="unknown")          # BLV | sighted | unknown
    assistive_tech: Mapped[str] = mapped_column(String(32), default="unknown")      # none | screen_reader | magnifier | unknown
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    sessions: Mapped[list["Session"]] = relationship(back_populates="participant", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    task_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    task_group: Mapped[str | None] = mapped_column(String(64), nullable=True)
    familiarity: Mapped[str | None] = mapped_column(String(16), nullable=True)
    difficulty_before: Mapped[str | None] = mapped_column(String(16), nullable=True)
    difficulty_after: Mapped[str | None] = mapped_column(String(16), nullable=True)
    success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    url_start: Mapped[str | None] = mapped_column(Text, nullable=True)
    browser: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extension_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    started_at_ms: Mapped[int] = mapped_column(BigInteger)
    ended_at_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="open")                   # open | closed | evaluated
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    participant: Mapped[Participant] = relationship(back_populates="sessions")
    events: Mapped[list["Event"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    evaluation: Mapped["Evaluation | None"] = relationship(back_populates="session", cascade="all, delete-orphan",
                                                         uselist=False)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    ts_ms: Mapped[int] = mapped_column(BigInteger, index=True)
    type: Mapped[str] = mapped_column(String(16))
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    x: Mapped[float | None] = mapped_column(Float, nullable=True)
    y: Mapped[float | None] = mapped_column(Float, nullable=True)
    scroll_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    key: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    target_tag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session: Mapped[Session] = relationship(back_populates="events")


class Evaluation(Base):
    __tablename__ = "evaluations"
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True)
    model_version: Mapped[str] = mapped_column(String(128))
    features: Mapped[dict] = mapped_column(JSON)          # vector completo usado por el modelo
    probabilities: Mapped[dict] = mapped_column(JSON)     # {"H1": 0.73, ...}
    predictions: Mapped[dict] = mapped_column(JSON)       # {"H1": 1, ...}
    thresholds: Mapped[dict] = mapped_column(JSON)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    n_events: Mapped[int] = mapped_column(Integer)
    history_sessions: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    session: Mapped[Session] = relationship(back_populates="evaluation")


engine = create_engine(config.DATABASE_URL, connect_args={"check_same_thread": False}
                       if config.DATABASE_URL.startswith("sqlite") else {})


if config.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _sqlite_fk(dbapi_conn, _):  # SQLite necesita activar las llaves foráneas para el borrado en cascada
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    if config.DATABASE_URL.startswith("sqlite"):
        from pathlib import Path
        Path(config.DATABASE_URL.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
