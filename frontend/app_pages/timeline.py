"""Timeline: which prospects are at what stage in their cadence."""

import datetime

import pandas as pd
import requests
import streamlit as st

from utils.api import delete_cadence, get_cadences, mark_replied, pause_cadence, resume_cadence, restart_cadence

try:
    cadences = get_cadences()
except requests.exceptions.ConnectionError:
    st.error(
        "Can't reach the Cadence Team backend at http://127.0.0.1:8010. "
        "Start it with `uvicorn app.main:app --port 8010` from the backend folder."
    )
    st.stop()

if not cadences:
    st.info("No cadences started yet. Start one from the Prospects page.")
    st.stop()


def _format_due(due_date: str) -> str:
    return datetime.date.fromisoformat(due_date).strftime("%b %d")


def _format_replied_at(value: str | None) -> str:
    """value is Graph's raw receivedDateTime string - older paused cadences
    predate this field being tracked, so it may be missing."""
    if not value:
        return "Unknown"
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%b %d, %Y %H:%M")
    except ValueError:
        return "Unknown"


def _stage_cell(task: dict) -> str:
    if task["status"] == "done":
        return "Done"
    if task["is_overdue"]:
        return f"Overdue (was due {_format_due(task['due_date'])})"
    return f"Due {_format_due(task['due_date'])}"


def _current_stage(tasks: list[dict]) -> str:
    for task in tasks:
        if task["status"] == "pending":
            return task["label"]
    return "Completed"


def _ooo_column(cadence: dict) -> str:
    if cadence["status"] != "out_of_office":
        return ""
    if cadence["ooo_return_date"]:
        return f"Back {datetime.date.fromisoformat(cadence['ooo_return_date']).strftime('%b %d')}"
    return "Out of office (return date unknown)"


replied = [c for c in cadences if c["status"] == "paused"]
completed = [c for c in cadences if c["status"] == "completed"]
manual_paused = [c for c in cadences if c["status"] == "manual_pause"]
in_progress = [c for c in cadences if c["status"] in ("active", "out_of_office")]

# Column order for the per-stage columns, taken from the first in-progress
# cadence's task list - guarded since in_progress can now be empty while
# other sections aren't. Every cadence today comes from the same fixed
# default sequence (app/cadence_rules.py), so they all share the same stage
# columns in the same order - this will need revisiting if per-prospect
# custom sequences are ever added.
stage_columns = [f"{t['label']} (Day {t['day_offset']})" for t in in_progress[0]["tasks"]] if in_progress else []


def _build_rows(cadence_list: list[dict]) -> pd.DataFrame:
    rows = []
    for cadence in cadence_list:
        row = {
            "Prospect": cadence["prospect_name"] or cadence["prospect_email"],
            "cadence_id": cadence["cadence_id"],
            "Email": cadence["prospect_email"],
            "Domain": cadence["prospect_domain"],
            "Started": cadence["started_at"],
            "Current stage": _current_stage(cadence["tasks"]),
            "Cadence status": cadence["status"],
            "Out of office until": _ooo_column(cadence),
        }
        for col, task in zip(stage_columns, cadence["tasks"]):
            row[col] = _stage_cell(task)
        rows.append(row)
    return pd.DataFrame(rows)


def _build_simple_rows(cadence_list: list[dict], extra_cols: dict | None = None) -> pd.DataFrame:
    """A lighter row shape for sections that don't need the full per-stage
    columns (Replied, Expired, Paused)."""
    rows = []
    for cadence in cadence_list:
        row = {
            "Prospect": cadence["prospect_name"] or cadence["prospect_email"],
            "cadence_id": cadence["cadence_id"],
            "Email": cadence["prospect_email"],
            "Domain": cadence["prospect_domain"],
        }
        if extra_cols:
            for label, fn in extra_cols.items():
                row[label] = fn(cadence)
        rows.append(row)
    return pd.DataFrame(rows)


column_config = {
    "cadence_id": None,
    "Started": st.column_config.DateColumn("Started"),
}


@st.dialog("Permanently delete this cadence?")
def _confirm_delete(cadence_id: int, label: str):
    st.write(
        f"This permanently deletes **{label}**'s cadence and prospect record. "
        "If they email again later, they will resurface as a brand-new prospect "
        "instead of being recognized. This cannot be undone."
    )
    col1, col2 = st.columns(2)
    if col1.button("Cancel", width="stretch"):
        st.rerun()
    if col2.button("Yes, delete permanently", type="primary", width="stretch"):
        try:
            delete_cadence(cadence_id)
            st.toast("Cadence deleted", icon=":material/delete:")
        except requests.exceptions.RequestException as e:
            st.error(f"Could not delete: {e}")
        st.rerun()


