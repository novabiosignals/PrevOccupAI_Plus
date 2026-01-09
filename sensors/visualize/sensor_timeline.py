# -*- coding: utf-8 -*-
"""
Functions to generate the sensor timeline plot.

Available Functions
-------------------
[Public]
visualize_group_acquisitions(...): Generate daily acquisition plots for each subject in a group.
get_daily_acquisitions_metadata(...): Aggregate acquisition lengths and start times for all devices on a given day.
-------------------

[Private]
_visualize_daily_acquisitions(...): Plot acquisitions for a subject on a given day, including missing data, and save the visualization as a PNG file.
_calculate_df_length(...): Compute the number of rows in each DataFrame of signals.
_normalize_device_names(...): Translate raw device names into human-readable labels (Portuguese).
_add_missing_device(...): Add a device missing for the entire day into the missing-data dictionary using a reference device.
_get_acquisition_time_range(...): Determine earliest and latest acquisition times across devices.
_plot_device_bars(...): Draw horizontal bars for each device’s acquisitions or missing data on a timeline.
_plot_reference_acquisition(...): Plot a reference duration line (e.g., 20 min) on top of acquisitions.
_plot_device_labels_and_guides(...): Plot device labels and dashed guidelines for visual clarity.
-------------------
"""

# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import os
import pandas as pd
from typing import Dict, Any, Optional, Tuple, Callable, Union
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.dates import DateFormatter
from matplotlib.patches import Patch
import re

# internal imports
import sensors.load
from constants import ACQUISITION_TIME_SECONDS, MBAN_RIGHT
from OH_profile.constants import SENSOR_TIMELINE_MISSING_TIMES_KEY, SENSOR_TIMELINE_TIMES_KEY
from sensors.impute.impute_sensor_timeline import compute_end_times
from .plot_utils import RefLine, HandlerRefLine, get_weekday_name

# ------------------------------------------------------------------------------------------------------------------- #
# file specific constants
# ------------------------------------------------------------------------------------------------------------------- #
LOGGER_FILENAME_PREFIX = 'opensignals_ACQUISITION_LOG_'
LENGTH = 'length'
START_TIMES = 'start_times'
END_TIMES = 'end_times'
TIME_FORMAT = "%H-%M-%S"
COLOR_PALLETE = ['#f2b36f', "#F07A15", '#4D92D0', '#3C787E']

SMARTPHONE = 'Smartphone'
SMARTWATCH = 'Smartwatch'
MBAN_ESQ = "mBAN esq."
MBAN_DIR = "mBAN dir."
DEVICE_ORDER = [MBAN_ESQ, MBAN_DIR, SMARTWATCH,SMARTPHONE]
REF_DEVICES = [SMARTWATCH, MBAN_DIR, MBAN_ESQ]
SMART = 'Smart'

VERTICAL_SPACING = 0.2
BAR_HEIGHT = 0.1
ACQUISITION_TIME_MINUTES = 20
# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #

