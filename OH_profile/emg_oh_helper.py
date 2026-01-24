"""
EMG OH Profile Helper Functions

Functions to save EMG metrics to Occupational Health profiles.
Uses Active APDF + Rest Time framework for physiologically meaningful metrics.

OH Profile EMG Structure:
    EMG_session: duration_s, mvc_peak, active_duration_s
    EMG_intensity: mean/max/min_percent_mvc, iemg_percent_seconds
    EMG_apdf: {full: {p10, p50, p90}, active: {p10, p50, p90}}
    EMG_rest_recovery: rest_percent, gap_frequency, max_sustained, gap_count
    EMG_relative_bins: below_usual_pct, typical_low_pct, typical_high_pct, high_for_you_pct
"""

# external imports
import pandas as pd
from typing import Dict, Any

# OH profile imports
from OH_profile.load import get_OH_profile
from OH_profile.write import save_OH_profile, write_to_OH_profile
from OH_profile.constants import (
    SENSOR_METRICS_KEY, EMG_KEY,
    # Group keys (for nested structure)
    EMG_SESSION_GROUP_KEY, EMG_INTENSITY_GROUP_KEY, EMG_APDF_GROUP_KEY,
    EMG_REST_GROUP_KEY, EMG_RELATIVE_BINS_GROUP_KEY,
    # Session group
    EMG_DURATION_S_KEY, EMG_MVC_PEAK_KEY, EMG_ACTIVE_DURATION_S_KEY,
    # Intensity group
    EMG_MEAN_PERCENT_MVC_KEY, EMG_MAX_PERCENT_MVC_KEY, EMG_MIN_PERCENT_MVC_KEY,
    EMG_IEMG_PERCENT_SECONDS_KEY,
    # APDF group
    EMG_APDF_FULL_KEY, EMG_APDF_ACTIVE_KEY,
    EMG_APDF_P10_KEY, EMG_APDF_P50_KEY, EMG_APDF_P90_KEY,
    # Rest group
    EMG_REST_PERCENT_KEY, EMG_GAP_FREQUENCY_PER_MINUTE_KEY,
    EMG_MAX_SUSTAINED_ACTIVITY_S_KEY, EMG_GAP_COUNT_KEY,
    # Relative bins group
    EMG_BIN_BELOW_USUAL_PCT_KEY, EMG_BIN_TYPICAL_LOW_PCT_KEY,
    EMG_BIN_TYPICAL_HIGH_PCT_KEY, EMG_BIN_HIGH_FOR_YOU_PCT_KEY,
    # Aggregation keys
    EMG_DAILY_AGGREGATE_KEY, EMG_WEEKLY_AGGREGATE_KEY,
    EMG_SESSION_COUNT_KEY, EMG_DAY_COUNT_KEY,
)

# -------------------------------------------------------------------------------------------------------------------- #
# OH Profile Helper Functions
# -------------------------------------------------------------------------------------------------------------------- #

def _round_floats(value: Any, ndigits: int = 4) -> Any:
    """
    Recursively round all float values inside nested dict/list/tuple structures.

    :param value: Arbitrary nested structure containing floats.
    :param ndigits: Number of decimal places to round to.
    :return: Structure with floats rounded to the specified precision.
    """
    if isinstance(value, float):
        return round(value, ndigits)
    if isinstance(value, dict):
        return {k: _round_floats(v, ndigits) for k, v in value.items()}
    if isinstance(value, list):
        return [_round_floats(v, ndigits) for v in value]
    if isinstance(value, tuple):
        return tuple(_round_floats(v, ndigits) for v in value)
    return value

