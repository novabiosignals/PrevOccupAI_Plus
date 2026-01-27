"""
Utils for the visualizations functions

Available Functions
-------------------
[Class]
HandlerRefLine(HandlerBase): overrides method in HandleBase for drawing horizontal lines with vertical ticks

-------------------
[Public]
plot_timeline_per_acquisition(...): Generate a timeline plot per acquisition for a given day.
get_day_string(...): Gets the day as a string (i.e. Mon, Tue, Wednesday, etc.) from a date string in the language of the defined locale
generate_acquisition_labels(...): Generates the labels of each acquisition as time (start-end) or as a roman numer (I, II, II, IV)
generate_grouped_legend(...): Generate a grouped legend using Roman numerals and time intervals.
handle_plot(...): Handle plot saving and display logic.
reconstruct_df_from_dict(...): Rebuild a DataFrame from compressed sensor timelines.
get_weekday_name(...): gets the day of the week from a date string
-------------------
[Private]

-------------------
"""
# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import locale
import os
import pandas as pd
from datetime import datetime, timedelta
from typing import Tuple, Dict
import matplotlib.pyplot as plt
from matplotlib.legend_handler import HandlerBase
from matplotlib.lines import Line2D
from typing import List, Sequence
from collections import defaultdict
from matplotlib.artist import Artist
import matplotlib.dates as mdates
from babel.dates import format_datetime

# internal imports
from utils import create_dir
from constants import DATE_FORMAT
from.constants import ROMAN_NUMBERS

# ------------------------------------------------------------------------------------------------------------------- #
# class
# ------------------------------------------------------------------------------------------------------------------- #

# Dummy handle for the reference line
class RefLine:
    pass

# Custom handler to draw horizontal line with vertical ticks (|-|)
class HandlerRefLine(HandlerBase):
    def create_artists(self, legend, orig_handle,
                       xdescent, ydescent, width, height, fontsize, trans):
        y = height / 2.0
        tick_height = height * 0.3   # vertical tick height
        lw = 2

        # Horizontal line
        line = Line2D([xdescent, xdescent + width],
                      [y, y], color="#26373C", lw=lw, transform=trans)

        # Vertical ticks at ends
        left_tick = Line2D([xdescent, xdescent],
                           [y - tick_height/2, y + tick_height/2],
                           color="#26373C", lw=lw, transform=trans)
        right_tick = Line2D([xdescent + width, xdescent + width],
                            [y - tick_height/2, y + tick_height/2],
                            color="#26373C", lw=lw, transform=trans)

        return [line, left_tick, right_tick]


# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #

def plot_timeline_per_acquisition(day_metrics_dict: Dict, day: str, subject: str, output_folder_path: str,*, timeline_key,
                                  class_colors: Dict[str, str], legend_handles: Sequence[Artist], filename_prefix: str,
                                  gap_threshold=timedelta(seconds=30)) -> None:
    """
    Generate a timeline plot per acquisition for a given day.

    This function is a generic timeline plotting utility used to visualize class-based temporal data (e.g., noise levels,
    heart rate categories). Each acquisition is plotted as a horizontal timeline, where contiguous segments of the same
    class are rendered as colored blocks.

    :param day_metrics_dict: Dictionary containing metrics for a given day. Keys correspond to acquisition identifiers
                            and values contain timeline metric data.
    :param day: Day identifier in DD-MM-YYYY format.
    :param subject:  Subject identifier.
    :param output_folder_path: Base directory where output plots will be saved.
    :param timeline_key: Key used to extract the timeline metrics from each acquisition entry.
    :param class_colors: Mapping from class label to color (hex or named color) used to draw timeline segments.
    :param legend_handles: Preconfigured matplotlib legend handles (e.g., ``Line2D`` or ``Patch``) describing the classes
                            displayed in the plot.
    :param filename_prefix: Prefix used when generating output image filenames.
    :param gap_threshold: Minimum time gap between consecutive samples that triggers a new timeline block. Defaults to 30 seconds.
    :return: None
    """
    # generate path to the folder where the plots will be saved
    output_path = create_dir(output_folder_path, os.path.join(str(subject), f"{filename_prefix}_timeline"))

    # counter for the acquisitions
    acq_counter = 0

    # cycle over the acquisitions of the day
    for key, features_dict in day_metrics_dict.items():

        # update counter
        acq_counter += 1

        # get inner dict with the timeline metrics only
        timeline_metrics_dict = features_dict[timeline_key]

        if not timeline_metrics_dict:
            raise ValueError(f"No timeline metrics to plot for acquisition time: {key}")

        # reconstruct dataframe with hr ratio class column and timestamp column
        df = reconstruct_df_from_dict(timeline_metrics_dict, fs=100, class_column_name='class_column')

        # ignore rows without a valid class
        valid = df[df['class_column'] != "no data"].copy()

        fig, ax = plt.subplots(figsize=(15, 3))

        valid["gap"] = valid["timestamp"].diff()
        new_block = (
            (valid['class_column'] != valid['class_column'].shift()) |
            (valid["gap"].isna()) |
            (valid["gap"] > gap_threshold)
        )
        block_id = new_block.cumsum()

        for _, grp in valid.groupby(block_id, sort=False):
            cls = grp['class_column'].iloc[0]
            ax.hlines(y=0, xmin=grp["timestamp"].iloc[0], xmax=grp["timestamp"].iloc[-1], color=class_colors.get(cls, "gray"), linewidth=6)

        weekday_label = format_datetime(datetime.strptime(day, DATE_FORMAT),"dd-MM-yyyy (EEEE)", locale="pt_PT")

        ax.set_yticks([])
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

        # remove axis lines
        for spine in ax.spines.values():
            spine.set_visible(False)

        ax.set_xlabel("Hora do Dia", fontsize=12)
        ax.set_title(f"Sujeito: {subject} | Dia: {weekday_label} | Aquisição: {acq_counter}", fontsize=14)

        # add legend
        ax.legend(handles=legend_handles, bbox_to_anchor=(1.04, 1), loc="lower center")

        plt.tight_layout()

        filename = f"{filename_prefix}_{day}_acq_{acq_counter}.png"
        handle_plot(save_dir=output_path, save=True, filename=filename)


