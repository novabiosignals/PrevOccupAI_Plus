"""
EMG OH Profile Helper Functions

Functions to save EMG metrics to Occupational Health profiles.
Uses Active APDF + Rest Time framework for physiologically meaningful metrics.
"""

# external imports
import pandas as pd
from typing import Dict, Any

# OH profile imports
from OH_profile.load import get_OH_profile
from OH_profile.write import save_OH_profile, write_to_OH_profile
from OH_profile.constants import (
    SENSOR_METRICS_KEY, EMG_KEY,
    # Basic metrics
    EMG_DURATION_S_KEY, EMG_MEAN_PERCENT_MVC_KEY, EMG_MAX_PERCENT_MVC_KEY,
    EMG_MIN_PERCENT_MVC_KEY, EMG_IEMG_PERCENT_SECONDS_KEY, EMG_MVC_PEAK_KEY,
    # Traditional APDF
    EMG_APDF_P10_KEY, EMG_APDF_P50_KEY, EMG_APDF_P90_KEY,
    # Active APDF (intensity when working)
    EMG_ACTIVE_APDF_P10_KEY, EMG_ACTIVE_APDF_P50_KEY, EMG_ACTIVE_APDF_P90_KEY,
    # Rest metrics
    EMG_REST_PERCENT_KEY,
    EMG_MAX_SUSTAINED_ACTIVITY_S_KEY, EMG_ACTIVE_DURATION_S_KEY, EMG_GAP_COUNT_KEY, EMG_GAP_FREQUENCY_PER_MINUTE_KEY,
    # Relative bins (weekly only)
    EMG_BIN_BELOW_USUAL_PCT_KEY, EMG_BIN_TYPICAL_LOW_PCT_KEY,
    EMG_BIN_TYPICAL_HIGH_PCT_KEY, EMG_BIN_HIGH_FOR_YOU_PCT_KEY,
    # Aggregation keys
    EMG_DAILY_AGGREGATE_KEY, EMG_WEEKLY_AGGREGATE_KEY,
    EMG_SESSION_COUNT_KEY, EMG_DAY_COUNT_KEY,
)

# -------------------------------------------------------------------------------------------------------------------- #
# OH Profile Helper Functions
# -------------------------------------------------------------------------------------------------------------------- #

def _build_session_metrics_dict(row: pd.Series) -> Dict[str, Any]:
    """
    Build a dictionary of EMG metrics for a single session.
    
    Includes basic stats, traditional APDF, Active APDF, rest metrics,
    and relative intensity bins (compared to weekly baseline).
    
    :param row: Series containing session metrics from compute_session_metrics().
    :return: Dictionary with OH profile keys mapped to metric values.
    """
    return {
        # Basic metrics
        EMG_DURATION_S_KEY: row.get("duration_s", 0.0),
        EMG_MEAN_PERCENT_MVC_KEY: row.get("mean_percent_mvc", 0.0),
        EMG_MAX_PERCENT_MVC_KEY: row.get("max_percent_mvc", 0.0),
        EMG_MIN_PERCENT_MVC_KEY: row.get("min_percent_mvc", 0.0),
        EMG_IEMG_PERCENT_SECONDS_KEY: row.get("iemg_percent_seconds", 0.0),
        EMG_MVC_PEAK_KEY: row.get("mvc_peak", 0.0),
        # Traditional APDF percentiles (all samples)
        EMG_APDF_P10_KEY: row.get("apdf_p10", 0.0),
        EMG_APDF_P50_KEY: row.get("apdf_p50", 0.0),
        EMG_APDF_P90_KEY: row.get("apdf_p90", 0.0),
        # Active APDF percentiles (only active samples)
        EMG_ACTIVE_APDF_P10_KEY: row.get("active_apdf_p10", 0.0),
        EMG_ACTIVE_APDF_P50_KEY: row.get("active_apdf_p50", 0.0),
        EMG_ACTIVE_APDF_P90_KEY: row.get("active_apdf_p90", 0.0),
        # Rest metrics
        EMG_REST_PERCENT_KEY: row.get("rest_percent", 0.0),
        EMG_GAP_FREQUENCY_PER_MINUTE_KEY: row.get("gap_frequency_per_minute", 0.0),
        EMG_MAX_SUSTAINED_ACTIVITY_S_KEY: row.get("max_sustained_activity_s", 0.0),
        EMG_ACTIVE_DURATION_S_KEY: row.get("active_duration_s", 0.0),
        EMG_GAP_COUNT_KEY: row.get("gap_count", 0),
        # Relative intensity bins (compared to weekly baseline)
        EMG_BIN_BELOW_USUAL_PCT_KEY: row.get("bin_below_usual_pct", None),
        EMG_BIN_TYPICAL_LOW_PCT_KEY: row.get("bin_typical_low_pct", None),
        EMG_BIN_TYPICAL_HIGH_PCT_KEY: row.get("bin_typical_high_pct", None),
        EMG_BIN_HIGH_FOR_YOU_PCT_KEY: row.get("bin_high_for_you_pct", None),
    }


