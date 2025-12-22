"""
EMG Metrics Calculation Functions

This module contains functions for computing EMG-related metrics such as:
- APDF (Amplitude Probability Distribution Function) percentiles
- Session metrics (duration, mean/max/min %MVC, iEMG)
- Effort bin distribution (time spent in low/medium/high effort zones)
- Daily and weekly aggregations
- Percentage changes over time
"""

from typing import List, Tuple

import numpy as np
import pandas as pd


# -------------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------------- #

# Effort band definitions: (lower_bound, upper_bound, label)
EFFORT_BANDS = (
    (0.0, 33.0, "Low effort"),
    (33.0, 66.0, "Moderate effort"),
    (66.0, 100.0, "High effort"),
)


# -------------------------------------------------------------------------------------------------------------------- #
# APDF Functions
# -------------------------------------------------------------------------------------------------------------------- #

def compute_apdf(signal_percent: np.ndarray, percentiles: tuple = (10, 50, 90)) -> dict:
    """
    Compute the Amplitude Probability Distribution Function (APDF) for a %MVC signal.

    The APDF shows what percentage of time the signal spends below each amplitude level.

    :param signal_percent: Array of EMG amplitudes expressed as %MVC.
    :param percentiles: Which percentile values to extract (default: P10, P50, P90).
    :return: Dictionary with keys:
        - 'probs': Array of probability values (0-100%)
        - 'amplitudes': Sorted amplitude values
        - 'percentiles': Dict mapping percentile level to amplitude value
    """
    signal_flat = np.asarray(signal_percent).flatten()
    amps_sorted = np.sort(signal_flat)
    probs = np.linspace(0, 100, len(amps_sorted), endpoint=True)

    # Extract the requested percentile values
    perc_values = {}
    for p in percentiles:
        perc_values[int(p)] = float(np.percentile(signal_flat, p))

    return {
        "probs": probs,
        "amplitudes": amps_sorted,
        "percentiles": perc_values
    }


# -------------------------------------------------------------------------------------------------------------------- #
# Effort Bins Functions
# -------------------------------------------------------------------------------------------------------------------- #

def compute_effort_bins(amplitudes: np.ndarray, fs: float) -> Tuple[List[float], List[float]]:
    """
    Compute time spent in each effort zone based on %MVC amplitude.

    Effort zones:
    - Low effort: 0-33% MVC
    - Moderate effort: 33-66% MVC
    - High effort: 66-100% MVC
    - Over 100%: >100% MVC (overflow)

    :param amplitudes: Array of %MVC values.
    :param fs: Sampling frequency in Hz (used to convert samples to minutes).
    :return: Tuple of (minutes_list, percentages_list) for each effort zone.
             Both lists have 4 elements: [low, moderate, high, over100]
    """
    arr = np.asarray(amplitudes).flatten()
    counts = []

    # Count samples in each effort band
    for lower, upper, _label in EFFORT_BANDS:
        if upper == EFFORT_BANDS[-1][1]:  # Last band includes upper bound
            mask = (arr >= lower) & (arr <= upper)
        else:
            mask = (arr >= lower) & (arr < upper)
        counts.append(int(np.count_nonzero(mask)))

    # Count overflow (>100% MVC)
    overflow_mask = arr > EFFORT_BANDS[-1][1]
    counts.append(int(np.count_nonzero(overflow_mask)))

    # Calculate percentages and minutes
    total_samples = float(arr.size) if arr.size > 0 else 1.0

    if fs and fs > 0:
        minutes = [count / fs / 60.0 for count in counts]
    else:
        minutes = [float(count) for count in counts]

    percentages = [(count / total_samples) * 100.0 for count in counts]

    return minutes, percentages


# -------------------------------------------------------------------------------------------------------------------- #
# Session Metrics Functions
# -------------------------------------------------------------------------------------------------------------------- #

def compute_session_metrics(signal_percent: np.ndarray, fs: float, metadata: dict,
                            percentiles: tuple = (10, 50, 90)) -> Tuple[dict, dict]:
    """
    Compute all EMG metrics for a single session.

    :param signal_percent: Session envelope expressed as %MVC.
    :param fs: Sampling frequency in Hz.
    :param metadata: Dictionary with session context (subject_id, date, side, etc.).
    :param percentiles: Which APDF percentiles to compute.
    :return: Tuple of (metrics_dict, apdf_dict).
             metrics_dict contains all computed values.
             apdf_dict contains the APDF result for plotting.
    """
    # Basic metrics
    duration_s = len(signal_percent) / fs if fs else 0.0
    mean_val = float(np.mean(signal_percent))
    max_val = float(np.max(signal_percent))
    min_val = float(np.min(signal_percent))

    # Integrated EMG (area under the curve)
    iemg_val = float(np.trapz(signal_percent, dx=1 / fs)) if fs else float("nan")

    # APDF percentiles
    apdf_result = compute_apdf(signal_percent, percentiles)

    # Effort bins
    effort_minutes, effort_percentages = compute_effort_bins(signal_percent, fs)

    # Build the metrics dictionary
    metrics = {
        **metadata,
        "duration_s": duration_s,
        "mean_percent_mvc": mean_val,
        "max_percent_mvc": max_val,
        "min_percent_mvc": min_val,
        "iemg_percent_seconds": iemg_val,
        # Effort bin percentages
        "effort_low_pct": effort_percentages[0],
        "effort_moderate_pct": effort_percentages[1],
        "effort_high_pct": effort_percentages[2],
        "effort_over100_pct": effort_percentages[3],
        # Effort bin minutes
        "effort_low_min": effort_minutes[0],
        "effort_moderate_min": effort_minutes[1],
        "effort_high_min": effort_minutes[2],
        "effort_over100_min": effort_minutes[3],
    }

    # Add APDF percentiles to metrics
    for perc, value in apdf_result["percentiles"].items():
        metrics[f"apdf_p{perc}"] = value

    return metrics, apdf_result


