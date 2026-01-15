"""
EMG Research Visualizations (In-Memory / Signal-Based)

This module contains functions for creating EMG visualizations from in-memory data:
- APDF (Amplitude Probability Distribution Function) curves
- Histograms of signal amplitudes
- Metric series over time (from DataFrames/CSVs)
- MVC segment diagnostics
- Session timeline visualizations with relative intensity zones

All functions in this module COMPUTE and visualize from raw signals or DataFrames.
For functions that READ pre-computed metrics from OH profiles, see emg_oh.py.

Uses Active APDF + Rest Time framework for physiologically meaningful metrics.
Plot labels are in European Portuguese.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.dates as mdates
from matplotlib.axes import Axes
import numpy as np
import pandas as pd
from scipy.ndimage import uniform_filter1d


# -------------------------------------------------------------------------------------------------------------------- #
# Constants - Processing Parameters
# -------------------------------------------------------------------------------------------------------------------- #

# Processing parameters based on literature recommendations
RMS_WINDOW_S = 0.5  # 500ms RMS window for load envelope (Hansson et al.)
REST_THRESHOLD_MVC = 0.5  # 0.5% MVC rest threshold (Veiersted et al., 2013)
TIME_BIN_S = 5  # 5-second bins for timeline aggregation (cleaner visualization)

# Relative intensity bin colors
COLOR_BELOW_USUAL = "#8BC34A"    # Light green - below P10
COLOR_TYPICAL_LOW = "#4CAF50"    # Green - P10 to P50
COLOR_TYPICAL_HIGH = "#FF9800"   # Orange - P50 to P90
COLOR_HIGH_FOR_YOU = "#F44336"   # Red - above P90
COLOR_ENVELOPE = "#1565C0"       # Dark blue for EMG trace
COLOR_THRESHOLD_LINES = "#666666"  # Gray for threshold lines

# Bin colors and labels in order
BIN_COLORS = [COLOR_BELOW_USUAL, COLOR_TYPICAL_LOW, COLOR_TYPICAL_HIGH, COLOR_HIGH_FOR_YOU]
BIN_LABELS_PT = ["Abaixo do habitual", "Típico-baixo", "Típico-alto", "Alto para si"]
BIN_LABELS_EN = ["Below usual", "Typical low", "Typical high", "High for you"]

# Portuguese translations
TRANSLATIONS_PT = {
    "Time": "Hora",
    "EMG (%MVC)": "EMG (%MVC)",
    "Rest": "Descanso",
    "Left": "Esquerdo",
    "Right": "Direito",
    "left": "Esquerdo",
    "right": "Direito",
    "Session Timeline": "Cronograma da Sessão",
    "Summary": "Resumo",
    "min": "min",
    "No data": "Sem dados",
    "Below usual": "Abaixo do habitual",
    "Typical low": "Típico-baixo",
    "Typical high": "Típico-alto",
    "High for you": "Alto para si",
    "Time in each zone": "Tempo em cada zona",
    "vs Weekly Baseline": "vs Linha de Base Semanal",
    "P10": "P10",
    "P50": "P50", 
    "P90": "P90",
}


# -------------------------------------------------------------------------------------------------------------------- #
# Helper Functions
# -------------------------------------------------------------------------------------------------------------------- #

def ensure_parent(path: Path) -> None:
    """
    Create parent directories if they don't exist.

    :param path: Path whose parent directories should be created.
    """
    path.parent.mkdir(parents=True, exist_ok=True)


def create_weekly_baseline(p10: float, p50: float, p90: float) -> Dict[str, float]:
    """
    Create a weekly baseline dictionary for relative intensity binning.
    
    :param p10: 10th percentile of weekly Active APDF.
    :param p50: 50th percentile (median).
    :param p90: 90th percentile.
    :returns: Dict with keys 'p10', 'p50', 'p90'.
    """
    return {"p10": p10, "p50": p50, "p90": p90}


# -------------------------------------------------------------------------------------------------------------------- #
# APDF Plotting Functions
# -------------------------------------------------------------------------------------------------------------------- #

def plot_apdf(apdf: dict, output_path: Path, title: str) -> None:
    """
    Plot and save an APDF (Amplitude Probability Distribution Function) curve.

    :param apdf: Dictionary with keys 'probs', 'amplitudes', 'percentiles'.
                 - probs: 1D array of probability values (0-100)
                 - amplitudes: 1D array of %MVC amplitude values
                 - percentiles: dict mapping percentile values to amplitude values
    :param output_path: Where the PNG should be saved.
    :param title: Plot title providing subject/session context.
    """
    ensure_parent(output_path)

    plt.figure(figsize=(8, 5))
    plt.plot(apdf["probs"], apdf["amplitudes"], label="APDF")

    # Mark the percentile values
    for perc, value in apdf["percentiles"].items():
        plt.axvline(perc, color="grey", linestyle="--", alpha=0.5)
        plt.axhline(value, color="grey", linestyle="--", alpha=0.5)
        plt.scatter(perc, value, color="red")
        plt.text(perc + 1, value, f"P{perc}: {value:.1f}%", fontsize=8)

    plt.title(title)
    plt.xlabel("Time (%)")
    plt.ylabel("Amplitude (%MVC)")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def plot_histogram(amplitudes: np.ndarray, output_path: Path, title: str) -> None:
    """
    Create a histogram of EMG amplitudes.

    :param amplitudes: 1-D array of %MVC values.
    :param output_path: Destination file path for the PNG.
    :param title: Plot title for context.
    """
    ensure_parent(output_path)

    plt.figure(figsize=(8, 5))
    plt.hist(amplitudes, bins=40, color="#4C72B0", alpha=0.85)
    plt.title(title)
    plt.xlabel("Amplitude (%MVC)")
    plt.ylabel("Frequency")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


# -------------------------------------------------------------------------------------------------------------------- #
# Metric Series Plotting
# -------------------------------------------------------------------------------------------------------------------- #

def plot_metric_series(df: pd.DataFrame, value_col: str, order_col: str,
                       output_path: Path, title: str, ylabel: str = "% change") -> None:
    """
    Plot a metric value across sessions or days.

    :param df: DataFrame filtered to a single subject/side group.
    :param value_col: Column name containing the metric to plot.
    :param order_col: Column used for X-axis ordering (session label or date).
    :param output_path: Destination PNG path.
    :param title: Figure title.
    :param ylabel: Label for the Y-axis (default: "% change").
    """
    ensure_parent(output_path)

    df_sorted = df.sort_values(order_col)

    plt.figure(figsize=(8, 5))
    plt.plot(df_sorted[order_col], df_sorted[value_col], marker="o")
    plt.title(title)
    plt.xlabel(order_col.replace('_', ' ').title())
    plt.ylabel(ylabel)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


# -------------------------------------------------------------------------------------------------------------------- #
# MVC Plotting Functions
# -------------------------------------------------------------------------------------------------------------------- #

def plot_mvc_segments(
    envelope: np.ndarray,
    segments: List[tuple[int, int]],
    fs: float,
    threshold_value: float,
    output_path: Path,
    title: str,
    method: str = "unknown",
    show: bool = False,
) -> None:
    """
    Plot MVC envelope with detected segments and threshold.

    :param envelope: 1-D array of the MVC envelope signal.
    :param segments: List of (start, end) sample index tuples for detected segments.
    :param fs: Sampling frequency in Hz.
    :param threshold_value: Amplitude threshold used for segment detection.
    :param output_path: Destination file path for the PNG.
    :param title: Plot title for context.
    :param method: Segmentation method used (e.g., "TKEO", "envelope", "envelope fallback").
    :param show: If True, display the plot interactively before closing.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    t = np.arange(len(envelope)) / fs if fs else np.arange(len(envelope))
    env_abs = np.abs(envelope)

    plt.figure(figsize=(10, 4))
    plt.plot(t, env_abs, label="MVC envelope", color="#1f77b4", linewidth=1.2)
    plt.axhline(threshold_value, color="red", linestyle="--", linewidth=1.0, 
                label=f"threshold={threshold_value:.3f}")

    for idx, (start, end) in enumerate(segments):
        plt.axvspan(start / fs, end / fs, alpha=0.2, color="#2ca02c", 
                    label=f"segment ({method})" if idx == 0 else None)

    plt.title(title)
    plt.xlabel("Time (s)")
    plt.ylabel("Amplitude (mV)")
    plt.grid(True, alpha=0.3)
    plt.legend(loc="upper right")
    plt.tight_layout()

    if show:
        plt.show(block=True)  # allow user interaction before persisting to disk

    plt.savefig(output_path)
    plt.close()


