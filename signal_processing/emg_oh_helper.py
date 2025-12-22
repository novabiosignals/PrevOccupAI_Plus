"""Functions to save EMG metrics to OH profiles."""

# external imports
import pandas as pd
from typing import Dict, Any

# OH profile imports
from OH_profile.load import get_OH_profile
from OH_profile.write import save_OH_profile, write_to_OH_profile
from OH_profile.constants import (
    SENSOR_METRICS_KEY, EMG_KEY,
    EMG_DURATION_S_KEY, EMG_MEAN_PERCENT_MVC_KEY, EMG_MAX_PERCENT_MVC_KEY,
    EMG_MIN_PERCENT_MVC_KEY, EMG_IEMG_PERCENT_SECONDS_KEY, EMG_MVC_PEAK_KEY,
    EMG_APDF_P10_KEY, EMG_APDF_P50_KEY, EMG_APDF_P90_KEY,
    EMG_EFFORT_LOW_PCT_KEY, EMG_EFFORT_MODERATE_PCT_KEY, EMG_EFFORT_HIGH_PCT_KEY,
    EMG_EFFORT_OVER100_PCT_KEY, EMG_EFFORT_LOW_MIN_KEY, EMG_EFFORT_MODERATE_MIN_KEY,
    EMG_EFFORT_HIGH_MIN_KEY, EMG_EFFORT_OVER100_MIN_KEY,
    EMG_DAILY_AGGREGATE_KEY, EMG_WEEKLY_AGGREGATE_KEY,
    EMG_SESSION_COUNT_KEY, EMG_DAY_COUNT_KEY,
)

# -------------------------------------------------------------------------------------------------------------------- #
# OH Profile Helper Functions
# -------------------------------------------------------------------------------------------------------------------- #

def _build_session_metrics_dict(row: pd.Series) -> Dict[str, Any]:
    """Build a dictionary of EMG metrics for a single session using OH profile constants."""
    return {
        EMG_DURATION_S_KEY: row["duration_s"],
        EMG_MEAN_PERCENT_MVC_KEY: row["mean_percent_mvc"],
        EMG_MAX_PERCENT_MVC_KEY: row["max_percent_mvc"],
        EMG_MIN_PERCENT_MVC_KEY: row["min_percent_mvc"],
        EMG_IEMG_PERCENT_SECONDS_KEY: row["iemg_percent_seconds"],
        EMG_MVC_PEAK_KEY: row.get("mvc_peak", 0.0),
        EMG_APDF_P10_KEY: row["apdf_p10"],
        EMG_APDF_P50_KEY: row["apdf_p50"],
        EMG_APDF_P90_KEY: row["apdf_p90"],
        EMG_EFFORT_LOW_PCT_KEY: row.get("effort_low_pct", 0.0),
        EMG_EFFORT_MODERATE_PCT_KEY: row.get("effort_moderate_pct", 0.0),
        EMG_EFFORT_HIGH_PCT_KEY: row.get("effort_high_pct", 0.0),
        EMG_EFFORT_OVER100_PCT_KEY: row.get("effort_over100_pct", 0.0),
        EMG_EFFORT_LOW_MIN_KEY: row.get("effort_low_min", 0.0),
        EMG_EFFORT_MODERATE_MIN_KEY: row.get("effort_moderate_min", 0.0),
        EMG_EFFORT_HIGH_MIN_KEY: row.get("effort_high_min", 0.0),
        EMG_EFFORT_OVER100_MIN_KEY: row.get("effort_over100_min", 0.0),
    }


def _build_daily_aggregate_dict(row: pd.Series) -> Dict[str, Any]:
    """Build a dictionary of aggregated daily EMG metrics using OH profile constants."""
    return {
        EMG_SESSION_COUNT_KEY: int(row.get("session_count", 0)),
        EMG_DURATION_S_KEY: row.get("duration_s", 0.0),
        EMG_MEAN_PERCENT_MVC_KEY: row["mean_percent_mvc"],
        EMG_MAX_PERCENT_MVC_KEY: row["max_percent_mvc"],
        EMG_MIN_PERCENT_MVC_KEY: row["min_percent_mvc"],
        EMG_IEMG_PERCENT_SECONDS_KEY: row["iemg_percent_seconds"],
        EMG_APDF_P10_KEY: row["apdf_p10"],
        EMG_APDF_P50_KEY: row["apdf_p50"],
        EMG_APDF_P90_KEY: row["apdf_p90"],
        EMG_EFFORT_LOW_PCT_KEY: row.get("effort_low_pct", 0.0),
        EMG_EFFORT_MODERATE_PCT_KEY: row.get("effort_moderate_pct", 0.0),
        EMG_EFFORT_HIGH_PCT_KEY: row.get("effort_high_pct", 0.0),
        EMG_EFFORT_OVER100_PCT_KEY: row.get("effort_over100_pct", 0.0),
        EMG_EFFORT_LOW_MIN_KEY: row.get("effort_low_min", 0.0),
        EMG_EFFORT_MODERATE_MIN_KEY: row.get("effort_moderate_min", 0.0),
        EMG_EFFORT_HIGH_MIN_KEY: row.get("effort_high_min", 0.0),
        EMG_EFFORT_OVER100_MIN_KEY: row.get("effort_over100_min", 0.0),
    }


