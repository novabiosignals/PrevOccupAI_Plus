"""
EMG Session Timeline Visualization

This module generates participant-friendly timeline visualizations showing:
- Smoothed EMG amplitude (RMS envelope) over time
- Background shading based on relative intensity bins (vs weekly baseline)

The relative intensity approach uses the subject's own weekly P10/P50/P90 
Active APDF values as thresholds, creating four zones:
- Below usual (< P10): Light green - lower than typical effort
- Typical low (P10-P50): Green - normal low effort
- Typical high (P50-P90): Orange - normal high effort  
- High for you (> P90): Red - elevated compared to your baseline

This personalized approach is more meaningful than absolute thresholds,
especially for datasets where true rest (<0.5% MVC) is rare.

Plot labels are in European Portuguese.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.dates as mdates
import numpy as np
from matplotlib.axes import Axes
from scipy.ndimage import uniform_filter1d

# -------------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------------- #

# Processing parameters based on literature recommendations
RMS_WINDOW_S = 0.5  # 500ms RMS window for load envelope (Hansson et al.)
REST_THRESHOLD_MVC = 0.5  # 0.5% MVC rest threshold (Veiersted et al., 2013)
TIME_BIN_S = 5  # 5-second bins for timeline aggregation (cleaner visualization)

# Relative intensity bin colors (same as oh_profile_plots.py)
COLOR_BELOW_USUAL = "#8BC34A"    # Light green - below P10
COLOR_TYPICAL_LOW = "#4CAF50"    # Green - P10 to P50
COLOR_TYPICAL_HIGH = "#FF9800"   # Orange - P50 to P90
COLOR_HIGH_FOR_YOU = "#F44336"   # Red - above P90
COLOR_ENVELOPE = "#1565C0"       # Dark blue for EMG trace (better contrast)
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
# Helper Functions for Baseline Dict
# -------------------------------------------------------------------------------------------------------------------- #

def create_weekly_baseline(p10: float, p50: float, p90: float) -> Dict[str, float]:
    """
    Create a weekly baseline dictionary for relative intensity binning.
    
    :param p10: 10th percentile of weekly Active APDF.
    :param p50: 50th percentile (median).
    :param p90: 90th percentile.
    :returns: Dict with keys 'p10', 'p50', 'p90'.
    """
    return {"p10": p10, "p50": p50, "p90": p90}


def classify_sample(value: float, baseline: Dict[str, float]) -> int:
    """
    Classify a single sample into bins 0-3 based on baseline thresholds.
    
    :param value: Sample value in %MVC.
    :param baseline: Dict with 'p10', 'p50', 'p90' keys.
    :returns: Bin index (0=Below usual, 1=Typical-low, 2=Typical-high, 3=High for you).
    """
    if value < baseline["p10"]:
        return 0  # Below usual
    elif value < baseline["p50"]:
        return 1  # Typical low
    elif value < baseline["p90"]:
        return 2  # Typical high
    else:
        return 3  # High for you


# -------------------------------------------------------------------------------------------------------------------- #
# Signal Processing Functions
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


def detect_rest_periods(
    amplitude_mvc: np.ndarray,
    threshold_mvc: float = REST_THRESHOLD_MVC,
) -> np.ndarray:
    """
    Detect rest periods where EMG is below threshold.
    
    :param amplitude_mvc: RMS envelope in %MVC.
    :param threshold_mvc: Rest threshold in %MVC (default: 0.5%).
    :returns: Boolean mask where True indicates rest.
    """
    return amplitude_mvc < threshold_mvc


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
# Visualization Functions
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


def _draw_threshold_lines(
    ax: Axes,
    baseline: Dict[str, float],
    time_min: np.ndarray,
) -> None:
    """Draw horizontal dashed lines at P10/P50/P90 thresholds (legacy for relative time)."""
    line_style = {'linestyle': '--', 'linewidth': 1.0, 'alpha': 0.7, 'zorder': 5}
    
    ax.axhline(y=baseline["p10"], color=COLOR_THRESHOLD_LINES, **line_style)
    ax.axhline(y=baseline["p50"], color=COLOR_THRESHOLD_LINES, **line_style)
    ax.axhline(y=baseline["p90"], color=COLOR_THRESHOLD_LINES, **line_style)
    
    # Add labels on the right side
    x_pos = time_min[-1] * 1.01 if len(time_min) > 0 else 1.0
    label_style = {'fontsize': 8, 'color': COLOR_THRESHOLD_LINES, 'va': 'center'}
    
    ax.text(x_pos, baseline["p10"], f'P10 ({baseline["p10"]:.1f}%)', **label_style)
    ax.text(x_pos, baseline["p50"], f'P50 ({baseline["p50"]:.1f}%)', **label_style)
    ax.text(x_pos, baseline["p90"], f'P90 ({baseline["p90"]:.1f}%)', **label_style)


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
# Integration with Pipeline
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
        print(f"[emg_timeline] Error generating timeline for {subject_id}/{date}/{session_label}: {e}")
        return None


def create_baseline_from_oh_profile(
    oh_profile: dict,
    side: str,
) -> Optional[Dict[str, float]]:
    """
    Extract weekly baseline from an OH profile for timeline generation.
    
    :param oh_profile: OH profile dictionary.
    :param side: 'left' or 'right'.
    :returns: Dict with 'p10', 'p50', 'p90' keys, or None if data not available.
    """
    try:
        from OH_profile.constants import (
            SENSOR_METRICS_KEY,
            EMG_KEY,
            EMG_WEEKLY_AGGREGATE_KEY,
        )
        from OH_profile.emg_oh_helper import get_emg_apdf_active
        
        emg_data = oh_profile.get(SENSOR_METRICS_KEY, {}).get(EMG_KEY, {})
        weekly_agg = emg_data.get(EMG_WEEKLY_AGGREGATE_KEY, {})
        side_data = weekly_agg.get(side, {})
        
        # Use helper to extract from nested structure
        active_apdf = get_emg_apdf_active(side_data)
        p10 = active_apdf.get('p10')
        p50 = active_apdf.get('p50')
        p90 = active_apdf.get('p90')
        
        if p10 is not None and p50 is not None and p90 is not None:
            return create_weekly_baseline(p10=p10, p50=p50, p90=p90)
        
    except Exception as e:
        print(f"[emg_timeline] Error extracting baseline from OH profile: {e}")
    
    return None
