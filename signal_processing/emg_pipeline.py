from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

from constants import FS_MBAN, MBAN_LEFT, MBAN_RIGHT
from emg_analysis.metrics import (APDFResult, aggregate_daily_metrics,
                                  compute_percentage_changes, compute_session_metrics)
from emg_analysis.preprocessing import preprocess_emg, transfer_emg
from emg_analysis.visuals import (EFFORT_BANDS, plot_apdf, plot_histogram, plot_metric_series,
                                  plot_session_effort_grid, plot_session_effort_session_stacks)
from load_signals.data_quality import FileQualityReport, write_quality_report
from visualize.processing import plot_envelope

from load_signals.dataset_loader import DayAcquisition, load_day_acquisitions


@dataclass(slots=True)
class PreprocessConfig:
    """Container holding the DSP knobs used while transforming raw EMG signals.

    Attributes map directly to the helper functions inside :mod:`emg_analysis.preprocessing` so
    the pipeline can thread a single object through each processing stage instead of passing a
    long list of individual parameters.
    """

    fs: float = FS_MBAN
    lowcut: float = 10.0
    highcut: float = 450.0
    smooth_sigma_ms: float = 50.0
    envelope_preview_seconds: float = 30.0


def run_emg_pipeline(
    day_descriptors: Sequence[DayAcquisition],
    selected_sensors: Dict[str, List[str]],
    results_root: Path,
    plots_root: Path,
    config: PreprocessConfig | None = None,
    percentiles: Sequence[int] = (10, 50, 90),
    generate_visuals: bool = True,
    quality_log: Optional[List[FileQualityReport]] = None,
) -> Dict[str, Path]:
    """Process every subject/day descriptor and persist metrics + visuals.

    :param day_descriptors: Iterable of :class:`DayAcquisition` entries describing what to load.
    :param selected_sensors: Mapping of device name to sensors so the loader knows what to fetch.
    :param results_root: Root directory where CSV artifacts will be persisted.
    :param plots_root: Root directory for plots. The structure beneath mirrors subject/date/side hierarchy.
    :param config: Optional :class:`PreprocessConfig`; defaults to :data:`DEFAULT_CONFIG` upstream.
    :param percentiles: Amplitude percentiles to compute for the APDF summary table.
    :param generate_visuals: Skip plot rendering when ``False`` to shorten quick test cycles.
    :param quality_log: Optional list that is populated with :class:`FileQualityReport` objects for bad files.
    :returns: Dict that names each artifact (e.g. ``session_metrics``) and where it lives on disk.
    """

    if config is None:
        config = PreprocessConfig()

    # Keep output folders ready so downstream helpers can assume they exist.
    results_root.mkdir(parents=True, exist_ok=True)
    plots_root.mkdir(parents=True, exist_ok=True)

    quality_records = quality_log if quality_log is not None else []
    session_metrics: List[dict] = []
    effort_records: List[dict] = []
    for day in day_descriptors:
        day_data = load_day_acquisitions(day, selected_sensors, quality_log=quality_records)
        if not day_data:
            print(f"[emg_pipeline] No data found for {day.subject_id} on {day.date_label}")
            continue
        session_metrics.extend(
            _process_day(
                day,
                day_data,
                config,
                percentiles,
                plots_root if generate_visuals else None,
                effort_records,
            )
        )

    report_path = _persist_quality_report(quality_records, results_root)
    effort_path = _write_effort_bins(effort_records, results_root)

    if not session_metrics:
        print("[emg_pipeline] No session metrics were computed.")
        artifacts: Dict[str, Path] = {}
        if report_path:
            artifacts["quality_report"] = report_path
        if effort_path:
            artifacts["effort_bins"] = effort_path
        return artifacts

    tables = _build_tables(session_metrics)
    _write_tables(tables, results_root)

    if generate_visuals:
        _plot_metric_trends(tables, plots_root)

    artifacts = {
        "session_metrics": results_root / "session_metrics.csv",
        "daily_metrics": results_root / "daily_metrics.csv",
    }

    if report_path is not None:
        artifacts["quality_report"] = report_path
    if effort_path is not None:
        artifacts["effort_bins"] = effort_path

    return artifacts


