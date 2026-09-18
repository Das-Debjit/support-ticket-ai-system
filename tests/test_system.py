"""Basic tests for the SQL safety checks and anomaly detection."""

import pytest

from app.llm import extract_sql, validate_sql, LLMError
from app.anomalies import run_anomaly_detection


def test_validate_sql_allows_select():
    validate_sql("SELECT * FROM tickets;")


def test_validate_sql_blocks_drop():
    with pytest.raises(LLMError):
        validate_sql("DROP TABLE tickets;")


def test_validate_sql_blocks_delete():
    with pytest.raises(LLMError):
        validate_sql("DELETE FROM tickets;")


def test_validate_sql_blocks_non_select():
    with pytest.raises(LLMError):
        validate_sql("UPDATE tickets SET status = 'Open';")


def test_extract_sql_from_markdown_fence():
    raw = "```sql\nSELECT COUNT(*) FROM tickets;\n```"
    assert extract_sql(raw) == "SELECT COUNT(*) FROM tickets;"


def test_extract_sql_plain_text():
    raw = "SELECT COUNT(*) FROM tickets;"
    assert extract_sql(raw) == "SELECT COUNT(*) FROM tickets;"


def test_anomaly_detection_counts():
    result = run_anomaly_detection()
    assert result["resolution_time_outliers"]["count"] == 17
    assert result["aging_unresolved_high_priority"]["count"] == 80
    assert result["total_anomalies"] == 97