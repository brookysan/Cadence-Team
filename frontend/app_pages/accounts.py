"""My Accounts: view, search, add, delete, replace, and merge your account list."""

import pandas as pd
import requests
import streamlit as st

from utils.api import (
    add_account,
    delete_account,
    delete_ignored_domain,
    get_accounts,
    get_ignored_domains,
    merge_accounts_file,
    replace_accounts_file,
)

try:
    accounts = get_accounts()
except requests.exceptions.ConnectionError:
    st.error(
        "Can't reach the Cadence Team backend at http://127.0.0.1:8010. "
        "Start it with `uvicorn app.main:app --port 8010` from the backend folder."
    )
    st.stop()

search = st.text_input("Search", placeholder="Filter by name...", label_visibility="collapsed")

if accounts:
    df = pd.DataFrame(accounts)
    if search:
        df = df[df["name"].str.contains(search, case=False, na=False)]
    df["actions"] = [[":material/delete: Delete"]] * len(df)

    def _handle_delete():
        click = st.session_state.account_actions
        if click is None:
            return
        account_id = int(df.iloc[click.row]["id"])
        try:
            delete_account(account_id)
            st.toast("Account deleted", icon=":material/delete:")
            st.rerun()
        except requests.exceptions.RequestException as e:
            st.error(f"Could not delete: {e}")

    st.dataframe(
        df,
        column_config={
            "id": None,
            "name": st.column_config.TextColumn("Account name"),
            "created_at": st.column_config.DatetimeColumn("Added", format="MMM D, YYYY HH:mm"),
            "actions": st.column_config.ButtonColumn("Actions", on_click=_handle_delete, key="account_actions"),
        },
        hide_index=True,
    )
else:
    st.info("No accounts yet - add one below or upload a list.")

st.divider()

st.subheader("Add an account")
with st.form("add_account_form", clear_on_submit=True):
    new_name = st.text_input("Account name", label_visibility="collapsed", placeholder="Company name")
    if st.form_submit_button("Add") and new_name.strip():
        try:
            add_account(new_name.strip())
            st.toast(f"Added {new_name.strip()}", icon=":material/check_circle:")
            st.rerun()
        except requests.exceptions.RequestException as e:
            st.error(f"Could not add: {e}")

st.divider()

st.subheader("Upload a list")
uploaded = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx"])
if uploaded is not None:
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Merge with existing list", width="stretch"):
            try:
                result = merge_accounts_file(uploaded.name, uploaded.getvalue())
                st.success(f"Added {result['added']} new account(s). {result['total']} total.")
                st.rerun()
            except requests.exceptions.RequestException as e:
                st.error(f"Merge failed: {e}")
    with col2:
        confirm_replace = st.checkbox("I understand this replaces the entire list")
        if st.button("Replace entire list", width="stretch", disabled=not confirm_replace, type="primary"):
            try:
                result = replace_accounts_file(uploaded.name, uploaded.getvalue())
                st.success(f"List replaced with {result['total']} account(s).")
                st.rerun()
            except requests.exceptions.RequestException as e:
                st.error(f"Replace failed: {e}")

st.divider()

st.subheader("Ignored domains")
st.caption('Domains you chose "Always Ignore" on from the Targets page - they never surface again.')
try:
    ignored = get_ignored_domains()
except requests.exceptions.RequestException:
    ignored = []

if ignored:
    idf = pd.DataFrame(ignored)
    idf["actions"] = [[":material/delete: Remove"]] * len(idf)

    def _handle_unignore():
        click = st.session_state.ignored_actions
        if click is None:
            return
        ignored_id = int(idf.iloc[click.row]["id"])
        try:
            delete_ignored_domain(ignored_id)
            st.toast("Domain un-ignored", icon=":material/check_circle:")
            st.rerun()
        except requests.exceptions.RequestException as e:
            st.error(f"Could not remove: {e}")

    st.dataframe(
        idf,
        column_config={
            "id": None,
            "domain": st.column_config.TextColumn("Domain"),
            "created_at": st.column_config.DatetimeColumn("Ignored since", format="MMM D, YYYY"),
            "actions": st.column_config.ButtonColumn("Actions", on_click=_handle_unignore, key="ignored_actions"),
        },
        hide_index=True,
    )
else:
    st.caption("None yet.")