def _build_session_metrics_dict(row: pd.Series) -> Dict[str, Any]:
    """
    Build a nested dictionary of EMG metrics for a single session.
    
    Structure:
        EMG_session: {duration_s, mvc_peak, active_duration_s}
        EMG_intensity: {mean_percent_mvc, max_percent_mvc, min_percent_mvc, iemg_percent_seconds}
        EMG_apdf: {full: {p10, p50, p90}, active: {p10, p50, p90}}
        EMG_rest_recovery: {rest_percent, gap_frequency_per_minute, max_sustained_activity_s, gap_count}
        EMG_relative_bins: {below_usual_pct, typical_low_pct, typical_high_pct, high_for_you_pct}
    
    :param row: Series containing session metrics from compute_session_metrics().
    :return: Nested dictionary with grouped EMG metrics.
    """
    metrics = {
        # Session metadata
        EMG_SESSION_GROUP_KEY: {
            EMG_DURATION_S_KEY: row.get("duration_s", 0.0),
            EMG_MVC_PEAK_KEY: row.get("mvc_peak", 0.0),
            EMG_ACTIVE_DURATION_S_KEY: row.get("active_duration_s", 0.0),
        },
        # Intensity metrics
        EMG_INTENSITY_GROUP_KEY: {
            EMG_MEAN_PERCENT_MVC_KEY: row.get("mean_percent_mvc", 0.0),
            EMG_MAX_PERCENT_MVC_KEY: row.get("max_percent_mvc", 0.0),
            EMG_MIN_PERCENT_MVC_KEY: row.get("min_percent_mvc", 0.0),
            EMG_IEMG_PERCENT_SECONDS_KEY: row.get("iemg_percent_seconds", 0.0),
        },
        # APDF percentiles (full and active)
        EMG_APDF_GROUP_KEY: {
            EMG_APDF_FULL_KEY: {
                EMG_APDF_P10_KEY: row.get("apdf_p10", 0.0),
                EMG_APDF_P50_KEY: row.get("apdf_p50", 0.0),
                EMG_APDF_P90_KEY: row.get("apdf_p90", 0.0),
            },
            EMG_APDF_ACTIVE_KEY: {
                EMG_APDF_P10_KEY: row.get("active_apdf_p10", 0.0),
                EMG_APDF_P50_KEY: row.get("active_apdf_p50", 0.0),
                EMG_APDF_P90_KEY: row.get("active_apdf_p90", 0.0),
            },
        },
        # Rest/recovery metrics
        EMG_REST_GROUP_KEY: {
            EMG_REST_PERCENT_KEY: row.get("rest_percent", 0.0),
            EMG_GAP_FREQUENCY_PER_MINUTE_KEY: row.get("gap_frequency_per_minute", 0.0),
            EMG_MAX_SUSTAINED_ACTIVITY_S_KEY: row.get("max_sustained_activity_s", 0.0),
            EMG_GAP_COUNT_KEY: row.get("gap_count", 0),
        },
        # Relative intensity bins (compared to weekly baseline)
        EMG_RELATIVE_BINS_GROUP_KEY: {
            EMG_BIN_BELOW_USUAL_PCT_KEY: row.get("bin_below_usual_pct", None),
            EMG_BIN_TYPICAL_LOW_PCT_KEY: row.get("bin_typical_low_pct", None),
            EMG_BIN_TYPICAL_HIGH_PCT_KEY: row.get("bin_typical_high_pct", None),
            EMG_BIN_HIGH_FOR_YOU_PCT_KEY: row.get("bin_high_for_you_pct", None),
        },
    }

    return _round_floats(metrics, ndigits=4)


