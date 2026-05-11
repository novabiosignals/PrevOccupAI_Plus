"""
EMG Metrics Calculation Functions

This module contains functions for computing EMG-related metrics such as:
- APDF (Amplitude Probability Distribution Function) percentiles
- Active APDF (percentiles computed only on active samples, excluding rest)
- Rest metrics (time below rest threshold, gap analysis)
- Relative intensity bins (compared to weekly Active APDF baseline)
- Session metrics (duration, mean/max/min %MVC, iEMG)
- Daily and weekly aggregations
- Percentage changes over time

The Active APDF approach separates "intensity when working" from "relaxation time",
providing more physiologically meaningful metrics for occupational EMG analysis.
See: Marker et al. (2016), Veiersted et al. (2013) for methodology background.
"""

from typing import List, Tuple, Dict, Any, Optional

import numpy as np
import pandas as pd


# -------------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------------- #

# Default rest threshold (0.5% MVC) - literature standard for trapezius
# Veiersted et al. (2013): 0.5% EMGmax often performs best as discrimination level
DEFAULT_REST_THRESHOLD_MVC = 0.5

# Minimum gap duration to count as a micro-break (seconds)
DEFAULT_GAP_MIN_DURATION_S = 0.25

# Minimum total active time (seconds) required for stable weekly baseline computation
# 30 minutes = 1800 seconds
MIN_ACTIVE_DURATION_FOR_BASELINE_S = 1800


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
# Active APDF Functions (Intensity When Working)
# -------------------------------------------------------------------------------------------------------------------- #

def compute_active_apdf(
    signal_percent: np.ndarray,
    rest_threshold: float = DEFAULT_REST_THRESHOLD_MVC,
    percentiles: tuple = (10, 50, 90),
) -> dict:
    """
    Compute Active APDF: percentiles only on samples above the rest threshold.
    
    This removes the influence of rest/idle periods on intensity metrics,
    providing a clearer picture of "how intense was it when you were working?"
    
    :param signal_percent: Array of EMG amplitudes expressed as %MVC.
    :param rest_threshold: Threshold below which samples are considered "rest" (default: 0.5% MVC).
    :param percentiles: Which percentile values to extract (default: P10, P50, P90).
    :return: Dictionary with keys:
        - 'active_samples': Number of samples above rest threshold
        - 'total_samples': Total number of samples
        - 'active_fraction': Fraction of time in active state (0-1)
        - 'percentiles': Dict mapping percentile level to amplitude value (None if no active samples)
    """
    signal_flat = np.asarray(signal_percent).flatten()
    active_mask = signal_flat >= rest_threshold
    active_samples = signal_flat[active_mask]
    
    result = {
        "active_samples": int(len(active_samples)),
        "total_samples": int(len(signal_flat)),
        "active_fraction": float(len(active_samples) / len(signal_flat)) if len(signal_flat) > 0 else 0.0,
        "rest_threshold": float(rest_threshold),
        "percentiles": {},
    }
    
    # Only compute percentiles if we have active samples
    if len(active_samples) > 0:
        for p in percentiles:
            result["percentiles"][int(p)] = float(np.percentile(active_samples, p))
    else:
        # No active samples - return None for percentiles
        for p in percentiles:
            result["percentiles"][int(p)] = None
    
    return result


# -------------------------------------------------------------------------------------------------------------------- #
# Rest and Gap Analysis Functions
# -------------------------------------------------------------------------------------------------------------------- #

def compute_rest_metrics(
    signal_percent: np.ndarray,
    fs: float,
    rest_threshold: float = DEFAULT_REST_THRESHOLD_MVC,
    gap_min_duration_s: float = DEFAULT_GAP_MIN_DURATION_S,
) -> dict:
    """
    Compute rest-related metrics: rest time percentage, gap frequency, and max sustained activity.
    
    These time-pattern measures are specifically recommended for full-shift trapezius analyses.
    See Veiersted et al. (2013) for methodology.
    
    :param signal_percent: Array of EMG amplitudes expressed as %MVC.
    :param fs: Sampling frequency in Hz.
    :param rest_threshold: Threshold below which samples are considered "rest" (default: 0.5% MVC).
    :param gap_min_duration_s: Minimum gap duration to count as a micro-break (default: 0.25s).
    :return: Dictionary with:
        - 'rest_percent': Percentage of time below rest threshold (0-100)
        - 'rest_threshold_mvc': The threshold used
        - 'gap_count': Number of rest gaps (micro-breaks) detected
        - 'gap_frequency_per_minute': Gaps per minute of recording (better for short sessions)
        - 'max_sustained_activity_s': Longest continuous active period in seconds
        - 'active_duration_s': Total time in active state in seconds
    """
    signal_flat = np.asarray(signal_percent).flatten()
    is_rest = signal_flat < rest_threshold
    
    total_samples = len(signal_flat)
    rest_samples = int(np.sum(is_rest))
    active_samples = total_samples - rest_samples
    
    # Rest percentage
    rest_percent = (rest_samples / total_samples * 100.0) if total_samples > 0 else 0.0
    
    # Active duration in seconds
    active_duration_s = active_samples / fs if fs > 0 else 0.0
    
    # Find rest gaps (periods of rest)
    gap_min_samples = int(gap_min_duration_s * fs)
    gaps = _find_gaps(is_rest, gap_min_samples)
    gap_count = len(gaps)
    
    # Gap frequency per minute (better for short sessions <= 20 min)
    duration_minutes = total_samples / fs / 60 if fs > 0 else 0.0
    gap_frequency_per_minute = gap_count / duration_minutes if duration_minutes > 0 else 0.0
    
    # Max sustained activity (longest continuous active period)
    is_active = ~is_rest
    max_sustained_samples = _find_max_continuous_true(is_active)
    max_sustained_activity_s = max_sustained_samples / fs if fs > 0 else 0.0
    
    return {
        "rest_percent": float(rest_percent),
        "rest_threshold_mvc": float(rest_threshold),
        "gap_count": int(gap_count),
        "gap_frequency_per_minute": float(gap_frequency_per_minute),
        "max_sustained_activity_s": float(max_sustained_activity_s),
        "active_duration_s": float(active_duration_s),
    }