# -------------------------------------------------------------------------------------------------------------------- #
# Aggregation Functions
# -------------------------------------------------------------------------------------------------------------------- #

def aggregate_daily_metrics(session_df: pd.DataFrame, value_columns: list,
                            sum_columns: list | None = None) -> pd.DataFrame:
    """
    Aggregate session metrics to daily level using duration-weighted averages.

    Percentage and intensity metrics are weighted by session duration to ensure
    accurate aggregation (e.g., a 60-min session contributes more than a 20-min session).

    :param session_df: DataFrame with per-session metrics.
    :param value_columns: All columns to include in aggregation.
    :param sum_columns: Columns to sum (e.g., duration, effort minutes). Others use weighted average.
    :return: DataFrame with one row per subject/side/date combination.
    """
    sum_cols = set(sum_columns) if sum_columns else set()

    records = []

    for (subject_id, side, date), group in session_df.groupby(["subject_id", "side", "date"]):
        entry = {
            "subject_id": subject_id,
            "side": side,
            "date": date,
            "session_count": len(group),
        }

        # Get durations for weighting
        durations = group["duration_s"].values if "duration_s" in group.columns else np.ones(len(group))
        total_duration = durations.sum()

        for col in value_columns:
            if col not in group.columns:
                continue

            if col in sum_cols:
                # Sum columns (duration, effort minutes)
                entry[col] = group[col].sum()
            else:
                # Duration-weighted average for percentages and intensity metrics
                if total_duration > 0:
                    entry[col] = np.average(group[col].values, weights=durations)
                else:
                    entry[col] = group[col].mean()

        records.append(entry)

    return pd.DataFrame(records)


def aggregate_weekly_metrics(daily_df: pd.DataFrame, sum_columns: list,
                             mean_columns: list) -> pd.DataFrame:
    """
    Aggregate daily metrics to weekly level using duration-weighted averages.

    Weeks are numbered starting from the first acquisition date (week_1, week_2, ...).
    Percentage and intensity metrics are weighted by daily duration.

    :param daily_df: DataFrame with daily aggregated metrics.
    :param sum_columns: Columns to sum across the week.
    :param mean_columns: Columns to use duration-weighted average.
    :return: DataFrame with one row per subject/side/week combination.
    """
    if daily_df.empty:
        return pd.DataFrame()

    # Convert date column to datetime
    df = daily_df.copy()
    df["_date_dt"] = pd.to_datetime(df["date"])

    records = []

    for (subject_id, side), group in df.groupby(["subject_id", "side"]):
        group_sorted = group.sort_values("_date_dt")
        first_date = group_sorted["_date_dt"].iloc[0]

        # Calculate week number for each day (week_1, week_2, etc.)
        group_sorted = group_sorted.copy()
        group_sorted["_week_num"] = ((group_sorted["_date_dt"] - first_date).dt.days // 7) + 1

        for week_num, week_group in group_sorted.groupby("_week_num"):
            entry = {
                "subject_id": subject_id,
                "side": side,
                "week": f"week_{int(week_num)}",
                "day_count": len(week_group),
            }

            # Get durations for weighting
            durations = week_group["duration_s"].values if "duration_s" in week_group.columns else np.ones(len(week_group))
            total_duration = durations.sum()

            # Sum columns
            for col in sum_columns:
                if col in week_group.columns:
                    entry[col] = week_group[col].sum()

            # Duration-weighted average columns
            for col in mean_columns:
                if col in week_group.columns:
                    if total_duration > 0:
                        entry[col] = np.average(week_group[col].values, weights=durations)
                    else:
                        entry[col] = week_group[col].mean()

            records.append(entry)

    return pd.DataFrame(records)


def compute_percentage_changes(df: pd.DataFrame, group_cols: list, order_col: str,
                               value_cols: list, label: str) -> pd.DataFrame:
    """
    Compute percentage change for metrics between consecutive time points.

    Example: How much did iEMG change from session 1 to session 2?

    :param df: DataFrame with metric values.
    :param group_cols: Columns that define groups (e.g., ["subject_id", "side", "date"]).
    :param order_col: Column that defines order within group (e.g., "session_label").
    :param value_cols: Columns to compute changes for.
    :param label: Prefix for output columns (e.g., "session" → "session_iemg_pct_change").
    :return: DataFrame with original values plus percentage change columns.
    """
    records = []

    for _, group in df.groupby(list(group_cols)):
        ordered = group.sort_values(order_col)
        prev_row = None

        for _, row in ordered.iterrows():
            entry = {col: row[col] for col in group_cols}
            entry[order_col] = row[order_col]

            for value_col in value_cols:
                entry[value_col] = row[value_col]
                change_col = f"{label}_{value_col}_pct_change"

                if prev_row is None or prev_row[value_col] == 0:
                    entry[change_col] = np.nan
                else:
                    change = ((row[value_col] - prev_row[value_col]) / prev_row[value_col]) * 100.0
                    entry[change_col] = change

            prev_row = row
            records.append(entry)

    return pd.DataFrame(records)