def _process_day(
    day: DayAcquisition,
    day_data: Dict[str, Dict[str, pd.DataFrame]],
    config: PreprocessConfig,
    percentiles: Sequence[int],
    plots_root: Optional[Path],
    effort_records: Optional[List[dict]],
) -> List[dict]:
    """Compute per-session metrics and optional visuals for a single calendar day.

    :param day: Descriptor that points to folders and metadata (subject, group, MAC addresses).
    :param day_data: Nested dict shaped ``device -> session_label -> DataFrame`` from the loader.
    :param config: Shared preprocessing configuration for filtering/enveloping.
    :param percentiles: Percentiles used when building the APDF summary record.
    :param plots_root: Root path where visuals should be written, or ``None`` to skip.
    :param effort_records: Mutable list that is extended with effort-bin summaries for CSV export.
    :returns: List of metric dictionaries that later become rows in ``session_metrics.csv``.
    """

    day_metrics: List[dict] = []
    daily_payload: Dict[tuple[str, str], tuple[np.ndarray, float]] = {}

    for device_label, acquisitions in day_data.items():
        mvc_label, mvc_df = _pick_mvc(acquisitions)
        if mvc_df is None:
            print(f"[emg_pipeline] Missing MVC for {day.subject_id} {device_label} on {day.date_label}")
            continue

        try:
            mvc_env = _compute_envelope(mvc_df, config)
        except ValueError as exc:
            print(f"[emg_pipeline] MVC preprocessing error ({day.subject_id} {device_label}): {exc}")
            continue

        mvc_peak = float(np.max(mvc_env))
        if mvc_peak <= 0:
            print(f"[emg_pipeline] MVC peak <= 0 for {day.subject_id} {device_label}")
            continue

        for session_label, session_df in acquisitions.items():
            if session_label == mvc_label:
                continue
            try:
                envelope_mv, raw_mv = _compute_envelope(session_df, config, return_raw=True)
            except ValueError as exc:
                print(f"[emg_pipeline] Session preprocessing error ({day.subject_id} {session_label}): {exc}")
                continue

            # Normalize against the MVC peak so that downstream plots and metrics work in %MVC space.
            percent_signal = (envelope_mv / mvc_peak) * 100.0
            metadata = _build_metadata(day, device_label, session_label, config.fs)
            side_label = metadata["side"]
            metrics, apdf = compute_session_metrics(percent_signal, config.fs, metadata, percentiles)
            day_metrics.append(metrics)

            if effort_records is not None:
                _record_effort_bins(effort_records, metadata, percent_signal, config.fs)

            if plots_root:
                _save_session_visuals(
                    plots_root,
                    day,
                    device_label,
                    session_label,
                    raw_mv,
                    envelope_mv,
                    percent_signal,
                    apdf,
                    config,
                    metadata,
                )

            # Keep a separate copy because ``percent_signal`` is mutated later inside matplotlib.
            daily_payload[(side_label, session_label)] = (percent_signal.copy(), config.fs)

    if plots_root and daily_payload:
        _save_day_visuals(plots_root, day, daily_payload)

    return day_metrics


def _compute_envelope(
    df: pd.DataFrame,
    config: PreprocessConfig,
    return_raw: bool = False,
) -> np.ndarray | tuple[np.ndarray, np.ndarray]:
    """Transform a raw session dataframe into an EMG envelope (and optionally raw signal).

    :param df: DataFrame that still contains nSeq + EMG (and possibly ACC) columns.
    :param config: Frequency-domain configuration shared across sessions.
    :param return_raw: When ``True`` also returns the unfiltered EMG trace for plotting.
    :returns: Envelope-only array or ``(envelope, raw)`` tuple when ``return_raw`` is set.
    """

    emg_mv = _extract_emg_mv(df)
    envelope = preprocess_emg(emg_mv, config.fs, config.lowcut, config.highcut, config.smooth_sigma_ms)
    if return_raw:
        return envelope, emg_mv
    return envelope


