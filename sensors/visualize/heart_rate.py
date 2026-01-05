"""

"""
# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import os
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from babel.dates import format_datetime
from matplotlib.lines import Line2D
from utils import create_dir

# internal imports
from sensors.metrics.heart_rate import DAILY_PROPORTIONS, METRICS, TIMELINE_METRICS
from constants import HR_CLASS_COLUMN_NAME

# ------------------------------------------------------------------------------------------------------------------- #
# file specific constants
# ------------------------------------------------------------------------------------------------------------------- #

CLASS_COLORS = {
    'normal': 'green',
    'potentially abnormal': 'orange',
    'abnormal': 'red',
    'no data': 'white'
}

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #

def plot_hr_timeline_per_acquisition(hr_metrics_dict: Dict, day: str, group: str, subject: str, output_folder_path: str,
    gap_threshold=timedelta(seconds=30), show=False) -> None:
    """
    # TODO UPDATE THIS DOCSTRING
    Generates a heart rate timeline plot for each acquisition (each DataFrame) separately.

    Folder structure:
        {save_root}/{group}/{subject}/HEART_RATE/HEART_RATE_TIMELINE/hr_timeline_{day}_acq{idx}.png

    :param day:
    :param hr_metrics_dict: dict where keys are dates (YYYY-MM-DD) and values are lists of DataFrames
                            containing heart rate data for that day.
    :param group: Group identifier (e.g., '001')
    :param subject: Subject identifier (e.g., '001')
    :param gap_threshold: timedelta indicating the minimum gap between consecutive points to start a new block
                          (default = 30 seconds)
    :param output_folder_path: Path to the folder where plots will be saved.
    :param show: boolean, if True displays the plots, if False closes them (default = True)
    :return: None
    """

    # create output directory
    output_path = create_dir(output_folder_path, os.path.join(str(group), str(subject), "heart_rate"))

    # counter for the acquisitions
    acq_counter = 0

    for key, hr_features_dict in hr_metrics_dict.items():

        if key != DAILY_PROPORTIONS:

            # update counter
            acq_counter += 1

            # get timeline metrics
            timeline_metrics_dict = hr_features_dict[METRICS][TIMELINE_METRICS]

            # raise error if there are no metrics to plot
            if len(timeline_metrics_dict) == 0:

                raise ValueError(f"No timeline metrics to plot for acquisition time: {key}")

            # reconstruct dataframe with hr ratio class column and timestamp column
            df = _reconstruct_df_from_dict(timeline_metrics_dict, fs = 100)

            # convert timestamps into datetime objects
            tmp = df.copy()

            valid = tmp[tmp[HR_CLASS_COLUMN_NAME] != 'no data'].copy()

            # Create figure
            fig, ax = plt.subplots(figsize=(15, 3))

            # Identify continuous blocks
            valid['gap'] = valid['timestamp'].diff()
            new_block = (
                (valid[HR_CLASS_COLUMN_NAME] != valid[HR_CLASS_COLUMN_NAME].shift()) |
                (valid['gap'].isna()) |
                (valid['gap'] > gap_threshold)
            )
            block_id = new_block.cumsum()

            for _, grp in valid.groupby(block_id, sort=False):
                cls = grp[HR_CLASS_COLUMN_NAME].iloc[0]
                x0 = grp['timestamp'].iloc[0]
                x1 = grp['timestamp'].iloc[-1]
                ax.hlines(y=0, xmin=x0, xmax=x1, color=CLASS_COLORS.get(cls, 'gray'), linewidth=6)

            weekday_label = format_datetime(
                datetime.strptime(day, "%Y-%m-%d"),
                "dd-MM-yyyy (EEEE)",
                locale="pt_PT"
            )

            # Axis config
            ax.set_yticks([])
            ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            for spine in ax.spines.values():
                spine.set_visible(False)

            ax.set_xlabel("Hora do Dia", fontsize=12)
            group_num = ''.join(filter(str.isdigit, str(group)))
            ax.set_title(
                f"Grupo: {group_num} | Sujeito: {subject} | Dia: {weekday_label} | Aquisição: {acq_counter}",
                fontsize=14
            )

            # Legend
            legend_handles = [
                Line2D([0], [0], color=CLASS_COLORS['normal'], lw=6, label='Normal'),
                Line2D([0], [0], color=CLASS_COLORS['potentially abnormal'], lw=6, label='Potencialmente anormal'),
                Line2D([0], [0], color=CLASS_COLORS['abnormal'], lw=6, label='Anormal'),
            ]
            ax.legend(handles=legend_handles, bbox_to_anchor=(1.04, 1), loc='lower center')

            plt.tight_layout()

            # Save figure
            filename = f"hr_timeline_{day}_acq{acq_counter}.png"
            _handle_plot(
                save_dir=output_path,
                show=show,
                save=True,
                filename=filename
            )




# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #

def _reconstruct_df_from_dict(timeline_metrics_dict: Dict[str, str], fs: int = 100) -> pd.DataFrame:
    """
    Reconstruct the original DataFrame from a compressed timeline dictionary.

    :param timeline_metrics_dict: Dictionary with the timeline metrics needed for generating the plots.
        Keys: "startTimestamp_endTimestamp"
        Values: class labels (e.g. 'normal', 'abnormal')
        Must be ordered chronologically.
    :param fs: Sampling frequency.
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
    df = pd.DataFrame(rows, columns=["timestamp", HR_CLASS_COLUMN_NAME])

    # Sort index just in case
    df.sort_index(inplace=True)

    return df


def _handle_plot(save_dir:str, show=True, save=False, filename="plot.png")-> None:
    """
    Handles the display and saving of matplotlib plots based on user-defined options.

    This utility function centralizes logic for whether a plot should be shown on screen,
    saved to disk, or both. If saving is enabled, the function ensures the output directory exists
    and stores the plot using the specified filename.

    :param save_dir: String specifying the directory path where the plot should be saved
                     if `save=True`. The directory is created if it doesn't exist.

    :param show: Boolean indicating whether to display the plot interactively on screen.
                 If False, the plot is closed after saving. Default is True.

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
    if show:
        plt.show()
    else:
        plt.close()