def _build_daily_aggregate_dict(row: pd.Series) -> Dict[str, Any]:
    """
    Build a nested dictionary of aggregated daily EMG metrics.
    
    Same structure as session metrics, plus session_count in EMG_session.
    
    :param row: Series containing daily aggregated metrics.
    :return: Nested dictionary with grouped EMG metrics.
    """
    metrics = {
        # Session metadata (includes session_count for aggregates)
        EMG_SESSION_GROUP_KEY: {
            EMG_SESSION_COUNT_KEY: int(row.get("session_count", 0)),
            EMG_DURATION_S_KEY: row.get("duration_s", 0.0),
            EMG_ACTIVE_DURATION_S_KEY: row.get("active_duration_s", 0.0),
        },
        # Intensity metrics
        EMG_INTENSITY_GROUP_KEY: {
            EMG_MEAN_PERCENT_MVC_KEY: row.get("mean_percent_mvc", 0.0),
            EMG_MAX_PERCENT_MVC_KEY: row.get("max_percent_mvc", 0.0),
            EMG_MIN_PERCENT_MVC_KEY: row.get("min_percent_mvc", 0.0),
            EMG_IEMG_PERCENT_SECONDS_KEY: row.get("iemg_percent_seconds", 0.0),
        },
        # APDF percentiles (full and active)
        EMG_APDF_GROUP_KEY: {
            EMG_APDF_FULL_KEY: {
                EMG_APDF_P10_KEY: row.get("apdf_p10", 0.0),
                EMG_APDF_P50_KEY: row.get("apdf_p50", 0.0),
                EMG_APDF_P90_KEY: row.get("apdf_p90", 0.0),
            },
            EMG_APDF_ACTIVE_KEY: {
                EMG_APDF_P10_KEY: row.get("active_apdf_p10", 0.0),
                EMG_APDF_P50_KEY: row.get("active_apdf_p50", 0.0),
                EMG_APDF_P90_KEY: row.get("active_apdf_p90", 0.0),
            },
        },
        # Rest/recovery metrics
        EMG_REST_GROUP_KEY: {
            EMG_REST_PERCENT_KEY: row.get("rest_percent", 0.0),
            EMG_GAP_FREQUENCY_PER_MINUTE_KEY: row.get("gap_frequency_per_minute", 0.0),
            EMG_MAX_SUSTAINED_ACTIVITY_S_KEY: row.get("max_sustained_activity_s", 0.0),
            EMG_GAP_COUNT_KEY: row.get("gap_count", 0),
        },
        # Relative intensity bins (averaged across sessions)
        EMG_RELATIVE_BINS_GROUP_KEY: {
            EMG_BIN_BELOW_USUAL_PCT_KEY: row.get("bin_below_usual_pct", None),
            EMG_BIN_TYPICAL_LOW_PCT_KEY: row.get("bin_typical_low_pct", None),
            EMG_BIN_TYPICAL_HIGH_PCT_KEY: row.get("bin_typical_high_pct", None),
            EMG_BIN_HIGH_FOR_YOU_PCT_KEY: row.get("bin_high_for_you_pct", None),
        },
    }

    return _round_floats(metrics, ndigits=4)


def _build_weekly_aggregate_dict(row: pd.Series) -> Dict[str, Any]:
    """
    Build a nested dictionary of aggregated weekly EMG metrics.
    
    Same structure as daily, but uses day_count instead of session_count.
    
    :param row: Series containing weekly aggregated metrics.
    :return: Nested dictionary with grouped EMG metrics.
    """
    metrics = {
        # Session metadata (uses day_count for weekly)
        EMG_SESSION_GROUP_KEY: {
            EMG_DAY_COUNT_KEY: int(row.get("day_count", 0)),
            EMG_DURATION_S_KEY: row.get("duration_s", 0.0),
            EMG_ACTIVE_DURATION_S_KEY: row.get("active_duration_s", 0.0),
        },
        # Intensity metrics
        EMG_INTENSITY_GROUP_KEY: {
            EMG_MEAN_PERCENT_MVC_KEY: row.get("mean_percent_mvc", 0.0),
            EMG_MAX_PERCENT_MVC_KEY: row.get("max_percent_mvc", 0.0),
            EMG_MIN_PERCENT_MVC_KEY: row.get("min_percent_mvc", 0.0),
            EMG_IEMG_PERCENT_SECONDS_KEY: row.get("iemg_percent_seconds", 0.0),
        },
        # APDF percentiles (full and active - weekly baseline)
        EMG_APDF_GROUP_KEY: {
            EMG_APDF_FULL_KEY: {
                EMG_APDF_P10_KEY: row.get("apdf_p10", 0.0),
                EMG_APDF_P50_KEY: row.get("apdf_p50", 0.0),
                EMG_APDF_P90_KEY: row.get("apdf_p90", 0.0),
            },
            EMG_APDF_ACTIVE_KEY: {
                EMG_APDF_P10_KEY: row.get("active_apdf_p10", 0.0),
                EMG_APDF_P50_KEY: row.get("active_apdf_p50", 0.0),
                EMG_APDF_P90_KEY: row.get("active_apdf_p90", 0.0),
            },
        },
        # Rest/recovery metrics
        EMG_REST_GROUP_KEY: {
            EMG_REST_PERCENT_KEY: row.get("rest_percent", 0.0),
            EMG_GAP_FREQUENCY_PER_MINUTE_KEY: row.get("gap_frequency_per_minute", 0.0),
            EMG_MAX_SUSTAINED_ACTIVITY_S_KEY: row.get("max_sustained_activity_s", 0.0),
            EMG_GAP_COUNT_KEY: row.get("gap_count", 0),
        },
        # Relative intensity bins (null at weekly level - this IS the baseline)
        EMG_RELATIVE_BINS_GROUP_KEY: {
            EMG_BIN_BELOW_USUAL_PCT_KEY: row.get("bin_below_usual_pct", None),
            EMG_BIN_TYPICAL_LOW_PCT_KEY: row.get("bin_typical_low_pct", None),
            EMG_BIN_TYPICAL_HIGH_PCT_KEY: row.get("bin_typical_high_pct", None),
            EMG_BIN_HIGH_FOR_YOU_PCT_KEY: row.get("bin_high_for_you_pct", None),
        },
    }

    return _round_floats(metrics, ndigits=4)


