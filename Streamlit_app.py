import streamlit as st

app_page = st.Page(page="app.py", title="Home")
compliance_page = st.Page(page="pages/compliance.py", title="Compliance")

pg = st.navigation(
    pages=[app_page, compliance_page]
)

pg.run()