# ---- Replied ----------------------------------------------------------------

if replied:
    st.subheader("Replied")
    replied_df = _build_simple_rows(replied, {"Replied at": lambda c: _format_replied_at(c["last_reply_at"])})
    st.dataframe(replied_df, column_config={"cadence_id": None}, hide_index=True)
    st.divider()


# ---- In progress (+ nested Expired / Paused) ---------------------------------

st.subheader("In progress")


def _handle_in_progress_action():
    click = st.session_state.timeline_progress_actions
    if click is None:
        return
    cadence_id = int(progress_df.iloc[click.row]["cadence_id"])
    try:
        if "Resume" in click.label:
            resume_cadence(cadence_id)
            st.toast("Cadence resumed", icon=":material/play_arrow:")
        elif "Mark as replied" in click.label:
            mark_replied(cadence_id)
            st.toast("Marked as replied", icon=":material/check_circle:")
        else:  # Pause
            pause_cadence(cadence_id)
            st.toast("Cadence paused", icon=":material/pause:")
        st.rerun()
    except requests.exceptions.RequestException as e:
        st.error(f"Action failed: {e}")


if in_progress:
    progress_df = _build_rows(in_progress)
    progress_df["Actions"] = [
        [":material/play_arrow: Resume cadence", ":material/pause: Pause", ":material/check_circle: Mark as replied"]
        if status == "out_of_office"
        else [":material/pause: Pause", ":material/check_circle: Mark as replied"]
        for status in progress_df["Cadence status"]
    ]
    st.dataframe(
        progress_df,
        column_config={
            **column_config,
            "Actions": st.column_config.ButtonColumn(
                "Actions", on_click=_handle_in_progress_action, key="timeline_progress_actions"
            ),
        },
        hide_index=True,
    )
else:
    st.caption("Nothing in progress.")


def _handle_expired_action():
    click = st.session_state.timeline_expired_actions
    if click is None:
        return
    cadence_id = int(expired_df.iloc[click.row]["cadence_id"])
    try:
        if "Mark as replied" in click.label:
            mark_replied(cadence_id)
            st.toast("Marked as replied", icon=":material/check_circle:")
        else:
            restart_cadence(cadence_id)
            st.toast("Cadence restarted", icon=":material/restart_alt:")
        st.rerun()
    except requests.exceptions.RequestException as e:
        st.error(f"Action failed: {e}")


if completed:
    st.markdown("**Expired**")
    expired_df = _build_simple_rows(completed)
    expired_df["Actions"] = [
        [":material/restart_alt: Restart cadence", ":material/check_circle: Mark as replied"]
    ] * len(expired_df)
    st.dataframe(
        expired_df,
        column_config={
            "cadence_id": None,
            "Actions": st.column_config.ButtonColumn(
                "Actions", on_click=_handle_expired_action, key="timeline_expired_actions"
            ),
        },
        hide_index=True,
    )


def _handle_paused_action():
    click = st.session_state.timeline_paused_actions
    if click is None:
        return
    row = paused_df.iloc[click.row]
    cadence_id = int(row["cadence_id"])
    if "Delete" in click.label:
        _confirm_delete(cadence_id, str(row["Prospect"]))
        return
    try:
        if "Mark as replied" in click.label:
            mark_replied(cadence_id)
            st.toast("Marked as replied", icon=":material/check_circle:")
        else:  # Restart
            restart_cadence(cadence_id)
            st.toast("Cadence restarted", icon=":material/restart_alt:")
        st.rerun()
    except requests.exceptions.RequestException as e:
        st.error(f"Action failed: {e}")


if manual_paused:
    st.markdown("**Paused**")
    paused_df = _build_simple_rows(manual_paused)
    paused_df["Actions"] = [
        [
            ":material/restart_alt: Restart",
            ":material/check_circle: Mark as replied",
            ":material/delete_forever: Permanently delete",
        ]
    ] * len(paused_df)
    st.dataframe(
        paused_df,
        column_config={
            "cadence_id": None,
            "Actions": st.column_config.ButtonColumn(
                "Actions", on_click=_handle_paused_action, key="timeline_paused_actions"
            ),
        },
        hide_index=True,
    )
