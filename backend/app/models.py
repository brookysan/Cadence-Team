"""Cadence database schema: Prospect -> Cadence -> Task."""

from __future__ import annotations

import datetime

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Account(Base):
    """A company on your uploaded account list. Prospect emails are only kept
    if their domain matches one of these - see app/matching.py."""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)


class IgnoredDomain(Base):
    """A domain the user chose to "Always Ignore" from Target Detection.
    Stored as the tldextract-resolved root (see app/matching.py domain_root),
    so ignoring "newcorp.com" also covers "mail.newcorp.co.uk" etc."""

    __tablename__ = "ignored_domains"

    id: Mapped[int] = mapped_column(primary_key=True)
    domain: Mapped[str] = mapped_column(String, unique=True, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)


class SyncState(Base):
    """Single-row table (id is always 1) tracking the Sent Items sync
    watermark, so the poller can ask Graph for "everything since here"
    instead of guessing how many recent messages is enough."""

    __tablename__ = "sync_state"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    last_synced_at: Mapped[str | None] = mapped_column(String, nullable=True)


class Prospect(Base):
    __tablename__ = "prospects"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    domain: Mapped[str] = mapped_column(String, index=True)
    # 'detected' (new, no cadence started yet), 'active', 'completed', 'paused',
    # 'out_of_office', 'manual_pause' (user manually paused/stopped - distinct
    # from 'paused', which is a genuine reply), 'dismissed', 'unmatched_domain'
    # (Target Detection - sales-looking email to a domain not on the account
    # list, awaiting a Targets page decision). Mirrors this prospect's
    # Cadence.status once a cadence exists - see cadence_service.py,
    # routers/tasks.py, routers/cadences.py, replies.py.
    status: Mapped[str] = mapped_column(String, default="detected")
    first_detected_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    # The Graph message this prospect was detected from - captured at
    # detection time, so both fields are only populated for prospects
    # detected after this feature was added (NULL for earlier ones).
    source_email_link: Mapped[str | None] = mapped_column(String, nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String, nullable=True)

    cadences: Mapped[list["Cadence"]] = relationship(back_populates="prospect")


class Cadence(Base):
    __tablename__ = "cadences"

    id: Mapped[int] = mapped_column(primary_key=True)
    prospect_id: Mapped[int] = mapped_column(ForeignKey("prospects.id"), index=True)
    started_at: Mapped[datetime.date] = mapped_column(Date)
    # 'active', 'completed', 'paused' (genuine reply - human takes over),
    # 'out_of_office' (auto-reply detected - see app/ooo_detection.py),
    # 'manual_pause' (user manually paused/stopped this cadence - see
    # routers/cadences.py; restartable or permanently deletable, unlike a
    # genuine reply pause)
    status: Mapped[str] = mapped_column(String, default="active")
    # Set when status is 'out_of_office' and a return date could be parsed
    # out of the auto-reply; cleared when the cadence auto-resumes.
    ooo_return_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    # The receivedDateTime (Graph's raw string) of the last prospect message
    # already reacted to - so an old out-of-office reply that's still the
    # newest message in the thread doesn't get re-processed forever once its
    # return date has passed and the cadence has resumed.
    last_reply_at: Mapped[str | None] = mapped_column(String, nullable=True)

    prospect: Mapped["Prospect"] = relationship(back_populates="cadences")
    tasks: Mapped[list["Task"]] = relationship(back_populates="cadence", order_by="Task.due_date")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    cadence_id: Mapped[int] = mapped_column(ForeignKey("cadences.id"), index=True)
    day_offset: Mapped[int] = mapped_column()
    label: Mapped[str] = mapped_column(String)
    due_date: Mapped[datetime.date] = mapped_column(Date, index=True)
    # 'pending', 'done'
    status: Mapped[str] = mapped_column(String, default="pending")
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    cadence: Mapped["Cadence"] = relationship(back_populates="tasks")