def _build_weekly_aggregate_dict(row: pd.Series) -> Dict[str, Any]:
    """Build a dictionary of aggregated weekly EMG metrics using OH profile constants."""
    return {
        EMG_DAY_COUNT_KEY: int(row.get("day_count", 0)),
        EMG_DURATION_S_KEY: row.get("duration_s", 0.0),
        EMG_MEAN_PERCENT_MVC_KEY: row["mean_percent_mvc"],
        EMG_MAX_PERCENT_MVC_KEY: row["max_percent_mvc"],
        EMG_MIN_PERCENT_MVC_KEY: row["min_percent_mvc"],
        EMG_IEMG_PERCENT_SECONDS_KEY: row["iemg_percent_seconds"],
        EMG_APDF_P10_KEY: row["apdf_p10"],
        EMG_APDF_P50_KEY: row["apdf_p50"],
        EMG_APDF_P90_KEY: row["apdf_p90"],
        EMG_EFFORT_LOW_PCT_KEY: row.get("effort_low_pct", 0.0),
        EMG_EFFORT_MODERATE_PCT_KEY: row.get("effort_moderate_pct", 0.0),
        EMG_EFFORT_HIGH_PCT_KEY: row.get("effort_high_pct", 0.0),
        EMG_EFFORT_OVER100_PCT_KEY: row.get("effort_over100_pct", 0.0),
        EMG_EFFORT_LOW_MIN_KEY: row.get("effort_low_min", 0.0),
        EMG_EFFORT_MODERATE_MIN_KEY: row.get("effort_moderate_min", 0.0),
        EMG_EFFORT_HIGH_MIN_KEY: row.get("effort_high_min", 0.0),
        EMG_EFFORT_OVER100_MIN_KEY: row.get("effort_over100_min", 0.0),
    }

def _build_emg_profile_structure(
    session_df: pd.DataFrame,
    daily_df: pd.DataFrame,
    weekly_df: pd.DataFrame,
) -> Dict[str, Any]:
    """Build the nested EMG structure for a subject's OH profile.

    Structure: date → session → side → metrics
               date → daily_aggregate → side → metrics
               weekly_aggregate → week_N → side → metrics
    """
    emg_structure: Dict[str, Any] = {}

    # Build session-level data: date → session → side → metrics
    for _, row in session_df.iterrows():
        date = str(row["date"])
        session = str(row["session_label"])
        side = str(row["side"])

        if date not in emg_structure:
            emg_structure[date] = {}
        if session not in emg_structure[date]:
            emg_structure[date][session] = {}

        emg_structure[date][session][side] = _build_session_metrics_dict(row)

    # Build daily aggregates: date → daily_aggregate → side → metrics
    for _, row in daily_df.iterrows():
        date = str(row["date"])
        side = str(row["side"])

        if date not in emg_structure:
            emg_structure[date] = {}
        if EMG_DAILY_AGGREGATE_KEY not in emg_structure[date]:
            emg_structure[date][EMG_DAILY_AGGREGATE_KEY] = {}

        emg_structure[date][EMG_DAILY_AGGREGATE_KEY][side] = _build_daily_aggregate_dict(row)

    # Build weekly aggregates: weekly_aggregate → side → metrics
    # (No week_N layer since each subject only has one week of acquisitions)
    if not weekly_df.empty:
        emg_structure[EMG_WEEKLY_AGGREGATE_KEY] = {}
        for _, row in weekly_df.iterrows():
            side = str(row["side"])
            emg_structure[EMG_WEEKLY_AGGREGATE_KEY][side] = _build_weekly_aggregate_dict(row)

    return emg_structure

def _save_emg_to_oh_profiles(
    session_df: pd.DataFrame,
    daily_df: pd.DataFrame,
    weekly_df: pd.DataFrame,
    oh_profiles_path: str,
) -> None:
    """Save EMG metrics to OH profiles for each subject.

    :param session_df: DataFrame with per-session metrics.
    :param daily_df: DataFrame with daily aggregated metrics.
    :param weekly_df: DataFrame with weekly aggregated metrics.
    :param oh_profiles_path: Path to OH profiles folder.
    """
    subjects = session_df["subject_id"].unique()
    for subject_id in subjects:
        subject_id_str = str(subject_id)

        # Filter data for this subject
        subj_session_df = session_df[session_df["subject_id"] == subject_id]
        subj_daily_df = daily_df[daily_df["subject_id"] == subject_id]
        subj_weekly_df = weekly_df[weekly_df["subject_id"] == subject_id] if not weekly_df.empty else pd.DataFrame()

        # Build the nested EMG structure
        emg_structure = _build_emg_profile_structure(subj_session_df, subj_daily_df, subj_weekly_df)

        # Load, update, and save OH profile
        oh_profile = get_OH_profile(oh_profiles_path, subject_id_str)
        oh_profile = write_to_OH_profile(oh_profile, SENSOR_METRICS_KEY, EMG_KEY, emg_structure)
        save_OH_profile(oh_profiles_path, subject_id_str, oh_profile)
        print(f"[emg_pipeline] Saved OH profile for subject {subject_id_str}")

