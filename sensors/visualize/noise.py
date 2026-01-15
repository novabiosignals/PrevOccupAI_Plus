"""
Functions for visualizing noise data across days and subjects.

Available Functions
-------------------
[Public]
plot_noise_proportions_per_day(...): Creates stacked bar charts per day, showing proportions of
    low, medium, and high noise levels for each subject.
plot_noise_timeline_per_day(...): Generates timeline plots using fixed-size windows to display
    noise classifications across the day for each subject.
-------------------
"""

# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import matplotlib.patches as mpatches
from matplotlib.ticker import FuncFormatter
from typing import Dict

# internal imports
from .plot_utils import handle_plot, get_weekday_name
from utils import create_dir
from sensors.metrics.noise import NOISE_NEAR_SILENCE_KEY, NOISE_LOW_KEY, NOISE_DISTURBING_KEY, NOISE_HIGH_KEY, NOISE_TIMELINE_WLEN, NOISE_DISTRIBUTIONS_NOISE, W_SIZE_MINUTES
from constants import DATE_FORMAT
from .constants import GREEN, PALE_GREEN, YELLOW, RED
# ------------------------------------------------------------------------------------------------------------------- #
# file specific constants
# ------------------------------------------------------------------------------------------------------------------- #
CLASS_COLORS = {NOISE_NEAR_SILENCE_KEY: GREEN,
                NOISE_LOW_KEY: PALE_GREEN,
                NOISE_DISTURBING_KEY: YELLOW,
                NOISE_HIGH_KEY: RED
                }

LEGEND_PATCHES = [
            mpatches.Patch(color=CLASS_COLORS[NOISE_NEAR_SILENCE_KEY], label=f"{NOISE_NEAR_SILENCE_KEY}  ≤ 40 dBA"),
            mpatches.Patch(color=CLASS_COLORS[NOISE_LOW_KEY], label=f"{NOISE_LOW_KEY} 40–60 dBA"),
            mpatches.Patch(color=CLASS_COLORS[NOISE_DISTURBING_KEY], label=f"{NOISE_DISTURBING_KEY} 60–80 dBA"),
            mpatches.Patch(color=CLASS_COLORS[NOISE_HIGH_KEY], label=f"{NOISE_HIGH_KEY} ≥ 80 dBA")
        ]

CLASS_ORDER = [NOISE_NEAR_SILENCE_KEY, NOISE_LOW_KEY, NOISE_DISTURBING_KEY, NOISE_HIGH_KEY]

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #

def plot_noise_metrics_per_week(oh_profile: Dict, subject: str, output_folder_path: str) -> None:
    """
    Generate noise timeline plots for a single day per subject.

    This function is a wrapper around `plot_timeline_per_acquisition specifically configured to plot noise levels. It
    visualizes contiguous segments of noise classes as colored blocks along a horizontal timeline, with a legend
    describing each noise category.

    :param oh_profile: OH profile containing the features extracted from the noise recorder, particularly the
                            timeline metrics
    :param subject: Subject identifier.
    :param output_folder_path: Path to the base folder where the generated plots will be saved.
    :return: None
    """
    # init dict for storing the timeline data and distributions
    timeline_dict = {}
    distributions_dict = {}

    # cycle over the dates in the profile
    for date_key, day_data in oh_profile.items():

        # initialize date level only once
        timeline_dict.setdefault(date_key, {})
        distributions_dict.setdefault(date_key, {})

        # cycle over the inner keys with the acquisition times
        for time_key, acquisition_data in day_data.items():

            timeline_dict[date_key][time_key] = acquisition_data[NOISE_TIMELINE_WLEN]
            distributions_dict[date_key][time_key] = acquisition_data[NOISE_DISTRIBUTIONS_NOISE]

    # create directory to store the plots
    out_dir = create_dir(output_folder_path, os.path.join(f'{subject}', 'noise_plots'))

    _plot_noise_timeline_per_week(timeline_dict=timeline_dict, subject=subject, save_dir=out_dir)
    # generate weekly bar plot
    _plot_noise_distributions_per_week(distributions_dict=distributions_dict, subject=subject, save_dir=out_dir)


# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #

