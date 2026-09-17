"""REST API for the support ticket system."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.anomalies import run_anomaly_detection
from app.db import get_connection, TABLE_NAME
from app.llm import answer_question, LLMError

app = FastAPI(
    title="Support Ticket AI System",
    description="Natural language querying and anomaly detection over a support ticket dataset.",
    version="1.0.0",
)

# lets the Streamlit UI (running on a different port) call this API from the browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    question: str


@app.get("/health")
def health():
    try:
        conn = get_connection()
        conn.execute(f"SELECT 1 FROM {TABLE_NAME} LIMIT 1")
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database not ready: {exc}")


@app.post("/query")
def query(request: QueryRequest):
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question must not be empty.")

    try:
        return answer_question(request.question)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}")


@app.get("/anomalies")
def anomalies():
    try:
        return run_anomaly_detection()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Anomaly detection failed: {exc}")


@app.get("/stats")
def stats():
    conn = get_connection()

    def counts(column):
        cur = conn.execute(f"SELECT {column}, COUNT(*) FROM {TABLE_NAME} GROUP BY {column}")
        return dict(cur.fetchall())

    total = conn.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]

    return {
        "total_tickets": total,
        "by_status": counts("status"),
        "by_priority": counts("priority"),
        "by_category": counts("category"),
    }