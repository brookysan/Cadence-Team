"""One-time Microsoft Graph sign-in for Cadence Team.

Run this once before first use:
    python setup_auth.py

It's a device-code sign-in: this prints a URL and a short code, you open the
URL on any device and enter the code, and this script waits and saves the
result. No password or token is ever typed into this terminal.

Safe to re-run any time - if you're already signed in, it just confirms that
and does nothing else.
"""

from app.graph import GraphClient, TOKEN_FILE


def main() -> None:
    client = GraphClient()

    if client.get_token():
        me = client.get("/me")
        print(f"Already signed in as {me.get('displayName')} <{me.get('mail') or me.get('userPrincipalName')}>")
        print(f"Token file: {TOKEN_FILE}")
        return

    result = client.start_auth()
    print("=" * 60)
    print("Microsoft Graph sign-in")
    print("=" * 60)
    print(f"\n  1. Open:  {result['url']}")
    print(f"  2. Enter: {result['user_code']}")
    print("\nWaiting for you to finish signing in...\n")

    outcome = client.complete_auth(
        result["device_code"],
        interval=result["interval"],
        timeout=result["expires_in"],
    )
    if outcome["status"] != "ok":
        print(f"Sign-in failed: {outcome['error']}")
        print("Run this script again to retry.")
        return

    me = client.get("/me")
    print(f"Signed in as {me.get('displayName')} <{me.get('mail') or me.get('userPrincipalName')}>")
    print(f"Token saved to: {outcome['token_file']}")


if __name__ == "__main__":
    main()
