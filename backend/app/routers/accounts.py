"""My Accounts: view, search, add, delete, replace, and merge your account
list, plus managing domains you've chosen to always ignore (see targets.py)."""

from __future__ import annotations

import datetime

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from app.accounts_io import extract_account_names
from app.db import get_session
from app.models import Account, IgnoredDomain

router = APIRouter()


class AccountOut(BaseModel):
    id: int
    name: str
    created_at: str


class AddAccountIn(BaseModel):
    name: str


class UploadResult(BaseModel):
    added: int
    total: int


class IgnoredDomainOut(BaseModel):
    id: int
    domain: str
    created_at: str


def _account_key(name: str) -> str:
    return " ".join(name.lower().split())


@router.get("/accounts", response_model=list[AccountOut])
def list_accounts():
    """All accounts, alphabetical. Search/filter happens client-side - the
    list is small enough that a server-side query param isn't needed."""
    session = get_session()
    try:
        accounts = session.query(Account).order_by(Account.name).all()
        return [AccountOut(id=a.id, name=a.name, created_at=a.created_at.isoformat()) for a in accounts]
    finally:
        session.close()


@router.post("/accounts", response_model=AccountOut)
def add_account(body: AddAccountIn):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name cannot be empty")
    session = get_session()
    try:
        existing_names = { _account_key(a.name) for a in session.query(Account).all() }
        if _account_key(name) in existing_names:
            raise HTTPException(status_code=409, detail="Account already exists")
        account = Account(name=name, created_at=datetime.datetime.now(datetime.UTC))
        session.add(account)
        session.commit()
        return AccountOut(id=account.id, name=account.name, created_at=account.created_at.isoformat())
    finally:
        session.close()


@router.delete("/accounts/{account_id}")
def delete_account(account_id: int):
    session = get_session()
    try:
        account = session.get(Account, account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Account not found")
        session.delete(account)
        session.commit()
        return {"deleted": account_id}
    finally:
        session.close()


@router.post("/accounts/merge", response_model=UploadResult)
async def merge_accounts(file: UploadFile):
    """Add any names from the upload not already in the list. Existing
    accounts are left untouched - same dedup semantics as import_accounts.py."""
    content = await file.read()
    try:
        names = extract_account_names(file.filename or "", content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    session = get_session()
    try:
        existing = {_account_key(a.name) for a in session.query(Account).all()}
        added = 0
        for name in names:
            key = _account_key(name)
            if key in existing:
                continue
            session.add(Account(name=name, created_at=datetime.datetime.now(datetime.UTC)))
            existing.add(key)
            added += 1
        session.commit()
        total = session.query(Account).count()
    finally:
        session.close()
    return UploadResult(added=added, total=total)


@router.post("/accounts/replace", response_model=UploadResult)
async def replace_accounts(file: UploadFile):
    """Wipe the entire account list and replace it with the upload."""
    content = await file.read()
    try:
        names = extract_account_names(file.filename or "", content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    session = get_session()
    try:
        session.query(Account).delete()
        added = 0
        seen = set()
        for name in names:
            key = _account_key(name)
            if key in seen:
                continue
            session.add(Account(name=name, created_at=datetime.datetime.now(datetime.UTC)))
            seen.add(key)
            added += 1
        session.commit()
        total = session.query(Account).count()
    finally:
        session.close()
    return UploadResult(added=added, total=total)


@router.get("/ignored-domains", response_model=list[IgnoredDomainOut])
def list_ignored_domains():
    """Domains marked "Always Ignore" from the Targets page - listed here so
    a mistake can be undone without direct database access."""
    session = get_session()
    try:
        rows = session.query(IgnoredDomain).order_by(IgnoredDomain.domain).all()
        return [IgnoredDomainOut(id=r.id, domain=r.domain, created_at=r.created_at.isoformat()) for r in rows]
    finally:
        session.close()


@router.delete("/ignored-domains/{ignored_id}")
def delete_ignored_domain(ignored_id: int):
    session = get_session()
    try:
        row = session.get(IgnoredDomain, ignored_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Not found")
        session.delete(row)
        session.commit()
        return {"deleted": ignored_id}
    finally:
        session.close()