def _extract_emg_mv(df: pd.DataFrame) -> np.ndarray:
    """Locate the EMG column, convert it to millivolts, and guard against empty recordings.

    :param df: Session dataframe containing EMG plus optional auxiliary channels.
    :returns: One-dimensional NumPy array with values expressed in millivolts.
    """

    emg_cols = [col for col in df.columns if "emg" in str(col).lower()]
    target_col = None
    if emg_cols:
        target_col = emg_cols[0]
    elif len(df.columns) > 1:
        target_col = df.columns[1]
    else:
        raise ValueError("No EMG column available")

    raw_values = df[target_col].to_numpy()
    if raw_values.size == 0:
        raise ValueError("Empty EMG column")
    return _to_millivolts(raw_values)


def _to_millivolts(raw_values: np.ndarray) -> np.ndarray:
    """Convert EMG samples to millivolts, respecting files that are already scaled.

    :param raw_values: EMG samples straight from disk (could be ints or floats, scaled or not).
    :returns: Array of EMG values in millivolts.
    """

    arr = np.asarray(raw_values)

    # Raw OpenSignals files store EMG as unsigned integers; StudioData MVC files are floats in mV already.
    if np.issubdtype(arr.dtype, np.integer):
        return transfer_emg(arr.astype(float))

    arr = arr.astype(float)
    finite = arr[np.isfinite(arr)]
    max_abs = float(np.max(np.abs(finite))) if finite.size else 0.0

    # Values below ~10 mV typically indicate that the file is already calibrated; avoid double-scaling.
    if max_abs <= 10.0:
        return arr

    return transfer_emg(arr)


def _pick_mvc(acquisitions: Dict[str, pd.DataFrame]) -> tuple[Optional[str], Optional[pd.DataFrame]]:
    """Return the acquisition labeled as MVC along with its dataframe if present.

    :param acquisitions: Mapping ``session_label -> dataframe`` for a device/day pair.
    :returns: Tuple of ``(label, dataframe)`` or ``(None, None)`` if no MVC was found.
    """

    for key, df in acquisitions.items():
        if "mvc" in key.lower():
            return key, df
    return None, None


def _build_metadata(day: DayAcquisition, device_label: str, session_label: str, fs: float) -> dict:
    """Compose a metadata dictionary that tags every metric row/plot with context.

    The payload is intentionally flat and JSON-friendly so that both pandas and logging sinks
    can consume it without extra conversions.

    :param day: High-level descriptor for the subject/day folder.
    :param device_label: e.g. ``mBAN_left`` so we can infer side and device metadata.
    :param session_label: Time slot or label such as ``09-30-00``.
    :param fs: Sampling rate carried forward for reference.
    :returns: Dictionary with descriptive keys (subject, side, mac_address, etc.).
    """

    device_lower = device_label.lower()
    if MBAN_LEFT.lower() in device_lower:
        side = "left"
        mac = day.left_mac
    elif MBAN_RIGHT.lower() in device_lower:
        side = "right"
        mac = day.right_mac
    else:
        side = device_label
        mac = ""

    return {
        "subject_id": day.subject_id,
        "group": day.group,
        "device_num": day.device_num,
        "side": side,
        "device_label": device_label,
        "mac_address": mac,
        "date": day.date_label,
        "session_label": session_label,
        "fs_hz": fs,
    }


