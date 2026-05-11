"""
EMG Signal Processing Pipeline.

This module implements the end-to-end EMG processing pipeline, including:
- Loading day acquisitions
- Preprocessing (filtering, rectification, smoothing)
- MVC normalization
- Metric computation (APDF, Active APDF, rest metrics, session/daily/weekly aggregates)
- Visualization generation (APDF plots, histograms, envelope previews, rest vs active charts)

Uses Active APDF + Rest Time framework for physiologically meaningful metrics.

Architecture
------------
The pipeline uses a two-pass approach:
1. **First pass**: Process each day/session, compute metrics, cache signals
2. **Second pass**: Compute weekly baselines and relative intensity bins

Quality checks are applied at multiple stages:
- Loading: ADC saturation, short recordings
- MVC: Faulty sensor, PSD noise, segment validation
- Session: Faulty sensor, PSD noise

All rejected sessions are logged to a quality report CSV with diagnostic plots.
"""
# -------------------------------------------------------------------------------------------------------------------- #
# Imports
# -------------------------------------------------------------------------------------------------------------------- #
from __future__ import annotations

# Standard library
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, cast

from OH_profile.constants import SESSION_KEY

# Type alias for preprocessing configuration dictionary.
# Keys typically include: fs, lowcut, highcut, smooth_sigma_ms, envelope_preview_seconds
PreprocessConfig = Dict[str, Any]

# Third-party
import numpy as np
import pandas as pd

# Internal - constants
from constants import FS_MBAN, MBAN_LEFT, MBAN_RIGHT

# Internal - data loading and quality
from sensors.load.data_quality import FileQualityReport, create_file_quality_report, create_quality_issue
from sensors.load.dataset_loader import load_day_acquisitions
from sensors.process.emg_quality_analysis import (
    assess_mvc_signal_quality,
    detect_adc_saturation,
    detect_psd_noise,
    is_faulty_mban,
    save_adc_saturation_plot,
    save_quality_assessment_plot,
)

# Internal - metrics computation
from sensors.metrics.emg_metrics import (
    MIN_ACTIVE_DURATION_FOR_BASELINE_S,
    compute_relative_intensity_bins,
    compute_session_metrics,
)
from sensors.metrics.emg_output import (
    build_tables,
    export_mvc_quality_summary,
    persist_quality_report,
    write_tables,
)

# Internal - signal processing
from sensors.process.emg_mvc import _detect_mvc_segments, detect_mvc_segments_hybrid, pick_mvc
from sensors.process.emg_preprocessing import (
    _compute_envelope,
    _extract_emg_mv,
    bandpass_filter,
    compute_mvc_peak_rms,
    compute_tkeo_envelope,
    preprocess_emg,
    transfer_emg,
)

# Internal - visualization
from sensors.visualize.emg_research import (
    generate_session_timeline_from_signal,
    plot_apdf,
    plot_envelope,
    plot_histogram,
    plot_mvc_hybrid_diagnostics,
    plot_mvc_segments,
)
from sensors.visualize.emg_oh import generate_emg_plots_from_oh_profiles

# Internal - OH profile persistence
from OH_profile.emg_oh_helper import save_emg_to_oh_profiles


# -------------------------------------------------------------------------------------------------------------------- #
# Module API
# -------------------------------------------------------------------------------------------------------------------- #
__all__ = ["run_emg_pipeline", "create_preprocess_config", "PreprocessConfig"]

