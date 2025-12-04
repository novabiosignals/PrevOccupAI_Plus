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
from typing import Sequence

import matplotlib.pyplot as plt
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
    ordered_labels = list(dict.fromkeys(session_labels))
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
                ax.text(text_x, y_pos, "no data", va="center", ha=halign,
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
            label_ax.text(0.5, y_pos, label_text, ha="center", va="center", fontweight="bold")
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

def _plot_effort_bars(ax: plt.Axes, percentages: list) -> None:
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


def _annotate_missing(ax: plt.Axes, message: str) -> None:
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
