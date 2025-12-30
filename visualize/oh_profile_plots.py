"""
OH Profile EMG Visualization Functions

This module contains functions for creating EMG plots from OH profile JSON data.
These plots are generated AFTER the pipeline writes metrics to JSON files, allowing
visualization from persisted data rather than in-memory arrays.

Uses Active APDF + Rest Time framework for physiologically meaningful metrics:
- Active APDF shows intensity when working (excluding rest)
- Rest metrics show relaxation patterns (rest%, gap frequency)
- Relative intensity bins compare to personal weekly baseline

Plots generated here:
- Rest vs Active time distribution (pie/donut charts)
- Active APDF percentile comparisons
- Session-level metric trends
- Daily-level metric trends

Note: Envelope, APDF, and histogram plots require raw signal arrays and are
generated during processing in emg_pipeline.py.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
import numpy as np

from OH_profile.load import get_OH_profile
from OH_profile.constants import (
    SENSOR_METRICS_KEY, EMG_KEY,
    EMG_DAILY_AGGREGATE_KEY, EMG_WEEKLY_AGGREGATE_KEY,
    # Basic and traditional APDF
    EMG_IEMG_PERCENT_SECONDS_KEY, EMG_APDF_P50_KEY,
    EMG_DURATION_S_KEY, EMG_SESSION_COUNT_KEY,
    # Active APDF (intensity when working)
    EMG_ACTIVE_APDF_P10_KEY, EMG_ACTIVE_APDF_P50_KEY, EMG_ACTIVE_APDF_P90_KEY,
    # Rest metrics
    EMG_REST_PERCENT_KEY, EMG_GAP_FREQUENCY_PER_MINUTE_KEY,
    EMG_MAX_SUSTAINED_ACTIVITY_S_KEY, EMG_ACTIVE_DURATION_S_KEY,
    # Relative bins (weekly level)
    EMG_BIN_BELOW_USUAL_PCT_KEY, EMG_BIN_TYPICAL_LOW_PCT_KEY,
    EMG_BIN_TYPICAL_HIGH_PCT_KEY, EMG_BIN_HIGH_FOR_YOU_PCT_KEY,
)


# -------------------------------------------------------------------------------------------------------------------- #
# Constants
# -------------------------------------------------------------------------------------------------------------------- #

# Colors for rest vs active distribution
REST_ACTIVE_COLORS = ["#4CAF50", "#2196F3"]  # Green for rest, blue for active
REST_ACTIVE_LABELS = ["Rest time (<0.5% MVC)", "Active time (≥0.5% MVC)"]

# Colors for relative intensity bins (compared to weekly baseline)
RELATIVE_BIN_COLORS = ["#81C784", "#4CAF50", "#FF9800", "#F44336"]  # Light green → red
RELATIVE_BIN_LABELS = ["Below usual", "Typical-low", "Typical-high", "High for you"]


# -------------------------------------------------------------------------------------------------------------------- #
# Helper Functions
# -------------------------------------------------------------------------------------------------------------------- #

def ensure_parent(path: Path) -> None:
    """Create parent directories if they don't exist."""
    path.parent.mkdir(parents=True, exist_ok=True)


def _get_emg_data(oh_profile: Dict[str, Any]) -> Dict[str, Any]:
    """Extract EMG data from OH profile, returning empty dict if not found."""
    sensor_metrics = oh_profile.get(SENSOR_METRICS_KEY, {})
    return sensor_metrics.get(EMG_KEY, {})


def _get_rest_active_percentages(metrics: Dict[str, Any]) -> List[float]:
    """Extract rest vs active time percentages from a metrics dict."""
    rest_pct = metrics.get(EMG_REST_PERCENT_KEY, 0.0)
    active_pct = 100.0 - rest_pct
    return [rest_pct, active_pct]


def _get_relative_bin_percentages(metrics: Dict[str, Any]) -> List[float]:
    """Extract relative intensity bin percentages from a metrics dict."""
    return [
        metrics.get(EMG_BIN_BELOW_USUAL_PCT_KEY, 0.0) or 0.0,
        metrics.get(EMG_BIN_TYPICAL_LOW_PCT_KEY, 0.0) or 0.0,
        metrics.get(EMG_BIN_TYPICAL_HIGH_PCT_KEY, 0.0) or 0.0,
        metrics.get(EMG_BIN_HIGH_FOR_YOU_PCT_KEY, 0.0) or 0.0,
    ]


def _get_active_apdf_values(metrics: Dict[str, Any]) -> Dict[str, float]:
    """Extract Active APDF percentile values from a metrics dict."""
    return {
        "P10": metrics.get(EMG_ACTIVE_APDF_P10_KEY, 0.0),
        "P50": metrics.get(EMG_ACTIVE_APDF_P50_KEY, 0.0),
        "P90": metrics.get(EMG_ACTIVE_APDF_P90_KEY, 0.0),
    }


# -------------------------------------------------------------------------------------------------------------------- #
# Rest vs Active Distribution Plots (from JSON)
# -------------------------------------------------------------------------------------------------------------------- #