def _plot_noise_timeline_per_week(timeline_dict: dict, subject: str, save_dir: str) -> None:
    """
    Generate a noise timeline plot per subject, using a dictionary with
    precomputed noise intervals.

    :param timeline_dict: Nested dictionary with dates -> acquisition times -> "Noise_timeline".
                       Example:
                       {"30-09-2025": {"14-16-00": {"Noise_timeline": {...}}}, ...}
    :param subject: Subject identifier
    :param save_dir: Directory path to save plots.
    """

    # sort dates chronologically
    unique_dates = sorted(timeline_dict.keys(), key=lambda d: datetime.strptime(d, DATE_FORMAT).weekday())

    date_to_idx = {d: i for i, d in enumerate(timeline_dict.keys())}

    fig, ax = plt.subplots(figsize=(14, 6))

    plot_date = datetime(2000, 1, 1)  # dummy date for plotting time

    for date in unique_dates:
        y_idx = date_to_idx[date]

        # Iterate over all acquisition blocks for that day
        for acq_time, timeline in timeline_dict[date].items():

            for time_range, noise_class in timeline.items():
                start_str, end_str = time_range.split("_")
                start_dt = datetime.strptime(start_str, "%H:%M:%S.%f")
                end_dt = datetime.strptime(end_str, "%H:%M:%S.%f")

                start_plot = plot_date.replace(hour=start_dt.hour,
                                               minute=start_dt.minute,
                                               second=start_dt.second,
                                               microsecond=start_dt.microsecond)
                end_plot = plot_date.replace(hour=end_dt.hour,
                                             minute=end_dt.minute,
                                             second=end_dt.second,
                                             microsecond=end_dt.microsecond)

                ax.plot([start_plot, end_plot], [y_idx, y_idx],
                        color=CLASS_COLORS.get(noise_class, "gray"),
                        linewidth=10)

    # Configure axes
    ax.set_yticks(range(len(unique_dates)))
    ax.set_yticklabels([get_weekday_name(d, 'pt_PT.UTF-8') for d in unique_dates])
    ax.set_ylim(-0.5, len(unique_dates) - 0.5)
    ax.invert_yaxis()

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.set_xlabel("Hora do Dia", fontsize=12)
    ax.set_title(f"Nível de ruído ao longo do dia", fontsize=14)

    ax.grid(axis="x", linestyle="--", alpha=0.4)
    ax.tick_params(axis="y", length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.legend(handles=LEGEND_PATCHES, loc="upper center", bbox_to_anchor=(0.5, -0.15),
              ncol=len(CLASS_COLORS), frameon=False, fontsize=12)

    plt.tight_layout(rect=[0, 0, 1, 0.95])

    filename = f"{subject}_noise_timeline.png"

    handle_plot(save_dir=save_dir, save=True, filename=filename)


def _plot_noise_distributions_per_week(distributions_dict: dict, subject: str, save_dir: str) -> None:
    """
    Generate stacked bar charts showing daily noise distribution ,
    using predefined class colors (CLASS_COLORS).

    :param distributions_dict: Dictionary with dates as keys, each containing acquisition times
                        with dictionaries of class percentages.
                        Example:
                        {'2026-01-01': {'08:00': {'normal': 0.5, 'abnormal': 0.5}}}
    :param subject: Subject identifier
    :param save_dir: Directory path where plots will be saved if `save=True`.
    """

    # Sort dates
    dates_sorted = sorted(distributions_dict.keys())
    date_labels = []

    # Dynamically collect all class names
    all_classes = set()
    for date_data in distributions_dict.values():
        for acq_time, class_data in date_data.items():
            all_classes.update(class_data.keys())

    # Keep only classes present in data, but follow CLASS_ORDER
    all_classes = [cls for cls in CLASS_ORDER if cls in all_classes]

    # Initialize dict of lists for each class
    class_props = {cls: [] for cls in all_classes}

    # Build daily proportions
    for date_str in dates_sorted:
        date_data = distributions_dict[date_str]

        # Sum percentages over all acquisition times for that day
        daily_totals = {cls: 0 for cls in all_classes}
        for acq_time, class_data in date_data.items():
            for cls in all_classes:
                daily_totals[cls] += class_data.get(cls, 0) * 100  # convert to percent
        # Average if multiple acquisition times
        n_times = len(date_data)
        for cls in all_classes:
            class_props[cls].append(daily_totals[cls] / n_times if n_times else 0)

        # Format date label
        formatted_date = get_weekday_name(date_str, locale_string='pt_PT.UTF-8')
        date_labels.append(formatted_date)

    # Assign colors: use CLASS_COLORS if available, otherwise default gray
    colors = {cls: CLASS_COLORS.get(cls, "#B0BEC5") for cls in all_classes}

    # Plot
    fig, ax = plt.subplots(figsize=(12, 6))
    positions = list(range(len(dates_sorted)))

    bottom = np.zeros(len(dates_sorted))
    for cls in all_classes:
        ax.bar(positions, class_props[cls], bottom=bottom, color=colors[cls], label=cls)
        bottom += np.array(class_props[cls])

    ax.grid(axis="y", color="lightgray", linestyle="--", linewidth=0.7)
    ax.set_axisbelow(True)

    ax.set_xticks(positions)
    ax.set_xticklabels(date_labels, rotation=0, ha="center", fontsize=12)
    ax.set_ylabel("Percentagem de Tempo (%)", fontsize=12)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.0f}%"))

    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.set_title(f" Distribuição de Ruído por Dia", fontsize=14)
    ax.legend(handles=LEGEND_PATCHES, loc="upper center", bbox_to_anchor=(0.5, -0.15),
              ncol=len(CLASS_COLORS), frameon=False, fontsize=12)
    plt.tight_layout()

    filename = f"{subject}_noise_distribution.png"

    handle_plot(save_dir=save_dir, save=True, filename=filename)
