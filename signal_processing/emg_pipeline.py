'''
EMG signal processing pipeline.

This module implements the end-to-end EMG processing pipeline, including:
- Loading day acquisitions
- Preprocessing (filtering, rectification, smoothing)
- MVC normalization
- Metric computation (APDF, Active APDF, rest metrics, session/daily/weekly aggregates)
- Visualization generation (APDF plots, histograms, envelope previews, rest vs active charts)

Uses Active APDF + Rest Time framework for physiologically meaningful metrics.
'''
# external imports
from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, cast, Tuple
import numpy as np
import pandas as pd

# internal imports
from constants import FS_MBAN, MBAN_LEFT, MBAN_RIGHT
from sensors.load.data_quality import FileQualityReport, create_file_quality_report, create_quality_issue
from sensors.load.dataset_loader import load_day_acquisitions
from sensors.metrics.emg_metrics import compute_session_metrics, compute_relative_intensity_bins, MIN_ACTIVE_DURATION_FOR_BASELINE_S
from signal_processing.emg_preprocessing import preprocess_emg, transfer_emg, bandpass_filter
from visualize.emg_visuals import plot_mvc_segments, plot_mvc_hybrid_diagnostics, plot_apdf, plot_histogram
from visualize.oh_profile_plots import generate_emg_plots_from_oh_profiles
from visualize.processing import plot_envelope
from .emg_metrics_export import (
    build_tables,
    persist_quality_report,
    write_tables,
)
from .emg_mvc import (
    _detect_mvc_segments,
    _robust_sigma,
    _select_quiet_baseline,
    detect_mvc_segments_tkeo,
    detect_mvc_segments_hybrid,
    pick_mvc,
)
from .emg_oh_helper import _save_emg_to_oh_profiles
from .emg_preprocessing import _compute_envelope, _extract_emg_mv, compute_tkeo_envelope, compute_mvc_peak_rms
from .emg_types import PreprocessConfig  # shared type definition

# Re-export PreprocessConfig for backwards compatibility
__all__ = ["run_emg_pipeline", "create_preprocess_config", "PreprocessConfig"]

def create_preprocess_config(
    fs: float = FS_MBAN,
    lowcut: float = 10.0,
    highcut: float = 450.0,
    smooth_sigma_ms: float = 50.0,
    envelope_preview_seconds: float = 30.0,
) -> PreprocessConfig:
    """Create a preprocessing configuration dictionary.

    :param fs: Sampling frequency in Hz (default: 1000 Hz for muscleBAN).
    :param lowcut: Bandpass filter low cutoff frequency in Hz.
    :param highcut: Bandpass filter high cutoff frequency in Hz.
    :param smooth_sigma_ms: Gaussian smoothing sigma in milliseconds.
    :param envelope_preview_seconds: Duration of envelope preview for plotting.
    :returns: Dict with all preprocessing parameters.
    """
    return {
        "fs": fs,
        "lowcut": lowcut,
        "highcut": highcut,
        "smooth_sigma_ms": smooth_sigma_ms,
        "envelope_preview_seconds": envelope_preview_seconds,
    }

