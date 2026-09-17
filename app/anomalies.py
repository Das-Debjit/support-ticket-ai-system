"""Rule-based anomaly detection for the tickets dataset."""

import pandas as pd

from app.db import get_connection, TABLE_NAME

OUTLIER_STD_THRESHOLD = 2.0
UNRESOLVED_AGE_THRESHOLD_HRS = 24


def load_dataframe():
    conn = get_connection()
    df = pd.read_sql(f"SELECT * FROM {TABLE_NAME}", conn, parse_dates=["created_at"])
    return df


def detect_resolution_time_outliers(df):
    resolved = df[df["resolution_time_hrs"].notna()]
    if resolved.empty:
        return []

    mean = resolved["resolution_time_hrs"].mean()
    std = resolved["resolution_time_hrs"].std()
    threshold = mean + OUTLIER_STD_THRESHOLD * std

    outliers = resolved[resolved["resolution_time_hrs"] > threshold]

    results = []
    for row in outliers.itertuples():
        results.append({
            "ticket_id": row.ticket_id,
            "reason": "Abnormally long resolution time",
            "detail": f"Took {row.resolution_time_hrs:.1f}h to resolve, average is {mean:.1f}h (threshold {threshold:.1f}h)",
            "priority": row.priority,
            "status": row.status,
        })
    return results


def detect_aging_unresolved_high_priority(df):
    # dataset is historical, so we use its latest timestamp as "now"
    now = df["created_at"].max()

    mask = df["priority"].isin(["High", "Critical"]) & df["status"].isin(["Open", "Escalated"])
    candidates = df[mask].copy()
    candidates["age_hrs"] = (now - candidates["created_at"]).dt.total_seconds() / 3600
    aging = candidates[candidates["age_hrs"] > UNRESOLVED_AGE_THRESHOLD_HRS]

    results = []
    for row in aging.itertuples():
        results.append({
            "ticket_id": row.ticket_id,
            "reason": "Unresolved high priority ticket aging beyond threshold",
            "detail": f"{row.priority} priority, still {row.status} after {row.age_hrs:.1f}h (threshold {UNRESOLVED_AGE_THRESHOLD_HRS}h)",
            "priority": row.priority,
            "status": row.status,
        })
    return results


def run_anomaly_detection():
    df = load_dataframe()

    resolution_outliers = detect_resolution_time_outliers(df)
    aging_unresolved = detect_aging_unresolved_high_priority(df)

    return {
        "reference_timestamp": str(df["created_at"].max()),
        "resolution_time_outliers": {
            "count": len(resolution_outliers),
            "rule": f"Resolution time more than {OUTLIER_STD_THRESHOLD} standard deviations above the mean (resolved tickets only)",
            "tickets": resolution_outliers,
        },
        "aging_unresolved_high_priority": {
            "count": len(aging_unresolved),
            "rule": f"High or Critical priority, still Open or Escalated, open for more than {UNRESOLVED_AGE_THRESHOLD_HRS} hours",
            "tickets": aging_unresolved,
        },
        "total_anomalies": len(resolution_outliers) + len(aging_unresolved),
    }