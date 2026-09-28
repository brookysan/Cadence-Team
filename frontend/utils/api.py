"""Thin client for the Cadence FastAPI backend.

Runs server-side inside the Streamlit process (not in the browser), so there's
no CORS to configure - this is just a normal Python HTTP call to localhost.
"""

import requests

API_BASE = "http://127.0.0.1:8010"


def get_today() -> list[dict]:
    resp = requests.get(f"{API_BASE}/today", timeout=10)
    resp.raise_for_status()
    return resp.json()


def complete_task(task_id: int) -> dict:
    resp = requests.post(f"{API_BASE}/tasks/{task_id}/complete", timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_prospects() -> list[dict]:
    resp = requests.get(f"{API_BASE}/prospects", timeout=10)
    resp.raise_for_status()
    return resp.json()


def start_cadence(prospect_id: int) -> dict:
    resp = requests.post(f"{API_BASE}/prospects/{prospect_id}/start-cadence", timeout=10)
    resp.raise_for_status()
    return resp.json()


def dismiss_prospect(prospect_id: int) -> dict:
    resp = requests.post(f"{API_BASE}/prospects/{prospect_id}/dismiss", timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_cadences() -> list[dict]:
    resp = requests.get(f"{API_BASE}/cadences", timeout=10)
    resp.raise_for_status()
    return resp.json()


def resume_cadence(cadence_id: int) -> dict:
    resp = requests.post(f"{API_BASE}/cadences/{cadence_id}/resume", timeout=10)
    resp.raise_for_status()
    return resp.json()


def pause_cadence(cadence_id: int) -> dict:
    resp = requests.post(f"{API_BASE}/cadences/{cadence_id}/pause", timeout=10)
    resp.raise_for_status()
    return resp.json()


def restart_cadence(cadence_id: int) -> dict:
    resp = requests.post(f"{API_BASE}/cadences/{cadence_id}/restart", timeout=10)
    resp.raise_for_status()
    return resp.json()


def mark_replied(cadence_id: int) -> dict:
    resp = requests.post(f"{API_BASE}/cadences/{cadence_id}/mark-replied", timeout=10)
    resp.raise_for_status()
    return resp.json()


def delete_cadence(cadence_id: int) -> dict:
    resp = requests.delete(f"{API_BASE}/cadences/{cadence_id}", timeout=10)
    resp.raise_for_status()
    return resp.json()


# ---- Contacts ---------------------------------------------------------------


def get_contacts() -> list[dict]:
    resp = requests.get(f"{API_BASE}/contacts", timeout=10)
    resp.raise_for_status()
    return resp.json()


# ---- My Accounts -----------------------------------------------------------


def get_accounts() -> list[dict]:
    resp = requests.get(f"{API_BASE}/accounts", timeout=10)
    resp.raise_for_status()
    return resp.json()


def add_account(name: str) -> dict:
    resp = requests.post(f"{API_BASE}/accounts", json={"name": name}, timeout=10)
    resp.raise_for_status()
    return resp.json()


def delete_account(account_id: int) -> dict:
    resp = requests.delete(f"{API_BASE}/accounts/{account_id}", timeout=10)
    resp.raise_for_status()
    return resp.json()


def merge_accounts_file(filename: str, content: bytes) -> dict:
    resp = requests.post(f"{API_BASE}/accounts/merge", files={"file": (filename, content)}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def replace_accounts_file(filename: str, content: bytes) -> dict:
    resp = requests.post(f"{API_BASE}/accounts/replace", files={"file": (filename, content)}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_ignored_domains() -> list[dict]:
    resp = requests.get(f"{API_BASE}/ignored-domains", timeout=10)
    resp.raise_for_status()
    return resp.json()


def delete_ignored_domain(ignored_id: int) -> dict:
    resp = requests.delete(f"{API_BASE}/ignored-domains/{ignored_id}", timeout=10)
    resp.raise_for_status()
    return resp.json()


# ---- Target Detection -------------------------------------------------------


def get_targets() -> list[dict]:
    resp = requests.get(f"{API_BASE}/targets", timeout=10)
    resp.raise_for_status()
    return resp.json()


def add_account_and_start_cadence(prospect_id: int) -> dict:
    resp = requests.post(f"{API_BASE}/targets/{prospect_id}/add-account-and-start-cadence", timeout=10)
    resp.raise_for_status()
    return resp.json()


def start_cadence_only(prospect_id: int) -> dict:
    resp = requests.post(f"{API_BASE}/targets/{prospect_id}/start-cadence-only", timeout=10)
    resp.raise_for_status()
    return resp.json()


def always_ignore_domain(prospect_id: int) -> dict:
    resp = requests.post(f"{API_BASE}/targets/{prospect_id}/always-ignore-domain", timeout=10)
    resp.raise_for_status()
    return resp.json()