def get_day_string(date_string: str, locale_string: str = "Portuguese_Portugal.1252") -> Tuple[str, str]:
    """
    Gets the day as a string (i.e. Mon, Tue, Wednesday, etc.) from a date string in the language of the defined locale

    :param date_string: the date as string. The date should be in the format (year-month-day)
    :param locale_string: string indicating the local for returning the day string in a specific language
    :return: the day of the week as a string
    """
    # get a datetime object from the date string
    date_time = datetime.strptime(date_string, '%Y-%m-%d')

    # set the locale_string
    locale.setlocale(locale.LC_TIME, locale_string)

    return date_time.strftime('%A'), date_time.strftime('%x')


def generate_acquisition_labels(dates: List[str], times: List[str], mode="time_labels"):
    """
    Generate acquisition labels in two modes:
    1. 'time_labels': HH:MM - HH:MM format extracted from times list
    2. 'acq_num': Acquisition number using Roman numerals I to IV,
       with 'X+' as a fallback if more than 4 acquisitions per day

    :param dates: list of weekdays like ['Segunda', 'Terça', ...]
    :param times: list of time ranges like ['11:32:13_11:48:34', ...]
    :param mode: 'time_labels' or 'acq_num'
    :return: list of labels
    """

    # Generate labels showing start and end times
    if mode == "time_labels":
        labels = []
        for t in times:
            if t.startswith("missing_"):

                labels.append(f"Sem dados")
            else:
                # start time in format H
                # HH:MM - string
                start_str = t[:5].replace("-", ":")

                # parse start time
                start_time = datetime.strptime(start_str, "%H:%M")

                # add 20 minutes
                end_time = start_time + timedelta(minutes=20)

                # format back to HH:MM
                end_str = end_time.strftime("%H:%M")

                # final label
                labels.append(f"{start_str} - {end_str}")
        return labels
    # Generate acquisition numbers (Roman numerals)
    elif mode == "acq_num":
        labels = []
        day_count = {}
        for day in dates:
            # Count acquisitions for each day
            day_count[day] = day_count.get(day, 0) + 1
            # Current acquisition number for this day
            num = day_count[day]
            if num <= 4:
                labels.append(ROMAN_NUMBERS[num - 1])
            else:
                labels.append("X+")
        return labels

    # Handle invalid mode input
    else:
        raise ValueError("Invalid mode. Use 'time_labels' or 'acq_num'.")


def generate_grouped_legend(dates: List[str], times: List[str]) -> List[str]:
    """
    Generate a grouped legend using Roman numerals and time intervals.

    :param dates: List of weekday names, one for each acquisition.
    :param times: List of time ranges ("start_end") corresponding to each date.
    :return: Ordered list of formatted legend strings ready for display.
    """
    roman_labels = generate_acquisition_labels(dates, times, mode="acq_num")
    time_labels = generate_acquisition_labels(dates, times, mode="time_labels")

    day_dict = defaultdict(list)

    # Group acquisitions by day
    for day, roman, tlabel in zip(dates, roman_labels, time_labels):
        day_dict[day].append(f"  {roman} - {tlabel}")

    # Build final legend lines
    legend_lines = []
    for i, day in enumerate(day_dict):
        legend_lines.append(f"{day}:")
        legend_lines.extend(day_dict[day])
        if i < len(day_dict) - 1:
            legend_lines.append("")

    return legend_lines