def plot_day_rest_active_grid_from_json(
    oh_profile: Dict[str, Any],
    date: str,
    plots_root: Path,
    subject_id: str,
    max_sessions: int = 4,
) -> Optional[Path]:
    """
    Plot a left/right rest vs active time distribution grid for a single day.

    Shows the percentage of time in rest (<0.5% MVC) vs active (≥0.5% MVC) states
    for each session. This is a cleaner, more physiologically meaningful view than
    the old arbitrary effort bins.

    :param oh_profile: OH profile dictionary containing EMG metrics.
    :param date: Date string (e.g., "2024-01-15") to plot.
    :param plots_root: Root directory for plots.
    :param subject_id: Subject identifier for plot title and path.
    :param max_sessions: Maximum number of session rows to show.
    :returns: Path to the generated plot, or None if no data available.
    """
    emg_data = _get_emg_data(oh_profile)
    if not emg_data or date not in emg_data:
        return None

    day_data = emg_data[date]
    
    # Collect session labels (exclude daily_aggregate and weekly_aggregate)
    session_labels = [
        key for key in day_data.keys()
        if key not in (EMG_DAILY_AGGREGATE_KEY, EMG_WEEKLY_AGGREGATE_KEY)
    ]
    session_labels = sorted(session_labels)[:max_sessions]
    
    if not session_labels:
        return None

    # Pad to max_sessions
    while len(session_labels) < max_sessions:
        session_labels.append(None)

    sides = ("left", "right")
    n_rows = len(session_labels)
    fig, axes = plt.subplots(n_rows, len(sides), figsize=(12, 2.8 * n_rows), squeeze=False)
    fig.suptitle(f"{subject_id} – {date} – Rest vs Active Time", fontsize=14, fontweight="bold")

    for row_idx, session_label in enumerate(session_labels):
        for col_idx, side in enumerate(sides):
            ax = axes[row_idx][col_idx]
            if row_idx == 0:
                ax.set_title(f"{side.title()} mBAN")

            if session_label is None:
                _annotate_missing(ax, "No session configured")
                continue

            session_data = day_data.get(session_label, {})
            side_metrics = session_data.get(side)

            if side_metrics is None:
                _annotate_missing(ax, "No data for this session")
                continue

            percentages = _get_rest_active_percentages(side_metrics)
            _plot_rest_active_bars(ax, percentages)

            if col_idx == 0:
                ax.set_ylabel("Session time (%)")
            else:
                ax.set_ylabel("")

            ax.text(-0.25, 0.5, session_label, transform=ax.transAxes, rotation=90,
                    va="center", ha="center", fontweight="bold")

    output_path = plots_root / subject_id / date / "summary" / "rest_active_distribution.png"
    ensure_parent(output_path)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(output_path)
    plt.close(fig)
    return output_path


def plot_day_rest_active_donut_from_json(
    oh_profile: Dict[str, Any],
    date: str,
    plots_root: Path,
    subject_id: str,
) -> Optional[List[Path]]:
    """
    Plot daily-aggregate rest vs active time as donuts (left/right).

    Shows rest time (<0.5% MVC) vs active time, plus Active APDF percentiles
    as text annotation in the center.

    :param oh_profile: OH profile dictionary containing EMG metrics.
    :param date: Date string to plot.
    :param plots_root: Root directory for plots.
    :param subject_id: Subject identifier.
    :returns: List of paths to generated plots, or None if no data.
    """
    emg_data = _get_emg_data(oh_profile)
    if not emg_data or date not in emg_data:
        return None

    day_data = emg_data[date]
    daily_agg = day_data.get(EMG_DAILY_AGGREGATE_KEY, {})
    if not daily_agg:
        return None

    output_paths: List[Path] = []
    for side in ("left", "right"):
        side_metrics = daily_agg.get(side)
        if side_metrics is None:
            continue

        percentages = _get_rest_active_percentages(side_metrics)
        active_apdf = _get_active_apdf_values(side_metrics)
        
        output_path = plots_root / subject_id / date / "summary" / f"rest_active_donut_{side}.png"
        ensure_parent(output_path)

        fig, ax = plt.subplots(figsize=(5.5, 5.5))
        wedges, _ = ax.pie(
            percentages,
            colors=REST_ACTIVE_COLORS,
            labels=None,
            wedgeprops={"width": 0.35, "edgecolor": "white"},
            startangle=90,
        )

        # Annotate percentages on the donut
        for i, (wedge, pct) in enumerate(zip(wedges, percentages)):
            if round(pct) < 1:
                continue
            angle = 0.5 * (wedge.theta2 + wedge.theta1)
            radians = np.deg2rad(angle)
            label = f"{pct:.0f}%"
            
            width = getattr(wedge, "width", 0.0)
            inner_r = wedge.r - width * 0.5
            x_inner = inner_r * np.cos(radians)
            y_inner = inner_r * np.sin(radians)
            ax.text(x_inner, y_inner, label, ha="center", va="center", fontsize=10, 
                    color="white", fontweight="bold")

        # Add Active APDF values in center
        center_text = f"Active APDF\nP10: {active_apdf['P10']:.1f}%\nP50: {active_apdf['P50']:.1f}%\nP90: {active_apdf['P90']:.1f}%"
        ax.text(0, 0, center_text, ha="center", va="center", fontsize=9)

        ax.legend(
            wedges,
            REST_ACTIVE_LABELS,
            loc="lower center",
            bbox_to_anchor=(0.5, -0.12),
            ncol=2,
            frameon=True,
            prop={"size": 9},
        )
        ax.set_title(f"{subject_id} – {date} – {side.title()}")
        fig.subplots_adjust(bottom=0.2, top=0.9, left=0.1, right=0.9)
        fig.savefig(output_path, format="png")
        plt.close(fig)
        output_paths.append(output_path)

    return output_paths or None


