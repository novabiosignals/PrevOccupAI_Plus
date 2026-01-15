"""
EMG Output: Orchestration and Persistence

This module handles:
- Table building: Orchestrates session → daily → weekly aggregation
- CSV export: Writes DataFrames to disk
- Quality reports: Persists data quality findings

For core metric computation functions, see ``sensors.metrics.emg_metrics``.
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
# Constants
# ---------------------------------------------------------------------------
# Threshold for flagging potential MVC calibration issues
# Sessions with mean %MVC > this value likely have underestimated MVC peaks
MVC_QUALITY_THRESHOLD_PERCENT = 50.0


# ---------------------------------------------------------------------------
# Table building
# ---------------------------------------------------------------------------
def _add_mvc_quality_flags(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add MVC quality flag column to identify sessions with potential calibration issues.
    
    Sessions where mean_percent_mvc > 50% are flagged as 'mvc_underestimated',
    indicating the MVC calibration peak was likely too low.
    
    :param df: DataFrame with session metrics including 'mean_percent_mvc'.
    :returns: DataFrame with 'mvc_quality_flag' column added.
    """
    if 'mean_percent_mvc' not in df.columns:
        df['mvc_quality_flag'] = None
        return df
    
    df['mvc_quality_flag'] = df['mean_percent_mvc'].apply(
        lambda x: 'mvc_underestimated' if x > MVC_QUALITY_THRESHOLD_PERCENT else None
    )
    return df


def build_tables(session_metrics: List[dict]) -> Dict[str, pd.DataFrame]:
    """
    Convert raw session dictionaries into tidy DataFrames with aggregates/deltas.
    
    Uses Active APDF metrics (intensity when working) and rest metrics.
    Adds MVC quality flags to identify sessions with potential calibration issues.

    :param session_metrics: List of per-session metric dicts returned by ``compute_session_metrics``.
    :returns: Dict with DataFrames (sessions, daily/weekly aggregates, and change tables).
    """
    session_df = pd.DataFrame(session_metrics)
    
    # Add MVC quality flags (mean %MVC > 50% indicates underestimated MVC)
    session_df = _add_mvc_quality_flags(session_df)

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
    print(f"[emg_output] Data-quality report written to {path} ({len(reports)} issue(s))")
    return path


# ---------------------------------------------------------------------------
# MVC quality summary export
# ---------------------------------------------------------------------------
def export_mvc_quality_summary(
    tables: Dict[str, pd.DataFrame],
    output_root: Path,
) -> Path | None:
    """
    Export a summary of sessions flagged with MVC quality issues.

    Creates a CSV listing all sessions where mean %MVC exceeded the threshold,
    indicating likely MVC underestimation during calibration.

    :param tables: Tables dict from :func:`build_tables` containing ``session_metrics``.
    :param output_root: Directory where the report will be written.
    :returns: Path to the CSV or ``None`` if no sessions were flagged.
    """
    session_df = tables.get("session_metrics")
    if session_df is None or "mvc_quality_flag" not in session_df.columns:
        return None

    flagged = session_df[session_df["mvc_quality_flag"].notna()].copy()
    if flagged.empty:
        return None

    # Select relevant columns for the summary
    summary_cols = [
        "subject_id", "group", "side", "date", "session_label",
        "mean_percent_mvc", "mvc_peak", "mvc_quality_flag"
    ]
    # Only keep columns that exist
    summary_cols = [c for c in summary_cols if c in flagged.columns]
    summary_df = flagged[summary_cols].sort_values(
        ["subject_id", "side", "date"], ignore_index=True
    )

    path = output_root / "mvc_quality_summary.csv"
    summary_df.to_csv(path, index=False)
    print(
        f"[emg_output] MVC quality summary written to {path} "
        f"({len(summary_df)} session(s) flagged with mean %MVC > {MVC_QUALITY_THRESHOLD_PERCENT}%)"
    )
    return path
