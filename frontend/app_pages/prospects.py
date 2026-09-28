"""Prospects: newly detected external contacts with no cadence started yet."""

import pandas as pd
import requests
import streamlit as st

from utils.api import dismiss_prospect, get_prospects, start_cadence

try:
    prospects = get_prospects()
except requests.exceptions.ConnectionError:
    st.error(
        "Can't reach the Cadence Team backend at http://127.0.0.1:8010. "
        "Start it with `uvicorn app.main:app --port 8010` from the backend folder."
    )
    st.stop()

if not prospects:
    st.info("No new prospects detected yet.")
    st.stop()

df = pd.DataFrame(prospects)
df["actions"] = [[":material/play_arrow: Start cadence", ":material/delete: Delete"]] * len(df)


def _handle_action():
    click = st.session_state.prospect_actions
    if click is None:
        return
    prospect_id = int(df.iloc[click.row]["id"])
    try:
        if "Delete" in click.label:
            dismiss_prospect(prospect_id)
            st.toast("Prospect dismissed", icon=":material/delete:")
        else:
            start_cadence(prospect_id)
            st.toast("Cadence started", icon=":material/rocket_launch:")
        st.rerun()
    except requests.exceptions.RequestException as e:
        st.error(f"Action failed: {e}")


st.dataframe(
    df,
    column_config={
        "id": None,
        "status": None,
        "name": st.column_config.TextColumn("Name"),
        "email": st.column_config.TextColumn("Email"),
        "domain": st.column_config.TextColumn("Domain"),
        "first_detected_at": st.column_config.DatetimeColumn("Detected", format="MMM D, YYYY HH:mm"),
        "source_email_link": st.column_config.LinkColumn("Email thread", display_text="Open in Outlook"),
        "actions": st.column_config.ButtonColumn("Actions", on_click=_handle_action, key="prospect_actions"),
    },
    hide_index=True,
)