def _save_session_visuals(
    plots_root: Path,
    day: DayAcquisition,
    device_label: str,
    session_label: str,
    raw_mv: np.ndarray,
    envelope_mv: np.ndarray,
    percent_signal: np.ndarray,
    apdf: APDFResult,
    config: PreprocessConfig,
    metadata: dict,
) -> None:
    """Persist APDF, histogram, and envelope preview for one session on disk.

    :param plots_root: Root folder for all plots.
    :param day: Descriptor describing the subject/date.
    :param device_label: Original device descriptor (still useful for naming).
    :param session_label: Acquisition identifier used for file names.
    :param raw_mv: Raw EMG trace sampled at :attr:`PreprocessConfig.fs`.
    :param envelope_mv: Smoothed/enveloped EMG amplitude in millivolts.
    :param percent_signal: Envelope normalized to MVC (used when plotting envelope preview).
    :param apdf: Tuple containing APDF arrays + percentile lookups.
    :param config: Preprocessing configuration (needed for preview duration).
    :param metadata: Extra context such as ``side`` used in folder naming.
    """

    side = metadata.get("side", device_label)
    session_dir = plots_root / day.subject_id / day.date_label / side / session_label
    session_dir.mkdir(parents=True, exist_ok=True)
    title = f"{day.subject_id} | {side} | {day.date_label} {session_label}"
    plot_apdf(apdf, session_dir / f"{session_label}_apdf.png", title)
    plot_histogram(apdf.amplitudes, session_dir / f"{session_label}_hist.png", f"Histogram – {title}")

    preview_samples = min(len(raw_mv), int(config.fs * config.envelope_preview_seconds))
    if preview_samples > 0:
        raw_series = pd.Series(raw_mv[:preview_samples])
        env_series = pd.Series(envelope_mv[:preview_samples])
        plot_envelope(raw_series, env_series, f"{session_label}_envelope", str(session_dir))


def _save_day_visuals(
    plots_root: Path,
    day: DayAcquisition,
    payloads: Dict[tuple[str, str], tuple[np.ndarray, float]],
) -> None:
    """Generate day-level effort distribution plots summarizing left/right activity.

    :param plots_root: Root folder for plots.
    :param day: Descriptor describing the subject/date combination.
    :param payloads: Dict mapping ``(side, session_label) -> (percent_signal, fs)`` arrays.
    """

    session_labels = sorted({label for (_, label) in payloads.keys()})
    day_dir = plots_root / day.subject_id / day.date_label / "summary"
    plot_session_effort_grid(
        payloads,
        session_labels,
        day_dir / "effort_distribution.png",
        f"{day.subject_id} – {day.date_label}",
    )
    plot_session_effort_session_stacks(
        payloads,
        session_labels,
        day_dir / "effort_sessions.png",
        f"{day.subject_id} – {day.date_label} session progression",
    )


def _build_tables(session_metrics: List[dict]) -> Dict[str, pd.DataFrame]:
    """Convert raw session dictionaries into tidy DataFrames with aggregates/deltas.

    :param session_metrics: List of per-session metric dicts returned by ``compute_session_metrics``.
    :returns: Dict with four DataFrames (sessions, daily aggregates, and two change tables).
    """

    session_df = pd.DataFrame(session_metrics)
    value_cols = [
        "iemg_percent_seconds",
        "mean_percent_mvc",
        "max_percent_mvc",
        "min_percent_mvc",
        "apdf_p10",
        "apdf_p50",
        "apdf_p90",
    ]

    daily_df = aggregate_daily_metrics(session_df, value_cols)
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
        "session_increments": session_increments,
        "daily_increments": daily_increments,
    }


def _write_tables(tables: Dict[str, pd.DataFrame], output_root: Path) -> None:
    """Save each table to CSV, naming files after the dictionary keys.

    :param tables: Mapping of ``name -> DataFrame`` produced by :func:`_build_tables`.
    :param output_root: Directory where CSVs must be written.
    """

    for name, df in tables.items():
        path = output_root / f"{name}.csv"
        df.to_csv(path, index=False)


