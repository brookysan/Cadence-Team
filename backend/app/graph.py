"""Minimal Microsoft Graph read client for Cadence Team.

Self-contained: unlike the personal Cadence app, this fork does not depend on
any Claude Code skill being installed. It signs in on its own via a
device-code flow (see setup_auth.py) and stores its own token, independent of
the personal app's or any Claude skill's credential.

If this ever reports "no usable token", run:
    python setup_auth.py
from this folder (backend/).
"""

from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path
from typing import Any

import requests

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Microsoft Teams desktop public client - pre-consented tenant-wide at AMD, so
# any AMD user can sign in through it with no new app registration or admin
# consent needed. Same client ID the personal Cadence app reuses from the
# slai-email Claude Code skill, but this fork does its own sign-in with it
# rather than depending on that skill having already signed in.
CLIENT_ID = "1fec8e78-bce4-4aaf-ab1b-5451cc387264"
SCOPES = "Files.ReadWrite.All Sites.ReadWrite.All offline_access"

# A directory name distinct from "microsoft-graph" (the personal app's/Claude
# skill's shared credential folder) so this fork's token can never collide
# with or overwrite that one, even when tested on the same machine.
CONFIG_DIR = Path(os.environ.get("CADENCE_TEAM_GRAPH_CONFIG_DIR") or (Path.home() / ".config" / "cadence-team"))
TOKEN_FILE = CONFIG_DIR / "token.json"


class GraphAuthError(RuntimeError):
    """Raised when there is no usable Microsoft Graph token."""


