"""Cadence FastAPI app: background Sent Items poller + REST API."""

from __future__ import annotations

import asyncio
import contextlib

from fastapi import FastAPI

from app import singleton_lock
from app.config import POLL_INTERVAL_SECONDS
from app.db import init_db
from app.poller import sync_sent_items
from app.replies import check_for_replies
from app.routers import accounts, cadences, contacts, prospects, targets, tasks


async def _poll_loop() -> None:
    while True:
        try:
            # Both sync_sent_items() and check_for_replies() are synchronous
            # and make blocking Graph HTTP calls (one per active cadence for
            # replies) - run them off the event loop so a slow poll cycle
            # doesn't freeze every other API request the whole time it runs.
            summary = await asyncio.to_thread(sync_sent_items)
            if summary["new_prospects"]:
                print(f"Sync: {len(summary['new_prospects'])} new prospect(s)")
            if summary["new_targets"]:
                print(f"Sync: {len(summary['new_targets'])} new target(s) detected")
        except Exception as e:
            # A transient Graph/network hiccup shouldn't kill the loop - it
            # just tries again next interval.
            print(f"WARNING: sync failed: {e}")
        try:
            reply_summary = await asyncio.to_thread(check_for_replies)
            if reply_summary["paused"]:
                print(f"Reply check: paused {len(reply_summary['paused'])} cadence(s)")
            if reply_summary["marked_ooo"]:
                print(f"Reply check: {len(reply_summary['marked_ooo'])} cadence(s) marked out-of-office")
            if reply_summary["resumed"]:
                print(f"Reply check: {len(reply_summary['resumed'])} cadence(s) resumed from out-of-office")
        except Exception as e:
            print(f"WARNING: reply check failed: {e}")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    singleton_lock.acquire()
    try:
        init_db()
        task = asyncio.create_task(_poll_loop())
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
    finally:
        singleton_lock.release()


app = FastAPI(title="Cadence", lifespan=lifespan)
app.include_router(prospects.router)
app.include_router(tasks.router)
app.include_router(cadences.router)
app.include_router(accounts.router)
app.include_router(targets.router)
app.include_router(contacts.router)


@app.get("/health")
def health():
    return {"status": "ok"}
