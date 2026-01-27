"""
EMG OH Profile Visualizations

This module generates visualization plots from OH profile JSON files:
- Daily relative intensity donut charts (aggregate per day)
- Weekly relative intensity bins overview (3 days per row)
- Daily relative intensity session stacks
- Weekly Active APDF trends
- Session timeline with relative intensity zones (using OH profile baseline)

All functions in this module READ pre-computed metrics from OH profiles.
For functions that COMPUTE metrics from raw signals, see emg_research.py.

Plot labels and legends are in European Portuguese.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.dates as mdates
from matplotlib.transforms import Bbox
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from datetime import datetime, timedelta
from babel.dates import format_date
from scipy.ndimage import uniform_filter1d

from OH_profile.constants import (
    SENSOR_METRICS_KEY,
    EMG_KEY,
    EMG_APDF_GROUP_KEY,
    EMG_APDF_ACTIVE_KEY,
    EMG_APDF_P10_KEY,
    EMG_APDF_P50_KEY,
    EMG_APDF_P90_KEY,
    EMG_RELATIVE_BINS_GROUP_KEY,
    EMG_BIN_BELOW_USUAL_PCT_KEY,
    EMG_BIN_TYPICAL_LOW_PCT_KEY,
    EMG_BIN_TYPICAL_HIGH_PCT_KEY,
    EMG_BIN_HIGH_FOR_YOU_PCT_KEY,
    EMG_DAILY_AGGREGATE_KEY,
    EMG_WEEKLY_AGGREGATE_KEY,
)
from OH_profile.load import get_OH_profile
from OH_profile.emg_oh_helper import get_emg_apdf_active, get_emg_relative_bins


# -------------------------------------------------------------------------------------------------------------------- #
# Constants - Portuguese Labels for Plots
# -------------------------------------------------------------------------------------------------------------------- #

# Colors for relative intensity bins (ordered by intensity: lightest to darkest)
RELATIVE_BIN_COLORS = ["#C8E6C9FF", "#A5D6A7FF", "#FFCC80FF", "#EF9A9AFF"]

# Color for "no data" indicators
NO_DATA_COLOR = "#E0E0E0"
RELATIVE_BIN_KEYS = [
    EMG_BIN_BELOW_USUAL_PCT_KEY,
    EMG_BIN_TYPICAL_LOW_PCT_KEY,
    EMG_BIN_TYPICAL_HIGH_PCT_KEY,
    EMG_BIN_HIGH_FOR_YOU_PCT_KEY,
]

# Portuguese labels for relative intensity bins
RELATIVE_BIN_LABELS_PT = [
    "Abaixo do habitual",
    "Típico-baixo",
    "Típico-alto",
    "Alto para si",
]

# Portuguese translations for plot text
TRANSLATIONS_PT = {
    "left": "Esquerdo",
    "right": "Direito",
    "Left mBAN": "Ombro Esquerdo",
    "Right mBAN": "Ombro Direito",
    "Day": "Dia",
    "Active time (%)": "Tempo ativo (%)",
    "Relative Intensity (vs Weekly Baseline)": "Intensidade Relativa (vs Linha de Base Semanal)",
    "Week Relative Intensity Overview": "Visão Geral Semanal de Intensidade Relativa",
    "Weekly Active APDF Trend": "Tendência Semanal de APDF Ativo",
    "Active APDF (%MVC)": "APDF Ativo (%MVC)",
    "Date": "Data",
    "No data": "Sem dados",
    "No sessions": "Sem sessões",
    "MVC underestimated": "MVC subestimado",
    "Time": "Hora",
    "EMG (%MVC)": "EMG (%MVC)",
    "Rest": "Descanso",
    "Left": "Esquerdo",
    "Right": "Direito",
    "Session Timeline": "Cronograma da Sessão",
    "Summary": "Resumo",
    "min": "min",
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

# Timeline processing constants
RMS_WINDOW_S = 0.5
REST_THRESHOLD_MVC = 0.5
TIME_BIN_S = 5

# Timeline bin colors
COLOR_BELOW_USUAL = "#8BC34A"
COLOR_TYPICAL_LOW = "#4CAF50"
COLOR_TYPICAL_HIGH = "#FF9800"
COLOR_HIGH_FOR_YOU = "#F44336"
COLOR_ENVELOPE = "#1565C0"
COLOR_THRESHOLD_LINES = "#666666"

BIN_COLORS = [COLOR_BELOW_USUAL, COLOR_TYPICAL_LOW, COLOR_TYPICAL_HIGH, COLOR_HIGH_FOR_YOU]
BIN_LABELS_PT = ["Abaixo do habitual", "Típico-baixo", "Típico-alto", "Alto para si"]


# -------------------------------------------------------------------------------------------------------------------- #
# Helper Functions
# -------------------------------------------------------------------------------------------------------------------- #

def ensure_parent(path: Path) -> None:
    """Create parent directories if they don't exist."""
    path.parent.mkdir(parents=True, exist_ok=True)