def plot_mvc_hybrid_diagnostics(
    emg_mv: np.ndarray,
    segments: List[tuple[int, int]],
    debug_info: dict,
    fs: float,
    output_path: Path,
    title: str = "MVC Hybrid Detection Diagnostics",
    show: bool = False,
) -> None:
    """
    Multi-panel diagnostic plot for hybrid MVC segmentation.

    Creates a 4-panel figure showing:
    - Panel 1: Filtered EMG with detected segments highlighted + baseline window
    - Panel 2: Log-energy curve with threshold lines and baseline region
    - Panel 3: Histogram of log-energy with thresholds and baseline IQR info
    - Panel 4: Binary activation mask with segment ranking (top-2 by energy)

    :param emg_mv: Original raw EMG signal in millivolts.
    :param segments: List of (start, end) sample index tuples for detected segments.
    :param debug_info: Dictionary from detect_mvc_segments_hybrid containing:
                       emg_filt, log_energy, threshold, threshold_otsu,
                       threshold_baseline, threshold_method, p10, p90, floor,
                       baseline_start, baseline_end, robust_sigma, binary.
    :param fs: Sampling frequency in Hz.
    :param output_path: Destination file path for the PNG.
    :param title: Overall figure title.
    :param show: If True, display the plot interactively before saving.
    """
    ensure_parent(output_path)

    # Extract debug values
    emg_filt = debug_info.get("emg_filt", emg_mv)
    log_energy = debug_info["log_energy"]
    threshold = debug_info["threshold"]
    threshold_otsu = debug_info["threshold_otsu"]
    threshold_baseline = debug_info["threshold_baseline"]
    threshold_method = debug_info["threshold_method"]
    p10 = debug_info["p10"]
    p90 = debug_info["p90"]
    floor_val = debug_info["floor"]
    baseline_median = debug_info.get("baseline_median", threshold_baseline - 6 * 0.1)
    baseline_start = debug_info.get("baseline_start", 0)
    baseline_end = debug_info.get("baseline_end", 0)
    robust_sigma = debug_info.get("robust_sigma", 0.1)
    binary = debug_info["binary"]
    
    # Get candidate scores for display
    candidate_scores = debug_info.get("candidate_scores", {})
    best_score = debug_info.get("best_score", 0)

    # Time axis
    t = np.arange(len(emg_filt)) / fs

    # Create figure with 4 panels
    fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True)
    fig.suptitle(f"{title}\n[Method: {threshold_method.upper()} | Score: {best_score:.1f} | σ: {robust_sigma:.3f}]", 
                 fontsize=14, fontweight="bold")

    # -------------------------------------------------------------------------
    # Panel 1: Filtered EMG with segments and baseline window
    # -------------------------------------------------------------------------
    ax1 = axes[0]
    ax1.plot(t, emg_filt, color="#1f77b4", linewidth=0.5, alpha=0.8)
    
    # Highlight baseline window
    if baseline_start < baseline_end:
        t_bl_start, t_bl_end = baseline_start / fs, baseline_end / fs
        ax1.axvspan(t_bl_start, t_bl_end, alpha=0.2, color="cyan",
                    label=f"Baseline window ({t_bl_end - t_bl_start:.2f}s)")
    
    # Highlight detected segments
    n_segments = len(segments)
    for idx, (start, end) in enumerate(segments):
        t_start, t_end = start / fs, end / fs
        ax1.axvspan(t_start, t_end, alpha=0.3, color="#2ca02c",
                    label=f"MVC segment (n={n_segments})" if idx == 0 else None)
    ax1.set_ylabel("EMG (mV)")
    ax1.set_title("Filtered EMG with Detected MVC Segments & Baseline Window")
    ax1.legend(loc="upper right")
    ax1.grid(True, alpha=0.3)

    # -------------------------------------------------------------------------
    # Panel 2: Log-energy with threshold lines and baseline region
    # -------------------------------------------------------------------------
    ax2 = axes[1]
    ax2.plot(t[:len(log_energy)], log_energy, color="#ff7f0e", linewidth=0.8)
    
    # Highlight baseline region on energy plot
    if baseline_start < baseline_end:
        ax2.axvspan(baseline_start / fs, baseline_end / fs, alpha=0.15, color="cyan")

    # Threshold used (solid red)
    score_str = ""
    if threshold_method in candidate_scores:
        score_str = f" [score={candidate_scores[threshold_method]['score']:.1f}]"
    ax2.axhline(threshold, color="red", linestyle="-", linewidth=1.5,
                label=f"✓ Used ({threshold_method}): {threshold:.2f}{score_str}")

    # Otsu threshold (dashed blue)
    otsu_info = ""
    if "otsu" in candidate_scores:
        otsu_n = candidate_scores['otsu']['n_segments']
        otsu_info = f" [n={otsu_n}, score={candidate_scores['otsu']['score']:.1f}]"
    ax2.axhline(threshold_otsu, color="blue", linestyle="--", linewidth=1.0, alpha=0.7,
                label=f"Otsu: {threshold_otsu:.2f}{otsu_info}")

    # Baseline threshold (dashed green) - only if different from used
    if threshold_method != "baseline":
        baseline_info = ""
        if "baseline" in candidate_scores:
            base_n = candidate_scores['baseline']['n_segments']
            baseline_info = f" [n={base_n}, score={candidate_scores['baseline']['score']:.1f}]"
        ax2.axhline(threshold_baseline, color="green", linestyle="--", linewidth=1.0, alpha=0.7,
                    label=f"Baseline: {threshold_baseline:.2f}{baseline_info}")

    # Floor (dotted gray) - baseline-derived
    ax2.axhline(floor_val, color="gray", linestyle=":", linewidth=1.0, alpha=0.5,
                label=f"Floor (median+2σ): {floor_val:.2f}")
    
    # Baseline median (dotted cyan)
    ax2.axhline(baseline_median, color="cyan", linestyle=":", linewidth=1.0, alpha=0.5,
                label=f"Baseline median: {baseline_median:.2f}")

    ax2.set_ylabel("Log₁₀(Energy)")
    ax2.set_title("Log-Energy with Threshold Lines (Evidence-Driven Selection)")
    ax2.legend(loc="upper right", fontsize=7)
    ax2.grid(True, alpha=0.3)

    # -------------------------------------------------------------------------
    # Panel 3: Histogram of log-energy with thresholds and sigma info
    # -------------------------------------------------------------------------
    ax3 = axes[2]
    ax3.hist(log_energy, bins=100, color="#9467bd", alpha=0.7, edgecolor="none", density=True)
    ax3.axvline(threshold, color="red", linestyle="-", linewidth=2,
                label=f"Used: {threshold:.2f}")
    ax3.axvline(threshold_otsu, color="blue", linestyle="--", linewidth=1.5,
                label=f"Otsu: {threshold_otsu:.2f}")
    if threshold_method != "baseline":
        ax3.axvline(threshold_baseline, color="green", linestyle="--", linewidth=1.5,
                    label=f"Baseline: {threshold_baseline:.2f}")
    ax3.axvline(p10, color="gray", linestyle=":", linewidth=1.0, alpha=0.6,
                label=f"P10: {p10:.2f}")
    ax3.axvline(p90, color="gray", linestyle=":", linewidth=1.0, alpha=0.6,
                label=f"P90: {p90:.2f}")
    ax3.axvline(baseline_median, color="cyan", linestyle=":", linewidth=1.5, alpha=0.8,
                label=f"Baseline med: {baseline_median:.2f}")
    
    # Add text annotation with key parameters
    dynamic_range = p90 - p10
    info_text = (f"σ_robust = {robust_sigma:.3f}\n"
                 f"Range (P90-P10) = {dynamic_range:.2f}\n"
                 f"Threshold = med + 6σ")
    ax3.text(0.02, 0.98, info_text, transform=ax3.transAxes, fontsize=8,
             verticalalignment='top', fontfamily='monospace',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    ax3.set_ylabel("Density")
    ax3.set_xlabel("Log₁₀(Energy)")
    ax3.set_title("Log-Energy Distribution with Threshold Analysis")
    ax3.legend(loc="upper right", fontsize=8)
    ax3.grid(True, alpha=0.3)

    # -------------------------------------------------------------------------
    # Panel 4: Binary activation mask with segment details
    # -------------------------------------------------------------------------
    ax4 = axes[3]
    ax4.fill_between(t[:len(binary)], 0, binary, step="mid", color="#2ca02c", alpha=0.6)
    
    # Annotate each segment with duration and rank (if >2 segments)
    if len(segments) > 0:
        # Compute peak energy for each segment to determine top-2
        seg_info = []
        for start, end in segments:
            peak_e = float(np.max(log_energy[start:end]))
            duration = (end - start) / fs
            seg_info.append((peak_e, start, end, duration))
        
        # Sort by peak energy for ranking
        seg_info_sorted = sorted(seg_info, key=lambda x: x[0], reverse=True)
        rank_map = {(s, e): rank + 1 for rank, (_, s, e, _) in enumerate(seg_info_sorted)}
        
        # Add annotations
        for peak_e, start, end, duration in seg_info:
            center_t = (start + end) / 2 / fs
            rank = rank_map[(start, end)]
            
            # Color top-2 differently
            if rank <= 2:
                color = "#2ca02c"
                label = f"#{rank} ({duration:.1f}s)"
            else:
                color = "#d62728"
                label = f"#{rank} ({duration:.1f}s)"
            
            ax4.annotate(label, xy=(center_t, 0.5), fontsize=8, ha='center', 
                        color=color, fontweight='bold')
    
    ax4.set_ylim(-0.1, 1.1)
    ax4.set_yticks([0, 1])
    ax4.set_yticklabels(["Rest", "Active"])
    ax4.set_ylabel("State")
    ax4.set_xlabel("Time (s)")
    ax4.set_title(f"Binary Activation Mask ({len(segments)} segments detected)")
    ax4.grid(True, alpha=0.3)

    # Finalize
    fig.tight_layout(rect=(0, 0, 1, 0.96))

    if show:
        plt.show(block=True)

    fig.savefig(output_path, dpi=150)
    plt.close(fig)


# -------------------------------------------------------------------------------------------------------------------- #
# Signal Processing for Timeline
# -------------------------------------------------------------------------------------------------------------------- #

def compute_rms_envelope(
    signal: np.ndarray,
    fs: float,
    window_s: float = RMS_WINDOW_S,
) -> np.ndarray:
    """
    Compute RMS envelope with specified window size.
    
    Uses a sliding RMS window to create a smooth "load" envelope that reflects
    muscular effort without high-frequency noise.
    
    :param signal: Input signal (already MVC-normalized, in %MVC).
    :param fs: Sampling frequency in Hz.
    :param window_s: RMS window duration in seconds (default: 500ms).
    :returns: RMS envelope at original sampling rate.
    """
    window_samples = int(window_s * fs)
    if window_samples < 1:
        window_samples = 1
    
    # Ensure window is odd for symmetric centering
    if window_samples % 2 == 0:
        window_samples += 1
    
    # Vectorized sliding RMS using convolution
    signal_sq = signal ** 2
    
    # Use uniform_filter1d for efficient moving average (much faster than loop)
    mean_sq = uniform_filter1d(signal_sq, size=window_samples, mode='nearest')
    rms = np.sqrt(mean_sq)
    
    return rms


def classify_into_bins(
    amplitude_mvc: np.ndarray,
    baseline: Dict[str, float],
) -> np.ndarray:
    """
    Classify each sample into relative intensity bins based on weekly baseline.
    
    :param amplitude_mvc: RMS envelope in %MVC.
    :param baseline: Dict with 'p10', 'p50', 'p90' thresholds.
    :returns: Array of bin indices (0-3) for each sample.
    """
    bin_indices = np.zeros(len(amplitude_mvc), dtype=int)
    
    # Vectorized classification
    bin_indices[amplitude_mvc < baseline["p10"]] = 0
    bin_indices[(amplitude_mvc >= baseline["p10"]) & (amplitude_mvc < baseline["p50"])] = 1
    bin_indices[(amplitude_mvc >= baseline["p50"]) & (amplitude_mvc < baseline["p90"])] = 2
    bin_indices[amplitude_mvc >= baseline["p90"]] = 3
    
    return bin_indices


def process_session_for_timeline(
    percent_signal: np.ndarray,
    baseline: Optional[Dict[str, float]] = None,
    fs: float = 1000.0,
    rms_window_s: float = RMS_WINDOW_S,
    time_bin_s: float = TIME_BIN_S,
) -> Dict:
    """
    Process a session's MVC-normalized signal for timeline visualization.
    
    This is the main entry point for processing. Takes the already-normalized
    percent_signal (output of emg_pipeline) and prepares it for visualization.
    
    The processing pipeline:
    1. Compute 500ms RMS envelope (standard EMG amplitude)
    2. Aggregate into time bins (default 5s) using median amplitude
    3. Classify each bin into relative intensity zones
    
    :param percent_signal: MVC-normalized envelope in %MVC (from emg_pipeline).
    :param baseline: Dict with 'p10', 'p50', 'p90' for relative intensity binning.
                     If None, will use session's own percentiles as fallback.
    :param fs: Sampling frequency in Hz.
    :param rms_window_s: RMS window for load smoothing.
    :param time_bin_s: Duration of each time bin in seconds (default: 5s).
    :returns: Dict with timeline data ready for plotting.
    """
    # Create time axis at original sampling rate
    n_samples = len(percent_signal)
    time_s_full = np.arange(n_samples) / fs
    total_duration_s = time_s_full[-1] if len(time_s_full) > 0 else 0.0
    
    # Compute RMS envelope for load smoothing
    rms_envelope = compute_rms_envelope(percent_signal, fs, rms_window_s)
    
    # Create or use baseline for binning
    if baseline is None:
        # Fallback: use session's own percentiles (less meaningful but still works)
        # Only consider active samples (>0.5% MVC) for percentile calculation
        active_mask = rms_envelope >= REST_THRESHOLD_MVC
        if np.sum(active_mask) > 10:
            active_values = rms_envelope[active_mask]
            baseline = create_weekly_baseline(
                p10=float(np.percentile(active_values, 10)),
                p50=float(np.percentile(active_values, 50)),
                p90=float(np.percentile(active_values, 90)),
            )
        else:
            # Not enough active data, use arbitrary defaults
            baseline = create_weekly_baseline(p10=1.0, p50=5.0, p90=15.0)
    
    # Aggregate into time bins
    samples_per_bin = int(time_bin_s * fs)
    n_bins = max(1, int(np.ceil(n_samples / samples_per_bin)))
    
    binned_amplitude = np.zeros(n_bins)
    binned_p25 = np.zeros(n_bins)
    binned_p75 = np.zeros(n_bins)
    binned_time_centers = np.zeros(n_bins)
    
    for i in range(n_bins):
        start_idx = i * samples_per_bin
        end_idx = min((i + 1) * samples_per_bin, n_samples)
        bin_data = rms_envelope[start_idx:end_idx]
        
        # Median (P50) and percentiles in this time bin
        binned_amplitude[i] = np.percentile(bin_data, 50)  # Median - always within P25-P75
        binned_p25[i] = np.percentile(bin_data, 25)
        binned_p75[i] = np.percentile(bin_data, 75)
        # Time center of this bin
        binned_time_centers[i] = (start_idx + end_idx) / 2 / fs
    
    # Classify each time bin into intensity zones
    binned_indices = classify_into_bins(binned_amplitude, baseline)
    
    # Compute time in each zone (using full resolution for accuracy)
    sample_bin_indices = classify_into_bins(rms_envelope, baseline)
    samples_per_zone = [np.sum(sample_bin_indices == i) for i in range(4)]
    sample_duration = 1.0 / fs
    bin_durations_s = [count * sample_duration for count in samples_per_zone]
    total_binned = sum(bin_durations_s)
    bin_percentages = [(d / total_binned * 100.0) if total_binned > 0 else 0.0 
                       for d in bin_durations_s]
    
    return {
        "time_s": binned_time_centers,
        "amplitude_mvc": binned_amplitude,
        "amplitude_p25": binned_p25,
        "amplitude_p75": binned_p75,
        "bin_indices": binned_indices,
        "baseline": baseline,
        "bin_durations_s": bin_durations_s,
        "bin_percentages": bin_percentages,
        "total_duration_s": total_duration_s,
        "time_bin_s": time_bin_s,
    }


# -------------------------------------------------------------------------------------------------------------------- #
# Time Parsing Helpers
# -------------------------------------------------------------------------------------------------------------------- #

def parse_session_start_time(session_label: str, date: str) -> datetime:
    """
    Parse session start time from session label and date.
    
    :param session_label: Session label in format "HH-MM-SS" (e.g., "09-30-00").
    :param date: Date string in format "YYYY-MM-DD".
    :returns: datetime object representing session start.
    """
    try:
        # Parse date
        date_parts = date.split("-")
        year, month, day = int(date_parts[0]), int(date_parts[1]), int(date_parts[2])
        
        # Parse time from session label (format: HH-MM-SS)
        time_parts = session_label.replace("_", "-").split("-")
        hour, minute, second = int(time_parts[0]), int(time_parts[1]), int(time_parts[2])
        
        return datetime(year, month, day, hour, minute, second)
    except (ValueError, IndexError):
        # Fallback to midnight if parsing fails
        return datetime(2024, 1, 1, 0, 0, 0)


def create_time_axis(start_time: datetime, duration_s: float, n_samples: int) -> np.ndarray:
    """
    Create datetime array for X-axis.
    
    :param start_time: Session start datetime.
    :param duration_s: Total duration in seconds.
    :param n_samples: Number of samples.
    :returns: Array of datetime objects.
    """
    time_deltas = np.linspace(0, duration_s, n_samples)
    return np.array([start_time + timedelta(seconds=t) for t in time_deltas])


# -------------------------------------------------------------------------------------------------------------------- #
# Timeline Visualization
# -------------------------------------------------------------------------------------------------------------------- #

def plot_session_timeline(
    timeline_data: Dict,
    output_path: Path,
    subject_id: str,
    date: str,
    session_label: str,
    side: str,
    y_max: Optional[float] = None,
    show_summary_box: bool = True,
    show_threshold_lines: bool = True,
    figsize: Tuple[float, float] = (14, 5),
) -> Path:
    """
    Generate a participant-friendly timeline visualization with uncertainty bands.
    
    The plot shows:
    - X-axis with real clock time (HH:MM format)
    - Median EMG intensity line (5-second bins)
    - P25-P75 shaded uncertainty band showing variability within each bin
    - Background zone shading (Below usual, Typical-low, Typical-high, High for you)
    - Horizontal dashed lines at P10/P50/P90 thresholds
    - Summary box with time spent in each zone
    
    :param timeline_data: Dict with processed timeline data.
    :param output_path: Path to save the plot.
    :param subject_id: Subject identifier.
    :param date: Date string (YYYY-MM-DD).
    :param session_label: Session identifier (HH-MM-SS format).
    :param side: 'left' or 'right'.
    :param y_max: Optional Y-axis maximum (auto-scaled if None).
    :param show_summary_box: Whether to show summary statistics box.
    :param show_threshold_lines: Whether to show P10/P50/P90 threshold lines.
    :param figsize: Figure size (width, height) in inches.
    :returns: Path to the saved plot.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    side_label = TRANSLATIONS_PT.get(side.capitalize(), side)
    
    fig, ax = plt.subplots(figsize=figsize)
    
    # Create real clock time axis for bin centers
    start_time = parse_session_start_time(session_label, date)
    time_axis = create_time_axis(start_time, timeline_data["total_duration_s"], len(timeline_data["amplitude_mvc"]))
    
    baseline = timeline_data["baseline"]
    
    # Determine Y-axis limits (include P75 for uncertainty band)
    if y_max is None:
        y_max = max(20.0, np.max(timeline_data["amplitude_p75"]) * 1.2)
        if baseline:
            y_max = max(y_max, baseline["p90"] * 1.3)
    
    # Draw horizontal zone bands based on thresholds (background shading)
    if baseline:
        _draw_bin_shading(ax, baseline, y_max)
    
    # Draw threshold lines if baseline available
    if show_threshold_lines and baseline:
        _draw_threshold_lines_with_time(ax, baseline, time_axis)
    
    # Draw P25-P75 uncertainty band (shows variability within each time bin)
    ax.fill_between(time_axis, timeline_data["amplitude_p25"], timeline_data["amplitude_p75"],
                    color=COLOR_ENVELOPE, alpha=0.25, zorder=8, label='P25-P75')
    
    # Draw the median EMG amplitude line on top
    ax.plot(time_axis, timeline_data["amplitude_mvc"], color=COLOR_ENVELOPE, 
            linewidth=1.5, alpha=0.95, zorder=10)
    
    # Configure axes with time formatting
    ax.set_xlim(time_axis[0], time_axis[-1])
    ax.set_ylim(0, y_max)
    ax.set_xlabel(TRANSLATIONS_PT["Time"], fontsize=11)
    ax.set_ylabel(TRANSLATIONS_PT["EMG (%MVC)"], fontsize=11)
    ax.grid(True, alpha=0.3, zorder=1, color='white')
    
    # Format X-axis as clock time (HH:MM)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate(rotation=0, ha='center')
    
    # Title with start and end times
    end_time = start_time + timedelta(seconds=timeline_data["total_duration_s"])
    title = f"{subject_id} – {date} – mBAN {side_label}\n{start_time.strftime('%H:%M')} → {end_time.strftime('%H:%M')} ({TRANSLATIONS_PT['vs Weekly Baseline']})"
    ax.set_title(title, fontsize=12, fontweight='bold')
    
    # Legend for bins
    legend_handles = [
        mpatches.Patch(facecolor=BIN_COLORS[i], alpha=0.6, label=BIN_LABELS_PT[i])
        for i in range(4)
    ]
    ax.legend(handles=legend_handles, loc='upper right', fontsize=9, ncol=2)
    
    # Summary box
    if show_summary_box:
        _add_summary_box(ax, timeline_data)
    
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    
    return output_path


def _draw_bin_shading(
    ax: Axes,
    baseline: Dict[str, float],
    y_max: float,
) -> None:
    """Draw horizontal zone bands based on relative intensity thresholds."""
    # Zone 0: Below usual (0 to P10) - light green
    ax.axhspan(0, baseline["p10"], color=BIN_COLORS[0], alpha=0.4, zorder=0)
    
    # Zone 1: Typical low (P10 to P50) - green
    ax.axhspan(baseline["p10"], baseline["p50"], color=BIN_COLORS[1], alpha=0.4, zorder=0)
    
    # Zone 2: Typical high (P50 to P90) - orange
    ax.axhspan(baseline["p50"], baseline["p90"], color=BIN_COLORS[2], alpha=0.4, zorder=0)
    
    # Zone 3: High for you (P90 to y_max) - red
    ax.axhspan(baseline["p90"], y_max, color=BIN_COLORS[3], alpha=0.4, zorder=0)


def _draw_threshold_lines_with_time(
    ax: Axes,
    baseline: Dict[str, float],
    time_axis: np.ndarray,
) -> None:
    """Draw horizontal dashed lines at P10/P50/P90 thresholds with time-based X-axis."""
    line_style = {'linestyle': '--', 'linewidth': 1.0, 'alpha': 0.7, 'zorder': 5}
    
    ax.axhline(y=baseline["p10"], color=COLOR_THRESHOLD_LINES, **line_style)
    ax.axhline(y=baseline["p50"], color=COLOR_THRESHOLD_LINES, **line_style)
    ax.axhline(y=baseline["p90"], color=COLOR_THRESHOLD_LINES, **line_style)
    
    # Add labels on the right side (use transform to place outside plot area)
    label_style = {'fontsize': 8, 'color': COLOR_THRESHOLD_LINES, 'va': 'center', 'ha': 'left'}
    
    # Position labels at right edge using axes transform
    ax.text(1.01, baseline["p10"], f' P10 ({baseline["p10"]:.1f}%)', transform=ax.get_yaxis_transform(), **label_style)
    ax.text(1.01, baseline["p50"], f' P50 ({baseline["p50"]:.1f}%)', transform=ax.get_yaxis_transform(), **label_style)
    ax.text(1.01, baseline["p90"], f' P90 ({baseline["p90"]:.1f}%)', transform=ax.get_yaxis_transform(), **label_style)


def _add_summary_box(ax: Axes, timeline_data: Dict) -> None:
    """Add a summary statistics box showing time in each zone."""
    lines = [f"{TRANSLATIONS_PT['Time in each zone']}:"]
    
    for i in range(4):
        duration_min = timeline_data["bin_durations_s"][i] / 60.0
        pct = timeline_data["bin_percentages"][i]
        lines.append(f"  {BIN_LABELS_PT[i]}: {duration_min:.1f} {TRANSLATIONS_PT['min']} ({pct:.0f}%)")
    
    summary_text = "\n".join(lines)
    
    props = dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.9, edgecolor='gray')
    ax.text(0.02, 0.98, summary_text, transform=ax.transAxes, fontsize=9,
            verticalalignment='top', bbox=props, family='monospace')


# -------------------------------------------------------------------------------------------------------------------- #
# Pipeline Integration
# -------------------------------------------------------------------------------------------------------------------- #

def generate_session_timeline_from_signal(
    percent_signal: np.ndarray,
    output_path: Path,
    subject_id: str,
    date: str,
    session_label: str,
    side: str,
    fs: float = 1000.0,
    weekly_p10: Optional[float] = None,
    weekly_p50: Optional[float] = None,
    weekly_p90: Optional[float] = None,
    **kwargs,
) -> Optional[Path]:
    """
    Complete pipeline: process signal and generate timeline visualization.
    
    This is the main entry point for generating timeline plots from session data.
    Pass the weekly baseline percentiles for meaningful relative intensity shading.
    
    :param percent_signal: MVC-normalized envelope in %MVC.
    :param output_path: Path to save the plot.
    :param subject_id: Subject identifier.
    :param date: Date string.
    :param session_label: Session identifier.
    :param side: 'left' or 'right'.
    :param fs: Sampling frequency in Hz.
    :param weekly_p10: Weekly Active APDF P10 threshold.
    :param weekly_p50: Weekly Active APDF P50 threshold.
    :param weekly_p90: Weekly Active APDF P90 threshold.
    :param kwargs: Additional arguments passed to plot_session_timeline.
    :returns: Path to the saved plot, or None if processing failed.
    """
    if percent_signal is None or len(percent_signal) == 0:
        return None
    
    # Build baseline dict from weekly thresholds if provided
    baseline = None
    if weekly_p10 is not None and weekly_p50 is not None and weekly_p90 is not None:
        baseline = create_weekly_baseline(p10=weekly_p10, p50=weekly_p50, p90=weekly_p90)
    
    try:
        timeline_data = process_session_for_timeline(percent_signal, baseline=baseline, fs=fs)
        return plot_session_timeline(
            timeline_data,
            output_path,
            subject_id,
            date,
            session_label,
            side,
            **kwargs,
        )
    except Exception as e:
        print(f"[emg_research] Error generating timeline for {subject_id}/{date}/{session_label}: {e}")
        return None


# -------------------------------------------------------------------------------------------------------------------- #
# Envelope Plotting
# -------------------------------------------------------------------------------------------------------------------- #

def plot_envelope(
    emg_series: pd.Series,
    envelope_series: pd.Series,
    title: str,
    plot_folder: str,
) -> None:
    """
    Plot EMG signal with its envelope overlay.

    :param emg_series: Raw EMG signal as pandas Series.
    :param envelope_series: Envelope of the EMG signal as pandas Series.
    :param title: Plot title (also used for filename).
    :param plot_folder: Directory path where the plot will be saved.
    """
    import os
    
    plt.figure(figsize=(12, 5))
    plt.title('Envelope_' + title)
    plt.plot(emg_series, color='cornflowerblue', lw=2.0)
    plt.plot(envelope_series, color='orange', lw=1.0)
    plt.xlabel('Samples [n]')
    plt.ylabel('EMG [mV]')
    plt.savefig(os.path.join(plot_folder, title + '.png'))
    plt.close()