class GraphClient:
    """Read-only Microsoft Graph client with its own device-code sign-in."""

    def __init__(self) -> None:
        self._access_token = ""
        self._refresh_token = ""
        self._client_id = CLIENT_ID
        self._tenant_id = ""
        self._expires_at = 0.0
        self._load_token()

    def _load_token(self) -> None:
        if not TOKEN_FILE.exists():
            return
        try:
            data = json.loads(TOKEN_FILE.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return
        self._refresh_token = data.get("refresh_token") or ""
        self._client_id = data.get("client_id") or CLIENT_ID
        self._tenant_id = data.get("tenant_id") or ""
        self._access_token = data.get("access_token") or ""
        try:
            self._expires_at = float(data.get("expires_at") or 0.0)
        except (TypeError, ValueError):
            self._expires_at = 0.0

    def _save_token(self) -> None:
        payload = json.dumps(
            {
                "refresh_token": self._refresh_token,
                "client_id": self._client_id,
                "tenant_id": self._tenant_id,
                "access_token": self._access_token,
                "expires_at": self._expires_at,
            },
            indent=2,
        )
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = TOKEN_FILE.with_name(TOKEN_FILE.name + ".tmp")
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, TOKEN_FILE)

    def _refresh(self) -> str:
        if not self._refresh_token or not self._tenant_id:
            return ""
        url = f"https://login.microsoftonline.com/{self._tenant_id}/oauth2/v2.0/token"
        resp = requests.post(
            url,
            data={
                "client_id": self._client_id,
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
                "scope": SCOPES,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            return ""
        data = resp.json()
        self._access_token = data["access_token"]
        self._expires_at = time.time() + data.get("expires_in", 3600) - 60
        if "refresh_token" in data:
            self._refresh_token = data["refresh_token"]
        self._save_token()
        return self._access_token

    def get_token(self) -> str:
        if self._access_token and time.time() < self._expires_at:
            return self._access_token
        return self._refresh()

    def require_token(self) -> str:
        token = self.get_token()
        if not token:
            raise GraphAuthError(
                f"No usable Microsoft Graph token at {TOKEN_FILE}. "
                "Run: python setup_auth.py (from the backend folder)"
            )
        return token

    # ---- Device-code sign-in --------------------------------------------

    def start_auth(self, tenant_id: str = "organizations", scope: str = SCOPES) -> dict[str, Any]:
        """Begin a device-code sign-in. Returns the code/URL to show the user."""
        resp = requests.post(
            f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/devicecode",
            data={"client_id": CLIENT_ID, "scope": scope},
            timeout=30,
        )
        resp.raise_for_status()
        d = resp.json()
        self._client_id = CLIENT_ID
        self._tenant_id = tenant_id
        return {
            "message": d["message"],
            "user_code": d["user_code"],
            "url": d["verification_uri"],
            "device_code": d["device_code"],
            "expires_in": d.get("expires_in", 900),
            "interval": d.get("interval", 5),
        }

    def complete_auth(
        self,
        device_code: str,
        interval: float = 5.0,
        timeout: float = 600.0,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        """Poll until the user finishes signing in, or `timeout` seconds pass."""
        tid = tenant_id or self._tenant_id or "organizations"
        url = f"https://login.microsoftonline.com/{tid}/oauth2/v2.0/token"
        deadline = time.time() + timeout
        while True:
            resp = requests.post(
                url,
                data={
                    "client_id": self._client_id,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": device_code,
                },
                timeout=30,
            )
            if resp.status_code == 200:
                d = resp.json()
                self._access_token = d["access_token"]
                self._refresh_token = d.get("refresh_token", "")
                self._expires_at = time.time() + d.get("expires_in", 3600) - 60
                try:
                    payload = d["access_token"].split(".")[1]
                    payload += "=" * (-len(payload) % 4)
                    claims = json.loads(base64.urlsafe_b64decode(payload))
                    self._tenant_id = claims.get("tid", tid)
                except Exception:
                    pass
                self._save_token()
                return {"status": "ok", "token_file": str(TOKEN_FILE)}

            body = resp.json()
            err = body.get("error", "")
            if err in ("authorization_pending", "slow_down"):
                if err == "slow_down":
                    interval += 5
                if time.time() + interval >= deadline:
                    break
                time.sleep(interval)
                continue
            return {"status": "error", "error": f"{err}: {body.get('error_description', '')[:300]}"}
        return {"status": "error", "error": "Timed out waiting for sign-in."}

    # ---- Reads ------------------------------------------------------------

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        resp = requests.get(
            f"{GRAPH_BASE}{path}",
            headers={"Authorization": f"Bearer {self.require_token()}"},
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def _get_absolute(self, url: str) -> Any:
        """GET a full URL as-is - used for @odata.nextLink pages, which
        already include their own query string."""
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {self.require_token()}"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def list_sent_items(self, top: int = 10) -> list[dict]:
        """The most recent messages from Sent Items, newest first.

        Used only for the one-time initial backfill and manual inspection
        scripts. The poll loop uses list_sent_items_since() instead, since a
        fixed "most recent N" can't guarantee nothing scrolls out of view
        between polls.
        """
        data = self.get(
            "/me/mailFolders/SentItems/messages",
            params={
                "$top": top,
                "$orderby": "sentDateTime desc",
                "$select": "id,subject,sentDateTime,toRecipients,ccRecipients,from,webLink,conversationId",
            },
        )
        return data.get("value", [])

    def list_sent_items_since(self, since: str | None, top: int = 100, max_pages: int = 20) -> list[dict]:
        """Every Sent Items message strictly after `since` (a Graph
        sentDateTime string, e.g. "2026-08-24T10:16:01Z"), oldest first.

        Paginated via @odata.nextLink, so no message is missed even if more
        than `top` were sent since the last sync - unlike list_sent_items(),
        this can't let a genuine new prospect scroll out of a fixed window.
        `since=None` returns the whole mailbox history, which callers should
        avoid except deliberately.
        """
        params = {
            "$orderby": "sentDateTime asc",
            "$select": "id,subject,sentDateTime,toRecipients,ccRecipients,from,webLink,conversationId",
            "$top": top,
        }
        if since:
            params["$filter"] = f"sentDateTime gt {since}"
        data = self.get("/me/mailFolders/SentItems/messages", params=params)
        messages = list(data.get("value", []))
        next_link = data.get("@odata.nextLink")
        pages = 1
        while next_link and pages < max_pages:
            data = self._get_absolute(next_link)
            messages.extend(data.get("value", []))
            next_link = data.get("@odata.nextLink")
            pages += 1
        return messages

    def list_conversation_messages(self, conversation_id: str, top: int = 50, max_pages: int = 10) -> list[dict]:
        """Every message (sent or received, any folder) in a conversation.

        Used to check whether a prospect has replied: their conversationId is
        the same as the original outbound message's, so any message in this
        list with a `from` address other than the account owner's is a reply.

        Paginated via @odata.nextLink - a single unpaginated page could
        silently omit the newest reply in a long-running thread.
        """
        # OData string literals escape a single quote by doubling it - guard
        # against a conversationId that happens to contain one.
        escaped = conversation_id.replace("'", "''")
        data = self.get(
            "/me/messages",
            params={
                "$filter": f"conversationId eq '{escaped}'",
                "$select": "from,receivedDateTime,subject,body",
                "$top": top,
            },
        )
        messages = list(data.get("value", []))
        next_link = data.get("@odata.nextLink")
        pages = 1
        while next_link and pages < max_pages:
            data = self._get_absolute(next_link)
            messages.extend(data.get("value", []))
            next_link = data.get("@odata.nextLink")
            pages += 1
        return messages
