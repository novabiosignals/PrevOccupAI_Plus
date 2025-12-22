"""
EMG Visualization Functions

This module contains functions for creating EMG-related plots:
- APDF (Amplitude Probability Distribution Function) curves
- Histograms of signal amplitudes
- Metric series over time
- Effort distribution grids and stacked bar charts

All functions use simple data structures (dicts, arrays) rather than classes.
"""

from pathlib import Path
from typing import Sequence, List

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
import numpy as np
import pandas as pd

from sensors.metrics.emg_metrics import EFFORT_BANDS, compute_effort_bins


# -------------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------------- #

# Colors for effort bands: green (low), amber (moderate), red (high), dark red (>100%)
EFFORT_COLORS = ["#2ca02c", "#ffbf00", "#d62728", "#7f0000"]


# -------------------------------------------------------------------------------------------------------------------- #
# Helper Functions
# -------------------------------------------------------------------------------------------------------------------- #

def ensure_parent(path: Path) -> None:
    """
    Create parent directories if they don't exist.

    :param path: Path whose parent directories should be created.
    """
    path.parent.mkdir(parents=True, exist_ok=True)


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
# Effort Distribution Plots
# -------------------------------------------------------------------------------------------------------------------- #

def plot_session_effort_grid(
    payloads: dict,
    session_labels: Sequence[str],
    output_path: Path,
    title: str,
    max_rows: int = 4,
) -> None:
    """
    Plot a left/right effort distribution grid for up to four sessions.

    :param payloads: Dict mapping (side, session_label) to (percent_signal, fs).
                     Keys are tuples like ("left", "session_1").
                     Values are tuples like (numpy_array, 1000.0).
    :param session_labels: Desired ordering of session labels in the grid.
    :param output_path: Destination PNG path.
    :param title: Figure title summarizing subject/day.
    :param max_rows: Maximum number of session rows to show.
    """
    ensure_parent(output_path)

    # Preserve order but limit/pad to the requested number of rows
    ordered_labels: list[str | None] = list(dict.fromkeys(session_labels))
    ordered_labels = ordered_labels[:max_rows]
    while len(ordered_labels) < max_rows:
        ordered_labels.append(None)

    sides = ("left", "right")
    n_rows = len(ordered_labels)
    fig, axes = plt.subplots(n_rows, len(sides), figsize=(12, 2.8 * n_rows), squeeze=False)
    fig.suptitle(title, fontsize=14, fontweight="bold")

    for row_idx, session_label in enumerate(ordered_labels):
        for col_idx, side in enumerate(sides):
            ax = axes[row_idx][col_idx]
            if row_idx == 0:
                ax.set_title(f"{side.title()} mBAN")

            if session_label is None:
                _annotate_missing(ax, "No session configured")
                continue

            payload = payloads.get((side, session_label))
            if payload is None or payload[0].size == 0:
                _annotate_missing(ax, "No data for this session")
                continue

            amplitudes, fs = payload
            minutes, percentages = compute_effort_bins(amplitudes, fs)
            _plot_effort_bars(ax, percentages)

            if col_idx == 0:
                ax.set_ylabel("Session time (%)")
            else:
                ax.set_ylabel("")

            ax.text(-0.25, 0.5, session_label, transform=ax.transAxes, rotation=90,
                    va="center", ha="center", fontweight="bold")

    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(output_path)
    plt.close(fig)


