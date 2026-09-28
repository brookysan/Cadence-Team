"""Parse an uploaded account-list file (CSV or Excel) into a list of names.

Shared by the /accounts/replace and /accounts/merge endpoints, and follows
the same "column literally named 'name'" convention as import_accounts.py.
"""

from __future__ import annotations

import csv
import io

import pandas as pd


def _find_name_column(columns) -> str:
    for col in columns:
        if str(col).strip().lower() == "name":
            return col
    raise ValueError(f"No 'name' column found. Columns were: {list(columns)}")


def extract_account_names(filename: str, content: bytes) -> list[str]:
    """Read a CSV or XLSX file's "name" column into a list of non-empty names."""
    lower = filename.lower()
    if lower.endswith(".xlsx") or lower.endswith(".xls"):
        df = pd.read_excel(io.BytesIO(content))
        name_col = _find_name_column(df.columns)
        return [str(v).strip() for v in df[name_col].dropna() if str(v).strip()]

    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV appears to have no header row.")
    name_col = _find_name_column(reader.fieldnames)
    return [row[name_col].strip() for row in reader if row.get(name_col, "").strip()]