def plot_day_rest_active_stacks_from_json(
    oh_profile: Dict[str, Any],
    date: str,
    plots_root: Path,
    subject_id: str,
    max_sessions: int = 4,
) -> Optional[Path]:
    """
    Plot stacked rest/active bars per session for left/right mBANs.

    Shows session progression with rest vs active time plus Active APDF P50 values.

    :param oh_profile: OH profile dictionary containing EMG metrics.
    :param date: Date string to plot.
    :param plots_root: Root directory for plots.
    :param subject_id: Subject identifier for plot title and path.
    :param max_sessions: Maximum number of sessions to show.
    :returns: Path to the generated plot, or None if no data available.
    """
    emg_data = _get_emg_data(oh_profile)
    if not emg_data or date not in emg_data:
        return None

    day_data = emg_data[date]
    
    # Collect session labels (exclude aggregates)
    session_labels = [
        key for key in day_data.keys()
        if key not in (EMG_DAILY_AGGREGATE_KEY, EMG_WEEKLY_AGGREGATE_KEY)
    ]
    session_labels = sorted(session_labels)[:max_sessions]
    
    if not session_labels:
        return None

    sides = ("left", "right")

    # Extra height to leave room for a bottom legend without clipping
    fig = plt.figure(figsize=(12, 4.8))
    gs = fig.add_gridspec(1, 3, width_ratios=(1, 0.18, 1), wspace=0.2)
    axes_map = {
        "left": fig.add_subplot(gs[0, 0]),
        "right": fig.add_subplot(gs[0, 2]),
    }
    label_ax = fig.add_subplot(gs[0, 1])
    label_ax.axis("off")
    fig.suptitle(f"{subject_id} – {date} – Rest vs Active", fontsize=14, fontweight="bold")

    legend_handles = []
    legend_labels = []
    y_positions = np.arange(len(session_labels))

    for idx, side in enumerate(sides):
        ax = axes_map[side]
        ax.set_title(f"{side.title()} mBAN – Sessions")
        session_data_list = []
        active_p50_list = []

        for session_label in session_labels:
            session_data = day_data.get(session_label, {})
            side_metrics = session_data.get(side)

            if side_metrics is None:
                session_data_list.append(None)
                active_p50_list.append(None)
                continue

            percentages = _get_rest_active_percentages(side_metrics)
            session_data_list.append(percentages)
            active_p50_list.append(side_metrics.get(EMG_ACTIVE_APDF_P50_KEY, 0.0))

        if not any(session_data_list):
            _annotate_missing(ax, "No sessions for this day")
            continue

        left_offsets = np.zeros(len(session_labels))

        for bin_idx, bin_label in enumerate(REST_ACTIVE_LABELS):
            widths = [values[bin_idx] if values is not None else 0.0 for values in session_data_list]
            bars = ax.barh(y_positions, widths, height=0.6, left=left_offsets,
                           color=REST_ACTIVE_COLORS[bin_idx], label=bin_label)
            left_offsets += widths

            if len(legend_handles) < len(REST_ACTIVE_LABELS):
                legend_handles.append(bars[0])
                legend_labels.append(bin_label)

        # Add Active APDF P50 annotations
        for y_pos, p50 in zip(y_positions, active_p50_list):
            if p50 is not None and p50 > 0:
                text_x = 102 if side == "left" else -2
                halign = "left" if side == "left" else "right"
                ax.text(text_x, float(y_pos), f"P50: {p50:.1f}%", va="center", ha=halign,
                        fontsize=7, color="#333333")

        for y_pos, values in zip(y_positions, session_data_list):
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
        fig.legend(
            legend_handles,
            legend_labels,
            loc="lower center",
            bbox_to_anchor=(0.5, 0.02),
            ncol=len(legend_labels),
            frameon=True,
            prop={"size": 9},
        )

    # Add session labels in center column
    if len(y_positions) > 0:
        label_ax.set_ylim(-0.5, len(session_labels) - 0.5)
        for y_pos, session_label in zip(y_positions, session_labels):
            label_ax.text(0.5, float(y_pos), session_label, va="center", ha="center", fontweight="bold")
        label_ax.invert_yaxis()

    output_path = plots_root / subject_id / date / "summary" / "rest_active_sessions.png"
    ensure_parent(output_path)
    fig.subplots_adjust(bottom=0.22, top=0.9, left=0.08, right=0.98)
    fig.savefig(output_path)
    plt.close(fig)
    return output_path


