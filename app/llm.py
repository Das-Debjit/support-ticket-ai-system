"""Handles natural language questions about the tickets using Groq's LLM."""

import os
import re

from groq import Groq

from app.db import get_connection, get_schema_description

MODEL_NAME = "openai/gpt-oss-20b"

# blocks the LLM from generating anything that could modify the database
FORBIDDEN_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|ATTACH|PRAGMA)\b",
    re.IGNORECASE,
)


class LLMError(Exception):
    pass


def get_client():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key or api_key == "your_groq_api_key_here":
        raise LLMError("GROQ_API_KEY is not set. Add it to your .env file.")
    return Groq(api_key=api_key)


def extract_sql(raw_text):
    fenced = re.search(r"```(?:sql)?\s*(.*?)```", raw_text, re.DOTALL | re.IGNORECASE)
    sql = fenced.group(1).strip() if fenced else raw_text.strip()
    sql = sql.split(";")[0].strip() + ";"
    return sql


def validate_sql(sql):
    if not sql.strip().upper().startswith("SELECT"):
        raise LLMError(f"Refusing to run a non-SELECT query: {sql}")
    if FORBIDDEN_KEYWORDS.search(sql):
        raise LLMError(f"Refusing to run a query with a forbidden keyword: {sql}")


def question_to_sql(question):
    client = get_client()

    system_prompt = f"""You are a SQL generator for a SQLite database of customer support tickets.

{get_schema_description()}

Rules:
- Output ONLY a single valid SQLite SELECT query. No explanation, no markdown, no commentary.
- Never use INSERT, UPDATE, DELETE, DROP, or any statement that modifies data.
- If the question involves "this week" or "recent", treat the MAX(created_at) in the table as the current time, since this is a static historical dataset.
- If the question cannot be answered from this schema, output: SELECT 'UNANSWERABLE' AS result;
"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        temperature=0,
        max_tokens=300,
    )

    raw = response.choices[0].message.content
    sql = extract_sql(raw)
    validate_sql(sql)
    return sql


def run_sql(sql):
    conn = get_connection()
    cursor = conn.execute(sql)
    columns = [description[0] for description in cursor.description]
    rows = cursor.fetchall()
    return [dict(zip(columns, row)) for row in rows]


def results_to_answer(question, sql, rows):
    client = get_client()

    preview_rows = rows[:20]

    system_prompt = """You answer questions about support ticket data using ONLY the query
results provided. Be concise, 1 to 3 sentences. Include concrete numbers from the
results. If the results are empty, say so plainly. Do not invent data that
isn't in the results."""

    user_prompt = f"""Question: {question}

SQL used: {sql}

Result row count: {len(rows)}
Result rows (up to 20 shown): {preview_rows}

Answer the question in plain English."""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=200,
    )
    return response.choices[0].message.content.strip()


def answer_question(question):
    sql = question_to_sql(question)

    if "UNANSWERABLE" in sql.upper():
        return {
            "question": question,
            "sql": sql,
            "row_count": 0,
            "answer": "I could not map this question to the ticket data. Try asking about status, priority, category, agents, response or resolution times, or customer ratings.",
        }

    rows = run_sql(sql)
    answer = results_to_answer(question, sql, rows)

    return {
        "question": question,
        "sql": sql,
        "row_count": len(rows),
        "answer": answer,
    }