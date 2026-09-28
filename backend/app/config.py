"""Cadence configuration. Plain constants - single user, edit directly.

No .env/secrets needed here: the only Graph credential Cadence uses is the
shared one described in app/graph.py, and everything below is just filter
tuning, not something that needs to be hidden.
"""

# Your own company's domain - emails to this domain are never prospects.
OWN_DOMAIN = "amd.com"

# Domains that are clearly not sales prospects even though they're external:
# scheduling tools, e-signature services, video platforms, etc.
NON_SALES_DOMAINS = {
    "calendly.com",
    "docusign.net",
    "docusign.com",
    "zoom.us",
    "webex.com",
    "gotomeeting.com",
    "teams.microsoft.com",
}

# Local-part prefixes (before the @) that mark an address as automated/
# distribution rather than a person.
IGNORED_LOCAL_PARTS = (
    "noreply",
    "no-reply",
    "donotreply",
    "do-not-reply",
    "notifications",
    "communications",
    "distribution",
    "alerts",
)

# Sent Items subjects with these prefixes are calendar responses Outlook logs
# as "sent" mail, not actual outreach.
NOISE_SUBJECT_PREFIXES = (
    "Accepted:",
    "Declined:",
    "Tentatively accepted:",
    "Canceled:",
    "Cancelled:",
    "Updated:",
)

# How many of the most recent Sent Items to scan on the very first sync ever
# run (before there's a watermark to sync incrementally from). Every sync
# after that asks Graph for "everything since last time" instead, so this
# only matters once - make it generous enough to catch prospects who are
# genuinely recent but got crowded out of the last N by partner/internal
# noise (syncs, calendar responses, etc.).
INITIAL_BACKFILL_COUNT = 200

# Seconds between background syncs.
POLL_INTERVAL_SECONDS = 300