def generate_sensor_timeline_plot(week_metadata_dict: Dict[str, Dict[str, Dict[str, Dict[str, list]]]],
                                  output_folder_path: str, filename: str) -> None:
    """
    Generates a figure with the sensor timeline plots for all available days of the week for one subject.
    Each day is plotted in its own subplot with an independent x-axis.
    One shared legend is shown for the entire figure.

    week_metadata_dict must have the following format:
    {
        date: {
                SENSOR_TIMELINE_TIMES_KEY: {
                                            "phone": {"end_times": ["18:20:20"], "start_times": ["11:20:20"]},
                                            "watch": {"end_times": ["10:20:00", "12:20:00"], "start_times": ["10:00:00", "12:00:00"]}
                                            },
                SENSOR_TIMELINE_MISSING_TIMES_KEY: {
                                            "mban_right": {"end_time": ["10:20:00", "12:20:00"], "start_times": ["10:00:00", "12:00:00"]},
                                            "mban_left": {"end_time": ["10:20:00", "12:20:00"], "start_times": ["10:00:00", "12:00:00"]}
                                            }
                }
    }
    :param week_metadata_dict: Dictionary with the necessary metrics for the plot.
    :param output_folder_path: path to the folder where the results should be stored
    :param filename: plot filename
    :return: None
    """

    # get number of days that have data
    n_days = len(week_metadata_dict)

    # Figure with one subplot per day, independent x-axes
    fig, axs = plt.subplots(nrows=n_days, ncols=1, figsize=(12, 2 * n_days), sharex=False)

    # Ensure axs is iterable
    if n_days == 1:
        axs = [axs]
    else:
        axs = axs.ravel()

    # Plot each day in its own subplot
    for ax, (acquisition_date, day_meta_data_dict) in zip(axs, week_metadata_dict.items()):
        _visualize_daily_acquisitions(day_meta_data_dict[SENSOR_TIMELINE_TIMES_KEY],
                                      day_meta_data_dict[SENSOR_TIMELINE_MISSING_TIMES_KEY], acquisition_date, ax)

    # Hide x-axis labels for all but bottom subplot
    for ax in axs[:-1]:
        ax.set_xlabel("")

    # ---- Shared legend for the whole figure ----
    missing_patch = Patch(facecolor='lightgray', edgecolor='black', linestyle='dashed', label='Sem dados')
    ref_line = RefLine()

    # adjust spacings
    fig.subplots_adjust(hspace=0.6, right=0.93)  # add space for left legend
    fig.tight_layout(rect=[0, 0, 0.89, 1])  # leave margin for legend

    # generate legend
    fig.legend(
        handles=[missing_patch, ref_line],
        labels=["Sem dados", f"{ACQUISITION_TIME_SECONDS // 60} minutos"],
        handler_map={RefLine: HandlerRefLine()},
        loc='upper right',
        bbox_to_anchor=(1, 0.95),  # outside
        frameon=False, borderaxespad=0.0, handleheight=1, handlelength=2,
    )

    # Save figure
    plt.savefig(os.path.join(output_folder_path, filename), dpi=300, bbox_inches='tight')



def get_daily_acquisitions_metadata(daily_folder_path: str, fs: int) -> Dict[str, Dict[str, list]]:
    """
    Aggregates signal metadata (end time and start time) for each device across multiple acquisitions recorded in a single day.
    This function is intended for data collected from a smartwatch, smartphone, or MuscleBans (Plux Wireless Biosignals),
    using the OpenSignals application.

    This function scans a daily folder containing multiple acquisition subfolders. For each acquisition:
        - Loads the raw signals and calculates the number of rows (length) per device.
        - Determines the start timestamp for each device (using the logger file if available, if not use the filenames).
        - Calculates the end times based on the start time and the length of the signals
        - Accumulates these values into a dictionary grouped by device.

    :param fs: The sampling frequency in Hz
    :param daily_folder_path: Path to the folder containing the data from one day
    :return: A dictionary where keys are device names, and values are dictionaries with two lists:
             - 'end_times': List of signal end times.
             - 'start_times': List of corresponding start timestamps.
             Example:
             {
                "phone": {"end_times": ["18:20:20"], "start_times": ["11:20:20"]},
                "watch": {"end_times": ["10:20:00", "12:20:00"], "start_times": ["10:00:00", "12:00:00"]}
             }
    """
    final_dict = {}

    # iterate through the folders pertaining to the different acquisitions on the same day
    for acquisition_folder in os.listdir(daily_folder_path):

        # generate folder_path
        acquisition_folder_path = os.path.join(daily_folder_path, acquisition_folder)

        # load signals
        signals_dict = sensors.load.load_data_from_same_recording(acquisition_folder_path)

        # get lengths of the signals
        length_dict = _calculate_df_length(signals_dict)

        # logger file exists
        if sensors.load.check_logger_file(acquisition_folder_path):

            # load timestamps of each device based on the logger file
            start_times_dict = sensors.load.load_logger_file_info(acquisition_folder_path)

        # no logger file
        else:

            # extract timestamps from the filename
            start_times_dict = sensors.load.get_device_filename_timestamp(acquisition_folder_path)

        # combine and store results
        for device in length_dict:
            if device not in final_dict:

                final_dict[device] = {END_TIMES: [], START_TIMES: []}

            # add the start time to the dictionary
            start_time = start_times_dict.get(device, None)
            final_dict[device][START_TIMES].append(start_time)

            # compute duration in seconds from dataframe length
            length_samples = length_dict.get(device, 0)
            duration_seconds = length_samples / fs

            # compute end time using helper
            end_time = compute_end_times([start_time], [duration_seconds])[0]
            final_dict[device][END_TIMES].append(end_time)

    return final_dict


# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #
def _visualize_daily_acquisitions(acquisitions_dict: Dict[str, Dict[str, list]],
                                  missing_data_dict: Dict[str, Dict[str, list]],
                                  acquisition_date: str, ax=None, show_dates: bool = True) -> plt.Axes:
    """
    Visualizes daily signal acquisitions as horizontal bars over a timeline,
    including missing acquisitions.

    If `ax` is None, a new figure is created and a legend is added.
    If `ax` is provided (e.g., from visualize_group_acquisitions),
    plotting is done on that Axes and NO legend is added (so the group
    plot can have a single shared legend).

    :param acquisitions_dict: A dictionary where keys are device names, and values are dictionaries with two lists:
             - 'end_times': List of signal end times.
             - 'start_times': List of corresponding start timestamps.
             Example:
             {
                "phone": {"end_times": ["18:20:20"], "start_times": ["11:20:20"]},
                "watch": {"end_times": ["10:20:00", "12:20:00"], "start_times": ["10:00:00", "12:00:00"]}
             }
    :param missing_data_dict: same format as acquisitions_dict, but wth information regarding missing acquisitions. Can be empty.
    :param acquisition_date: str corresponding to the date of the acquisition (for plot title only).
    :param ax: Optional matplotlib Axes to plot on.
    :param show_dates: flag to add the date to the title pot
    :return: The matplotlib Axes used for plotting.
    """

    # Normalize device names
    acquisitions_dict = _normalize_device_names(acquisitions_dict)
    missing_data_dict = _normalize_device_names(missing_data_dict)

    # Add missing devices if necessary
    if len(acquisitions_dict) < 4:
        missing_data_dict = _add_missing_device(acquisitions_dict, missing_data_dict)

    # Time range for this day (each subplot uses its own)
    min_start_time, max_end_time = _get_acquisition_time_range(acquisitions_dict, missing_data_dict)

    # Sort devices according to DEVICE_ORDER
    all_devices = set(acquisitions_dict.keys()) | set(missing_data_dict.keys())
    sorted_devices = sorted(
        all_devices,
        key=lambda d: DEVICE_ORDER.index(d) if d in DEVICE_ORDER else len(DEVICE_ORDER)
    )
    device_to_index = {device: i for i, device in enumerate(sorted_devices)}

    # If no axis is provided, create a standalone figure (with legend)
    standalone = False
    if ax is None:
        standalone = True
        fig, ax = plt.subplots(figsize=(10, 3))

    # Plot acquisitions and missing data
    _plot_device_bars(ax,acquisitions_dict,device_to_index,color_map=lambda i: COLOR_PALLETE[i % len(COLOR_PALLETE)])
    _plot_device_bars(ax,missing_data_dict,device_to_index,color_map=lambda _: 'lightgray',edgecolor='#06171C',linestyle='dashed',linewidth=0.8)

    # Reference line and guides
    _plot_reference_acquisition(ax, acquisitions_dict, missing_data_dict, device_to_index)
    _plot_device_labels_and_guides(ax, device_to_index, min_start_time, max_end_time)

    # Axis formatting
    ax.xaxis.set_major_formatter(DateFormatter("%H:%M"))
    ax.set_xlim(min_start_time, max_end_time + timedelta(seconds=5))
    ax.set_xlabel("Tempo (hh:mm)", color='#06171C')
    ax.set_yticks([])

    week_day, date_str = get_weekday_name(acquisition_date)

    if show_dates:
        ax.set_title(f"{week_day} | {date_str}", color='#06171C', fontsize=10, fontweight='bold')

    else:

        # show only day of the week
        ax.set_title(f"{week_day}", color='#06171C', fontsize=10, fontweight='bold')

    # --- Custom ticks: start at min_start_time, then every 30 minutes ---
    tick_times = []
    current = min_start_time
    while current <= max_end_time:
        tick_times.append(current)
        current += timedelta(minutes=30)

    ax.set_xticks(tick_times)

    # Remove axes spines
    for spine in ['top', 'right', 'left', 'bottom']:
        ax.spines[spine].set_visible(False)

    # Legend ONLY when standalone
    if standalone:
        missing_patch = Patch(facecolor='lightgray', edgecolor='black', linestyle='dashed', label='Sem dados')
        ax.legend(
            handles=[missing_patch, RefLine()],
            labels=["Sem dados", f"{ACQUISITION_TIME_SECONDS // 60} minutos"],
            handler_map={RefLine: HandlerRefLine()},
            loc='upper left',
            bbox_to_anchor=(1.02, 1.02),
            frameon=False,
            handleheight=1,
            handlelength=2,
            borderaxespad=0.5
        )
        fig.tight_layout()

    return ax


