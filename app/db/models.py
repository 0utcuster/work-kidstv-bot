import datetime as dt
from sqlalchemy import (
    Integer, BigInteger, String, Text, Boolean, DateTime,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)

    full_name: Mapped[str] = mapped_column(String(256), default="")        # из Telegram
    display_name: Mapped[str] = mapped_column(String(128), default="")     # имя, которое ввёл пользователь
    phone: Mapped[str] = mapped_column(String(32), default="")             # по желанию

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_subscribed: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=lambda: dt.datetime.utcnow())
    last_seen_at: Mapped[dt.datetime] = mapped_column(DateTime, default=lambda: dt.datetime.utcnow())

    reactions: Mapped[list["EventReaction"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    starts_at: Mapped[dt.datetime] = mapped_column(DateTime)
    location: Mapped[str] = mapped_column(String(300), default="")
    url: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft/published/archived
    created_by_admin_tg_id: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=lambda: dt.datetime.utcnow())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=lambda: dt.datetime.utcnow())

    media: Mapped[list["EventMedia"]] = relationship(back_populates="event", cascade="all, delete-orphan")
    reactions: Mapped[list["EventReaction"]] = relationship(back_populates="event", cascade="all, delete-orphan")


class EventMedia(Base):
    __tablename__ = "event_media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    file_id: Mapped[str] = mapped_column(String(500))
    media_type: Mapped[str] = mapped_column(String(20), default="photo")  # photo/document

    event: Mapped["Event"] = relationship(back_populates="media")


class EventReaction(Base):
    __tablename__ = "event_reactions"
    __table_args__ = (UniqueConstraint("event_id", "user_id", name="uq_event_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    reaction: Mapped[str] = mapped_column(String(20))  # interested/declined
    reacted_at: Mapped[dt.datetime] = mapped_column(DateTime, default=lambda: dt.datetime.utcnow())

    event: Mapped["Event"] = relationship(back_populates="reactions")
    user: Mapped["User"] = relationship(back_populates="reactions")


class Broadcast(Base):
    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))  # event/custom
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # photo/document
    media_file_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft/running/done/failed
    audience: Mapped[str] = mapped_column(String(30), default="all")
    reminder_hours: Mapped[int] = mapped_column(Integer, default=12)
    created_by_admin_tg_id: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=lambda: dt.datetime.utcnow())
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class BroadcastRecipient(Base):
    __tablename__ = "broadcast_recipients"
    __table_args__ = (UniqueConstraint("broadcast_id", "user_id", name="uq_broadcast_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    broadcast_id: Mapped[int] = mapped_column(ForeignKey("broadcasts.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/sent/failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    action: Mapped[str] = mapped_column(String(50))
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=lambda: dt.datetime.utcnow())