# -------------------------------------------------------------------------------------------------------------------- #
# Main EMG Pipeline Functions
# -------------------------------------------------------------------------------------------------------------------- #
def run_emg_pipeline(
    day_descriptors: Sequence[dict],
    selected_sensors: Dict[str, List[str]],
    results_root: Path,
    plots_root: Path,
    config: PreprocessConfig | None = None,
    percentiles: Sequence[int] = (10, 50, 90),
    generate_visuals: bool = True,
    quality_log: Optional[List[FileQualityReport]] = None,
    oh_profiles_path: str | None = None,
    show_mvc_plots: bool = False,
    tkeo_segments: bool = False,
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
    :param oh_profiles_path: Optional path to OH profiles folder. If provided, EMG metrics
                             will be saved to each subject's OH profile JSON.
    :param tkeo_segments: Use TKEO-based MVC segmentation (enables debug plots even on guardrail fail).
    :returns: Dict that names each artifact (e.g. ``session_metrics``) and where it lives on disk.
    """

    if config is None:
        config = create_preprocess_config() 

    percentiles = tuple(percentiles)

    # Keep output folders ready so downstream helpers can assume they exist.
    results_root.mkdir(parents=True, exist_ok=True)
    plots_root.mkdir(parents=True, exist_ok=True)

    quality_records = quality_log if quality_log is not None else []

    session_metrics: List[dict] = []  # Accumulates metrics for all sessions processed
    session_signals: Dict[str, np.ndarray] = {}  # Cache signals for relative bin computation

    # Main per-day processing loop (first pass: compute metrics and cache signals)
    for day in day_descriptors:
        day_data = load_day_acquisitions(day, selected_sensors, quality_log=quality_records)
        if not day_data:
            print(f"[emg_pipeline] No data found for {day['subject_id']} on {day['date_label']}")
            continue
        day_metrics, day_signals = _process_day(
            day,
            day_data,
            config,
            percentiles,
            plots_root if generate_visuals else None,
            quality_log=quality_records,
            show_mvc_plots=show_mvc_plots,
            tkeo_segments=tkeo_segments,
        )
        session_metrics.extend(day_metrics)
        session_signals.update(day_signals)

    report_path = persist_quality_report(quality_records, results_root)

    if not session_metrics:
        print("[emg_pipeline] No session metrics were computed.")
        artifacts: Dict[str, Path] = {}
        if report_path:
            artifacts["quality_report"] = report_path
        return artifacts

    # Second pass: compute relative intensity bins using weekly baseline
    session_metrics = _add_relative_intensity_bins(
        session_metrics, session_signals, config["fs"]
    )

    tables = build_tables(session_metrics)
    write_tables(tables, results_root)

    # Save to OH profiles if path is provided
    if oh_profiles_path:
        session_df = tables["session_metrics"]
        daily_df = tables["daily_metrics"]
        weekly_df = tables.get("weekly_metrics", pd.DataFrame())
        _save_emg_to_oh_profiles(session_df, daily_df, weekly_df, oh_profiles_path)

        # Generate post-JSON visualizations (effort grids, stacks, metric trends)
        # These plots read from the persisted OH profile JSON files
        if generate_visuals:
            subject_ids = session_df["subject_id"].unique().tolist()
            generate_emg_plots_from_oh_profiles(oh_profiles_path, subject_ids, plots_root)

    artifacts = {
        "session_metrics": results_root / "session_metrics.csv",
        "daily_metrics": results_root / "daily_metrics.csv",
    }

    if report_path is not None:
        artifacts["quality_report"] = report_path

    return artifacts


# -------------------------------------------------------------------------------------------------------------------- #
# Relative Intensity Bins (Second Pass)
# -------------------------------------------------------------------------------------------------------------------- #

def _add_relative_intensity_bins(
    session_metrics: List[dict],
    session_signals: Dict[str, np.ndarray],
    fs: float,
) -> List[dict]:
    """
    Add relative intensity bins to session metrics using weekly baseline thresholds.
    
    This implements the second pass of the Active APDF + Rest Time framework:
    1. Compute weekly Active APDF baseline (P10, P50, P90) for each subject/side
    2. For each session, bin the active samples relative to that baseline
    
    Bins are:
    - Below usual: active EMG < weekly P10
    - Typical-low: weekly P10 to P50
    - Typical-high: weekly P50 to P90
    - High for you: > weekly P90
    
    :param session_metrics: List of session metric dicts from first pass.
    :param session_signals: Dict mapping session keys to %MVC signal arrays.
    :param fs: Sampling frequency in Hz.
    :returns: Updated session_metrics list with relative bin columns added.
    """
    # Convert to DataFrame for easier aggregation
    df = pd.DataFrame(session_metrics)
    
    # Compute weekly baseline (Active APDF P10, P50, P90) for each subject/side
    # Uses duration-weighted average across all sessions
    weekly_baseline = {}
    for (subject_id, side), group in df.groupby(["subject_id", "side"]):
        # Sum active duration to check minimum requirement
        total_active_duration = group["active_duration_s"].sum()
        
        if total_active_duration < MIN_ACTIVE_DURATION_FOR_BASELINE_S:
            # Not enough active time for stable baseline - skip relative binning
            print(
                f"[emg_pipeline] Insufficient active time for {subject_id} {side}: "
                f"{total_active_duration:.0f}s < {MIN_ACTIVE_DURATION_FOR_BASELINE_S}s minimum"
            )
            continue
        
        # Duration-weighted average of Active APDF percentiles
        durations = np.asarray(group["duration_s"].values)
        total_duration = durations.sum()
        
        if total_duration > 0:
            p10 = np.average(np.asarray(group["active_apdf_p10"].values), weights=durations)
            p50 = np.average(np.asarray(group["active_apdf_p50"].values), weights=durations)
            p90 = np.average(np.asarray(group["active_apdf_p90"].values), weights=durations)
        else:
            p10 = group["active_apdf_p10"].mean()
            p50 = group["active_apdf_p50"].mean()
            p90 = group["active_apdf_p90"].mean()
        
        weekly_baseline[(subject_id, side)] = {
            "p10": p10,
            "p50": p50,
            "p90": p90,
        }
    
    # Add relative bins to each session
    for metrics in session_metrics:
        subject_id = metrics["subject_id"]
        side = metrics["side"]
        date = metrics["date"]
        session_label = metrics["session_label"]
        
        # Look up baseline
        baseline = weekly_baseline.get((subject_id, side))
        if baseline is None:
            # No baseline available - set bins to None
            metrics["bin_below_usual_pct"] = None
            metrics["bin_typical_low_pct"] = None
            metrics["bin_typical_high_pct"] = None
            metrics["bin_high_for_you_pct"] = None
            continue
        
        # Look up cached signal
        signal_key = f"{subject_id}|{side}|{date}|{session_label}"
        signal = session_signals.get(signal_key)
        
        if signal is None:
            # Signal not cached (shouldn't happen, but handle gracefully)
            metrics["bin_below_usual_pct"] = None
            metrics["bin_typical_low_pct"] = None
            metrics["bin_typical_high_pct"] = None
            metrics["bin_high_for_you_pct"] = None
            continue
        
        # Compute relative intensity bins for this session
        bin_result = compute_relative_intensity_bins(
            signal,
            fs,
            weekly_active_p10=baseline["p10"],
            weekly_active_p50=baseline["p50"],
            weekly_active_p90=baseline["p90"],
        )
        
        # Add bin percentages to metrics
        metrics["bin_below_usual_pct"] = bin_result["bin_below_usual_pct"]
        metrics["bin_typical_low_pct"] = bin_result["bin_typical_low_pct"]
        metrics["bin_typical_high_pct"] = bin_result["bin_typical_high_pct"]
        metrics["bin_high_for_you_pct"] = bin_result["bin_high_for_you_pct"]
    
    return session_metrics


# -------------------------------------------------------------------------------------------------------------------- #
# Day Processing Functions
# -------------------------------------------------------------------------------------------------------------------- #
def _process_day(
    day: dict,
    day_data: Dict[str, Dict[str, pd.DataFrame]],
    config: PreprocessConfig,
    percentiles: Sequence[int],
    plots_root: Optional[Path],
    quality_log: Optional[List[FileQualityReport]] = None,
    show_mvc_plots: bool = False,
    tkeo_segments: bool = False,
) -> Tuple[List[dict], Dict[str, np.ndarray]]:
    """Compute per-session metrics and optional visuals for a single calendar day.

    :param day: Descriptor that points to folders and metadata (subject, group, MAC addresses).
    :param day_data: Nested dict shaped ``device -> session_label -> DataFrame`` from the loader.
    :param config: Shared preprocessing configuration for filtering/enveloping.
    :param percentiles: Percentiles used when building the APDF summary record.
    :param plots_root: Root path where visuals should be written, or ``None`` to skip.
    :param quality_log: Optional list of FileQualityReport entries to append guardrail failures.
    :param show_mvc_plots: If True, show MVC debug plots while running.
    :param tkeo_segments: If True, run TKEO-based MVC segmentation and still plot on guardrail failure.
    :returns: Tuple of:
        - List of metric dictionaries that become rows in ``session_metrics.csv``.
        - Dict mapping session keys (subject_id|side|date|session) to %MVC signal arrays
          for later relative intensity bin computation.
    """

    percentiles = tuple(percentiles)

    day_metrics: List[dict] = []
    day_signals: Dict[str, np.ndarray] = {}  # Cache signals for relative bin computation

    for device_label, acquisitions in day_data.items():
        mvc_label, mvc_df = pick_mvc(acquisitions) 
        if mvc_df is None:
            print(f"[emg_pipeline] Missing MVC for {day['subject_id']} {device_label} on {day['date_label']}")
            continue
        try:
            # Extract raw EMG in mV for MVC peak computation
            mvc_raw_mv = _extract_emg_mv(mvc_df)
            # preprocess the MVC recording to get its envelope (for segment detection/plotting)
            mvc_env = cast(np.ndarray, _compute_envelope(mvc_df, config)) # cast is used to inform type checker
        except ValueError as exc:
            print(f"[emg_pipeline] MVC preprocessing error ({day['subject_id']} {device_label}): {exc}")
            continue
        plot_signal: Optional[np.ndarray] = None
        threshold_val: Optional[float] = None
        title_suffix = ""
        debug_info: Optional[dict] = None
        raw_mv: Optional[np.ndarray] = None

        fallback_used = False

        if tkeo_segments:
            # Hybrid MVC segment detection with evidence-driven threshold selection
            raw_mv = _extract_emg_mv(mvc_df)
            # Use 1s minimum segment length (aligned with guardrail requirement)
            min_mvc_length = int(config["fs"])  # 1 second minimum
            segments, debug_info = detect_mvc_segments_hybrid(
                raw_mv,
                config["fs"],
                window_ms=50.0,
                baseline_window_s=0.5,
                k_mad=6.0,
                min_length_samples=min_mvc_length,
            )
            if plots_root:
                # Use TKEO envelope for visualization
                plot_signal = compute_tkeo_envelope(
                    raw_mv,
                    config["fs"],
                    smooth_cutoff_hz=50.0,
                )
                # For visualization, derive threshold from the detected segments
                # The log-space threshold doesn't translate directly to linear envelope
                if segments:
                    # Use minimum envelope value across detected segment starts as threshold
                    env_at_segments = [plot_signal[s[0]] for s in segments if s[0] < len(plot_signal)]
                    threshold_val = min(env_at_segments) * 0.9 if env_at_segments else 0.0
                else:
                    # Fallback: use percentile
                    threshold_val = float(np.percentile(plot_signal, 70))
                method_used = debug_info["threshold_method"]
                title_suffix = f"(hybrid-{method_used})"

            # Fallback to envelope-based detector if hybrid found nothing
            if not segments:
                segments = _detect_mvc_segments(
                    mvc_env,
                    config["fs"],
                    threshold_frac=0.2,
                    min_length_samples=int(config["fs"]),
                )
                fallback_used = True
                if plots_root:
                    plot_signal = mvc_env
                    threshold_val = 0.2 * float(np.max(mvc_env))
                    title_suffix = "(envelope fallback)"
        else:
            # Validate MVC recording: require two or more segments >= 1s each above a relative threshold
            segments = _detect_mvc_segments(
                mvc_env,
                config["fs"],
                threshold_frac=0.2,
                min_length_samples=int(config["fs"]),
            )
            if plots_root:
                plot_signal = mvc_env
                threshold_val = 0.2 * float(np.max(mvc_env))
                title_suffix = "(envelope)"

        if len(segments) < 2:
            print(
                f"[emg_pipeline] MVC segment check failed ({day['subject_id']} {device_label}): "
                f"expected 2 segments >=1s, found {len(segments)}"
            )
            if quality_log is not None:
                issue = create_quality_issue(
                    "mvc-guardrail-fail",
                    f"MVC segmentation found {len(segments)} segment(s) (<2) for {device_label} on {day['date_label']} — skipping side."
                )
                synthetic_path = Path(f"MVC/{day['subject_id']}_{day['date_label']}_{device_label}.mvc")
                quality_log.append(
                    create_file_quality_report(
                        file_path=synthetic_path,
                        issues=[issue],
                        rows=len(mvc_env),
                        columns=1,
                        device_label=device_label,
                        acquisition_label=mvc_label,
                    )
                )
            if plots_root and plot_signal is not None and threshold_val is not None:
                subject_id = day.get("subject_id", "unknown")
                date_label = day.get("date_label", "unknown_date")
                device_lower = device_label.lower()
                if MBAN_LEFT.lower() in device_lower:
                    side = "left"
                elif MBAN_RIGHT.lower() in device_lower:
                    side = "right"
                else:
                    side = device_label

                mvc_dir = plots_root / subject_id / date_label / side / "MVC"
                mvc_dir.mkdir(parents=True, exist_ok=True)

                # Determine method name for legend
                if tkeo_segments:
                    if fallback_used:
                        method_name = "envelope fallback"
                    else:
                        method_name = f"hybrid-{(debug_info or {}).get('threshold_method', 'otsu')}"
                else:
                    method_name = "envelope"

                plot_mvc_segments(
                    plot_signal,
                    segments,
                    config["fs"],
                    float(threshold_val),
                    mvc_dir / "mvc_segments_failed.svg",
                    f"MVC segmentation – {subject_id} {side} {date_label} {title_suffix} [FAILED: {len(segments)} segments]",
                    method=method_name,
                    show=show_mvc_plots,
                )

                # Also generate detailed diagnostic plot for hybrid method
                if tkeo_segments and not fallback_used and debug_info is not None and raw_mv is not None:
                    plot_mvc_hybrid_diagnostics(
                        raw_mv,
                        segments,
                        debug_info,
                        config["fs"],
                        mvc_dir / "mvc_diagnostics_failed.png",
                        title=f"MVC Diagnostics – {subject_id} {side} {date_label} [FAILED]",
                        show=show_mvc_plots,
                    )
            continue

        # Compute MVC peak using peak-centered RMS on rectified signal (no smoothing attenuation)
        mvc_peak = compute_mvc_peak_rms(
            mvc_raw_mv,
            config["fs"],
            lowcut=config["lowcut"],
            highcut=config["highcut"],
            window_ms=250.0,  # 250ms RMS window centered on peak
        )
        if mvc_peak <= 0:
            print(f"[emg_pipeline] MVC peak <= 0 for {day['subject_id']} {device_label}")
            continue

        # Optional visualization of MVC segmentation for QA (only on pass)
        if plots_root and plot_signal is not None and threshold_val is not None:
            subject_id = day.get("subject_id", "unknown")
            date_label = day.get("date_label", "unknown_date")
            device_lower = device_label.lower()
            if MBAN_LEFT.lower() in device_lower:
                side = "left"
            elif MBAN_RIGHT.lower() in device_lower:
                side = "right"
            else:
                side = device_label

            mvc_dir = plots_root / subject_id / date_label / side / "MVC"

            # Determine method name for legend
            if tkeo_segments:
                if fallback_used:
                    method_name = "envelope fallback"
                else:
                    method_name = f"hybrid-{(debug_info or {}).get('threshold_method', 'otsu')}"
            else:
                method_name = "envelope"

            plot_mvc_segments(
                plot_signal,
                segments,
                config["fs"],
                float(threshold_val),
                mvc_dir / "mvc_segments.svg",
                f"MVC segmentation – {subject_id} {side} {date_label} {title_suffix}",
                method=method_name,
                show=show_mvc_plots,
            )

            # Also generate detailed diagnostic plot for hybrid method
            if tkeo_segments and not fallback_used and debug_info is not None and raw_mv is not None:
                plot_mvc_hybrid_diagnostics(
                    raw_mv,
                    segments,
                    debug_info,
                    config["fs"],
                    mvc_dir / "mvc_diagnostics.png",
                    title=f"MVC Diagnostics – {subject_id} {side} {date_label}",
                    show=show_mvc_plots,
                )

        for session_label, session_df in acquisitions.items():
            if session_label == mvc_label:
                continue
            try:
                envelope_mv, raw_mv = _compute_envelope(session_df, config, return_raw=True)
            except ValueError as exc:
                print(f"[emg_pipeline] Session preprocessing error ({day['subject_id']} {session_label}): {exc}")
                continue

            # Normalize against the MVC peak so that downstream plots and metrics work in %MVC space.
            percent_signal = (envelope_mv / mvc_peak) * 100.0
            metadata = _build_metadata(day, device_label, session_label, config["fs"])
            side_label = metadata["side"]
            metrics, apdf = compute_session_metrics(percent_signal, config["fs"], metadata, percentiles)
            metrics["mvc_peak"] = mvc_peak  # Add MVC reference value (in mV)
            day_metrics.append(metrics)

            # Cache signal for relative bin computation (keyed by unique session identifier)
            signal_key = f"{day['subject_id']}|{side_label}|{day['date_label']}|{session_label}"
            day_signals[signal_key] = percent_signal

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

    # Note: Day-level visualizations (effort grid/stacks) are now generated
    # after OH profile JSON is written, using visualize.oh_profile_plots module.
    
    return day_metrics, day_signals

# -------------------------------------------------------------------------------------------------------------------- #
# Helper Functions
# -------------------------------------------------------------------------------------------------------------------- #  
def _build_metadata(day: dict, device_label: str, session_label: str, fs: float) -> dict:
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
        mac = day["left_mac"]
    elif MBAN_RIGHT.lower() in device_lower:
        side = "right"
        mac = day["right_mac"]
    else:
        side = device_label
        mac = ""

    return {
        "subject_id": day["subject_id"],
        "group": day["group"],
        "device_num": day["device_num"],
        "side": side,
        "device_label": device_label,
        "mac_address": mac,
        "date": day["date_label"],
        "session_label": session_label,
        "fs_hz": fs,
    }


def _save_session_visuals(
    plots_root: Path,
    day: dict,
    device_label: str,
    session_label: str,
    raw_mv: Optional[np.ndarray],
    envelope_mv: np.ndarray,
    percent_signal: np.ndarray,
    apdf: dict,
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
    :param apdf: Dictionary containing APDF arrays + percentile lookups (keys: probs, amplitudes, percentiles).
    :param config: Preprocessing configuration (needed for preview duration).
    :param metadata: Extra context such as ``side`` used in folder naming.
    """

    side = metadata.get("side", device_label)
    session_dir = plots_root / day["subject_id"] / day["date_label"] / side / session_label
    session_dir.mkdir(parents=True, exist_ok=True)
    title = f"{day['subject_id']} | {side} | {day['date_label']} {session_label}"
    plot_apdf(apdf, session_dir / f"{session_label}_apdf.png", title)
    plot_histogram(apdf["amplitudes"], session_dir / f"{session_label}_hist.png", f"Histogram – {title}")

    if raw_mv is not None:
        preview_samples = min(len(raw_mv), int(config["fs"] * config["envelope_preview_seconds"]))
        if preview_samples > 0:
            raw_series = pd.Series(raw_mv[:preview_samples])
            env_series = pd.Series(envelope_mv[:preview_samples])
            plot_envelope(raw_series, env_series, f"{session_label}_envelope", str(session_dir))


# Note: Day-level visuals (_save_day_visuals) and metric trend plots (_plot_metric_trends)
# have been moved to visualize/oh_profile_plots.py. They are now generated after writing
# metrics to OH profile JSON files, reading from the persisted data.
# Table-building, CSV export, and quality-report helpers have been consolidated in
# signal_processing/emg_metrics_export.py.
