"""SQLite engine/session setup. Single local file, single user, no server."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DB_PATH = Path(__file__).resolve().parent.parent / "cadence.db"
# timeout=10: the background poller and the API now genuinely run in
# different threads (poll loop moved off the event loop via asyncio.to_thread),
# so a real - if rare and short-lived - write-lock collision between them is
# possible. sqlite3's default 5s busy timeout is a plausible fit; 10s gives a
# generous margin for a single-user tool without introducing a UI-facing hang.
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"timeout": 10})
SessionLocal = sessionmaker(bind=engine)


def init_db() -> None:
    from app.models import Base  # imported here to avoid a circular import

    Base.metadata.create_all(engine)
    _ensure_schema()


def _ensure_schema() -> None:
    """Apply small SQLite schema upgrades that create_all() cannot handle.

    This app does not use Alembic yet, so model changes need a lightweight
    guard for existing local databases. Each statement is additive and safe to
    run repeatedly.
    """
    with sqlite3.connect(DB_PATH) as conn:
        prospect_columns = {row[1] for row in conn.execute("PRAGMA table_info(prospects)")}
        if "source_email_link" not in prospect_columns:
            conn.execute("ALTER TABLE prospects ADD COLUMN source_email_link TEXT")
        if "conversation_id" not in prospect_columns:
            conn.execute("ALTER TABLE prospects ADD COLUMN conversation_id TEXT")

        cadence_columns = {row[1] for row in conn.execute("PRAGMA table_info(cadences)")}
        if "ooo_return_date" not in cadence_columns:
            conn.execute("ALTER TABLE cadences ADD COLUMN ooo_return_date DATE")
        if "last_reply_at" not in cadence_columns:
            conn.execute("ALTER TABLE cadences ADD COLUMN last_reply_at TEXT")

        # Case-insensitive uniqueness at the DB level, not just app-level
        # lowercasing (see detection.py/poller.py) - belt-and-suspenders so a
        # future code path that forgets to normalize can't create a
        # duplicate differing only in case, the way the plain unique=True
        # index on Prospect.email (case-sensitive by default in SQLite) let
        # happen before this was added.
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_prospects_email_nocase ON prospects(email COLLATE NOCASE)")


def get_session() -> Session:
    return SessionLocal()
