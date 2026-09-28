"""The default outreach sequence created when you click Start Cadence.

(day_offset, label) pairs - due_date for each task is start date + day_offset.
Edit this list directly to change the steps or timing; nothing else needs to
change to pick it up.
"""

DEFAULT_SEQUENCE = [
    (0, "Initial email"),
    (3, "Follow-up email"),
    (7, "LinkedIn"),
    (10, "Call"),
    (14, "Follow-up"),
    (21, "Final email"),
]
