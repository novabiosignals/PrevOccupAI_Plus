"""
EMG Metrics Export and Persistence Utilities

This module consolidates all table-building, CSV export, and quality-report
persistence helpers used by the main EMG pipeline. Functions here are designed
to work with the data structures produced by ``sensors.metrics.emg_metrics``.

Uses Active APDF + Rest Time framework for physiologically meaningful metrics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from sensors.load.data_quality import FileQualityReport, write_quality_report
from sensors.metrics.emg_metrics import (
    aggregate_daily_metrics,
    aggregate_weekly_metrics,
    compute_percentage_changes,
)

__all__ = [
    "build_tables",
    "write_tables",
    "persist_quality_report",
]


# ---------------------------------------------------------------------------
# Table building
# ---------------------------------------------------------------------------
def build_tables(session_metrics: List[dict]) -> Dict[str, pd.DataFrame]:
    """
    Convert raw session dictionaries into tidy DataFrames with aggregates/deltas.
    
    Uses Active APDF metrics (intensity when working) and rest metrics.

    :param session_metrics: List of per-session metric dicts returned by ``compute_session_metrics``.
    :returns: Dict with DataFrames (sessions, daily/weekly aggregates, and change tables).
    """
    session_df = pd.DataFrame(session_metrics)

    # Columns for daily aggregation using weighted averages (intensity/percentage metrics)
    mean_value_cols = [
        # Basic metrics
        "iemg_percent_seconds",
        "mean_percent_mvc",
        "max_percent_mvc",
        "min_percent_mvc",
        # Traditional APDF
        "apdf_p10",
        "apdf_p50",
        "apdf_p90",
        # Active APDF (intensity when working)
        "active_apdf_p10",
        "active_apdf_p50",
        "active_apdf_p90",
        # Rest metrics (percentages and frequencies)
        "rest_percent",
        "gap_frequency_per_minute",
        # Relative intensity bins (computed vs weekly baseline)
        "bin_below_usual_pct",
        "bin_typical_low_pct",
        "bin_typical_high_pct",
        "bin_high_for_you_pct",
    ]

    # Columns to sum in daily aggregation (time-based metrics)
    sum_value_cols = [
        "duration_s",
        "active_duration_s",
        "max_sustained_activity_s",
        "gap_count",
    ]

    # Filter to only columns that exist in session_df
    all_daily_cols = [c for c in mean_value_cols + sum_value_cols if c in session_df.columns]
    sum_cols_present = [c for c in sum_value_cols if c in session_df.columns]

    daily_df = aggregate_daily_metrics(session_df, all_daily_cols, sum_columns=sum_cols_present)

    # Weekly aggregation
    weekly_sum_cols = [
        "duration_s",
        "iemg_percent_seconds",
        "active_duration_s",
        "gap_count",
    ]
    weekly_mean_cols = [
        "mean_percent_mvc",
        "max_percent_mvc",
        "min_percent_mvc",
        # Traditional APDF
        "apdf_p10",
        "apdf_p50",
        "apdf_p90",
        # Active APDF (weekly baseline)
        "active_apdf_p10",
        "active_apdf_p50",
        "active_apdf_p90",
        # Rest metrics
        "rest_percent",
        "gap_frequency_per_minute",
        "max_sustained_activity_s",
    ]

    # Filter to columns that exist in daily_df
    weekly_sum_cols = [c for c in weekly_sum_cols if c in daily_df.columns]
    weekly_mean_cols = [c for c in weekly_mean_cols if c in daily_df.columns]

    weekly_df = aggregate_weekly_metrics(daily_df, weekly_sum_cols, weekly_mean_cols)

    # Compute percentage changes between sessions
    session_increments = compute_percentage_changes(
        session_df,
        group_cols=["subject_id", "side", "date"],
        order_col="session_label",
        value_cols=["iemg_percent_seconds", "apdf_p50", "active_apdf_p50", "rest_percent"],
        label="session",
    )
    
    # Compute percentage changes between days
    daily_increments = compute_percentage_changes(
        daily_df,
        group_cols=["subject_id", "side"],
        order_col="date",
        value_cols=["iemg_percent_seconds", "apdf_p50", "active_apdf_p50", "rest_percent"],
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
    """
    Save each table to CSV, naming files after the dictionary keys.

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
    """
    Write the accumulated data-quality findings (if any) to disk and return the path.

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