def _build_daily_aggregate_dict(row: pd.Series) -> Dict[str, Any]:
    """
    Build a dictionary of aggregated daily EMG metrics.
    
    Includes relative intensity bins (averaged across sessions for the day).
    
    :param row: Series containing daily aggregated metrics.
    :return: Dictionary with OH profile keys mapped to metric values.
    """
    return {
        EMG_SESSION_COUNT_KEY: int(row.get("session_count", 0)),
        # Basic metrics
        EMG_DURATION_S_KEY: row.get("duration_s", 0.0),
        EMG_MEAN_PERCENT_MVC_KEY: row.get("mean_percent_mvc", 0.0),
        EMG_MAX_PERCENT_MVC_KEY: row.get("max_percent_mvc", 0.0),
        EMG_MIN_PERCENT_MVC_KEY: row.get("min_percent_mvc", 0.0),
        EMG_IEMG_PERCENT_SECONDS_KEY: row.get("iemg_percent_seconds", 0.0),
        # Traditional APDF
        EMG_APDF_P10_KEY: row.get("apdf_p10", 0.0),
        EMG_APDF_P50_KEY: row.get("apdf_p50", 0.0),
        EMG_APDF_P90_KEY: row.get("apdf_p90", 0.0),
        # Active APDF
        EMG_ACTIVE_APDF_P10_KEY: row.get("active_apdf_p10", 0.0),
        EMG_ACTIVE_APDF_P50_KEY: row.get("active_apdf_p50", 0.0),
        EMG_ACTIVE_APDF_P90_KEY: row.get("active_apdf_p90", 0.0),
        # Rest metrics
        EMG_REST_PERCENT_KEY: row.get("rest_percent", 0.0),
        EMG_GAP_FREQUENCY_PER_MINUTE_KEY: row.get("gap_frequency_per_minute", 0.0),
        EMG_MAX_SUSTAINED_ACTIVITY_S_KEY: row.get("max_sustained_activity_s", 0.0),
        EMG_ACTIVE_DURATION_S_KEY: row.get("active_duration_s", 0.0),
        EMG_GAP_COUNT_KEY: row.get("gap_count", 0),
        # Relative intensity bins (averaged across sessions)
        EMG_BIN_BELOW_USUAL_PCT_KEY: row.get("bin_below_usual_pct", None),
        EMG_BIN_TYPICAL_LOW_PCT_KEY: row.get("bin_typical_low_pct", None),
        EMG_BIN_TYPICAL_HIGH_PCT_KEY: row.get("bin_typical_high_pct", None),
        EMG_BIN_HIGH_FOR_YOU_PCT_KEY: row.get("bin_high_for_you_pct", None),
    }


def _build_weekly_aggregate_dict(row: pd.Series) -> Dict[str, Any]:
    """
    Build a dictionary of aggregated weekly EMG metrics.
    
    Weekly level also includes relative intensity bins (compared to baseline).
    
    :param row: Series containing weekly aggregated metrics.
    :return: Dictionary with OH profile keys mapped to metric values.
    """
    return {
        EMG_DAY_COUNT_KEY: int(row.get("day_count", 0)),
        # Basic metrics
        EMG_DURATION_S_KEY: row.get("duration_s", 0.0),
        EMG_MEAN_PERCENT_MVC_KEY: row.get("mean_percent_mvc", 0.0),
        EMG_MAX_PERCENT_MVC_KEY: row.get("max_percent_mvc", 0.0),
        EMG_MIN_PERCENT_MVC_KEY: row.get("min_percent_mvc", 0.0),
        EMG_IEMG_PERCENT_SECONDS_KEY: row.get("iemg_percent_seconds", 0.0),
        # Traditional APDF
        EMG_APDF_P10_KEY: row.get("apdf_p10", 0.0),
        EMG_APDF_P50_KEY: row.get("apdf_p50", 0.0),
        EMG_APDF_P90_KEY: row.get("apdf_p90", 0.0),
        # Active APDF (weekly baseline percentiles)
        EMG_ACTIVE_APDF_P10_KEY: row.get("active_apdf_p10", 0.0),
        EMG_ACTIVE_APDF_P50_KEY: row.get("active_apdf_p50", 0.0),
        EMG_ACTIVE_APDF_P90_KEY: row.get("active_apdf_p90", 0.0),
        # Rest metrics
        EMG_REST_PERCENT_KEY: row.get("rest_percent", 0.0),
        EMG_GAP_FREQUENCY_PER_MINUTE_KEY: row.get("gap_frequency_per_minute", 0.0),
        EMG_MAX_SUSTAINED_ACTIVITY_S_KEY: row.get("max_sustained_activity_s", 0.0),
        EMG_ACTIVE_DURATION_S_KEY: row.get("active_duration_s", 0.0),
        EMG_GAP_COUNT_KEY: row.get("gap_count", 0),
        # Relative intensity bins (only at weekly level, for comparing sessions to baseline)
        EMG_BIN_BELOW_USUAL_PCT_KEY: row.get("bin_below_usual_pct", None),
        EMG_BIN_TYPICAL_LOW_PCT_KEY: row.get("bin_typical_low_pct", None),
        EMG_BIN_TYPICAL_HIGH_PCT_KEY: row.get("bin_typical_high_pct", None),
        EMG_BIN_HIGH_FOR_YOU_PCT_KEY: row.get("bin_high_for_you_pct", None),
    }


def _build_emg_profile_structure(
    session_df: pd.DataFrame,
    daily_df: pd.DataFrame,
    weekly_df: pd.DataFrame,
) -> Dict[str, Any]:
    """
    Build the nested EMG structure for a subject's OH profile.

    Structure:
        date → session → side → metrics
        date → daily_aggregate → side → metrics
        weekly_aggregate → side → metrics
        
    :param session_df: DataFrame with per-session metrics.
    :param daily_df: DataFrame with daily aggregated metrics.
    :param weekly_df: DataFrame with weekly aggregated metrics.
    :return: Nested dictionary structure for OH profile.
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
    """
    Save EMG metrics to OH profiles for each subject.

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

