"""Loads the support ticket CSV into a SQLite database."""

import sqlite3
from pathlib import Path

import pandas as pd

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "support_tickets.csv"
TABLE_NAME = "tickets"

connection = None


def get_connection():
    global connection
    if connection is None:
        connection = build_database()
    return connection


def build_database():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found at {DATA_PATH}")

    df = pd.read_csv(DATA_PATH)
    df["created_at"] = pd.to_datetime(df["created_at"])

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    df.to_sql(TABLE_NAME, conn, index=False, if_exists="replace")
    return conn


def get_schema_description():
    return """
Table name: tickets

Columns:
- ticket_id (TEXT): unique ticket identifier, e.g. 'TKT-001'
- created_at (DATETIME): when the ticket was created
- category (TEXT): one of 'Billing', 'Technical', 'General'
- priority (TEXT): one of 'Low', 'Medium', 'High', 'Critical'
- status (TEXT): one of 'Open', 'Resolved', 'Escalated'
- response_time_hrs (REAL): hours from creation to first agent response
- resolution_time_hrs (REAL): hours from creation to resolution, NULL if unresolved
- agent_id (TEXT): support agent assigned, e.g. 'AGT-04'
- customer_rating (REAL): 1-5 satisfaction rating, NULL if unresolved
- issue_summary (TEXT): free-text description of the issue

Notes:
- Unresolved tickets means status is 'Open' or 'Escalated'.
- Treat the dataset's most recent created_at as "now" since this is historical data.
"""


def get_latest_timestamp():
    conn = get_connection()
    cur = conn.execute(f"SELECT MAX(created_at) FROM {TABLE_NAME}")
    return cur.fetchone()[0]