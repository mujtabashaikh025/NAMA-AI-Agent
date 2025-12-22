import streamlit as st
app_page = st.Page(page="app.py")
compliance_page = st.Page(page="pages/compliance.py")
pg=st.navigation(pages=[compliance_page])
#pg=st.navigation(pages=[app_page])
pg.run()
