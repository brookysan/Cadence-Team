"""Contacts: every engaged contact, grouped by account, split into replied
and not replied. Read-only - no actions here, see Timeline/Prospects/Targets
for cadence actions."""

import pandas as pd
import requests
import streamlit as st

from utils.api import get_contacts

try:
    groups = get_contacts()
except requests.exceptions.ConnectionError:
    st.error(
        "Can't reach the Cadence Team backend at http://127.0.0.1:8010. "
        "Start it with `uvicorn app.main:app --port 8010` from the backend folder."
    )
    st.stop()

if not groups:
    st.info("No contacts yet - start a cadence from the Prospects or Targets page.")
    st.stop()

for group in groups:
    st.subheader(group["account_name"])
    col1, col2 = st.columns(2)

    with col1:
        st.caption(f"Replied ({len(group['replied'])})")
        if group["replied"]:
            df = pd.DataFrame(group["replied"])[["name", "email"]].rename(columns={"name": "Name", "email": "Email"})
            st.dataframe(df, hide_index=True, width="stretch")
        else:
            st.caption("None yet.")

    with col2:
        st.caption(f"Not replied ({len(group['not_replied'])})")
        if group["not_replied"]:
            df = pd.DataFrame(group["not_replied"])[["name", "email"]].rename(
                columns={"name": "Name", "email": "Email"}
            )
            st.dataframe(df, hide_index=True, width="stretch")
        else:
            st.caption("None yet.")

    st.divider()
