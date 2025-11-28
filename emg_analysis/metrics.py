from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence

import numpy as np
import pandas as pd


@dataclass(slots=True)
class APDFResult:
    """Container for amplitude probability distribution outputs."""

    probs: np.ndarray
    amplitudes: np.ndarray
    percentiles: Dict[int, float]


def compute_apdf(signal_percent: np.ndarray, percentiles: Sequence[int] = (10, 50, 90)) -> APDFResult:
    """Compute the amplitude probability distribution for a %MVC signal.

    :param signal_percent: Flattenable array representing %MVC amplitudes.
    :param percentiles: Iterable of percentile levels to record.
    :returns: :class:`APDFResult` with sorted amplitudes, probability axis, and percentile lookup.
    """

    signal_flat = np.asarray(signal_percent).flatten()
    amps_sorted = np.sort(signal_flat)
    probs = np.linspace(0, 100, len(amps_sorted), endpoint=True)
    perc_values = {int(p): float(np.percentile(signal_flat, p)) for p in percentiles}
    return APDFResult(probs=probs, amplitudes=amps_sorted, percentiles=perc_values)


def compute_session_metrics(signal_percent: np.ndarray, fs: float, metadata: dict,
                            percentiles: Sequence[int] = (10, 50, 90)) -> tuple[dict, APDFResult]:
    """Generate core metrics for a single session.

    :param signal_percent: Session envelope already expressed in %MVC.
    :param fs: Sampling frequency (Hz).
    :param metadata: Context describing the session (subject, side, date, etc.).
    :param percentiles: Percentile cutoffs to compute within the APDF.
    :returns: Tuple ``(metrics_dict, apdf_result)`` used by the pipeline.
    """

    duration_s = len(signal_percent) / fs if fs else 0.0
    mean_val = float(np.mean(signal_percent))
    max_val = float(np.max(signal_percent))
    min_val = float(np.min(signal_percent))
    iemg_val = float(np.trapz(signal_percent, dx=1 / fs)) if fs else float("nan")
    apdf_res = compute_apdf(signal_percent, percentiles)

    metrics = {
        **metadata,
        "duration_s": duration_s,
        "mean_percent_mvc": mean_val,
        "max_percent_mvc": max_val,
        "min_percent_mvc": min_val,
        "iemg_percent_seconds": iemg_val,
    }
    for perc, value in apdf_res.percentiles.items():
        metrics[f"apdf_p{perc}"] = value

    return metrics, apdf_res


def aggregate_daily_metrics(session_df: pd.DataFrame, value_columns: Iterable[str]) -> pd.DataFrame:
    """Aggregate session metrics per subject/side/date.

    :param session_df: DataFrame with per-session metrics.
    :param value_columns: Column names that should be averaged across the day.
    :returns: DataFrame with ``session_count`` plus aggregated values.
    """

    agg_map = {col: "mean" for col in value_columns}
    agg_map["session_label"] = "count"
    daily_df = (
        session_df
        .groupby(["subject_id", "side", "date"], as_index=False)
        .agg(agg_map)
        .rename(columns={"session_label": "session_count"})
    )
    return daily_df


def compute_percentage_changes(df: pd.DataFrame, group_cols: Sequence[str], order_col: str,
                               value_cols: Sequence[str], label: str) -> pd.DataFrame:
    """Compute percentage change for value columns within ordered groups.

    :param df: DataFrame containing the metric values.
    :param group_cols: Columns defining each independent group (subject, side, etc.).
    :param order_col: Column that defines ordering within each group (session label or date).
    :param value_cols: Numeric columns for which percentage deltas should be computed.
    :param label: Prefix used when naming the output delta columns.
    :returns: DataFrame with original values plus ``{label}_{col}_pct_change`` columns.
    """

    records: list[dict] = []
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
                    entry[change_col] = ((row[value_col] - prev_row[value_col]) / prev_row[value_col]) * 100.0
            prev_row = row
            records.append(entry)
    return pd.DataFrame(records)