def _build_emg_profile_structure(
    session_df: pd.DataFrame,
    daily_df: pd.DataFrame,
    weekly_df: pd.DataFrame,
) -> Dict[str, Any]:
    """
    Build the nested EMG structure for a subject's OH profile.

    Structure:
        DD-MM-YYYY → session → side → metrics
        DD-MM-YYYY → EMG_daily_metrics → side → metrics
        EMG_weekly_metrics → side → metrics
        
    :param session_df: DataFrame with per-session metrics.
    :param daily_df: DataFrame with daily aggregated metrics.
    :param weekly_df: DataFrame with weekly aggregated metrics.
    :return: Nested dictionary structure for OH profile.
    """
    emg_structure: Dict[str, Any] = {}

    def _convert_date_format(date_str: str) -> str:
        """Convert date from YYYY-MM-DD to DD-MM-YYYY format."""
        try:
            parts = date_str.split('-')
            if len(parts) == 3 and len(parts[0]) == 4:  # YYYY-MM-DD format
                return f"{parts[2]}-{parts[1]}-{parts[0]}"
        except Exception:
            pass
        return date_str  # Return unchanged if not in expected format

    # Build session-level data: date → session → side → metrics
    for _, row in session_df.iterrows():
        date = _convert_date_format(str(row["date"]))
        session = str(row["session_label"])
        side = str(row["side"])

        if date not in emg_structure:
            emg_structure[date] = {}
        if session not in emg_structure[date]:
            emg_structure[date][session] = {}

        emg_structure[date][session][side] = _build_session_metrics_dict(row)

    # Build daily aggregates: date → EMG_daily_metrics → side → metrics
    for _, row in daily_df.iterrows():
        date = _convert_date_format(str(row["date"]))
        side = str(row["side"])

        if date not in emg_structure:
            emg_structure[date] = {}
        if EMG_DAILY_AGGREGATE_KEY not in emg_structure[date]:
            emg_structure[date][EMG_DAILY_AGGREGATE_KEY] = {}

        emg_structure[date][EMG_DAILY_AGGREGATE_KEY][side] = _build_daily_aggregate_dict(row)

    # Build weekly aggregates: EMG_weekly_metrics → side → metrics
    # (No week_N layer since each subject only has one week of acquisitions)
    if not weekly_df.empty:
        emg_structure[EMG_WEEKLY_AGGREGATE_KEY] = {}
        for _, row in weekly_df.iterrows():
            side = str(row["side"])
            emg_structure[EMG_WEEKLY_AGGREGATE_KEY][side] = _build_weekly_aggregate_dict(row)

    return emg_structure