def plot_week_rest_active_stacks_from_json(
    oh_profile: Dict[str, Any],
    plots_root: Path,
    subject_id: str,
) -> Optional[Path]:
    """
    Show session rest/active time per day, with left/right side-by-side, ordered by day.
    
    :param oh_profile: OH profile dictionary containing EMG metrics.
    :param plots_root: Root directory for plots.
    :param subject_id: Subject identifier.
    :returns: Path to generated plot, or None if no data.
    """
    emg_data = _get_emg_data(oh_profile)
    if not emg_data:
        return None

    # Collect per-day session data
    dates = [d for d in sorted(emg_data.keys()) if d != EMG_WEEKLY_AGGREGATE_KEY]
    if not dates:
        return None

    day_sessions: Dict[str, List[tuple[str, Dict[str, Any]]]] = {}
    max_sessions_for_layout = 0
    for date in dates:
        day_data = emg_data[date]
        sessions = [
            (label, session_data)
            for label, session_data in day_data.items()
            if label not in (EMG_DAILY_AGGREGATE_KEY, EMG_WEEKLY_AGGREGATE_KEY)
        ]
        sessions.sort(key=lambda x: x[0])
        day_sessions[date] = sessions
        max_sessions_for_layout = max(max_sessions_for_layout, len(sessions))

    # Layout: up to 3 days per row; center the final row when incomplete
    n_cols = min(3, len(dates))
    n_rows = int(np.ceil(len(dates) / n_cols))
    # Height per row scales with session count; width scales with columns. Add extra height for legend band.
    fig = plt.figure(figsize=(5 * n_cols, (max(2.5, 1.2 * max_sessions_for_layout) + 0.6) * n_rows))
    
    # Use 2x columns to allow centering of 1 or 2 items in a 3-column layout
    grid_cols = n_cols * 2
    outer_gs = fig.add_gridspec(n_rows, grid_cols, wspace=0.35, hspace=0.6)
    fig.suptitle(f"{subject_id} – Week Rest vs Active", fontsize=14, fontweight="bold")

    legend_handles: List[Any] = []
    legend_labels: List[str] = []

    for idx, date in enumerate(dates):
        row = idx // n_cols
        col_in_row = idx % n_cols
        
        # Calculate column span
        # Default: each item takes 2 grid columns
        # If it's the last row, we might need to offset
        
        items_in_this_row = n_cols
        if row == n_rows - 1:
            items_in_this_row = len(dates) % n_cols
            if items_in_this_row == 0:
                items_in_this_row = n_cols
        
        # Calculate offset to center the items
        # Total grid width = n_cols * 2
        # Items width = items_in_this_row * 2
        # Empty space = (n_cols * 2) - (items_in_this_row * 2)
        # Start offset = Empty space // 2
        
        offset = (grid_cols - items_in_this_row * 2) // 2
        
        col_start = offset + col_in_row * 2
        col_end = col_start + 2

        sub_gs = outer_gs[row, col_start:col_end].subgridspec(1, 3, width_ratios=(1, 0.32, 1), wspace=0.08)
        left_ax = fig.add_subplot(sub_gs[0, 0])
        right_ax = fig.add_subplot(sub_gs[0, 2])
        label_ax = fig.add_subplot(sub_gs[0, 1])
        label_ax.axis("off")
        day_label = f"Day {idx + 1}"
        label_ax.set_title(day_label, fontweight="bold", fontsize=10)

        sessions = day_sessions.get(date, [])
        if not sessions:
            _annotate_missing(left_ax, "No sessions")
            _annotate_missing(right_ax, "No sessions")
            left_ax.set_title("Left mBAN")
            right_ax.set_title("Right mBAN")
            continue

        y_positions = np.arange(len(sessions))
        for ax, side in ((left_ax, "left"), (right_ax, "right")):
            session_percentages = []
            for _, session_data in sessions:
                side_metrics = session_data.get(side)
                if side_metrics is None:
                    session_percentages.append(None)
                else:
                    session_percentages.append(_get_rest_active_percentages(side_metrics))

            all_missing = all(vals is None for vals in session_percentages)
            if all_missing:
                _annotate_missing(ax, "MVC missing")
                ax.set_title(f"{side.title()} mBAN")
                continue

            left_offsets = np.zeros(len(sessions))
            for bin_idx, bin_label in enumerate(REST_ACTIVE_LABELS):
                widths = [vals[bin_idx] if vals is not None else 0.0 for vals in session_percentages]
                bars = ax.barh(
                    y_positions,
                    widths,
                    height=0.6,
                    left=left_offsets,
                    color=REST_ACTIVE_COLORS[bin_idx],
                    label=bin_label,
                )
                left_offsets += widths

                # Capture legend only once
                if len(legend_handles) < len(REST_ACTIVE_LABELS):
                    legend_handles.append(bars[0])
                    legend_labels.append(bin_label)

            ax.set_yticks(y_positions)
            ax.set_yticklabels([])
            ax.set_xlim(0, 100)
            ax.set_xlabel("Session time (%)")
            ax.invert_yaxis()
            if side == "left":
                ax.invert_xaxis()
            ax.set_title(f"{side.title()} mBAN")
            ax.grid(axis="x", alpha=0.2)

        # Session labels in center
        label_ax.set_ylim(-0.5, len(sessions) - 0.5)
        for y_pos, (session_label, _) in zip(y_positions, sessions):
            label_ax.text(0.5, float(y_pos), session_label, va="center", ha="center", fontsize=8, fontweight="bold")
        label_ax.invert_yaxis()

    if legend_handles:
        fig.legend(
            legend_handles,
            legend_labels,
            loc="lower center",
            bbox_to_anchor=(0.5, 0.02),
            ncol=len(legend_labels),
            frameon=True,
            prop={"size": 9},
        )

    output_path = plots_root / subject_id / "week" / "rest_active_sessions_week.png"
    ensure_parent(output_path)
    fig.subplots_adjust(bottom=0.18, top=0.92, left=0.06, right=0.98)
    fig.savefig(output_path, format="png")
    plt.close(fig)
    return output_path


