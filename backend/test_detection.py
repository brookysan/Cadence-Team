"""Milestone 2: run real Sent Items through the rule-based detector, then
filter the result against your uploaded account list (see import_accounts.py).

Run with:
    python test_detection.py
"""

from app.db import get_session, init_db
from app.detection import classify_message
from app.graph import GraphAuthError, GraphClient
from app.matching import find_matching_account
from app.models import Account


def main() -> None:
    init_db()
    session = get_session()
    accounts = session.query(Account).all()
    session.close()
    if not accounts:
        print("NOTE: no accounts imported yet - everything will show as 'no matching account'.")
        print("Run: python import_accounts.py path/to/accounts.csv\n")

    client = GraphClient()
    try:
        messages = client.list_sent_items(top=20)
    except GraphAuthError as e:
        print(f"AUTH ERROR: {e}")
        return

    for m in messages:
        subject = m.get("subject") or "(no subject)"
        result = classify_message(m)
        if not result.is_prospect:
            print(f"[skip    ] {subject!r:50.50} - {result.reason}")
            continue

        account = find_matching_account(result.domain, accounts)
        if account is None:
            print(f"[skip    ] {subject!r:50.50} - no matching account ({result.domain})")
            continue

        print(f"[PROSPECT] {subject!r:50.50} - matches account '{account.name}'")
        print(f"             -> {result.name} <{result.email}> @ {result.domain}")


if __name__ == "__main__":
    main()