def save_emg_to_oh_profiles(
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


# Backwards compatibility alias
_save_emg_to_oh_profiles = save_emg_to_oh_profiles


# -------------------------------------------------------------------------------------------------------------------- #
# OH Profile Reading Helpers (for navigating nested structure)
# -------------------------------------------------------------------------------------------------------------------- #

def get_emg_apdf_active(metrics: Dict[str, Any]) -> Dict[str, float]:
    """
    Extract active APDF percentiles from nested EMG metrics.
    
    :param metrics: EMG metrics dict (from side-level in OH profile).
    :return: Dict with 'p10', 'p50', 'p90' keys.
    """
    apdf = metrics.get(EMG_APDF_GROUP_KEY, {})
    active = apdf.get(EMG_APDF_ACTIVE_KEY, {})
    return {
        'p10': active.get(EMG_APDF_P10_KEY),
        'p50': active.get(EMG_APDF_P50_KEY),
        'p90': active.get(EMG_APDF_P90_KEY),
    }


def get_emg_apdf_full(metrics: Dict[str, Any]) -> Dict[str, float]:
    """
    Extract full APDF percentiles from nested EMG metrics.
    
    :param metrics: EMG metrics dict (from side-level in OH profile).
    :return: Dict with 'p10', 'p50', 'p90' keys.
    """
    apdf = metrics.get(EMG_APDF_GROUP_KEY, {})
    full = apdf.get(EMG_APDF_FULL_KEY, {})
    return {
        'p10': full.get(EMG_APDF_P10_KEY),
        'p50': full.get(EMG_APDF_P50_KEY),
        'p90': full.get(EMG_APDF_P90_KEY),
    }


def get_emg_relative_bins(metrics: Dict[str, Any]) -> Dict[str, float]:
    """
    Extract relative intensity bins from nested EMG metrics.
    
    :param metrics: EMG metrics dict (from side-level in OH profile).
    :return: Dict with bin keys.
    """
    bins = metrics.get(EMG_RELATIVE_BINS_GROUP_KEY, {})
    return {
        'below_usual_pct': bins.get(EMG_BIN_BELOW_USUAL_PCT_KEY),
        'typical_low_pct': bins.get(EMG_BIN_TYPICAL_LOW_PCT_KEY),
        'typical_high_pct': bins.get(EMG_BIN_TYPICAL_HIGH_PCT_KEY),
        'high_for_you_pct': bins.get(EMG_BIN_HIGH_FOR_YOU_PCT_KEY),
    }


def get_emg_session_info(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract session info from nested EMG metrics.
    
    :param metrics: EMG metrics dict (from side-level in OH profile).
    :return: Dict with session keys.
    """
    session = metrics.get(EMG_SESSION_GROUP_KEY, {})
    return {
        'duration_s': session.get(EMG_DURATION_S_KEY),
        'mvc_peak': session.get(EMG_MVC_PEAK_KEY),
        'active_duration_s': session.get(EMG_ACTIVE_DURATION_S_KEY),
        'session_count': session.get(EMG_SESSION_COUNT_KEY),
        'day_count': session.get(EMG_DAY_COUNT_KEY),
    }


def get_emg_intensity(metrics: Dict[str, Any]) -> Dict[str, float]:
    """
    Extract intensity metrics from nested EMG metrics.
    
    :param metrics: EMG metrics dict (from side-level in OH profile).
    :return: Dict with intensity keys.
    """
    intensity = metrics.get(EMG_INTENSITY_GROUP_KEY, {})
    return {
        'mean_percent_mvc': intensity.get(EMG_MEAN_PERCENT_MVC_KEY),
        'max_percent_mvc': intensity.get(EMG_MAX_PERCENT_MVC_KEY),
        'min_percent_mvc': intensity.get(EMG_MIN_PERCENT_MVC_KEY),
        'iemg_percent_seconds': intensity.get(EMG_IEMG_PERCENT_SECONDS_KEY),
    }


def get_emg_rest_recovery(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract rest/recovery metrics from nested EMG metrics.
    
    :param metrics: EMG metrics dict (from side-level in OH profile).
    :return: Dict with rest recovery keys.
    """
    rest = metrics.get(EMG_REST_GROUP_KEY, {})
    return {
        'rest_percent': rest.get(EMG_REST_PERCENT_KEY),
        'gap_frequency_per_minute': rest.get(EMG_GAP_FREQUENCY_PER_MINUTE_KEY),
        'max_sustained_activity_s': rest.get(EMG_MAX_SUSTAINED_ACTIVITY_S_KEY),
        'gap_count': rest.get(EMG_GAP_COUNT_KEY),
    }