def _find_gaps(is_rest: np.ndarray, min_samples: int) -> List[Tuple[int, int]]:
    """
    Find rest periods (gaps) longer than minimum duration.
    
    :param is_rest: Boolean array where True indicates rest.
    :param min_samples: Minimum number of consecutive rest samples to count as a gap.
    :return: List of (start_idx, end_idx) tuples for each gap.
    """
    gaps = []
    in_gap = False
    start = 0
    
    for i, val in enumerate(is_rest):
        if val and not in_gap:
            in_gap = True
            start = i
        elif not val and in_gap:
            in_gap = False
            if i - start >= min_samples:
                gaps.append((start, i))
    
    # Handle gap at end of signal
    if in_gap and len(is_rest) - start >= min_samples:
        gaps.append((start, len(is_rest)))
    
    return gaps


def _find_max_continuous_true(arr: np.ndarray) -> int:
    """
    Find the longest continuous stretch of True values in a boolean array.
    
    :param arr: Boolean array.
    :return: Length of the longest continuous True stretch.
    """
    max_length = 0
    current_length = 0
    
    for val in arr:
        if val:
            current_length += 1
            max_length = max(max_length, current_length)
        else:
            current_length = 0
    
    return max_length


# -------------------------------------------------------------------------------------------------------------------- #
# Relative Intensity Bins (Compared to Weekly Baseline)
# -------------------------------------------------------------------------------------------------------------------- #

def compute_relative_intensity_bins(
    signal_percent: np.ndarray,
    fs: float,
    weekly_active_p10: float,
    weekly_active_p50: float,
    weekly_active_p90: float,
    rest_threshold: float = DEFAULT_REST_THRESHOLD_MVC,
) -> dict:
    """
    Compute relative intensity bins comparing session active EMG to weekly baseline.
    
    Bins are defined relative to the subject's weekly Active APDF percentiles:
    - Below usual: active EMG < weekly P10 (bottom 10% of their usual active intensity)
    - Typical-low: weekly P10 to P50
    - Typical-high: weekly P50 to P90
    - High for you: > weekly P90 (top 10% of their usual active intensity)
    
    :param signal_percent: Array of EMG amplitudes expressed as %MVC.
    :param fs: Sampling frequency in Hz.
    :param weekly_active_p10: Weekly Active APDF P10 (threshold T1).
    :param weekly_active_p50: Weekly Active APDF P50 (threshold T2).
    :param weekly_active_p90: Weekly Active APDF P90 (threshold T3).
    :param rest_threshold: Threshold below which samples are considered "rest".
    :return: Dictionary with bin percentages and minutes for active time only.
    """
    signal_flat = np.asarray(signal_percent).flatten()
    
    # Only consider active samples for binning
    active_mask = signal_flat >= rest_threshold
    active_samples = signal_flat[active_mask]
    
    if len(active_samples) == 0:
        # No active samples - return zeros
        return {
            "bin_below_usual_pct": 0.0,
            "bin_typical_low_pct": 0.0,
            "bin_typical_high_pct": 0.0,
            "bin_high_for_you_pct": 0.0,
            "bin_below_usual_min": 0.0,
            "bin_typical_low_min": 0.0,
            "bin_typical_high_min": 0.0,
            "bin_high_for_you_min": 0.0,
            "active_samples_binned": 0,
        }
    
    # Count samples in each bin
    below_usual = np.sum(active_samples < weekly_active_p10)
    typical_low = np.sum((active_samples >= weekly_active_p10) & (active_samples < weekly_active_p50))
    typical_high = np.sum((active_samples >= weekly_active_p50) & (active_samples < weekly_active_p90))
    high_for_you = np.sum(active_samples >= weekly_active_p90)
    
    total_active = len(active_samples)
    
    # Calculate percentages (of active time, not total time)
    bin_below_usual_pct = (below_usual / total_active * 100.0) if total_active > 0 else 0.0
    bin_typical_low_pct = (typical_low / total_active * 100.0) if total_active > 0 else 0.0
    bin_typical_high_pct = (typical_high / total_active * 100.0) if total_active > 0 else 0.0
    bin_high_for_you_pct = (high_for_you / total_active * 100.0) if total_active > 0 else 0.0
    
    # Calculate minutes (of active time in each bin)
    samples_to_min = 1.0 / fs / 60.0 if fs > 0 else 0.0
    
    return {
        "bin_below_usual_pct": float(bin_below_usual_pct),
        "bin_typical_low_pct": float(bin_typical_low_pct),
        "bin_typical_high_pct": float(bin_typical_high_pct),
        "bin_high_for_you_pct": float(bin_high_for_you_pct),
        "bin_below_usual_min": float(below_usual * samples_to_min),
        "bin_typical_low_min": float(typical_low * samples_to_min),
        "bin_typical_high_min": float(typical_high * samples_to_min),
        "bin_high_for_you_min": float(high_for_you * samples_to_min),
        "active_samples_binned": int(total_active),
    }


