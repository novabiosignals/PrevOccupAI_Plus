"""EMG metrics export and persistence utilities.

This module consolidates all table-building, CSV export, and quality-report
persistence helpers used by the main EMG pipeline. Functions here are designed
to work with the data structures produced by ``sensors.metrics.emg_metrics``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from sensors.load.data_quality import FileQualityReport, write_quality_report
from sensors.metrics.emg_metrics import (
    EFFORT_BANDS,
    aggregate_daily_metrics,
    aggregate_weekly_metrics,
    compute_effort_bins,
    compute_percentage_changes,
)

__all__ = [
    "normalize_band_label",
    "build_tables",
    "write_tables",
    "persist_quality_report",
    "record_effort_bins",
    "write_effort_bins",
]


# ---------------------------------------------------------------------------
# Label normalization
# ---------------------------------------------------------------------------
def normalize_band_label(label: str) -> str:
    """Create machine-friendly column names from human-readable effort labels.

    :param label: Original text label such as ``"Low effort"`` or ``">100%"``.
    :returns: Snake-case string safe for use as a column prefix.
    """
    cleaned = label.strip().lower()
    replacements = {
        "%": "pct",
        ">": "gt",
        "+": "plus",
        "-": "_",
        "–": "_",
        "/": "_",
    }
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    cleaned = "_".join(filter(None, cleaned.split()))
    if not cleaned:
        cleaned = "band"
    return cleaned


# ---------------------------------------------------------------------------
# Table building
# ---------------------------------------------------------------------------
def build_tables(session_metrics: List[dict]) -> Dict[str, pd.DataFrame]:
    """Convert raw session dictionaries into tidy DataFrames with aggregates/deltas.

    :param session_metrics: List of per-session metric dicts returned by ``compute_session_metrics``.
    :returns: Dict with DataFrames (sessions, daily/weekly aggregates, and change tables).
    """
    session_df = pd.DataFrame(session_metrics)

    # Columns to average in daily aggregation
    mean_value_cols = [
        "iemg_percent_seconds",
        "mean_percent_mvc",
        "max_percent_mvc",
        "min_percent_mvc",
        "apdf_p10",
        "apdf_p50",
        "apdf_p90",
        "effort_low_pct",
        "effort_moderate_pct",
        "effort_high_pct",
        "effort_over100_pct",
    ]

    # Columns to sum in daily aggregation
    sum_value_cols = [
        "duration_s",
        "effort_low_min",
        "effort_moderate_min",
        "effort_high_min",
        "effort_over100_min",
    ]

    # Filter to only columns that exist in session_df
    all_daily_cols = [c for c in mean_value_cols + sum_value_cols if c in session_df.columns]
    sum_cols_present = [c for c in sum_value_cols if c in session_df.columns]

    daily_df = aggregate_daily_metrics(session_df, all_daily_cols, sum_columns=sum_cols_present)

    # Weekly aggregation
    weekly_sum_cols = [
        "duration_s",
        "iemg_percent_seconds",
        "effort_low_min",
        "effort_moderate_min",
        "effort_high_min",
        "effort_over100_min",
    ]
    weekly_mean_cols = [
        "mean_percent_mvc",
        "max_percent_mvc",
        "min_percent_mvc",
        "apdf_p10",
        "apdf_p50",
        "apdf_p90",
        "effort_low_pct",
        "effort_moderate_pct",
        "effort_high_pct",
        "effort_over100_pct",
    ]

    # Filter to columns that exist in daily_df
    weekly_sum_cols = [c for c in weekly_sum_cols if c in daily_df.columns]
    weekly_mean_cols = [c for c in weekly_mean_cols if c in daily_df.columns]

    weekly_df = aggregate_weekly_metrics(daily_df, weekly_sum_cols, weekly_mean_cols)

    session_increments = compute_percentage_changes(
        session_df,
        group_cols=["subject_id", "side", "date"],
        order_col="session_label",
        value_cols=["iemg_percent_seconds", "apdf_p50"],
        label="session",
    )
    daily_increments = compute_percentage_changes(
        daily_df,
        group_cols=["subject_id", "side"],
        order_col="date",
        value_cols=["iemg_percent_seconds", "apdf_p50"],
        label="day",
    )

    return {
        "session_metrics": session_df,
        "daily_metrics": daily_df,
        "weekly_metrics": weekly_df,
        "session_increments": session_increments,
        "daily_increments": daily_increments,
    }


# ---------------------------------------------------------------------------
# CSV writing
# ---------------------------------------------------------------------------
def write_tables(tables: Dict[str, pd.DataFrame], output_root: Path) -> None:
    """Save each table to CSV, naming files after the dictionary keys.

    :param tables: Mapping of ``name -> DataFrame`` produced by :func:`build_tables`.
    :param output_root: Directory where CSVs must be written.
    """
    for name, df in tables.items():
        path = output_root / f"{name}.csv"
        df.to_csv(path, index=False)


# ---------------------------------------------------------------------------
# Quality report persistence
# ---------------------------------------------------------------------------
def persist_quality_report(
    reports: Sequence[FileQualityReport],
    output_root: Path,
) -> Path | None:
    """Write the accumulated data-quality findings (if any) to disk and return the path.

    :param reports: Collected list of :class:`FileQualityReport` objects from the loader phase.
    :param output_root: Folder containing EMG pipeline artifacts.
    :returns: Path to the CSV or ``None`` when no reports were logged.
    """
    if not reports:
        return None
    path = output_root / "data_quality_report.csv"
    write_quality_report(reports, path)
    print(f"[emg_metrics_export] Data-quality report written to {path} ({len(reports)} issue(s))")
    return path


# ---------------------------------------------------------------------------
# Effort bin helpers
# ---------------------------------------------------------------------------
def record_effort_bins(
    effort_records: List[dict],
    metadata: dict,
    percent_signal: np.ndarray,
    fs: float,
) -> None:
    """Append a CSV-ready effort-bin summary for the current session.

    :param effort_records: Master list that mirrors eventual CSV rows.
    :param metadata: Contextual information (subject, date, session, device side, etc.).
    :param percent_signal: Session envelope expressed in %MVC.
    :param fs: Sampling frequency so minutes can be derived from sample counts.
    """
    minutes, percentages = compute_effort_bins(percent_signal, fs)
    labels = [band[2] for band in EFFORT_BANDS] + [">100%"]
    record = {
        "subject_id": metadata.get("subject_id"),
        "group": metadata.get("group"),
        "date": metadata.get("date"),
        "side": metadata.get("side"),
        "device_label": metadata.get("device_label"),
        "session_label": metadata.get("session_label"),
        "mac_address": metadata.get("mac_address"),
        "fs_hz": metadata.get("fs_hz"),
    }
    total_minutes = 0.0
    for label, minutes_value, pct_value in zip(labels, minutes, percentages):
        key = normalize_band_label(label)
        record[f"{key}_minutes"] = minutes_value
        record[f"{key}_pct"] = pct_value
        total_minutes += minutes_value
    record["total_minutes"] = total_minutes
    effort_records.append(record)


def write_effort_bins(records: Sequence[dict], output_root: Path) -> Path | None:
    """Persist the effort-bin table (if populated) and report its location to callers.

    :param records: Sequence of dict rows assembled via :func:`record_effort_bins`.
    :param output_root: Folder that stores CSV artifacts.
    :returns: Path to the newly written CSV or ``None`` if ``records`` was empty.
    """
    if not records:
        return None
    path = output_root / "session_effort_bins.csv"
    df = pd.DataFrame(records)
    df.to_csv(path, index=False)
    print(f"[emg_metrics_export] Effort-bin table written to {path} ({len(df)} rows)")
    return path

    return output_path