def dates_to_weekdays(
    dates: List[str],
    date_format: str,
    locale: str = "en",
) -> List[str]:
    """
    Convert a list of date strings to localized weekday names.

    :param dates: List of date strings
    :param date_format: Format used to parse the input dates
    :param locale: Locale code (e.g. 'en', 'pt', 'pt_PT')
    :return: List of weekday names
    """
    fallback_formats = [
        date_format,
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%Y_%m_%d",
        "%d_%m_%Y",
    ]

    labels: List[str] = []
    for date_str in dates:
        parsed = None
        for fmt in fallback_formats:
            try:
                parsed = datetime.strptime(date_str, fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            labels.append(date_str)
            continue
        labels.append(format_date(parsed, format="EEEE", locale=locale))
    return labels


def _annotate_missing(ax: Axes, text: str) -> None:
    """Add a centered text annotation to an axis indicating missing data."""
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_facecolor(NO_DATA_COLOR)
    ax.axis("off")
    ax.text(0.5, 0.5, text, transform=ax.transAxes, ha="center", va="center",
            fontsize=12, color="#888888")


def _get_flagged_sessions(session_metrics_path: Optional[Path] = None) -> set:
    """
    Load flagged sessions from session_metrics.csv.

    Returns set of tuples (subject_id, side, date, session_label) that are flagged.
    """
    if session_metrics_path is None:
        session_metrics_path = Path(r"D:\Backup PrevOccupAI_PLUS Data\results\emg_pipeline\session_metrics.csv")

    if not session_metrics_path.exists():
        return set()

    try:
        df = pd.read_csv(session_metrics_path)
        if 'mvc_quality_flag' not in df.columns:
            return set()

        flagged = df[df['mvc_quality_flag'] == 'mvc_underestimated']
        return {
            (str(row['subject_id']), row['side'], row['date'], row['session_label'])
            for _, row in flagged.iterrows()
        }
    except Exception:
        return set()


def _get_emg_data(oh_profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract EMG sensor data from OH profile."""
    if not oh_profile:
        return None
    sensor_metrics = oh_profile.get(SENSOR_METRICS_KEY, {})
    return sensor_metrics.get(EMG_KEY)


def _get_relative_bin_percentages(metrics: Dict[str, Any]) -> List[Optional[float]]:
    """Extract relative intensity bin percentages from nested metrics dictionary."""
    bins = metrics.get(EMG_RELATIVE_BINS_GROUP_KEY, {})
    return [
        bins.get(key)
        for key in RELATIVE_BIN_KEYS
    ]


# -------------------------------------------------------------------------------------------------------------------- #
# OH Profile Baseline Extraction
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


def create_baseline_from_oh_profile(
    oh_profile: dict,
    side: str,
) -> Optional[Dict[str, float]]:
    """
    Extract weekly baseline from an OH profile for timeline generation.

    This function reads the pre-computed weekly Active APDF percentiles from
    an OH profile JSON and returns them as a baseline dictionary for use
    in timeline visualizations.

    :param oh_profile: OH profile dictionary.
    :param side: 'left' or 'right'.
    :returns: Dict with 'p10', 'p50', 'p90' keys, or None if data not available.
    """
    try:
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
        print(f"[emg_oh] Error extracting baseline from OH profile: {e}")

    return None


# -------------------------------------------------------------------------------------------------------------------- #
# Daily Aggregate Donut Charts - Relative Intensity Bins
# -------------------------------------------------------------------------------------------------------------------- #

def plot_day_relative_bins_donut_from_json(
    oh_profile: Dict[str, Any],
    date: str,
    plots_root: Path,
    subject_id: str,
) -> Optional[List[Path]]:
    """
    Plot daily aggregate relative intensity bin donut charts (one per side).

    This generates a donut chart showing the distribution of time spent in
    each relative intensity bin for the ENTIRE DAY (aggregate of all sessions).

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

        bin_percentages = _get_relative_bin_percentages(side_metrics)
        # Replace None with 0
        bin_percentages = [p if p is not None else 0.0 for p in bin_percentages]

        # Check if we have any data
        if sum(bin_percentages) == 0:
            continue

        output_path = plots_root / subject_id / date / "summary" / f"relative_bins_donut_{side}.png"
        ensure_parent(output_path)

        fig, ax = plt.subplots(figsize=(5.5, 5.5))

        # Only include non-zero slices
        sizes = []
        colors = []
        labels = []
        for i, pct in enumerate(bin_percentages):
            if pct > 0:
                sizes.append(pct)
                colors.append(RELATIVE_BIN_COLORS[i])
                labels.append(RELATIVE_BIN_LABELS_PT[i])

        wedges, texts = ax.pie(  # type: ignore[misc]
            sizes,
            colors=colors,
            labels=None,
            wedgeprops={"width": 0.35, "edgecolor": "white"},
            startangle=90,
        )

        # Annotate percentages on the donut
        for i, (wedge, pct) in enumerate(zip(wedges, sizes)):
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

        # Legend with all four bins (as handles even if some are 0)
        legend_handles = [mpatches.Patch(fc=RELATIVE_BIN_COLORS[i])
                          for i in range(len(RELATIVE_BIN_LABELS_PT))]
        ax.legend(
            legend_handles,
            RELATIVE_BIN_LABELS_PT,
            loc="lower center",
            bbox_to_anchor=(0.5, -0.12),
            ncol=2,
            frameon=True,
            prop={"size": 9},
        )

        side_label = TRANSLATIONS_PT[side]
        ax.set_title(f"{subject_id} – {date} – {side_label}\n{TRANSLATIONS_PT['Relative Intensity (vs Weekly Baseline)']}")
        fig.subplots_adjust(bottom=0.2, top=0.88, left=0.1, right=0.9)
        fig.savefig(output_path, format="png", dpi=150)
        plt.close(fig)
        output_paths.append(output_path)

    return output_paths or None


# -------------------------------------------------------------------------------------------------------------------- #
# Daily Session Stacks - Relative Intensity Bins
# -------------------------------------------------------------------------------------------------------------------- #

def plot_day_relative_bins_stacks_from_json(
    oh_profile: Dict[str, Any],
    date: str,
    plots_root: Path,
    subject_id: str,
    max_sessions: int = 4,
    flagged_sessions: Optional[set] = None,
) -> Optional[Path]:
    """
    Plot stacked relative intensity bins per session for left/right mBANs.

    Shows session progression with intensity compared to weekly baseline.

    :param oh_profile: OH profile dictionary containing EMG metrics.
    :param date: Date string to plot.
    :param plots_root: Root directory for plots.
    :param subject_id: Subject identifier for plot title and path.
    :param max_sessions: Maximum number of sessions to show.
    :param flagged_sessions: Set of flagged (subject, side, date, session) tuples.
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
    gs = fig.add_gridspec(1, 3, width_ratios=(1, 0.25, 1), wspace=0.08)
    axes_map = {
        "left": fig.add_subplot(gs[0, 0]),
        "right": fig.add_subplot(gs[0, 2]),
    }
    label_ax = fig.add_subplot(gs[0, 1])
    label_ax.axis("off")
    fig.suptitle(f"{subject_id} – {date}", fontsize=14, fontweight="bold")

    legend_handles = []
    legend_labels = []
    y_positions = np.arange(len(session_labels))

    for idx, side in enumerate(sides):
        ax = axes_map[side]
        side_label = TRANSLATIONS_PT[side]
        ax.set_title(f"Ombro {side_label}")
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
            _annotate_missing(ax, TRANSLATIONS_PT["No sessions"])
            continue

        # Draw grey background bars for sessions with no data
        no_data_mask = [vals is None or sum(vals) == 0 for vals in session_data_list]
        if any(no_data_mask):
            no_data_widths = [100 if is_missing else 0 for is_missing in no_data_mask]
            ax.barh(y_positions, no_data_widths, height=0.6, color=NO_DATA_COLOR, zorder=0)

        left_offsets = np.zeros(len(session_labels))

        for bin_idx, bin_label in enumerate(RELATIVE_BIN_LABELS_PT):
            widths = [values[bin_idx] if values is not None else 0.0 for values in session_data_list]
            bars = ax.barh(y_positions, widths, height=0.6, left=left_offsets,
                           color=RELATIVE_BIN_COLORS[bin_idx], label=bin_label, zorder=1)
            left_offsets += widths

            if len(legend_handles) < len(RELATIVE_BIN_LABELS_PT):
                legend_handles.append(bars[0])
                legend_labels.append(bin_label)

        # Mark flagged sessions with asterisk
        if flagged_sessions:
            for y_pos, session_label in enumerate(session_labels):
                key = (str(subject_id), side, date, session_label)
                if key in flagged_sessions:
                    text_x = 105 if side == "right" else -5
                    halign = "left" if side == "right" else "right"
                    ax.text(text_x, float(y_pos), "*", fontsize=14, fontweight="bold",
                           color="red", va="center", ha=halign)

        for y_pos, values in zip(y_positions, session_data_list):
            if values is None or sum(values) == 0:
                # Center "No data" text in the middle of the grey bar
                ax.text(50, float(y_pos), TRANSLATIONS_PT["No data"], va="center", ha="center",
                        fontsize=9, color="#888888")

        ax.set_yticks(y_positions)
        ax.set_yticklabels([])
        ax.set_xlim(0, 100)
        ax.set_xlabel(TRANSLATIONS_PT["Active time (%)"])
        ax.invert_yaxis()
        ax.set_axisbelow(True)
        ax.grid(axis="x", alpha=0.3, linestyle="--")

        # Remove all spines
        ax.spines["top"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["bottom"].set_visible(False)

        if side == "left":
            ax.invert_xaxis()
            ax.yaxis.tick_right()

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

    # Add session labels in center column (format as HH:MM)
    if len(y_positions) > 0:
        label_ax.set_ylim(-0.5, len(session_labels) - 0.5)
        for y_pos, session_label in zip(y_positions, session_labels):
            # Convert HH-MM-SS to HH:MM
            time_display = session_label.replace("-", ":")[:5] if len(session_label) >= 5 else session_label
            label_ax.text(0.5, float(y_pos), time_display, va="center", ha="center", fontweight="bold")
        label_ax.invert_yaxis()

    output_path = plots_root / subject_id / date / "summary" / "relative_bins_sessions.png"
    ensure_parent(output_path)
    fig.subplots_adjust(bottom=0.22, top=0.9, left=0.08, right=0.98)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


# -------------------------------------------------------------------------------------------------------------------- #
# Weekly Overview - Relative Intensity Bins (3 days per row format)
# -------------------------------------------------------------------------------------------------------------------- #

def plot_week_relative_bins_stacks_from_json(
    oh_profile: Dict[str, Any],
    plots_root: Path,
    subject_id: str,
    flagged_sessions: Optional[set] = None,
) -> Optional[Path]:
    """
    Show session relative intensity bins per day, with left/right side-by-side, ordered by day.

    Same format as the old "Week Rest vs Active" plot: 3 days per row, centered last row.

    :param oh_profile: OH profile dictionary containing EMG metrics.
    :param plots_root: Root directory for plots.
    :param subject_id: Subject identifier.
    :param flagged_sessions: Set of flagged (subject, side, date, session) tuples.
    :returns: Path to generated plot, or None if no data.
    """
    emg_data = _get_emg_data(oh_profile)
    if not emg_data:
        return None

    # Collect per-day session data
    dates = [d for d in sorted(emg_data.keys()) if d not in (EMG_WEEKLY_AGGREGATE_KEY,)]
    if not dates:
        return None

    day_sessions: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
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

    # Check if any session has relative bins data
    has_bins = False
    for date in dates:
        for session_label, session_data in day_sessions.get(date, []):
            for side in ("left", "right"):
                side_metrics = session_data.get(side, {})
                bin_pcts = _get_relative_bin_percentages(side_metrics)
                if any(p is not None and p > 0 for p in bin_pcts):
                    has_bins = True
                    break
            if has_bins:
                break
        if has_bins:
            break

    if not has_bins:
        return None

    weekday_labels = dates_to_weekdays(dates, "%Y-%m-%d", locale="pt_PT")

    # Layout: up to 3 days per row; center the final row when incomplete
    n_cols = min(2, len(dates))
    n_rows = int(np.ceil(len(dates) / n_cols))

    # Wider figure for better readability
    fig = plt.figure(figsize=(6 * n_cols, (max(2.5, 1.2 * max_sessions_for_layout) + 0.6) * n_rows))

    # Use 2x columns to allow centering of 1 or 2 items in a 3-column layout
    grid_cols = n_cols * 2
    outer_gs = fig.add_gridspec(n_rows, grid_cols, wspace=0.35, hspace=0.6)
    fig.suptitle(TRANSLATIONS_PT["Week Relative Intensity Overview"],
                 fontsize=14, fontweight="bold")

    legend_handles: List[Any] = []
    legend_labels: List[str] = []

    for idx, date in enumerate(dates):
        row = idx // n_cols
        col_in_row = idx % n_cols

        # Calculate items in this row for centering
        items_in_this_row = n_cols
        if row == n_rows - 1:
            items_in_this_row = len(dates) % n_cols
            if items_in_this_row == 0:
                items_in_this_row = n_cols

        # Calculate offset to center the items
        offset = (grid_cols - items_in_this_row * 2) // 2
        col_start = offset + col_in_row * 2
        col_end = col_start + 2

        sub_gs = outer_gs[row, col_start:col_end].subgridspec(1, 3, width_ratios=(1, 0.32, 1), wspace=0.08)
        left_ax = fig.add_subplot(sub_gs[0, 0])
        right_ax = fig.add_subplot(sub_gs[0, 2])
        label_ax = fig.add_subplot(sub_gs[0, 1])
        label_ax.axis("off")
        day_label = weekday_labels[idx] if idx < len(weekday_labels) else f"{TRANSLATIONS_PT['Day']} {idx + 1}"
        label_ax.set_title(day_label, fontweight="bold", fontsize=10)

        sessions = day_sessions.get(date, [])
        if not sessions:
            _annotate_missing(left_ax, TRANSLATIONS_PT["No sessions"])
            _annotate_missing(right_ax, TRANSLATIONS_PT["No sessions"])
            left_ax.set_title(f"Ombro {TRANSLATIONS_PT['left']}")
            right_ax.set_title(f"Ombro {TRANSLATIONS_PT['right']}")
            continue

        y_positions = np.arange(len(sessions))
        
        for ax, side in ((left_ax, "left"), (right_ax, "right")):
            session_bin_percentages = []
            for session_label, session_data in sessions:
                side_metrics = session_data.get(side)
                if side_metrics is None:
                    session_bin_percentages.append(None)
                else:
                    bin_pcts = _get_relative_bin_percentages(side_metrics)
                    bin_pcts = [p if p is not None else 0.0 for p in bin_pcts]
                    session_bin_percentages.append(bin_pcts)

            all_missing = all(vals is None for vals in session_bin_percentages)
            if all_missing:
                _annotate_missing(ax, TRANSLATIONS_PT["No data"])
                ax.set_title(f"Ombro {TRANSLATIONS_PT[side]}")
                continue

            # Draw grey background bars for sessions with no data
            no_data_mask = [vals is None or sum(vals) == 0 for vals in session_bin_percentages]
            if any(no_data_mask):
                no_data_widths = [100 if is_missing else 0 for is_missing in no_data_mask]
                ax.barh(y_positions, no_data_widths, height=0.6, color=NO_DATA_COLOR, zorder=0)
                # Add centered "No data" text for missing sessions
                for y_pos, is_missing in enumerate(no_data_mask):
                    if is_missing:
                        ax.text(50, float(y_pos), TRANSLATIONS_PT["No data"], va="center", ha="center",
                                fontsize=8, color="#888888", zorder=2)

            left_offsets = np.zeros(len(sessions))
            for bin_idx, bin_label in enumerate(RELATIVE_BIN_LABELS_PT):
                widths = [vals[bin_idx] if vals is not None else 0.0 for vals in session_bin_percentages]
                bars = ax.barh(
                    y_positions,
                    widths,
                    height=0.6,
                    left=left_offsets,
                    color=RELATIVE_BIN_COLORS[bin_idx],
                    label=bin_label,
                    zorder=1,
                )
                left_offsets += widths

                # Capture legend only once
                if len(legend_handles) < len(RELATIVE_BIN_LABELS_PT):
                    legend_handles.append(bars[0])
                    legend_labels.append(bin_label)

            # Mark flagged sessions with asterisk
            if flagged_sessions:
                for y_pos, (session_label, _) in enumerate(sessions):
                    key = (str(subject_id), side, date, session_label)
                    if key in flagged_sessions:
                        text_x = 105 if side == "right" else -5
                        halign = "left" if side == "right" else "right"
                        ax.text(text_x, float(y_pos), "*", fontsize=12, fontweight="bold", 
                               color="red", va="center", ha=halign)

            ax.set_yticks(y_positions)
            ax.set_yticklabels([])
            ax.set_xlim(0, 100)
            ax.set_xlabel(TRANSLATIONS_PT["Active time (%)"])
            ax.invert_yaxis()
            if side == "left":
                ax.invert_xaxis()
                ax.yaxis.tick_right()
            ax.set_title(f"Ombro {TRANSLATIONS_PT[side]}")
            ax.set_axisbelow(True)
            ax.grid(axis="x", alpha=0.3, linestyle="--", linewidth=1.5)
            
            # Remove all spines except bottom
            ax.spines["top"].set_visible(False)
            ax.spines["left"].set_visible(False)
            ax.spines["right"].set_visible(False)

        # Session labels in center (format as HH:MM)
        label_ax.set_ylim(-0.5, len(sessions) - 0.5)
        for y_pos, (session_label, _) in enumerate(sessions):
            # Convert HH-MM-SS to HH:MM
            time_display = session_label.replace("-", ":")[:5] if len(session_label) >= 5 else session_label
            label_ax.text(0.5, float(y_pos), time_display, va="center", ha="center", 
                         fontsize=8, fontweight="bold")
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

    output_path = plots_root / subject_id / "week" / "relative_bins_sessions_week.png"
    ensure_parent(output_path)
    fig.subplots_adjust(bottom=0.1, top=0.92, left=0.06, right=0.98)
    fig.savefig(output_path, format="png", dpi=150)
    plt.close(fig)
    return output_path


# -------------------------------------------------------------------------------------------------------------------- #
# Weekly Active APDF Trends
# -------------------------------------------------------------------------------------------------------------------- #

def plot_weekly_active_apdf_trend_from_json(
    oh_profile: Dict[str, Any],
    plots_root: Path,
    subject_id: str,
) -> List[Path]:
    """
    Weekly Active APDF trend chart (P10, P50, P90) per side.
    
    :param oh_profile: OH profile dictionary.
    :param plots_root: Root directory for plots.
    :param subject_id: Subject ID.
    :returns: List of paths to generated plots.
    """
    emg_data = _get_emg_data(oh_profile)
    if not emg_data:
        return []

    dates = [d for d in sorted(emg_data.keys()) if d not in (EMG_WEEKLY_AGGREGATE_KEY,)]
    if not dates:
        return []

    output_paths = []
    
    for side in ("left", "right"):
        # Collect daily aggregate data
        daily_data = []
        for date in dates:
            day_data = emg_data.get(date, {})
            daily_agg = day_data.get(EMG_DAILY_AGGREGATE_KEY, {})
            side_metrics = daily_agg.get(side, {})
            
            # Use helper to extract from nested structure
            active_apdf = get_emg_apdf_active(side_metrics)
            p10 = active_apdf.get('p10')
            p50 = active_apdf.get('p50')
            p90 = active_apdf.get('p90')
            
            if any(v is not None for v in [p10, p50, p90]):
                daily_data.append({
                    'date': date,
                    'p10': p10,
                    'p50': p50,
                    'p90': p90,
                })
        
        if not daily_data:
            continue
        
        output_path = plots_root / subject_id / "weekly" / f"active_apdf_trend_{side}.png"
        ensure_parent(output_path)
        
        # Sort by date
        sorted_data = sorted(daily_data, key=lambda x: x.get('date', ''))
        
        dates_labels = [d.get('date', '')[-5:] for d in sorted_data]  # MM-DD format
        p10_values = [d.get('p10') or np.nan for d in sorted_data]
        p50_values = [d.get('p50') or np.nan for d in sorted_data]
        p90_values = [d.get('p90') or np.nan for d in sorted_data]
        
        fig, ax = plt.subplots(figsize=(10, 5))
        
        x = np.arange(len(dates_labels))
        
        ax.plot(x, p10_values, 'o-', color='#4CAF50', label='P10', linewidth=2, markersize=8)
        ax.plot(x, p50_values, 's-', color='#2196F3', label='P50', linewidth=2, markersize=8)
        ax.plot(x, p90_values, '^-', color='#F44336', label='P90', linewidth=2, markersize=8)
        
        ax.set_xticks(x)
        ax.set_xticklabels(dates_labels, rotation=45, ha='right')
        ax.set_xlabel(TRANSLATIONS_PT["Date"], fontsize=11)
        ax.set_ylabel(TRANSLATIONS_PT["Active APDF (%MVC)"], fontsize=11)
        
        side_label = TRANSLATIONS_PT[side]
        ax.set_title(f"{subject_id} – {side_label} – {TRANSLATIONS_PT['Weekly Active APDF Trend']}", 
                    fontsize=12, fontweight='bold')
        ax.legend(loc='upper right')
        ax.grid(True, alpha=0.3)
        
        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
        output_paths.append(output_path)
    
    return output_paths


# -------------------------------------------------------------------------------------------------------------------- #
# Main Functions for Pipeline Integration
# -------------------------------------------------------------------------------------------------------------------- #

def generate_emg_plots_from_oh_profiles(
    oh_profiles_path: str,
    subject_ids: Sequence[str],
    plots_root: Path,
    session_metrics_path: Optional[Path] = None,
) -> Dict[str, List[Path]]:
    """
    Generate all EMG visualizations from OH profile JSON files.

    This function reads the persisted OH profiles and generates:
    - Day-level relative intensity bin donuts (daily aggregate)
    - Day-level relative intensity bin session stacks
    - Week-level relative intensity bin stacks (3 days per row)
    - Weekly Active APDF trends per side

    :param oh_profiles_path: Path to folder containing OH profile JSON files.
    :param subject_ids: List of subject IDs to process.
    :param plots_root: Root directory for generated plots.
    :param session_metrics_path: Path to session_metrics.csv for flagging.
    :returns: Dict mapping subject_id to list of generated plot paths.
    """
    all_plots: Dict[str, List[Path]] = {}
    flagged_sessions = _get_flagged_sessions(session_metrics_path)

    for subject_id in subject_ids:
        subject_id_str = str(subject_id)
        oh_profile = get_OH_profile(oh_profiles_path, subject_id_str)
        emg_data = _get_emg_data(oh_profile)

        if not emg_data:
            print(f"[emg_oh] No EMG data for subject {subject_id_str}")
            continue

        subject_plots: List[Path] = []

        # Get all dates (excluding weekly_aggregate key)
        dates = [
            key for key in emg_data.keys()
            if key not in (EMG_WEEKLY_AGGREGATE_KEY,)
        ]

        for date in sorted(dates):
            # Generate daily aggregate relative intensity bin donuts
            relative_bin_donut_paths = plot_day_relative_bins_donut_from_json(
                oh_profile, date, plots_root, subject_id_str
            )
            if relative_bin_donut_paths:
                subject_plots.extend(relative_bin_donut_paths)

            # Generate relative intensity bin session stacks
            relative_bin_stacks_path = plot_day_relative_bins_stacks_from_json(
                oh_profile, date, plots_root, subject_id_str,
                flagged_sessions=flagged_sessions,
            )
            if relative_bin_stacks_path:
                subject_plots.append(relative_bin_stacks_path)

        # Generate week-level stacked sessions view (3 days per row)
        week_stack_path = plot_week_relative_bins_stacks_from_json(
            oh_profile, plots_root, subject_id_str,
            flagged_sessions=flagged_sessions,
        )
        if week_stack_path:
            subject_plots.append(week_stack_path)

        # Generate weekly Active APDF trends per side
        trend_paths = plot_weekly_active_apdf_trend_from_json(
            oh_profile, plots_root, subject_id_str
        )
        subject_plots.extend(trend_paths)

        if subject_plots:
            all_plots[subject_id_str] = subject_plots
            print(f"[emg_oh] Generated {len(subject_plots)} plots for subject {subject_id_str}")

    return all_plots
