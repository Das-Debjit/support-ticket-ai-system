"""Minimal Streamlit UI for the Support Ticket AI System."""

import os

import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Support Ticket AI System", page_icon="🎫", layout="wide")
st.title("Support Ticket AI System")
st.caption(f"Backend API: {API_URL}")

try:
    health = requests.get(f"{API_URL}/health", timeout=5).json()
    st.success(f"API status: {health['status']} - database: {health['database']}")
except Exception:
    st.error(f"Could not reach the backend API at {API_URL}. Start it with: uvicorn app.api:app")
    st.stop()

with st.expander("Dataset overview", expanded=True):
    stats = requests.get(f"{API_URL}/stats", timeout=5).json()
    col1, col2, col3 = st.columns(3)
    col1.metric("Total tickets", stats["total_tickets"])
    col2.metric("Open", stats["by_status"].get("Open", 0))
    col3.metric("Escalated", stats["by_status"].get("Escalated", 0))

    c1, c2 = st.columns(2)
    with c1:
        st.write("By priority")
        st.bar_chart(stats["by_priority"])
    with c2:
        st.write("By category")
        st.bar_chart(stats["by_category"])

st.divider()

st.subheader("Ask a question about the tickets")

example_questions = [
    "How many tickets are currently open?",
    "Which agent resolved the most tickets?",
    "Show me all Critical tickets that are not resolved.",
    "What is the average customer rating for Technical category tickets?",
]

chosen_example = st.selectbox(
    "Try an example question, or type your own below:",
    ["-- type my own --"] + example_questions,
)

default_text = "" if chosen_example == "-- type my own --" else chosen_example
question = st.text_input("Your question:", value=default_text)

if st.button("Ask", type="primary") and question.strip():
    with st.spinner("Thinking..."):
        try:
            response = requests.post(f"{API_URL}/query", json={"question": question}, timeout=30)
            if response.status_code == 200:
                data = response.json()
                st.markdown(f"**Answer:** {data['answer']}")
                with st.expander("Show generated SQL and result count"):
                    st.code(data["sql"], language="sql")
                    st.write(f"Rows returned: {data['row_count']}")
            else:
                st.error(f"Error: {response.json().get('detail', response.text)}")
        except requests.exceptions.RequestException as exc:
            st.error(f"Could not reach the API: {exc}")

st.divider()

st.subheader("Anomaly detection")

if st.button("Run anomaly detection"):
    with st.spinner("Scanning for anomalies..."):
        try:
            result = requests.get(f"{API_URL}/anomalies", timeout=15).json()
            st.write(f"Reference time used as 'now': {result['reference_timestamp']} (dataset's most recent ticket timestamp)")

            col1, col2 = st.columns(2)
            with col1:
                res_outliers = result["resolution_time_outliers"]
                st.metric("Resolution time outliers", res_outliers["count"])
                st.caption(res_outliers["rule"])
                if res_outliers["tickets"]:
                    st.dataframe(res_outliers["tickets"], use_container_width=True)

            with col2:
                aging = result["aging_unresolved_high_priority"]
                st.metric("Aging unresolved (High/Critical)", aging["count"])
                st.caption(aging["rule"])
                if aging["tickets"]:
                    st.dataframe(aging["tickets"], use_container_width=True)

        except requests.exceptions.RequestException as exc:
            st.error(f"Could not reach the API: {exc}")