def _calculate_df_length(df_dict: Dict[str, pd.DataFrame]) -> Dict[str, int]:
    """
    Calculates the number of rows in each DataFrame contained in a dictionary.
    It returns a new dictionary with the same keys, where each value is the number of rows (i.e., length)
    of the corresponding DataFrame.

    :param df_dict: A dictionary mapping keys to pandas DataFrames.
    :return: A dictionary mapping each key to the number of rows in its corresponding DataFrame.
    """
    lengths_dict: Dict[str, int] = {}

    for key, df in df_dict.items():

        lengths_dict[key] = df.shape[0]

    return lengths_dict


def _normalize_device_names(acquisitions_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize the keys in the dictionary, which pertains to the device names, for more user-friendly names in portuguese.

    (phone -> Smartphone, watch -> Smartwatch, mBAN left -> mBAN esq, mBAN right -> mBAN dir)
    :param acquisitions_dict: A dictionary where the keys are the device names
    :return: The same dictionary with the normalized device names (keys)
    """
    # change muscleban device name to mBAN right or mBAN left
    normalized_acquisitions_dict: Dict[str, Any] = {}

    # cycle over the devices in the dictionary keys
    for device_raw, data in acquisitions_dict.items():
        if match := re.search(r'[A-Z0-9]{12}', device_raw):

            # load metadata
            meta_data_df = sensors.load.load_participants_info()

            # get muscleban side and remove '_'
            device = sensors.load.get_muscleban_side(meta_data_df, match.group())

            # translate to portuguese
            if device == MBAN_RIGHT:
                device = MBAN_DIR

            else:
                device = MBAN_ESQ

        # if it's phone or watch keep the device name as it is
        else:
            device = SMART + device_raw

        # add device names to dict
        normalized_acquisitions_dict[device] = data

    return normalized_acquisitions_dict


def _add_missing_device(data_dict: Dict[str, Dict[str, list]], missing_data_dict: Dict[str, Dict[str, list]]) \
        -> Dict[str, Dict[str, list]]:
    """
    Adds a device that did not acquire for the entire day to the missing_data_dict. This function:

    (1) goes over the devices in data_dict and finds one device that can be used as reference
    (watch, mBAN right, or mBAN left)

    (2) gets the timestamps of this reference device. If this device has missing acquisitions, gets the missing
    timestamps from the missing_data_dict.

    (3) all timestamps found will be used for the missing device, therefore these are added to the missing_data_dict,
    as well as, for each added timestamp, a end time is computed by adding 20 minutes to the start time

    :param data_dict: A dictionary where keys are device names, and values are dictionaries with two lists:
             - 'end_times': List of signal end times.
             - 'start_times': List of corresponding start timestamps.
             Example:
             {
                "phone": {"end_times": ["18:20:20"], "start_times": ["11:20:20"]},
                "watch": {"end_times": ["10:20:00", "12:20:00"], "start_times": ["10:00:00", "12:00:00"]}
             }
    :param missing_data_dict: A dictionary where keys are device names, and values are dictionaries with two lists: end times and start times
                                Same format as data_dict.
    :return: the missing_data_dict with the missing device (and correspondent start times and end times) added.
    """

    # variable for holding the device to be used as reference for getting the start times
    ref_device: Optional[str] = None

    # find the devices that are present
    present_devices = set(data_dict.keys()) | set(missing_data_dict.keys())

    # find the missing devices - except phone
    missing_devices = list((set(DEVICE_ORDER) - {SMARTPHONE}) - present_devices)

    # if watch and both muscleBANS are missing, raise error as it is no possible to get timestamps
    if len(missing_devices) == 3:
        raise ValueError("All 3 devices (watch + both mBANs) are missing. Cannot infer missing acquisitions.")

    # (1) get the reference device from the dictionary with the data
    for device in DEVICE_ORDER:

        if device != SMARTPHONE and device in data_dict:

            # get reference device
            ref_device = device
            break

    if ref_device is None:

        # This scenario does not occur, written for code completion
        return missing_data_dict

    # (2) Collect reference times. If the device that was used for reference has no missing start times, use the ones in data_dict.
    ref_times = data_dict[ref_device][START_TIMES].copy()

    # If the reference device has missing start times, merge the ones on both data_dict and missing_data_dict
    if ref_device in missing_data_dict:
        ref_times += missing_data_dict[ref_device][START_TIMES]

    # (3) Add missing devices data to missing_data_dict, including the end times of the acquisitions
    for dev in missing_devices:

        missing_data_dict[dev] = {
            START_TIMES: sorted(ref_times),
            END_TIMES: [compute_end_times([t], [ACQUISITION_TIME_SECONDS])[0]
                for t in sorted(ref_times)]
        }

    return missing_data_dict


def _get_acquisition_time_range(acquisitions_dict: Dict[str, Dict[str, list]],
                                missing_data_dict: Dict[str, Dict[str, list]]) -> Tuple[datetime, datetime]:
    """
    Compute the earliest start time and latest end time across all devices.
    Assumes data_dict contains 'start_times' and 'end_times' as HH-MM-SS strings.

    :param acquisitions_dict: A dictionary where keys are device names, and values are dictionaries with two lists:
             - 'end_times': List of signal end times.
             - 'start_times': List of corresponding start timestamps.
             Example:
             {
                "phone": {"end_times": ["18:20:20"], "start_times": ["11:20:20"]},
                "watch": {"end_times": ["10:20:00", "12:20:00"], "start_times": ["10:00:00", "12:00:00"]}
             }
    :param missing_data_dict: A dictionary where keys are device names, and values are dictionaries with two lists: end times and start times
                                Same format as data_dict.
    :return: Tuple with the start time of the first device and the end tie of the last device
    """
    all_start_times = []
    all_end_times = []

    for data_dict in (acquisitions_dict, missing_data_dict):
        for data in data_dict.values():
            all_start_times.extend(data[START_TIMES])
            all_end_times.extend(data[END_TIMES])

    min_start_time = min(datetime.strptime(t, TIME_FORMAT) for t in all_start_times)
    max_end_time = max(datetime.strptime(t, TIME_FORMAT) for t in all_end_times)

    return min_start_time, max_end_time


def _plot_device_bars(ax: Axes, data_dict: Dict[str, Dict[str, list]], device_to_index:  Dict[str, int],
                      color_map: Union[Callable[[int], str], Dict[str, str]], edgecolor: Optional[str] = None,
                      linestyle: str ='solid', linewidth: float = 1.0) -> None:
    """
    Plot horizontal bars for each device using start_times and end_times.

    :param ax: A Matplotlib Axes object to draw the horizontal bars on.
    :param data_dict: A dictionary where keys are device names, and values are dictionaries with two lists:
             - 'end_times': List of signal end times.
             - 'start_times': List of corresponding start timestamps.
             Example:
             {
                "phone": {"end_times": ["18:20:20"], "start_times": ["11:20:20"]},
                "watch": {"end_times": ["10:20:00", "12:20:00"], "start_times": ["10:00:00", "12:00:00"]}
             }
    :param device_to_index: A mapping assigning each device a vertical index (integer).
                            This is used to space devices evenly along the y-axis.
    :param color_map: Used to determine the fill color of each bar.
    :param edgecolor: Color for the bar edges. Defaults to ``None``.
    :param linestyle: Style of bar edges (e.g., "solid", "dashed"). Defaults to "solid".
    :param linewidth:  Width of bar edge lines. Defaults to 1.0.
    :return: None
    """
    for device, data in data_dict.items():
        i = device_to_index[device]
        y_center = i * VERTICAL_SPACING
        y_bottom = y_center - BAR_HEIGHT / 2

        for start_str, end_str in zip(data[START_TIMES], data[END_TIMES]):
            if not start_str or not end_str:
                continue
            start_dt = datetime.strptime(start_str, TIME_FORMAT)
            end_dt = datetime.strptime(end_str, TIME_FORMAT)
            duration = end_dt - start_dt

            ax.broken_barh(
                [(start_dt, duration)],
                (y_bottom, BAR_HEIGHT),
                facecolors=color_map(i) if callable(color_map) else color_map.get(device, 'gray'),
                edgecolor=edgecolor,
                linestyle=linestyle,
                linewidth=linewidth
            )


def _plot_reference_acquisition(ax, acquisitions_dict: Dict[str, Dict[str, list]],
                                missing_data_dict: Dict[str, Dict[str, list]],
                                device_to_index: Dict[str, int]) -> None:
    """
    Plots a reference acquisition line using the first available acquisition
    from one of the devices (watch, mBAN right, or mBAN left) based on actual start and end times.

    :param ax: The matplotlib axis to draw on.
    :param acquisitions_dict: Dictionary of acquisitions with start and end times.
    :param missing_data_dict: Dictionary of missing acquisitions with start and end times.
    :param device_to_index: Mapping from device name to vertical index for plotting.
    """

    ref_device = SMARTWATCH

    # Try acquisitions first, fallback to missing data
    data_dict = acquisitions_dict.get(ref_device) or missing_data_dict.get(ref_device)

    if not data_dict or not data_dict[START_TIMES]:
        return  # nothing to plot

    # Sort by time instead of blindly using index 0
    times = list(zip(data_dict[START_TIMES], data_dict[END_TIMES]))
    times.sort(key=lambda t: datetime.strptime(t[0], TIME_FORMAT))

    # Earliest start time
    start_str, _ = times[0]
    start_dt = datetime.strptime(start_str, TIME_FORMAT)

    # Fixed 20-minute reference window
    end_dt = start_dt + timedelta(minutes=ACQUISITION_TIME_MINUTES)

    # Position above bar
    y_top = device_to_index[ref_device] * VERTICAL_SPACING + BAR_HEIGHT / 2
    offset = 0.1 * BAR_HEIGHT
    y_line = y_top + offset

    # Draw a double-headed arrow
    ax.annotate(
        "",
        xy=(end_dt, y_line), xycoords="data",
        xytext=(start_dt, y_line), textcoords="data",
        arrowprops=dict(
            arrowstyle="|-|",
            shrinkA=0, shrinkB=0,
            color="#26373C",
            linewidth=2,
            mutation_scale=2
        )
    )


def _plot_device_labels_and_guides(ax: Axes, device_to_index: Dict[str, int], min_start_time: datetime,
                                   latest_end_time: datetime) -> None:
    """
    Plot dashed horizontal guidelines and device labels on the y-axis.

    :param ax: Matplotlib axis to plot on.
    :param device_to_index: Dictionary mapping device names to their y-index.
    :param min_start_time: Earliest acquisition time (datetime).
    :param latest_end_time: Latest acquisition time (datetime).
    """
    # Loop through devices and their vertical positions
    for device, i in device_to_index.items():
        # Compute vertical positions for the bar and label
        y_center = i * VERTICAL_SPACING
        y_bottom = y_center - BAR_HEIGHT / 2
        y_top = y_center + BAR_HEIGHT / 2

        # Draw dashed horizontal lines at the top and bottom of the bar
        ax.hlines(y=[y_bottom, y_top], xmin=min_start_time, xmax=latest_end_time + timedelta(seconds=5), colors="#06171C", linestyles="dashed", linewidth=0.5)

        # Add the device name as a label on the left side
        ax.text(min_start_time - timedelta(seconds=500), y_center, device, va="center", ha="right", fontsize=10, color="#06171C")