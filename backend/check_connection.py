"""Milestone 1: prove Cadence can read your Sent Items via Microsoft Graph.

Run with:
    python check_connection.py
"""

from app.graph import GraphAuthError, GraphClient


def _recipient_summary(recipients: list[dict]) -> str:
    parts = []
    for r in recipients:
        email_addr = r.get("emailAddress", {})
        name = email_addr.get("name") or ""
        address = email_addr.get("address") or ""
        parts.append(f"{name} <{address}>" if name else address)
    return ", ".join(parts) or "(none)"


def main() -> None:
    client = GraphClient()
    try:
        messages = client.list_sent_items(top=10)
    except GraphAuthError as e:
        print(f"AUTH ERROR: {e}")
        return

    if not messages:
        print("Connected, but Sent Items is empty (or nothing returned).")
        return

    print(f"Connected. Showing {len(messages)} most recent Sent Items:\n")
    for m in messages:
        sent = m.get("sentDateTime", "?")
        subject = m.get("subject") or "(no subject)"
        to = _recipient_summary(m.get("toRecipients", []))
        print(f"- [{sent}] {subject}")
        print(f"    To: {to}")


if __name__ == "__main__":
    main()
