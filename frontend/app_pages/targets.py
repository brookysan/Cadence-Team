"""Targets: sales-looking emails to a domain not on your account list yet."""

import pandas as pd
import requests
import streamlit as st

from utils.api import add_account_and_start_cadence, always_ignore_domain, dismiss_prospect, get_targets, start_cadence_only

try:
    targets = get_targets()
except requests.exceptions.ConnectionError:
    st.error(
        "Can't reach the Cadence Team backend at http://127.0.0.1:8010. "
        "Start it with `uvicorn app.main:app --port 8010` from the backend folder."
    )
    st.stop()

if not targets:
    st.info("No new targets detected yet.")
    st.stop()

df = pd.DataFrame(targets)
df["actions"] = [
    [
        ":material/domain_add: Add to Accounts + Start Cadence",
        ":material/rocket_launch: Start Cadence Only",
        ":material/visibility_off: Ignore",
        ":material/block: Always Ignore Domain",
    ]
] * len(df)


@st.dialog("Always ignore this domain?")
def _confirm_always_ignore(prospect_id: int, domain: str):
    st.write(
        f"This permanently ignores **{domain}** for everyone - it will never surface as a "
        "target again, and every *other* unresolved target on this same domain will be "
        "dismissed right now too. There is currently no page to view or restore dismissed "
        "targets, so this is effectively irreversible."
    )
    col1, col2 = st.columns(2)
    if col1.button("Cancel", width="stretch"):
        st.rerun()
    if col2.button("Yes, always ignore", type="primary", width="stretch"):
        try:
            result = always_ignore_domain(prospect_id)
            st.toast(f"Ignoring '{result['ignored_domain']}' from now on", icon=":material/block:")
        except requests.exceptions.RequestException as e:
            st.error(f"Action failed: {e}")
        st.rerun()


def _handle_action():
    click = st.session_state.target_actions
    if click is None:
        return
    prospect_id = int(df.iloc[click.row]["id"])
    try:
        if "Add to Accounts" in click.label:
            result = add_account_and_start_cadence(prospect_id)
            st.toast(f"Added account '{result['account']}' and started cadence", icon=":material/domain_add:")
        elif "Start Cadence Only" in click.label:
            start_cadence_only(prospect_id)
            st.toast("Cadence started", icon=":material/rocket_launch:")
        elif "Always Ignore" in click.label:
            _confirm_always_ignore(prospect_id, str(df.iloc[click.row]["domain"]))
            return
        else:  # Ignore (this one instance)
            dismiss_prospect(prospect_id)
            st.toast("Ignored", icon=":material/visibility_off:")
        st.rerun()
    except requests.exceptions.RequestException as e:
        st.error(f"Action failed: {e}")


st.dataframe(
    df,
    column_config={
        "id": None,
        "name": st.column_config.TextColumn("Name"),
        "email": st.column_config.TextColumn("Email"),
        "domain": st.column_config.TextColumn("Domain"),
        "first_detected_at": st.column_config.DatetimeColumn("Detected", format="MMM D, YYYY HH:mm"),
        "source_email_link": st.column_config.LinkColumn("Email thread", display_text="Open in Outlook"),
        "actions": st.column_config.ButtonColumn("Actions", on_click=_handle_action, key="target_actions"),
    },
    hide_index=True,
)
