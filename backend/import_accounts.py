"""Milestone 2.5: import your account list from a CSV file.

The CSV must have a header row with a column named "name" (case-insensitive) -
one company name per row. Anything else in the file is ignored.

Run with:
    python import_accounts.py path/to/accounts.csv

Safe to re-run: existing account names are left alone, only new ones are added.
"""

import csv
import datetime
import sys

from app.db import get_session, init_db
from app.models import Account


def _find_name_column(fieldnames: list[str]) -> str:
    for field in fieldnames:
        if field.strip().lower() == "name":
            return field
    raise SystemExit(
        f"ERROR: no 'name' column found. CSV columns were: {fieldnames}\n"
        "Add a header row with a column literally named 'name'."
    )


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python import_accounts.py path/to/accounts.csv")

    csv_path = sys.argv[1]
    init_db()

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise SystemExit("ERROR: CSV appears to have no header row.")
        name_col = _find_name_column(reader.fieldnames)
        rows = [row[name_col].strip() for row in reader if row.get(name_col, "").strip()]

    session = get_session()
    try:
        existing = {a.name for a in session.query(Account).all()}
        added = 0
        for name in rows:
            if name in existing:
                continue
            session.add(Account(name=name, created_at=datetime.datetime.now(datetime.UTC)))
            existing.add(name)
            added += 1
        session.commit()
        total = session.query(Account).count()
    finally:
        session.close()

    print(f"Added {added} new account(s). {total} total in the account list.")


if __name__ == "__main__":
    main()