def create_preprocess_config(
    fs: float = FS_MBAN,
    lowcut: float = 10.0,
    highcut: float = 450.0,
    smooth_sigma_ms: float = 50.0,
    envelope_preview_seconds: float = 90.0,
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
        config = create_preprocess_config() # define default paraemeters if none provided   

    percentiles = tuple(percentiles)

    # Keep output folders ready so downstream helpers can assume they exist.
    results_root.mkdir(parents=True, exist_ok=True)
    plots_root.mkdir(parents=True, exist_ok=True)

    quality_records = quality_log if quality_log is not None else []

    session_metrics: List[dict] = []  # Accumulates metrics for all sessions processed
    session_signals: Dict[str, np.ndarray] = {}  # Cache signals for relative bin computation

    # Main per-day processing loop (first pass: compute metrics and cache signals)
    for day in day_descriptors:

        # inform user
        print(f'Processing subject: {day["subject_id"]}')

        # Track quality_records length before loading to identify new rejections
        records_before_load = len(quality_records)
        
        day_data, session_ids_dict = load_day_acquisitions(day, selected_sensors, quality_log=quality_records)
        
        # Generate diagnostic plots for any sessions rejected during loading (e.g., ADC saturation)
        if generate_visuals and len(quality_records) > records_before_load:
            new_records = quality_records[records_before_load:]
            _generate_plots_for_loading_rejections(
                new_records,
                plots_root,
                day['subject_id'],
                day['date_label'],
            )
        
        if not day_data:
            print(f"[emg_pipeline] No data found for {day['subject_id']} on {day['date_label']}")
            continue
        day_metrics, day_signals = _process_day(
            day,
            day_data,
            session_ids_dict,
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

    # Second pass: compute relative intensity bins using weekly baseline + generate timeline plots
    session_metrics = _add_relative_intensity_bins(
        session_metrics,
        session_signals,
        config["fs"],
        plots_root=plots_root if generate_visuals else None,
        generate_timelines=generate_visuals,
    )

    tables = build_tables(session_metrics)
    write_tables(tables, results_root)
    export_mvc_quality_summary(tables, results_root)

    # Save to OH profiles if path is provided
    if oh_profiles_path:
        session_df = tables["session_metrics"]
        daily_df = tables["daily_metrics"]
        weekly_df = tables.get("weekly_metrics", pd.DataFrame())
        save_emg_to_oh_profiles(session_df, daily_df, weekly_df, oh_profiles_path)

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
# Relative Intensity Bins (Second Pass) + Timeline Generation
# -------------------------------------------------------------------------------------------------------------------- #

def _add_relative_intensity_bins(
    session_metrics: List[dict],
    session_signals: Dict[str, np.ndarray],
    fs: float,
    plots_root: Optional[Path] = None,
    generate_timelines: bool = True,
) -> List[dict]:
    """
    Add relative intensity bins to session metrics using weekly baseline thresholds.
    Optionally generate timeline plots for each session.
    
    This implements the second pass of the Active APDF + Rest Time framework:
    1. Compute weekly Active APDF baseline (P10, P50, P90) for each subject/side
    2. For each session, bin the active samples relative to that baseline
    3. Generate timeline plots showing EMG trace with intensity zone shading
    
    Bins are:
    - Below usual: active EMG < weekly P10
    - Typical-low: weekly P10 to P50
    - Typical-high: weekly P50 to P90
    - High for you: > weekly P90
    
    :param session_metrics: List of session metric dicts from first pass.
    :param session_signals: Dict mapping session keys to %MVC signal arrays.
    :param fs: Sampling frequency in Hz.
    :param plots_root: Root directory for plots (if None, no timelines generated).
    :param generate_timelines: Whether to generate timeline plots.
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
    
    # Track timeline generation count
    timeline_count = 0
    
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
        
        # Generate timeline plot if requested
        if generate_timelines and plots_root is not None:
            date_folder = _convert_date_to_dd_mm_yyyy(date)
            timeline_path = (
                plots_root / subject_id / date_folder / side / session_label / f"{session_label}_timeline.png"
            )
            result = generate_session_timeline_from_signal(
                percent_signal=signal,
                output_path=timeline_path,
                subject_id=subject_id,
                date=date,
                session_label=session_label,
                side=side,
                fs=fs,
                weekly_p10=baseline["p10"],
                weekly_p50=baseline["p50"],
                weekly_p90=baseline["p90"],
            )
            if result:
                timeline_count += 1
    
    if timeline_count > 0:
        print(f"[emg_pipeline] Generated {timeline_count} session timeline plots")
    
    return session_metrics


# -------------------------------------------------------------------------------------------------------------------- #
# Day Processing Helper Functions
# -------------------------------------------------------------------------------------------------------------------- #

def _get_side_from_device(device_label: str) -> str:
    """Extract 'left' or 'right' from device label."""
    device_lower = device_label.lower()
    if MBAN_LEFT.lower() in device_lower:
        return "left"
    elif MBAN_RIGHT.lower() in device_lower:
        return "right"
    return device_label


def _save_qa_plot(
    plots_root: Path,
    plot_type: str,
    signal: np.ndarray,
    subject_id: str,
    side: str,
    date_label: str,
    session_label: str,
    acquisition_type: str,
    fs: float,
) -> None:
    """Save a QA diagnostic plot to the qa_flagged folder.
    
    :param plots_root: Root directory for plots.
    :param plot_type: Either 'adc_saturation' or 'psd_noise'.
    :param signal: The signal data (raw_adc for ADC, filtered for PSD).
    :param subject_id: Subject identifier.
    :param side: 'left' or 'right'.
    :param date_label: Date in DD-MM-YYYY format.
    :param session_label: Session or MVC label.
    :param acquisition_type: 'mvc' or 'session'.
    :param fs: Sampling frequency.
    """
    qa_plots_dir = plots_root / "qa_flagged"
    qa_plots_dir.mkdir(parents=True, exist_ok=True)
    
    if plot_type == "adc_saturation":
        save_adc_saturation_plot(
            raw_adc=signal,
            output_dir=str(qa_plots_dir),
            subject_id=subject_id,
            side=side,
            session_label=session_label,
            acquisition_type=acquisition_type,
            fs=fs,
        )
    elif plot_type == "psd_noise":
        save_quality_assessment_plot(
            emg_filtered=signal,
            output_dir=str(qa_plots_dir),
            subject_id=subject_id,
            side=side,
            session_label=session_label,
            acquisition_type=acquisition_type,
            fs=fs,
        )


def _log_quality_issue(
    quality_log: List[FileQualityReport],
    issues: List[dict],
    subject_id: str,
    date_label: str,
    device_label: str,
    acquisition_label: Optional[str],
    signal_length: int,
    is_mvc: bool = False,
) -> None:
    """Append a quality report to the log.
    
    :param quality_log: List to append the report to.
    :param issues: List of quality issue dicts.
    :param subject_id: Subject identifier.
    :param date_label: Date label from raw data.
    :param device_label: Device label (e.g., 'mBAN_left').
    :param acquisition_label: Session or MVC label (can be None for MVC).
    :param signal_length: Number of samples in the signal.
    :param is_mvc: Whether this is an MVC recording.
    """
    acq_label = acquisition_label or "MVC"  # Default to "MVC" if None
    if is_mvc:
        synthetic_path = Path(f"MVC/{subject_id}_{date_label}_{device_label}.mvc")
    else:
        synthetic_path = Path(f"sessions/{subject_id}_{date_label}_{device_label}_{acq_label}.emg")
    
    quality_log.append(
        create_file_quality_report(
            file_path=synthetic_path,
            issues=issues,
            rows=signal_length,
            columns=1,
            device_label=device_label,
            acquisition_label=acq_label,
        )
    )


def _plot_mvc_segments_with_diagnostics(
    plots_root: Path,
    subject_id: str,
    date_label: str,
    side: str,
    plot_signal: np.ndarray,
    segments: List[Tuple[int, int]],
    threshold_val: float,
    fs: float,
    title_suffix: str,
    method_name: str,
    failed: bool = False,
    hybrid_debug_info: Optional[dict] = None,
    raw_mv: Optional[np.ndarray] = None,
    show: bool = False,
) -> None:
    """Save MVC segment visualization and optional hybrid diagnostics.
    
    :param plots_root: Root directory for plots.
    :param subject_id: Subject identifier.
    :param date_label: Date in DD-MM-YYYY format.
    :param side: 'left' or 'right'.
    :param plot_signal: Signal to plot (envelope or TKEO).
    :param segments: List of (start, end) segment tuples.
    :param threshold_val: Threshold value used for detection.
    :param fs: Sampling frequency.
    :param title_suffix: Suffix for plot title (e.g., '(hybrid: baseline)').
    :param method_name: Method name for legend.
    :param failed: Whether segmentation failed (affects filename and title).
    :param hybrid_debug_info: Optional debug info for hybrid diagnostics plot.
    :param raw_mv: Raw signal in mV (needed for hybrid diagnostics).
    :param show: Whether to display the plot interactively.
    """
    mvc_dir = plots_root / subject_id / date_label / side / "MVC"
    mvc_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine filenames based on success/failure
    if failed:
        segments_filename = "mvc_segments_failed.png"
        diagnostics_filename = "mvc_hybrid_diagnostics_failed.png"
        title_prefix = f"MVC segmentation – {subject_id} {side} {date_label} {title_suffix} [FAILED: {len(segments)} segments]"
        diag_title = f"MVC Hybrid Diagnostics – {subject_id} {side} {date_label} [FAILED]"
    else:
        segments_filename = "mvc_segments.png"
        diagnostics_filename = "mvc_hybrid_diagnostics.png"
        title_prefix = f"MVC segmentation – {subject_id} {side} {date_label} {title_suffix}"
        diag_title = f"MVC Hybrid Diagnostics – {subject_id} {side} {date_label}"
    
    plot_mvc_segments(
        plot_signal,
        segments,
        fs,
        float(threshold_val),
        mvc_dir / segments_filename,
        title_prefix,
        method=method_name,
        show=show,
    )
    
    # Plot hybrid diagnostics if available
    if hybrid_debug_info is not None and raw_mv is not None:
        plot_mvc_hybrid_diagnostics(
            raw_mv,
            segments,
            hybrid_debug_info,
            fs,
            mvc_dir / diagnostics_filename,
            title=diag_title,
            show=show,
        )


# -------------------------------------------------------------------------------------------------------------------- #
# Day Processing Main Function
# -------------------------------------------------------------------------------------------------------------------- #
def _process_day(
    day: dict,
    day_data: Dict[str, Dict[str, pd.DataFrame]],
    session_ids_dict: Dict[str, str],
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
    :param session_ids_dict: Dictionary containing info on which acquisition time corresponds to which session.
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
            # Extract raw EMG in mV for MVC peak computation (also get raw ADC for saturation check)
            mvc_raw_mv, mvc_raw_adc = _extract_emg_mv(mvc_df, return_raw_adc=True)
            # preprocess the MVC recording to get its envelope (for segment detection/plotting)
            mvc_env = cast(np.ndarray, _compute_envelope(mvc_df, config)) # cast is used to inform type checker
        except ValueError as exc:
            print(f"[emg_pipeline] MVC preprocessing error ({day['subject_id']} {device_label}): {exc}")
            continue

        # --- MVC Quality Checks ---
        side = _get_side_from_device(device_label)
        date_label_qa = _convert_date_to_dd_mm_yyyy(day["date_label"])
        
        # Check for ADC saturation/clipping first
        mvc_saturation = detect_adc_saturation(mvc_raw_adc) if mvc_raw_adc is not None else None
        if mvc_saturation:
            print(f"[emg_pipeline] MVC ADC saturation ({day['subject_id']} {device_label}): {mvc_saturation['message']}")
            if plots_root and mvc_raw_adc is not None:
                _save_qa_plot(plots_root, "adc_saturation", mvc_raw_adc, day["subject_id"], side, date_label_qa, f"{date_label_qa}_MVC", "mvc", config["fs"])
            if quality_log is not None:
                _log_quality_issue(quality_log, [mvc_saturation], day["subject_id"], day["date_label"], device_label, mvc_label, len(mvc_raw_mv), is_mvc=True)
            continue  # Skip this side entirely

        # Check for faulty sensor (all values same sign)
        faulty_issue = is_faulty_mban(mvc_raw_mv)
        if faulty_issue:
            print(f"[emg_pipeline] MVC faulty sensor ({day['subject_id']} {device_label}): {faulty_issue['message']}")
            if quality_log is not None:
                _log_quality_issue(quality_log, [faulty_issue], day["subject_id"], day["date_label"], device_label, mvc_label, len(mvc_raw_mv), is_mvc=True)
            continue  # Skip this side entirely
        
        # Check MVC signal quality (duration, amplitude)
        mvc_issues = assess_mvc_signal_quality(mvc_raw_mv, config["fs"])
        if mvc_issues:
            has_fatal = any(iss["code"] in ("mvc-too-short", "mvc-low-amplitude", "mvc-flat-signal") 
                          for iss in mvc_issues)
            if has_fatal:
                print(f"[emg_pipeline] MVC quality failed ({day['subject_id']} {device_label}): "
                      f"{'; '.join(iss['message'] for iss in mvc_issues)}")
                if quality_log is not None:
                    _log_quality_issue(quality_log, mvc_issues, day["subject_id"], day["date_label"], device_label, mvc_label, len(mvc_raw_mv), is_mvc=True)
                continue  # Skip this side entirely
        
        # Check for PSD noise in MVC (after bandpass filter)
        mvc_filtered = bandpass_filter(mvc_raw_mv - np.mean(mvc_raw_mv), config["fs"])
        is_mvc_noisy, psd_issues = detect_psd_noise(mvc_filtered, config["fs"])
        if is_mvc_noisy:
            print(f"[emg_pipeline] MVC noise detected ({day['subject_id']} {device_label}): "
                  f"{'; '.join(iss['message'] for iss in psd_issues)}")
            if plots_root:
                _save_qa_plot(plots_root, "psd_noise", mvc_filtered, day["subject_id"], side, date_label_qa, f"{date_label_qa}_MVC", "mvc", config["fs"])
            if quality_log is not None:
                _log_quality_issue(quality_log, psd_issues, day["subject_id"], day["date_label"], device_label, mvc_label, len(mvc_raw_mv), is_mvc=True)
            continue  # Skip this side entirely

        plot_signal: Optional[np.ndarray] = None
        threshold_val: Optional[float] = None
        title_suffix = ""
        raw_mv: Optional[np.ndarray] = None
        hybrid_debug_info: Optional[dict] = None

        fallback_used = False

        if tkeo_segments:
            # Hybrid MVC segment detection (multi-threshold scoring, quality-focused)
            raw_mv = cast(np.ndarray, _extract_emg_mv(mvc_df))
            min_mvc_length = int(config["fs"])  # 1 second minimum
            segments, debug_info = detect_mvc_segments_hybrid(
                raw_mv,
                config["fs"],
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
                if segments:
                    env_at_segments = [plot_signal[s[0]] for s in segments if s[0] < len(plot_signal)]
                    threshold_val = min(env_at_segments) * 0.9 if env_at_segments else 0.0
                else:
                    threshold_val = float(np.percentile(plot_signal, 70))
                title_suffix = f"(hybrid: {debug_info.get('threshold_method', 'unknown')})"
                
                # Store debug_info for hybrid diagnostics plot
                hybrid_debug_info = debug_info

            # Fallback to envelope-based detector if TKEO found nothing
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
                _log_quality_issue(quality_log, [issue], day["subject_id"], day["date_label"], device_label, mvc_label, len(mvc_env), is_mvc=True)
            if plots_root and plot_signal is not None and threshold_val is not None:
                # Determine method name for legend
                method_name = "envelope fallback" if (tkeo_segments and fallback_used) else ("TKEO" if tkeo_segments else "envelope")
                _plot_mvc_segments_with_diagnostics(
                    plots_root, day["subject_id"], date_label_qa, side, plot_signal, segments,
                    threshold_val, config["fs"], title_suffix, method_name, failed=True,
                    hybrid_debug_info=hybrid_debug_info, raw_mv=raw_mv, show=show_mvc_plots
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
            # Determine method name for legend
            method_name = "envelope fallback" if (tkeo_segments and fallback_used) else ("TKEO" if tkeo_segments else "envelope")
            _plot_mvc_segments_with_diagnostics(
                plots_root, day["subject_id"], date_label_qa, side, plot_signal, segments,
                threshold_val, config["fs"], title_suffix, method_name, failed=False,
                hybrid_debug_info=hybrid_debug_info, raw_mv=raw_mv, show=show_mvc_plots
            )

        for session_label, session_df in acquisitions.items():
            if session_label == mvc_label:
                continue
            try:
                result = _compute_envelope(session_df, config, return_raw=True, return_raw_adc=True)
                envelope_mv, raw_mv, raw_adc = cast(Tuple[np.ndarray, np.ndarray, np.ndarray], result)
            except ValueError as exc:
                print(f"[emg_pipeline] Session preprocessing error ({day['subject_id']} {session_label}): {exc}")
                continue

            # --- Session Quality Checks ---
            # Check for ADC saturation/clipping (before sensor fault check)
            saturation_issue = detect_adc_saturation(raw_adc) if raw_adc is not None else None
            if saturation_issue:
                print(f"[emg_pipeline] Session ADC saturation ({day['subject_id']} {device_label} {session_label}): "
                      f"{saturation_issue['message']}")
                if plots_root and raw_adc is not None:
                    _save_qa_plot(plots_root, "adc_saturation", raw_adc, day["subject_id"], side, date_label_qa, f"{date_label_qa}_{session_label}", "session", config["fs"])
                if quality_log is not None:
                    _log_quality_issue(quality_log, [saturation_issue], day["subject_id"], day["date_label"], device_label, session_label, len(raw_mv), is_mvc=False)
                continue  # Skip this session
            
            # Check for faulty sensor
            faulty_issue = is_faulty_mban(raw_mv)
            if faulty_issue:
                print(f"[emg_pipeline] Session faulty sensor ({day['subject_id']} {device_label} {session_label}): "
                      f"{faulty_issue['message']}")
                if quality_log is not None:
                    _log_quality_issue(quality_log, [faulty_issue], day["subject_id"], day["date_label"], device_label, session_label, len(raw_mv), is_mvc=False)
                continue  # Skip this session
            
            # Check for PSD noise (after bandpass filter)
            session_filtered = bandpass_filter(raw_mv - np.mean(raw_mv), config["fs"])
            is_session_noisy, psd_issues = detect_psd_noise(session_filtered, config["fs"])
            if is_session_noisy:
                print(f"[emg_pipeline] Session noise detected ({day['subject_id']} {device_label} {session_label}): "
                      f"{'; '.join(iss['message'] for iss in psd_issues)}")
                if plots_root:
                    _save_qa_plot(plots_root, "psd_noise", session_filtered, day["subject_id"], side, date_label_qa, f"{date_label_qa}_{session_label}", "session", config["fs"])
                if quality_log is not None:
                    _log_quality_issue(quality_log, psd_issues, day["subject_id"], day["date_label"], device_label, session_label, len(raw_mv), is_mvc=False)
                continue  # Skip this session

            # Normalize against the MVC peak so that downstream plots and metrics work in %MVC space.
            percent_signal = (envelope_mv / mvc_peak) * 100.0
            metadata = _build_metadata(day, device_label, session_label, config["fs"])
            side_label = metadata["side"]
            metrics, apdf = compute_session_metrics(percent_signal, config["fs"], metadata, percentiles)
            metrics["mvc_peak"] = mvc_peak  # Add MVC reference value (in mV)

            # add session id to identify which session it is
            metrics[SESSION_KEY] = session_ids_dict[session_label]

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
def _convert_date_to_dd_mm_yyyy(date_label: str) -> str:
    """Convert YYYY-MM-DD to DD-MM-YYYY format for consistency with OH profile keys.

    :param date_label: Date string, either YYYY-MM-DD or already DD-MM-YYYY.
    :returns: Date string in DD-MM-YYYY format.
    """
    try:
        # Try YYYY-MM-DD format first (raw data folder format)
        date_obj = datetime.strptime(date_label, "%Y-%m-%d")
        return date_obj.strftime("%d-%m-%Y")
    except ValueError:
        # Already in different format or not a date - return as-is
        return date_label


def _generate_plots_for_loading_rejections(
    quality_records: List[FileQualityReport],
    plots_root: Path,
    subject_id: str,
    date_label: str,
) -> None:
    """Generate diagnostic plots for sessions rejected during data loading.

    This function re-reads raw data files that were rejected during loading
    (e.g., ADC saturation) and generates diagnostic plots for QA purposes.

    :param quality_records: List of FileQualityReport entries from loading.
    :param plots_root: Root directory for plot outputs.
    :param subject_id: Subject ID for folder organization.
    :param date_label: Date label (YYYY-MM-DD format from raw data folders).
    """
    # Convert date label to DD-MM-YYYY for consistent folder naming
    date_folder = _convert_date_to_dd_mm_yyyy(date_label)

    for report in quality_records:
        # Check if this report has ADC saturation issue
        issue_codes = [issue.get("code", "") for issue in report.get("issues", [])]
        if "adc-saturation" not in issue_codes:
            continue

        file_path = report.get("file_path")
        if not file_path or not Path(file_path).exists():
            continue

        device_label = report.get("device_label", "unknown")
        acquisition_label = report.get("acquisition_label", "unknown")

        # Extract side from device label (e.g., "mBAN_right" -> "right")
        side = "left" if "left" in device_label.lower() else "right"

        # Determine output folder structure
        qa_folder = plots_root / "qa_flagged"
        qa_folder.mkdir(parents=True, exist_ok=True)

        # Read raw EMG data from the file
        try:
            raw_df = pd.read_csv(file_path, delimiter="\t", header=None, skiprows=3)
            raw_df = raw_df.dropna(axis=1, how="all")

            # Handle extra column in some firmware versions
            if len(raw_df.columns) > 8:
                raw_df = raw_df.drop(raw_df.columns[1], axis=1)

            # EMG is typically in the second column (index 1 after nSeq)
            if len(raw_df.columns) >= 2:
                raw_adc = raw_df.iloc[:, 1].to_numpy(dtype=float)

                # Generate ADC saturation diagnostic plot
                save_adc_saturation_plot(
                    raw_adc=raw_adc,
                    output_dir=str(qa_folder),
                    subject_id=subject_id,
                    side=side,
                    session_label=f"{date_folder}_{acquisition_label}",
                    acquisition_type="loading_rejected",
                )
                print(f"[emg_pipeline] Saved ADC saturation plot (loading rejection): {subject_id}/{side}/{acquisition_label}")

        except Exception as e:
            print(f"[emg_pipeline] Could not generate plot for rejected session: {e}")


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
    date_label = _convert_date_to_dd_mm_yyyy(day["date_label"])
    session_dir = plots_root / day["subject_id"] / date_label / side / session_label
    session_dir.mkdir(parents=True, exist_ok=True)
    title = f"{day['subject_id']} | {side} | {date_label} {session_label}"
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