# -------------------------------------------------------------------------------------------------------------------- #
# Metric Trend Plots (from JSON)
# -------------------------------------------------------------------------------------------------------------------- #

def plot_session_metric_trends_from_json(
    oh_profile: Dict[str, Any],
    date: str,
    plots_root: Path,
    subject_id: str,
    metrics: Sequence[str] = (EMG_IEMG_PERCENT_SECONDS_KEY, EMG_APDF_P50_KEY),
) -> List[Path]:
    """
    Plot metric values across sessions for a single day, showing session progression.

    :param oh_profile: OH profile dictionary containing EMG metrics.
    :param date: Date string to plot.
    :param plots_root: Root directory for plots.
    :param subject_id: Subject identifier.
    :param metrics: Metric keys to plot.
    :returns: List of paths to generated plots.
    """
    emg_data = _get_emg_data(oh_profile)
    if not emg_data or date not in emg_data:
        return []

    day_data = emg_data[date]
    output_paths = []

    # Collect session data for each side
    for side in ("left", "right"):
        session_values: Dict[str, Dict[str, float]] = {}
        
        for session_label, session_data in day_data.items():
            if session_label in (EMG_DAILY_AGGREGATE_KEY, EMG_WEEKLY_AGGREGATE_KEY):
                continue
            
            side_metrics = session_data.get(side)
            if side_metrics is None:
                continue
            
            session_values[session_label] = {
                metric: side_metrics.get(metric, 0.0) for metric in metrics
            }

        if len(session_values) < 2:
            # Need at least 2 sessions to show progression
            continue

        session_labels = sorted(session_values.keys())

        for metric in metrics:
            values = [session_values[s][metric] for s in session_labels]
            
            # Calculate percentage changes
            pct_changes = [0.0]  # First session has no change
            for i in range(1, len(values)):
                if values[i-1] != 0:
                    pct_changes.append(((values[i] - values[i-1]) / values[i-1]) * 100)
                else:
                    pct_changes.append(0.0)

            output_dir = plots_root / subject_id / date / side / "trends"
            output_path = output_dir / f"session_change_{metric}.png"
            ensure_parent(output_path)

            plt.figure(figsize=(8, 5))
            plt.plot(session_labels, pct_changes, marker="o")
            plt.title(f"Session Δ {metric} – {subject_id} {side} {date}")
            plt.xlabel("Session Label")
            plt.ylabel("% change")
            plt.grid(True, alpha=0.3)
            plt.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
            plt.tight_layout()
            plt.savefig(output_path)
            plt.close()
            output_paths.append(output_path)

    return output_paths


def plot_daily_metric_trends_from_json(
    oh_profile: Dict[str, Any],
    plots_root: Path,
    subject_id: str,
    metrics: Sequence[str] = (EMG_IEMG_PERCENT_SECONDS_KEY, EMG_APDF_P50_KEY),
) -> List[Path]:
    """
    Plot metric values across days, showing daily progression.

    :param oh_profile: OH profile dictionary containing EMG metrics.
    :param plots_root: Root directory for plots.
    :param subject_id: Subject identifier.
    :param metrics: Metric keys to plot.
    :returns: List of paths to generated plots.
    """
    emg_data = _get_emg_data(oh_profile)
    if not emg_data:
        return []

    output_paths = []

    # Collect daily aggregate data for each side
    for side in ("left", "right"):
        daily_values: Dict[str, Dict[str, float]] = {}
        
        for date, day_data in emg_data.items():
            if date == EMG_WEEKLY_AGGREGATE_KEY:
                continue
            
            daily_agg = day_data.get(EMG_DAILY_AGGREGATE_KEY, {})
            side_metrics = daily_agg.get(side)
            
            if side_metrics is None:
                continue
            
            daily_values[date] = {
                metric: side_metrics.get(metric, 0.0) for metric in metrics
            }

        if len(daily_values) < 2:
            # Need at least 2 days to show progression
            continue

        dates = sorted(daily_values.keys())

        for metric in metrics:
            values = [daily_values[d][metric] for d in dates]
            
            # Calculate percentage changes
            pct_changes = [0.0]  # First day has no change
            for i in range(1, len(values)):
                if values[i-1] != 0:
                    pct_changes.append(((values[i] - values[i-1]) / values[i-1]) * 100)
                else:
                    pct_changes.append(0.0)

            output_dir = plots_root / subject_id / "cross_day_trends" / side
            output_path = output_dir / f"daily_change_{metric}.png"
            ensure_parent(output_path)

            plt.figure(figsize=(8, 5))
            plt.plot(dates, pct_changes, marker="o")
            plt.title(f"Daily Δ {metric} – {subject_id} {side}")
            plt.xlabel("Date")
            plt.ylabel("% change")
            plt.xticks(rotation=45)
            plt.grid(True, alpha=0.3)
            plt.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
            plt.tight_layout()
            plt.savefig(output_path)
            plt.close()
            output_paths.append(output_path)

    return output_paths


