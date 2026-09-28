import streamlit as st

st.set_page_config(page_title="Cadence Team", layout="wide")

page = st.navigation(
    [
        st.Page("app_pages/today.py", title="Today", icon=":material/today:"),
        st.Page("app_pages/prospects.py", title="Prospects", icon=":material/person_add:"),
        st.Page("app_pages/targets.py", title="Targets", icon=":material/travel_explore:"),
        st.Page("app_pages/timeline.py", title="Timeline", icon=":material/timeline:"),
        st.Page("app_pages/contacts.py", title="Contacts", icon=":material/contacts:"),
        st.Page("app_pages/accounts.py", title="My Accounts", icon=":material/apartment:"),
    ],
    position="top",
)
st.title(page.title)
page.run()
