"""EMG session processing utilities.

This module provides helper functions for session-level EMG processing.
The main session processing logic remains in emg_pipeline.py for now,
but these utilities can be used for standalone session analysis.

Future refactoring may move more logic here from emg_pipeline._process_day.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd


def infer_sample_rate(df: pd.DataFrame, default_fs: float = 1000.0) -> float:
    """Infer sample rate from dataframe timestamps.

    :param df: Dataframe with time index or 'time' column.
    :param default_fs: Default sample rate if inference fails.
    :returns: Estimated sample rate in Hz.
    """
    if isinstance(df.index, pd.DatetimeIndex):
        dt = df.index.to_series().diff().median().total_seconds()
    elif "time" in df.columns:
        dt = df["time"].diff().median()
    else:
        return default_fs

    if dt > 0:
        return 1.0 / dt
    return default_fs


def compute_session_effort(
    envelope: np.ndarray,
    mvc: float,
    bands: Optional[Dict[str, Tuple[float, float]]] = None,
) -> Dict[str, float]:
    """Compute time spent in each effort band as percentage.

    :param envelope: Envelope array (positive values).
    :param mvc: MVC reference value.
    :param bands: Dict mapping band_name -> (low_pct, high_pct).
    :returns: Dict mapping band_name -> percentage of time in that band.
    """
    if bands is None:
        bands = {
            "rest": (0.0, 5.0),
            "low": (5.0, 30.0),
            "moderate": (30.0, 60.0),
            "high": (60.0, 100.0),
            "very_high": (100.0, float("inf")),
        }

    if mvc <= 0 or envelope.size == 0:
        return {k: 0.0 for k in bands}

    normalized = (np.abs(envelope) / mvc) * 100.0
    total = len(normalized)
    result = {}

    for name, (low, high) in bands.items():
        count = np.sum((normalized >= low) & (normalized < high))
        result[name] = float(count / total * 100.0)

    return result


def build_session_metadata(
    subject_id: str,
    date_label: str,
    session_label: str,
    side: str,
    device_label: str,
    fs: float,
    **extra: Any,
) -> Dict[str, Any]:
    """Build a metadata dictionary for a session.

    :param subject_id: Subject identifier.
    :param date_label: Date string (e.g., 'YYYY-MM-DD').
    :param session_label: Session identifier (e.g., time slot).
    :param side: Body side ('left', 'right').
    :param device_label: Device identifier.
    :param fs: Sampling frequency in Hz.
    :param extra: Additional metadata fields.
    :returns: Metadata dictionary.
    """
    metadata = {
        "subject_id": subject_id,
        "date": date_label,
        "session_label": session_label,
        "side": side,
        "device_label": device_label,
        "fs_hz": fs,
    }
    metadata.update(extra)
    return metadata