# -------------------------------------------------------------------------------------------------------------------- #
# Relative Intensity Bin Plots (from JSON)
# -------------------------------------------------------------------------------------------------------------------- #

def plot_day_relative_bins_from_json(
    oh_profile: Dict[str, Any],
    date: str,
    plots_root: Path,
    subject_id: str,
) -> Optional[List[Path]]:
    """
    Plot daily-aggregate relative intensity bins as donuts (left/right).
    
    Shows how the day's active EMG compares to the subject's weekly baseline:
    - Below usual: active EMG < weekly P10
    - Typical-low: between P10 and P50
    - Typical-high: between P50 and P90  
    - High for you: above weekly P90
    
    :param oh_profile: OH profile dictionary containing EMG metrics.
    :param date: Date string to plot.
    :param plots_root: Root directory for plots.
    :param subject_id: Subject identifier.
    :returns: List of paths to generated plots, or None if no data.
    """
    emg_data = _get_emg_data(oh_profile)
    if not emg_data or date not in emg_data:
        return None

    day_data = emg_data[date]
    daily_agg = day_data.get(EMG_DAILY_AGGREGATE_KEY, {})
    if not daily_agg:
        return None

    output_paths: List[Path] = []
    for side in ("left", "right"):
        side_metrics = daily_agg.get(side)
        if side_metrics is None:
            continue

        # Get relative bin percentages
        bin_percentages = _get_relative_bin_percentages(side_metrics)
        
        # Skip if no bins computed (all None/0)
        if all(p is None or p == 0.0 for p in bin_percentages):
            continue
        
        # Replace None with 0 for plotting
        bin_percentages = [p if p is not None else 0.0 for p in bin_percentages]
        
        # Also get Active APDF for center annotation
        active_apdf = _get_active_apdf_values(side_metrics)
        
        output_path = plots_root / subject_id / date / "summary" / f"relative_bins_donut_{side}.png"
        ensure_parent(output_path)

        fig, ax = plt.subplots(figsize=(5.5, 5.5))
        
        # Filter out zero values for cleaner donut
        non_zero_indices = [i for i, p in enumerate(bin_percentages) if p > 0]
        plot_percentages = [bin_percentages[i] for i in non_zero_indices]
        plot_colors = [RELATIVE_BIN_COLORS[i] for i in non_zero_indices]
        plot_labels = [RELATIVE_BIN_LABELS[i] for i in non_zero_indices]
        
        if not plot_percentages:
            plt.close(fig)
            continue
            
        wedges, _ = ax.pie(
            plot_percentages,
            colors=plot_colors,
            labels=None,
            wedgeprops={"width": 0.35, "edgecolor": "white"},
            startangle=90,
        )

        # Annotate percentages on the donut
        for i, (wedge, pct) in enumerate(zip(wedges, plot_percentages)):
            if round(pct) < 5:
                continue
            angle = 0.5 * (wedge.theta2 + wedge.theta1)
            radians = np.deg2rad(angle)
            label = f"{pct:.0f}%"
            
            width = getattr(wedge, "width", 0.0)
            inner_r = wedge.r - width * 0.5
            x_inner = inner_r * np.cos(radians)
            y_inner = inner_r * np.sin(radians)
            ax.text(x_inner, y_inner, label, ha="center", va="center", fontsize=10, 
                    color="white", fontweight="bold")

        # Add Active APDF values in center
        center_text = f"Active APDF\nP10: {active_apdf['P10']:.1f}%\nP50: {active_apdf['P50']:.1f}%\nP90: {active_apdf['P90']:.1f}%"
        ax.text(0, 0, center_text, ha="center", va="center", fontsize=9)

        # Legend with all four bins (even if some are 0)
        legend_handles = [plt.Rectangle((0, 0), 1, 1, fc=RELATIVE_BIN_COLORS[i]) 
                          for i in range(len(RELATIVE_BIN_LABELS))]
        ax.legend(
            legend_handles,
            RELATIVE_BIN_LABELS,
            loc="lower center",
            bbox_to_anchor=(0.5, -0.12),
            ncol=2,
            frameon=True,
            prop={"size": 9},
        )
        ax.set_title(f"{subject_id} – {date} – {side.title()}\nRelative Intensity (vs Weekly Baseline)")
        fig.subplots_adjust(bottom=0.2, top=0.88, left=0.1, right=0.9)
        fig.savefig(output_path, format="png")
        plt.close(fig)
        output_paths.append(output_path)

    return output_paths or None


