"""Today dashboard: tasks currently due (due today or overdue)."""

import pandas as pd
import requests
import streamlit as st

from utils.api import complete_task, get_today

try:
    tasks = get_today()
except requests.exceptions.ConnectionError:
    st.error(
        "Can't reach the Cadence Team backend at http://127.0.0.1:8010. "
        "Start it with `uvicorn app.main:app --port 8010` from the backend folder."
    )
    st.stop()

if not tasks:
    st.success("Nothing due today.")
    st.stop()

df = pd.DataFrame(tasks)
df["actions"] = [[":material/check: Mark complete"]] * len(df)


def _handle_complete():
    click = st.session_state.today_actions
    if click is None:
        return
    task_id = int(df.iloc[click.row]["id"])
    try:
        complete_task(task_id)
        st.toast("Marked complete", icon=":material/check_circle:")
        st.rerun()
    except requests.exceptions.RequestException as e:
        st.error(f"Could not mark complete: {e}")


st.dataframe(
    df,
    column_config={
        "id": None,
        "prospect_id": None,
        "prospect_domain": None,
        "label": st.column_config.TextColumn("Task"),
        "prospect_name": st.column_config.TextColumn("Prospect"),
        "prospect_email": st.column_config.TextColumn("Email"),
        "due_date": st.column_config.DateColumn("Due"),
        "is_overdue": st.column_config.CheckboxColumn("Overdue"),
        "actions": st.column_config.ButtonColumn("Actions", on_click=_handle_complete, key="today_actions"),
    },
    hide_index=True,
)
