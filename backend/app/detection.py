"""Rule-based sales-prospect detection for outbound (Sent Items) messages.

Deliberately crude - AI classification is a future upgrade. This just needs to
be right often enough to be a useful filter, not perfect.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import IGNORED_LOCAL_PARTS, NON_SALES_DOMAINS, NOISE_SUBJECT_PREFIXES, OWN_DOMAIN


@dataclass
class DetectionResult:
    is_prospect: bool
    reason: str
    name: str | None = None
    email: str | None = None
    domain: str | None = None


def _domain_of(address: str) -> str:
    return address.rsplit("@", 1)[-1].lower() if "@" in address else ""


def _local_part_of(address: str) -> str:
    return address.split("@", 1)[0].lower() if "@" in address else address.lower()


def classify_message(message: dict) -> DetectionResult:
    """Decide whether a Graph Sent Items message looks like sales outreach."""
    subject = (message.get("subject") or "").strip()
    if subject.startswith(NOISE_SUBJECT_PREFIXES):
        return DetectionResult(False, "calendar response, not outreach")

    to_recipients = message.get("toRecipients") or []
    if len(to_recipients) != 1:
        reason = "no recipients" if not to_recipients else "multiple recipients (not 1:1 outreach)"
        return DetectionResult(False, reason)

    email_address = to_recipients[0].get("emailAddress", {})
    # Lowercased once, here, at the source - email addresses are effectively
    # case-insensitive in practice (every real mail provider treats them that
    # way), but Graph/Outlook doesn't guarantee consistent casing across
    # messages for the same person (e.g. a reply can resolve a display name
    # to a differently-cased address than the original send). Without this,
    # the same real contact can silently become two different Prospect rows.
    address = (email_address.get("address") or "").strip().lower()
    name = (email_address.get("name") or "").strip()
    if not address:
        return DetectionResult(False, "recipient has no email address")

    domain = _domain_of(address)
    if domain == OWN_DOMAIN:
        return DetectionResult(False, "internal recipient")
    if domain in NON_SALES_DOMAINS:
        return DetectionResult(False, f"non-sales domain ({domain})")
    if _local_part_of(address) in IGNORED_LOCAL_PARTS:
        return DetectionResult(False, "automated/distribution address")

    return DetectionResult(True, "external 1:1 recipient", name=name or None, email=address, domain=domain)