def plot_day_relative_bins_stacks_from_json(
    oh_profile: Dict[str, Any],
    date: str,
    plots_root: Path,
    subject_id: str,
    max_sessions: int = 4,
) -> Optional[Path]:
    """
    Plot stacked relative intensity bins per session for left/right mBANs.
    
    Shows session progression with intensity compared to weekly baseline.
    
    :param oh_profile: OH profile dictionary containing EMG metrics.
    :param date: Date string to plot.
    :param plots_root: Root directory for plots.
    :param subject_id: Subject identifier for plot title and path.
    :param max_sessions: Maximum number of sessions to show.
    :returns: Path to the generated plot, or None if no data available.
    """
    emg_data = _get_emg_data(oh_profile)
    if not emg_data or date not in emg_data:
        return None

    day_data = emg_data[date]
    
    # Collect session labels (exclude aggregates)
    session_labels = [
        key for key in day_data.keys()
        if key not in (EMG_DAILY_AGGREGATE_KEY, EMG_WEEKLY_AGGREGATE_KEY)
    ]
    session_labels = sorted(session_labels)[:max_sessions]
    
    if not session_labels:
        return None
    
    # Check if any session has relative bins
    has_bins = False
    for session_label in session_labels:
        session_data = day_data.get(session_label, {})
        for side in ("left", "right"):
            side_metrics = session_data.get(side, {})
            bin_pcts = _get_relative_bin_percentages(side_metrics)
            if any(p is not None and p > 0 for p in bin_pcts):
                has_bins = True
                break
        if has_bins:
            break
    
    if not has_bins:
        return None

    sides = ("left", "right")

    fig = plt.figure(figsize=(12, 4.8))
    gs = fig.add_gridspec(1, 3, width_ratios=(1, 0.18, 1), wspace=0.2)
    axes_map = {
        "left": fig.add_subplot(gs[0, 0]),
        "right": fig.add_subplot(gs[0, 2]),
    }
    label_ax = fig.add_subplot(gs[0, 1])
    label_ax.axis("off")
    fig.suptitle(f"{subject_id} – {date} – Relative Intensity (vs Weekly Baseline)", fontsize=14, fontweight="bold")

    legend_handles = []
    legend_labels = []
    y_positions = np.arange(len(session_labels))

    for idx, side in enumerate(sides):
        ax = axes_map[side]
        ax.set_title(f"{side.title()} mBAN – Sessions")
        session_data_list = []

        for session_label in session_labels:
            session_data = day_data.get(session_label, {})
            side_metrics = session_data.get(side)

            if side_metrics is None:
                session_data_list.append(None)
                continue

            bin_pcts = _get_relative_bin_percentages(side_metrics)
            # Replace None with 0
            bin_pcts = [p if p is not None else 0.0 for p in bin_pcts]
            session_data_list.append(bin_pcts)

        if not any(session_data_list):
            _annotate_missing(ax, "No sessions for this day")
            continue

        left_offsets = np.zeros(len(session_labels))

        for bin_idx, bin_label in enumerate(RELATIVE_BIN_LABELS):
            widths = [values[bin_idx] if values is not None else 0.0 for values in session_data_list]
            bars = ax.barh(y_positions, widths, height=0.6, left=left_offsets,
                           color=RELATIVE_BIN_COLORS[bin_idx], label=bin_label)
            left_offsets += widths

            if len(legend_handles) < len(RELATIVE_BIN_LABELS):
                legend_handles.append(bars[0])
                legend_labels.append(bin_label)

        for y_pos, values in zip(y_positions, session_data_list):
            if values is None or sum(values) == 0:
                text_x = -1 if side == "left" else 101
                halign = "right" if side == "left" else "left"
                ax.text(text_x, float(y_pos), "no data", va="center", ha=halign,
                        fontsize=8, color="#555555")

        ax.set_yticks(y_positions)
        ax.set_yticklabels([])
        ax.set_xlim(0, 100)
        ax.set_xlabel("Active time (%)")
        ax.invert_yaxis()
        ax.grid(axis="x", alpha=0.2)

        if side == "left":
            ax.invert_xaxis()

    if legend_handles:
        fig.legend(
            legend_handles,
            legend_labels,
            loc="lower center",
            bbox_to_anchor=(0.5, 0.02),
            ncol=len(legend_labels),
            frameon=True,
            prop={"size": 9},
        )

    # Add session labels in center column
    if len(y_positions) > 0:
        label_ax.set_ylim(-0.5, len(session_labels) - 0.5)
        for y_pos, session_label in zip(y_positions, session_labels):
            label_ax.text(0.5, float(y_pos), session_label, va="center", ha="center", fontweight="bold")
        label_ax.invert_yaxis()

    output_path = plots_root / subject_id / date / "summary" / "relative_bins_sessions.png"
    ensure_parent(output_path)
    fig.subplots_adjust(bottom=0.22, top=0.9, left=0.08, right=0.98)
    fig.savefig(output_path)
    plt.close(fig)
    return output_path