def _plot_metric_trends(tables: Dict[str, pd.DataFrame], plots_root: Path) -> None:
    """Visualize percentage changes across sessions/days for quick visual QA.

    :param tables: Output from :func:`_build_tables` (needs increments tables inside).
    :param plots_root: Root folder for placing delta plots.
    """

    session_df = tables.get("session_increments")
    if session_df is not None and not session_df.empty:
        for (subject_id, side, date), group_df in session_df.groupby(["subject_id", "side", "date"]):
            for metric in ("iemg_percent_seconds", "apdf_p50"):
                change_col = f"session_{metric}_pct_change"
                if change_col not in group_df:
                    continue
                output = plots_root / subject_id / date / side / "trends" / f"session_change_{metric}.png"
                plot_metric_series(group_df, change_col, "session_label", output, f"Session Δ {metric} – {subject_id} {side} {date}")

    daily_df = tables.get("daily_increments")
    if daily_df is not None and not daily_df.empty:
        for (subject_id, side), group_df in daily_df.groupby(["subject_id", "side"]):
            for metric in ("iemg_percent_seconds", "apdf_p50"):
                change_col = f"day_{metric}_pct_change"
                if change_col not in group_df:
                    continue
                output = plots_root / subject_id / "cross_day_trends" / side / f"daily_change_{metric}.png"
                plot_metric_series(group_df, change_col, "date", output, f"Daily Δ {metric} – {subject_id} {side}")


def _persist_quality_report(
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
    print(f"[emg_pipeline] Data-quality report written to {path} ({len(reports)} issue(s))")
    return path


def _record_effort_bins(
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

    minutes, percentages = _compute_effort_bins(percent_signal, fs)
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
        key = _normalize_band_label(label)
        record[f"{key}_minutes"] = minutes_value
        record[f"{key}_pct"] = pct_value
        total_minutes += minutes_value
    record["total_minutes"] = total_minutes
    effort_records.append(record)


def _compute_effort_bins(amplitudes: np.ndarray, fs: float | None) -> tuple[list[float], list[float]]:
    """Return absolute time (minutes) and relative time (%) spent inside each effort band.

    :param amplitudes: Percent-MVC signal covering a session.
    :param fs: Sampling frequency (Hz) to convert counts to minutes; can be ``None`` for raw counts.
    :returns: Tuple ``(minutes_per_band, percentages_per_band)`` with overflow bin appended.
    """

    arr = np.asarray(amplitudes).flatten()
    counts: List[int] = []
    for lower, upper, _label in EFFORT_BANDS:
        mask = (arr >= lower) & (arr < upper)
        if upper == EFFORT_BANDS[-1][1]:
            mask = (arr >= lower) & (arr <= upper)
        counts.append(int(np.count_nonzero(mask)))

    overflow_mask = arr > EFFORT_BANDS[-1][1]
    counts.append(int(np.count_nonzero(overflow_mask)))

    total_samples = float(arr.size) if arr.size else 1.0

    if fs and fs > 0:
        minutes = [count / fs / 60 for count in counts]
    else:
        minutes = [float(count) for count in counts]

    percentages = [(count / total_samples) * 100 for count in counts]
    return minutes, percentages


def _normalize_band_label(label: str) -> str:
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


def _write_effort_bins(records: Sequence[dict], output_root: Path) -> Path | None:
    """Persist the effort-bin table (if populated) and report its location to callers.

    :param records: Sequence of dict rows assembled via :func:`_record_effort_bins`.
    :param output_root: Folder that stores CSV artifacts.
    :returns: Path to the newly written CSV or ``None`` if ``records`` was empty.
    """

    if not records:
        return None
    path = output_root / "session_effort_bins.csv"
    df = pd.DataFrame(records)
    df.to_csv(path, index=False)
    print(f"[emg_pipeline] Effort-bin table written to {path} ({len(df)} rows)")
    return path