def handle_plot(save_dir:str, save=True, filename="plot.png")-> None:
    """
    Handles the display and saving of matplotlib plots based on user-defined options.

    This utility function centralizes logic for whether a plot should be shown on screen,
    saved to disk, or both. If saving is enabled, the function ensures the output directory exists
    and stores the plot using the specified filename.

    :param save_dir: String specifying the directory path where the plot should be saved
                     if `save=True`. The directory is created if it doesn't exist.

    :param save: Boolean indicating whether to save the plot as an image file. Default is False.


    :param filename: String specifying the name of the image file to save, including the extension
                     (e.g., "my_plot.png"). Only relevant if `save=True`.
                     Default is "plot.png".
    :return: None
    """
    if save:
        print(f"Saving plot to: {os.path.join(save_dir, filename)}")  # <--- debug

        # Create the output directory if it doesn't exist
        os.makedirs(save_dir, exist_ok=True)
        # Save the current figure to the specified path
        plt.savefig(os.path.join(save_dir, filename))

        plt.close()


def reconstruct_df_from_dict(timeline_metrics_dict: Dict[str, str], fs: int, class_column_name: str) -> pd.DataFrame:
    """
    Reconstruct the original DataFrame from a compressed timeline dictionary.

    :param timeline_metrics_dict: Dictionary with the timeline metrics needed for generating the plots.
        Keys: "startTimestamp_endTimestamp"
        Values: class labels (e.g. 'normal', 'abnormal')
        Must be ordered chronologically.
    :param fs: Sampling frequency.
    :param class_column_name: Name of the class column.
    :return: DataFrame containing with the reconstructed timestamp and class label columns
    """

    # Convert sampling rate to pandas frequency string
    # Example: 100 Hz -> 1/100 s = 0.01 s = 10 ms
    freq_ms = 1000 / fs  # duration of one sample in milliseconds
    freq = f"{freq_ms}ms"

    # init list for holding the values of each row
    rows = []

    # cycle through the timeline metrics
    for time_range, class_label in timeline_metrics_dict.items():

        # get start and end time from key name and convert to datetime
        start_str, end_str = time_range.split("_")
        start_ts = pd.to_datetime(start_str)
        end_ts = pd.to_datetime(end_str)

        # Add the current chunk timestamps
        chunk_timestamps = pd.date_range(start=start_ts, end=end_ts, freq=freq, inclusive="both")

        # fill with the class label
        for ts in chunk_timestamps:
            rows.append((ts, class_label))

    # Build the DataFrame
    df = pd.DataFrame(rows, columns=["timestamp", class_column_name])

    # Sort index just in case
    df.sort_index(inplace=True)

    return df


def get_weekday_name(date_string, locale_string, date_format=DATE_FORMAT):
    """
    Returns the name of the day for a given date string in a specified locale.

    :param date_string: the date string in 'DD-MM-YYYY' format
    :param locale_string: the locale string (e.g., 'pt_BR', 'en_US') used to localize the day name
    :return: the localized day name without '-feira' and properly encoded in UTF-8
    """
    # parse the date string into a datetime object
    date_time = datetime.strptime(date_string, date_format)

    try:
        # set the locale for date formatting
        locale.setlocale(locale.LC_TIME, locale_string)
    except locale.Error:
        # fallback if the locale is not installed
        locale.setlocale(locale.LC_TIME, 'C')

    # get the full name of the day
    day_name = date_time.strftime('%A')

    # remove '-feira' if present (specific to Portuguese)
    day_name = day_name.replace('-feira', '')

    # ensure the string is properly encoded in UTF-8
    day_name = day_name.encode('latin1').decode('utf-8', errors='ignore')

    return day_name


def add_percentage_labels(ax,stacks: list[list[float]],fontsize: int = 12,use_axes: bool = False,
                          min_display_percent: float = 3) -> None:
    """
    Add percentage labels on top of stacked bars.
    Skips any percentage smaller than `min_display_percent`.

    :param ax: matplotlib Axes object
    :param stacks: list of lists, each sublist is the heights of one "layer" in the stack (0–100)
    :param fontsize: font size for the labels
    :param use_axes: if True, interpret heights as fractions of axes height (0–1)
    :param min_display_percent: percentages smaller than this are not shown
    """
    if not stacks:
        return

    n_bars = len(stacks[0])
    n_layers = len(stacks)

    for i in range(n_bars):
        bottom_accum = 0

        # Get the original values for this bar
        layer_vals_orig = [stacks[j][i] for j in range(n_layers)]

        # Skip layers smaller than min_display_percent
        display_flags = [val >= min_display_percent for val in layer_vals_orig]

        # Round for display if needed
        layer_vals = [round(val) for val in layer_vals_orig]
        if sum(display_flags) > 0:
            layer_vals[-1] = 100 - sum(layer_vals[:-1])  # ensure total 100

        for j, val in enumerate(layer_vals):
            layer_height = layer_vals_orig[j]

            if not display_flags[j] or layer_height <= 0:
                bottom_accum += layer_height
                continue

            # Decide vertical alignment
            y_pos = bottom_accum + layer_height / 2
            va = 'center'

            if use_axes:
                y_frac = y_pos / 100
                ax.text(0.5 if n_bars == 1 else i,y_frac,f"{val}%",ha='center',va=va,fontsize=fontsize,transform=ax.transAxes)
            else:
                ax.text(i,y_pos,f"{val}%",ha='center',va=va,fontsize=fontsize)

            bottom_accum += layer_height