# -------------------------------------------------------------------------------------------------------------------- #
# Internal Helper Functions
# -------------------------------------------------------------------------------------------------------------------- #

def _annotate_missing(ax: Axes, text: str) -> None:
    """Add a centered text annotation to an axis indicating missing data."""
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    ax.text(0.5, 0.5, text, transform=ax.transAxes, ha="center", va="center",
            fontsize=12, color="#888888")


def _plot_rest_active_bars(ax: Axes, percentages: List[float]) -> None:
    """Plot horizontal stacked bars for rest vs active percentages."""
    cumulative = 0.0
    for i, pct in enumerate(percentages):
        ax.barh(0, pct, left=cumulative, color=REST_ACTIVE_COLORS[i], height=0.6)
        cumulative += pct
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.5, 0.5)
    ax.set_yticks([])
    ax.set_xlabel("Session time (%)")


# -------------------------------------------------------------------------------------------------------------------- #
# Main Functions for Pipeline Integration
# -------------------------------------------------------------------------------------------------------------------- #

def generate_emg_plots_from_oh_profiles(
    oh_profiles_path: str,
    subject_ids: Sequence[str],
    plots_root: Path,
) -> Dict[str, List[Path]]:
    """
    Generate all EMG visualizations from OH profile JSON files.

    This function reads the persisted OH profiles and generates:
    - Day-level rest vs active distribution grids
    - Day-level rest vs active donuts with Active APDF
    - Day-level relative intensity bin donuts (vs weekly baseline)
    - Relative intensity bin session stacks
    - Session-level metric trends
    - Daily-level metric trends
    - Week-level rest vs active stacks

    :param oh_profiles_path: Path to folder containing OH profile JSON files.
    :param subject_ids: List of subject IDs to process.
    :param plots_root: Root directory for generated plots.
    :returns: Dict mapping subject_id to list of generated plot paths.
    """
    all_plots: Dict[str, List[Path]] = {}

    for subject_id in subject_ids:
        subject_id_str = str(subject_id)
        oh_profile = get_OH_profile(oh_profiles_path, subject_id_str)
        emg_data = _get_emg_data(oh_profile)
        
        if not emg_data:
            print(f"[oh_profile_plots] No EMG data for subject {subject_id_str}")
            continue

        subject_plots: List[Path] = []

        # Get all dates (excluding weekly_aggregate key)
        dates = [
            key for key in emg_data.keys()
            if key != EMG_WEEKLY_AGGREGATE_KEY
        ]

        for date in sorted(dates):
            # Generate rest vs active distribution grid
            rest_active_grid_path = plot_day_rest_active_grid_from_json(
                oh_profile, date, plots_root, subject_id_str
            )
            if rest_active_grid_path:
                subject_plots.append(rest_active_grid_path)

            # Generate daily aggregate rest vs active donuts (png)
            rest_active_donut_paths = plot_day_rest_active_donut_from_json(
                oh_profile, date, plots_root, subject_id_str
            )
            if rest_active_donut_paths:
                subject_plots.extend(rest_active_donut_paths)

            # Generate rest vs active session stacks
            rest_active_stacks_path = plot_day_rest_active_stacks_from_json(
                oh_profile, date, plots_root, subject_id_str
            )
            if rest_active_stacks_path:
                subject_plots.append(rest_active_stacks_path)

            # Generate relative intensity bin donuts (vs weekly baseline)
            relative_bin_donut_paths = plot_day_relative_bins_from_json(
                oh_profile, date, plots_root, subject_id_str
            )
            if relative_bin_donut_paths:
                subject_plots.extend(relative_bin_donut_paths)

            # Generate relative intensity bin session stacks
            relative_bin_stacks_path = plot_day_relative_bins_stacks_from_json(
                oh_profile, date, plots_root, subject_id_str
            )
            if relative_bin_stacks_path:
                subject_plots.append(relative_bin_stacks_path)

            # Generate session-level metric trends
            session_trend_paths = plot_session_metric_trends_from_json(
                oh_profile, date, plots_root, subject_id_str
            )
            subject_plots.extend(session_trend_paths)

        # Generate daily-level metric trends (cross-day)
        daily_trend_paths = plot_daily_metric_trends_from_json(
            oh_profile, plots_root, subject_id_str
        )
        subject_plots.extend(daily_trend_paths)

        # Generate week-level stacked sessions view (png)
        week_stack_path = plot_week_rest_active_stacks_from_json(
            oh_profile, plots_root, subject_id_str
        )
        if week_stack_path:
            subject_plots.append(week_stack_path)

        if subject_plots:
            all_plots[subject_id_str] = subject_plots
            print(f"[oh_profile_plots] Generated {len(subject_plots)} plots for subject {subject_id_str}")

    return all_plots

    return all_plots