def plot_session_effort_stacks(
    payloads: dict,
    session_labels: Sequence[str],
    output_path: Path,
    title: str,
) -> None:
    """
    Plot stacked effort bins per session for left/right mBANs.

    :param payloads: Dict mapping (side, session_label) to (percent_signal, fs).
    :param session_labels: Ordered list of session labels to include.
    :param output_path: Destination PNG path.
    :param title: Figure title summarizing subject/day.
    """
    ensure_parent(output_path)

    ordered_labels = list(dict.fromkeys(session_labels))
    if not ordered_labels:
        ordered_labels = sorted({session for (_, session) in payloads.keys()})
    ordered_labels = ordered_labels[:4]

    bin_labels = [band[2] for band in EFFORT_BANDS] + [">100%"]
    n_bins = len(bin_labels)

    fig = plt.figure(figsize=(12, 4))
    gs = fig.add_gridspec(1, 3, width_ratios=(1, 0.18, 1), wspace=0.2)
    axes_map = {
        "left": fig.add_subplot(gs[0, 0]),
        "right": fig.add_subplot(gs[0, 2]),
    }
    label_ax = fig.add_subplot(gs[0, 1])
    label_ax.axis("off")
    sides = ("left", "right")
    fig.suptitle(title, fontsize=14, fontweight="bold")

    legend_handles = []
    legend_labels = []

    y_positions = np.arange(len(ordered_labels)) if ordered_labels else np.array([])

    for idx, side in enumerate(sides):
        ax = axes_map[side]
        ax.set_title(f"{side.title()} mBAN – Sessions")
        session_data = []

        if not ordered_labels:
            _annotate_missing(ax, "No sessions configured")
            continue

        for session_label in ordered_labels:
            payload = payloads.get((side, session_label))
            if payload is None or payload[0].size == 0:
                session_data.append(None)
                continue

            amplitudes, fs = payload
            _minutes, percentages = compute_effort_bins(amplitudes, fs)
            needed = n_bins
            padded = percentages[:needed]
            if len(padded) < needed:
                padded = padded + [0.0] * (needed - len(padded))
            session_data.append(padded)

        if not session_data:
            _annotate_missing(ax, "No sessions for this day")
            continue

        left_offsets = np.zeros(len(ordered_labels))

        for bin_idx, bin_label in enumerate(bin_labels):
            widths = [values[bin_idx] if values is not None else 0.0 for values in session_data]
            bars = ax.barh(y_positions, widths, height=0.6, left=left_offsets,
                           color=EFFORT_COLORS[bin_idx], label=bin_label)
            left_offsets += widths

            if idx == 0:
                legend_handles.append(bars[0])
                legend_labels.append(bin_label)

        for y_pos, values in zip(y_positions, session_data):
            if values is None or sum(values) == 0:
                text_x = -1 if side == "left" else 101
                halign = "right" if side == "left" else "left"
                ax.text(text_x, float(y_pos), "no data", va="center", ha=halign,
                        fontsize=8, color="#555555")

        ax.set_yticks(y_positions)
        ax.set_yticklabels([])
        ax.set_xlim(0, 100)
        ax.set_xlabel("Session time (%)")
        ax.invert_yaxis()
        ax.grid(axis="x", alpha=0.2)

        if side == "left":
            ax.invert_xaxis()

    if legend_handles:
        fig.legend(legend_handles, legend_labels, loc="upper right", bbox_to_anchor=(0.98, 0.95))

    if len(y_positions) > 0:
        label_ax.set_ylim(-0.5, len(ordered_labels) - 0.5)
        label_ax.set_xlim(0, 1)
        label_ax.invert_yaxis()
        for y_pos, label_text in zip(y_positions, ordered_labels):
            label_ax.text(0.5, float(y_pos), label_text, ha="center", va="center", fontweight="bold")
    else:
        label_ax.set_xlim(0, 1)
        label_ax.set_ylim(0, 1)
        label_ax.text(0.5, 0.5, "No sessions", ha="center", va="center", color="#555555")

    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(output_path)
    plt.close(fig)


# -------------------------------------------------------------------------------------------------------------------- #
# Private Helper Functions
# -------------------------------------------------------------------------------------------------------------------- #
def _plot_effort_bars(ax: Axes, percentages: list) -> None:
    """
    Render a colored bar chart showing how time is distributed across effort bands.

    :param ax: Matplotlib axes to draw on.
    :param percentages: List of percentage values for each effort band.
    """
    num_base_bins = len(EFFORT_BANDS)
    overflow_percent = percentages[-1] if len(percentages) > num_base_bins else 0.0

    labels = [band[2] for band in EFFORT_BANDS] + [">100%"]
    values = percentages[:num_base_bins] + [overflow_percent]
    x_positions = np.arange(len(labels))

    bars = ax.bar(x_positions, values, color=EFFORT_COLORS[:len(labels)], width=0.7)
    ax.set_xticks(x_positions, labels, rotation=20)
    ax.set_ylim(0, 100)
    ax.grid(axis="y", alpha=0.2)

    max_height = max(values + [1e-6])

    for bar, duration in zip(bars, values):
        if duration <= 0:
            continue
        label = f"{duration:.1f}%"
        text_y = bar.get_height() + (0.01 * max_height)
        ax.text(bar.get_x() + bar.get_width() / 2, text_y,
                label, ha="center", va="bottom", fontsize=8)

def _annotate_missing(ax: Axes, message: str) -> None:
    """
    Display a neutral message in place of a plot when data is unavailable.

    :param ax: Matplotlib axes to annotate.
    :param message: Message to display.
    """
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_facecolor("#f2f2f2")
    ax.text(0.5, 0.5, message, ha="center", va="center", fontsize=10, color="#555555")
    for spine in ax.spines.values():
        spine.set_visible(False)


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