# -------------------------------------------------------------------------------------------------------------------- #
# Session Metrics Functions
# -------------------------------------------------------------------------------------------------------------------- #

def compute_session_metrics(
    signal_percent: np.ndarray,
    fs: float,
    metadata: dict,
    percentiles: tuple = (10, 50, 90),
    rest_threshold: float = DEFAULT_REST_THRESHOLD_MVC,
) -> Tuple[dict, dict]:
    """
    Compute all EMG metrics for a single session using Active APDF + Rest Time framework.

    This function computes:
    - Basic statistics (mean, max, min, iEMG)
    - Traditional APDF percentiles (for compatibility)
    - Active APDF percentiles (intensity when working, excluding rest)
    - Rest metrics (rest%, gap frequency, max sustained activity)

    Note: Relative intensity bins require weekly baseline and are computed separately
    via compute_relative_intensity_bins() after weekly aggregation.

    :param signal_percent: Session envelope expressed as %MVC.
    :param fs: Sampling frequency in Hz.
    :param metadata: Dictionary with session context (subject_id, date, side, etc.).
    :param percentiles: Which APDF percentiles to compute (default: P10, P50, P90).
    :param rest_threshold: Threshold below which samples are "rest" (default: 0.5% MVC).
    :return: Tuple of (metrics_dict, apdf_dict).
             metrics_dict contains all computed values.
             apdf_dict contains the traditional APDF result for plotting.
    """
    # Basic metrics
    duration_s = len(signal_percent) / fs if fs else 0.0
    mean_val = float(np.mean(signal_percent))
    max_val = float(np.max(signal_percent))
    min_val = float(np.min(signal_percent))

    # Integrated EMG (area under the curve)
    iemg_val = float(np.trapezoid(signal_percent, dx=1 / fs)) if fs else float("nan")

    # Traditional APDF percentiles (all samples, for backward compatibility)
    apdf_result = compute_apdf(signal_percent, percentiles)

    # Active APDF percentiles (only samples above rest threshold)
    active_apdf_result = compute_active_apdf(signal_percent, rest_threshold, percentiles)

    # Rest metrics (rest%, gap frequency, max sustained activity)
    rest_metrics = compute_rest_metrics(signal_percent, fs, rest_threshold)

    # Build the metrics dictionary
    metrics = {
        **metadata,
        "duration_s": duration_s,
        "mean_percent_mvc": mean_val,
        "max_percent_mvc": max_val,
        "min_percent_mvc": min_val,
        "iemg_percent_seconds": iemg_val,
        # Rest metrics
        "rest_percent": rest_metrics["rest_percent"],
        "gap_frequency_per_minute": rest_metrics["gap_frequency_per_minute"],
        "max_sustained_activity_s": rest_metrics["max_sustained_activity_s"],
        "active_duration_s": rest_metrics["active_duration_s"],
        "gap_count": rest_metrics["gap_count"],
    }

    # Add traditional APDF percentiles (all samples)
    for perc, value in apdf_result["percentiles"].items():
        metrics[f"apdf_p{perc}"] = value

    # Add Active APDF percentiles (only active samples)
    for perc, value in active_apdf_result["percentiles"].items():
        if value is not None:
            metrics[f"active_apdf_p{perc}"] = value
        else:
            # No active samples - use NaN
            metrics[f"active_apdf_p{perc}"] = float("nan")

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
        durations = np.asarray(group["duration_s"].values) if "duration_s" in group.columns else np.ones(len(group))
        total_duration = float(np.sum(durations))

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
            week_num_int = int(week_num) if isinstance(week_num, (int, float)) else int(str(week_num))
            entry = {
                "subject_id": subject_id,
                "side": side,
                "week": f"week_{week_num_int}",
                "day_count": len(week_group),
            }

            # Get durations for weighting
            durations = np.asarray(week_group["duration_s"].values) if "duration_s" in week_group.columns else np.ones(len(week_group))
            total_duration = float(np.sum(durations))

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
