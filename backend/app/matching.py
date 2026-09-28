"""Match a recipient's email domain against the uploaded account list.

The account list is company names only (no domains), so this is necessarily
approximate: "Hewlett Packard Enterprise" has to be connected to "hpe.com"
without ever being told the two are related. We try a few cheap heuristics
rather than one fuzzy-string-ratio, because acronym-vs-full-name (HPE) and
first-word (Dell Technologies -> dell.com) fail differently and one
similarity score doesn't catch both.
"""

from __future__ import annotations

import re

import tldextract

from app.models import Account

# suffix_list_urls=() skips the live fetch from publicsuffix.org entirely and
# uses the snapshot bundled with the package. AMD's network blocks that fetch
# anyway (TLS inspection breaks the cert chain), so trying it first just adds
# a slow, noisy failure before falling back to the same snapshot.
_extract = tldextract.TLDExtract(suffix_list_urls=())


def _squash(text: str) -> str:
    """Lowercase, alphanumeric only - "Dell Technologies" -> "delltechnologies"."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _words(name: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9]+", name)


def _account_candidates(name: str) -> set[str]:
    """Short tokens derived from an account name that a domain root might equal."""
    words = _words(name)
    if not words:
        return set()
    candidates = {_squash(name), _squash(words[0])}
    acronym = "".join(w[0] for w in words).lower()
    if acronym:
        candidates.add(acronym)
    return {c for c in candidates if c}


def domain_root(domain: str) -> str:
    """The registrable part of a domain, e.g. "mail.dell.com" -> "dell",
    "inchcape.co.uk" -> "inchcape".

    Uses tldextract (backed by the public suffix list) rather than a "last
    two labels" guess - a plain split breaks on compound TLDs like .co.uk,
    .com.au, .org.uk, where the naive "second-to-last label" is "co"/"com"/
    "org", not the company name.
    """
    return _extract(domain.lower()).domain


def matches_account(domain: str, account_name: str) -> bool:
    root = domain_root(domain)
    if not root:
        return False
    candidates = _account_candidates(account_name)
    if root in candidates:
        return True
    squashed_name = _squash(account_name)
    # Substring containment as a fallback, guarded by a minimum length so short
    # roots like "hp" don't match almost anything.
    if len(root) >= 3 and (root in squashed_name or squashed_name in root):
        return True
    return False


def find_matching_account(domain: str, accounts: list[Account]) -> Account | None:
    for account in accounts:
        if matches_account(domain, account.name):
            return account
    return None
