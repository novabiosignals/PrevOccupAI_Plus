"""

"""
# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import MultipleLocator
from babel.dates import format_datetime
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter
import copy
import re
import seaborn as sns
import locale
import datetime as dt


# internal imports
from sensors.metrics.heart_rate import DAILY_PROPORTIONS, METRICS, TIMELINE_METRICS, PROPORTIONS, NORMAL, POTENTIALLY_ABNORMAL, ABNORMAL
from constants import HR_CLASS_COLUMN_NAME, WALKING_PT, SITTING_PT, STANDING_PT
from utils import create_dir
from .plot_utils import generate_grouped_legend, generate_acquisition_labels
from OH_profile.constants import RELATIVE_HR_BASE_KEY
# ------------------------------------------------------------------------------------------------------------------- #
# file specific constants
# ------------------------------------------------------------------------------------------------------------------- #

CLASS_COLORS = {
    'normal': 'green',
    'potentially abnormal': 'orange',
    'abnormal': 'red',
    'no data': 'white'
}

HR_CLASS_COLORS = {
    NORMAL: "#A5D6A7",                # green
    POTENTIALLY_ABNORMAL: "#FFCC80",  # orange
    ABNORMAL: "#EF9A9A",              # red
    "no data": "#E0E0E0"                 # light gray
}

LEGEND_PT = {
    NORMAL: NORMAL,
    POTENTIALLY_ABNORMAL: POTENTIALLY_ABNORMAL,
    ABNORMAL: ABNORMAL,
    "no data": "Sem dados"
}

DESIRED_ORDER = [NORMAL, POTENTIALLY_ABNORMAL, ABNORMAL,"no data"]

ACTIVITY_NAMES_PT = {
    "walking": WALKING_PT,
    "sitting": SITTING_PT,
    "standing": STANDING_PT
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
                f"Grupo: {group_num} | Sujeito: {subject} | Dia: {weekday_label} | Aquisição: {acq_counter}",fontsize=14)

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
            _handle_plot(save_dir=output_path,show=show,save=True,filename=filename)


def plot_weekly_hr_data(oh_profile, group: str, subject: str, save_path: str, show_plot=False, save=True):
    """
    Plots heart rate distributions for all individuals, grouping all days in one plot per subject.

    :param oh_profile: dict structured as:
        oh_profile[SENSOR_METRICS_KEY][HEART_RATE_KEY] = {
            'date': {time: {'metrics':..., 'proportions':...}, ...},
            'date': {...}
        }
    :param show_plot: whether to display the plots
    :param save: whether to save the plots
    :param save_path: folder to save plots
    """
    # create copy
    oh_profile = copy.deepcopy(oh_profile)

    # delete relative HR base key for simplicity
    del oh_profile[RELATIVE_HR_BASE_KEY]

    # get only the relevant data in the following format {'date': {'acquisition_time': {proportions}}} - modify in place
    # cycle over the dates in the profile
    for date_key, day_data in oh_profile.items():

        # cycle over the inner keys with the acquisition times
        for time_key in list(day_data.keys()):

            # ignore total daily proportions
            if time_key == DAILY_PROPORTIONS:

                del day_data[time_key]
            else:
                # keep only the proportions and ignore the remaining metrics
                day_data[time_key] = day_data[time_key][PROPORTIONS]

    # generate weekly bar plot
    _plot_hr_dist(hr_percentage=oh_profile, group_num=group, subject=subject, show_plot=show_plot, save=save, save_path=save_path)

    # generate weekly circular plot
    plot_circular_hr_dist(hr_percentage=oh_profile, group_num=group, subject=subject, show_plot=show_plot, save=save, save_path=save_path)

# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #

def _plot_hr_dist(hr_percentage, group_num, subject, show_plot=False,
                  show_acquisition_labels=True, save=False, save_path='',
                  color_scheme=HR_CLASS_COLORS, locale_string='pt_PT.UTF-8', activity_name=None):
    """
    Plots a stacked bar chart of heart rate class distribution for each acquisition per day.

    :param hr_percentage: Dictionary containing percentages of each heart rate class per acquisition.
    :param group_num: Group identifier (e.g., 'group2'); only numeric part will be used in the title.
    :param subject: Subject identifier extracted from the device number (e.g., '001').
    :param show_plot: Whether to display the plot. Default: False
    :param show_acquisition_labels: Whether to show acquisition labels as Roman numerals below each bar. Default: True
    :param save: Whether to save the plot as a PNG. Default: False
    :param save_path: Directory to save the plot. If empty, saves in the current project folder.
    :param color_scheme: Colors used for each heart rate class. Should match the number of classes. Default: HR_CLASS_COLORS
    :param locale_string: Locale string for weekday names (used in the legend). Default: 'pt_PT.UTF-8'
    :param activity_name: Optional string to display below the title.
    :return: None
    """
    # Convert dictionary to DataFrame
    hr_percentage , activity_proportions = _dict_to_hr_percentage_df(hr_percentage)
    if hr_percentage.empty:
        print(f"[WARNING] No HR data available for Group {group_num}, Subject {subject}. Skipping plot.")
        return

    # Ensure consistent column order
    hr_percentage = hr_percentage[DESIRED_ORDER]

    # Create figure and axis
    fig, ax = plt.subplots(figsize=(16, 9))

    # Extract dates and times
    dates, times = _extract_date_time(hr_percentage, date_to_weekday=False)

    # Create X positions with gaps
    x_positions = []
    x = 0
    gap_acquisition = 0.05   # small gap between acquisitions
    gap_day = 0.4           # larger gap between days

    for i in range(len(dates)):
        x_positions.append(x)
        if i < len(dates) - 1:
            if dates[i] == dates[i+1]:
                x += 1 + gap_acquisition
            else:
                x += 1 + gap_day

    # Prepare colors aligned with DataFrame columns
    colors = [color_scheme.get(col, '#CCCCCC') for col in hr_percentage.columns]

    # Plot stacked bars manually
    bottom = np.zeros(len(x_positions))
    for col, color in zip(hr_percentage.columns, colors):
        values = hr_percentage[col].values
        ax.bar(x_positions, values, bottom=bottom, color=color, edgecolor="#222E35",
               linewidth=0.2, width=0.9)
        bottom += values

    # Formatting: remove left spine and rotate x-ticks
    sns.despine(left=True, ax=ax)
    ax.tick_params(axis='x', rotation=0)

    # Convert dates to day/month/year format
    dates_fmt = [pd.to_datetime(d).strftime('%d/%m/%Y') for d in dates]

    # Title, axis labels, and color legend
    group_num_numeric = re.search(r'\d+', group_num).group()
    title_base = f'Resumo Diário da Frequência Cardíaca - Grupo {group_num_numeric} | Sujeito {subject} | {dates_fmt[0]} a {dates_fmt[-1]}'

    # set titles and labels
    ax.set_title(title_base, fontsize=12, fontweight='bold', pad=40)
    plt.ylabel('Distribuição da Frequência Cardíaca (%)')

    # Create legend
    handles = [plt.Rectangle((0,0),1,1, color=color_scheme[col]) for col in hr_percentage.columns]
    labels_pt = [LEGEND_PT.get(l, l) for l in hr_percentage.columns]
    ax.legend(handles, labels_pt, bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)

    # Generate acquisition labels if requested
    if show_acquisition_labels:
        labels = generate_acquisition_labels(dates, times, mode="acq_num")
        ax.set_xticks(x_positions)
        ax.set_xticklabels(labels)
        y_pos_day_label = -0.08
    else:
        ax.set_xticks([])
        y_pos_day_label = -0.05

    # Convert dates to weekdays
    dates_week = [_get_day_string(date, locale_string) for date in dates]

    # Add day labels below the bars
    dates_series = pd.Series(dates)
    unique_days = dates_series.unique()
    day_limits = []

    for day in unique_days:
        idx = dates_series == day
        positions_for_day = np.array(x_positions)[idx]
        start = positions_for_day.min() - 0.5
        end = positions_for_day.max() + 0.5
        day_limits.append((start, end))

    sep_pos = [start for start, end in day_limits] + [day_limits[-1][1]]

    _show_day_labels(dates_week, sep_pos, ax, y_pos_day_label)

    # Generate lateral legend lines
    legend_lines = generate_grouped_legend(dates_week, times)

    # Add lateral legend to the right side of the plot; weekdays in bold
    for i, line in enumerate(legend_lines):
        y_start = 0.75
        y_step = 0.03
        if line.endswith(':'):
            fig.text(0.87, y_start - i * y_step, line, fontsize=9, va='top', ha='left', fontweight='bold')
        else:
            fig.text(0.87, y_start - i * y_step, line, fontsize=9, va='top', ha='left')

    # Set X and Y axis limits
    ax.set_xlim(min(x_positions)-0.5, max(x_positions)+0.5)
    ax.set_ylim(ymin=0)

    # Make 'no data' bars slightly transparent
    _change_transparency_for_category(ax, 'no data')

    # Y-axis ticks and grid
    ax.yaxis.set_major_locator(MultipleLocator(20))
    ax.yaxis.set_minor_locator(MultipleLocator(10))
    ax.yaxis.grid(True, which='both', linestyle='--', linewidth=0.5, alpha=0.7)  # linhas de grade

    fig.tight_layout()

    # Save or show plot
    if save or show_plot:

        out_dir = create_dir(save_path, os.path.join(f'{group_num}', f'{subject}', "HEART_RATE_PROPORTIONS"))
        filename = f'hr_plot_dist{subject}.png'
        _handle_plot(save_dir=out_dir, show=show_plot, save=save, filename=filename)


def plot_circular_hr_dist(hr_percentage, group_num, subject, lower_limit=30, upper_limit=70,
                          show_plot=False, show_acquisition_labels=True, save=False, save_path='',
                          color_scheme=HR_CLASS_COLORS, locale_string='pt_PT.UTF-8'):
    """
    Plots a circular representation of heart rate class distribution for each acquisition per day.

    :param hr_percentage: Dictionary containing percentages of each heart rate class per acquisition.
    :param group_num: Group identifier (e.g., 'group2'); only numeric part will be used in the title.
    :param subject: Subject identifier extracted from the device number (e.g., '001').
    :param lower_limit: Lower bound for scaling the bar lengths. Default: 30
    :param upper_limit: Upper bound for scaling the bar lengths. Default: 70
    :param show_plot: Whether to display the plot. Default: False
    :param show_acquisition_labels: Whether to show acquisition labels as Roman numerals. Default: True
    :param save: Whether to save the plot as a PNG. Default: False
    :param save_path: Directory to save the plot. If empty, saves in the current project folder.
    :param color_scheme: Colors used for each heart rate class. Should match the number of classes. Default: HR_CLASS_COLORS
    :param locale_string: Locale string for weekday names (used in the legend). Default: 'pt_PT.UTF-8'
    :return: None
    """

    # Convert dictionary to a DataFrame
    hr_percentage , activity_proportions = _dict_to_hr_percentage_df(hr_percentage)
    if hr_percentage.empty:
        print(f"[WARNING] No HR data available for Group {group_num}, Subject {subject}. Skipping plot.")
        return

    # Order the classes
    hr_percentage = hr_percentage[DESIRED_ORDER]

    # Create figure and polar axes
    fig, ax = plt.subplots(figsize=(14, 10), subplot_kw={'projection': 'polar'})

    # Scale data to fit limits
    hr_percentage = _scale_data(hr_percentage, lower_limit, upper_limit)

    # Plot circular bars
    width, angles = _plot_circ_bars(hr_percentage, color_scheme, lower_limit, ax)

    # Remove default grid
    plt.axis('off')

    # Extract dates and times from index
    dates, times = _extract_date_time(hr_percentage, date_to_weekday=False)

    # Convert dates to day/month/year format
    dates_fmt = [pd.to_datetime(d).strftime('%d/%m/%Y') for d in dates]

    # Title
    group_num_numeric = re.search(r'\d+', group_num).group()
    plt.title('Distribuição circular das classes de Frequência Cardíaca - Grupo {} | Sujeito {} | {} a {}'.format(group_num_numeric, subject, dates_fmt[0], dates_fmt[-1]))

    # Add color legend
    handles, labels = ax.get_legend_handles_labels()
    labels_pt = [LEGEND_PT.get(l, l) for l in labels]
    ax.legend(handles, labels_pt, loc='center', fontsize=8)

    # Convert dates to weekdays
    dates_week = [_get_day_string(date, locale_string) for date in dates]

    # Generate grouped acquisition legend (weekdays + acquisition times)
    legend_lines = generate_grouped_legend(dates_week, times)

    # Add lateral legend using fig.text; weekdays in bold
    for i, line in enumerate(legend_lines):
        if line.endswith(':'):  # Weekday
            fig.text(0.87, 0.95 - i * 0.03, line, fontsize=9, va='top', ha='left', fontweight='bold')
        else:
            fig.text(0.87, 0.95 - i * 0.03, line, fontsize=9, va='top', ha='left')

    # Draw vertical lines to separate days
    acquisition_counts = pd.Series(dates_week).value_counts().sort_index().values
    pos = np.append([0], acquisition_counts[:-1])
    pos = np.cumsum(pos)
    pos = [angles[i] for i in pos]
    pos = [p + width/2 for p in pos]  # Shift half bar width
    ax.vlines(pos, lower_limit - 5, upper_limit + 12, color="#FFFFFF", linewidth=6.5)

    # Show acquisition labels along the bars
    if show_acquisition_labels:
        labels = generate_acquisition_labels(dates_week, times, mode='acq_num')
        _show_acquisition_labels(angles, labels, ax, lower_limit)

    # Add day labels
    pos = np.append(pos, pos[0] + 2 * np.pi)
    _show_day_labels(dates_week, pos, ax, 1.03)

    # Make 'no data' bars slightly transparent
    _change_transparency_for_category(ax, 'no data')

    # Adjust layout
    fig.tight_layout()

    # Save or show the plot
    if save or show_plot:

        out_dir = create_dir(save_path, os.path.join(f'{group_num}', f'{subject}', "HEART_RATE_PROPORTIONS"))
        filename = f'hr_plot_circular{subject}.png'
        _handle_plot(save_dir=out_dir, show=show_plot, save=save, filename=filename)


def _plot_circ_bars(hr_percentage_df, color_scheme, lower_limit, ax):
    """
    Plots a circular stacked bar plot.
    :param hr_percentage_df: DataFrame with the percentages of each heart rate class during acquisitions
    :param color_scheme: dict (class_name -> color hex) or list of colors
    :param lower_limit: lower limit of the plot. Parameter to set the proportions of the plot.
    :param ax: matplotlib axis
    :return: (width, angles) of the bars
    """

    # initialize the bottom (where the bars should start)
    bottom = np.zeros(hr_percentage_df.shape[0]) + lower_limit

    # calculate the bar width and angles for plotting the bars
    width, angles = _get_bar_width_and_angles(hr_percentage_df)

    # if it's a list, make it iterable
    if isinstance(color_scheme, (list, tuple)):
        color_iter = iter(color_scheme)
    else:
        color_iter = None  # not needed if it's a dict

    # cycle through the columns and plot
    for column, values in hr_percentage_df.items():
        # choose the color
        if isinstance(color_scheme, dict):
            color = color_scheme.get(column, "#E0E0E0")  # fallback light gray
        else:
            color = _get_next_color(color_iter)

        # plot the bars
        ax.bar(x=angles,height=values,width=width,bottom=bottom,label=column,color=color,edgecolor="#FFFFFF",lw=0.8)

        # update the bottom (stacking)
        bottom = bottom + values

    return width, angles


def _dict_to_hr_percentage_df(summary_dict):
    """
    Converts a summary dictionary of acquisition proportions into a pandas DataFrame.
    Ensures all heart rate classes
    are present as columns. If any are missing, they are filled with zeros.
    Also ensures that each day contains exactly 4 acquisitions; if fewer exist, missing
    acquisitions are added with all zeros.

    :param summary_dict: dictionary containing acquisition proportions by date and start time
    :return: pandas DataFrame with proportions indexed by 'date/start_time'
    """

    records = []
    index = []
    activity_proportions = []

    # Step 1: convert dictionary entries to records
    for date_str, acquisitions in summary_dict.items():
        for time, session_data in acquisitions.items():

            row = {cls: session_data.get(cls, 0) for cls in DESIRED_ORDER}
            activity_proportions.append("")

            index.append(f"{date_str}/{time}")
            records.append(row)

        # Step 2: check number of acquisitions per day
        num_acq = len(acquisitions)
        if num_acq < 4:
            missing = 4 - num_acq
            for i in range(missing):
                missing_row = {cls: 0 for cls in DESIRED_ORDER}
                missing_row['no data'] = 1
                index.append(f"{date_str}/missing_{i + 1}")
                records.append(missing_row)

    # Step 3: build DataFrame
    df = pd.DataFrame(records, index=index)

    # Step 4: make sure all columns exist and fill missing values
    for cls in DESIRED_ORDER:
        if cls not in df.columns:
            df[cls] = 0

    return df[DESIRED_ORDER].fillna(0) * 100 , activity_proportions


def _extract_date_time(hr_percentage_df, date_to_weekday=True, locale_string='pt_PT.UTF-8'):
    """
    extracts the date and the time as lists from the index of the hr_percentage_dataframe
    :param hr_percentage_df: the dataframe containing the percentages for each class
    :param date_to_weekday: (optional) boolean to indicate if the dates should be transformed to weekdays
    :param locale_string: string indicating the local for returning the day string in a specific language
    :return: the extracted dates and times as an individual lists
    """

    # extract date and times from dataframe indexes
    date_time = hr_percentage_df.index.values

    # extract the dates and the times
    dates = [dtm.split("/")[0] for dtm in date_time]
    times = [dtm.split("/")[1] for dtm in date_time]

    # transform dates to weekdays if needed
    if date_to_weekday:
        dates = [_get_day_string(date, locale_string) for date in dates]

    return dates, times


def _show_acquisition_labels(angles, labels, ax, lower_limit):
    """
    adds acquisition labels to the bottom of the bars
    :param angles: the angles at which the center of the bar is located
    :param labels: the labels to add
    :param ax: the plot axis
    :param lower_limit: lower limit of the plot. Parameter to set the proportions of the plot.
    :return: none
    """

    for angle, label in zip(angles, labels):

        ax.text(x=angle, y=lower_limit - 5, s=label, va='center', ha='center')


def _get_day_string(date_string, locale_string):
    """
    Returns the name of the day for a given date string in a specified locale.

    :param date_string: the date string in 'YYYY-MM-DD' format
    :param locale_string: the locale string (e.g., 'pt_BR', 'en_US') used to localize the day name
    :return: the localized day name without '-feira' and properly encoded in UTF-8
    """
    # parse the date string into a datetime object
    date_time = dt.datetime.strptime(date_string, '%Y-%m-%d')

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


def _change_transparency_for_category(ax, category, alpha=0.5):
    '''
    changes the transparency for a category within a plot
    :param ax: the plot axis
    :param category: the category as a string
    :param alpha: (optional) the transparency value. default: 0.5
    :return:
    '''

    # 3. Make 'no data' bars slightly transparent
    for container in ax.containers:  # ax.containers returns the containers for each class

        # check if the label of the container is 'no data'
        if container.get_label() == category:

            # cycle through all the children and check where the height = 100.0
            for i, child in enumerate(container.get_children()):

                child.set_alpha(alpha)


def _scale_data(data, lower_limit, upper_limit):
    """
    scales the data between the lower and upper limit
    :param data: the data (pandas data frame)
    :param lower_limit: the lower limit to which the data should be scaled to
    :param upper_limit: the upper limit to which the data should be scaled to
    :return: pandas data frame with the scaled data
    """
    # put the values between a range of [lower_limit, upper_limit (for visualization purposes)
    # 1. compute the maximum value in the entire dataset
    max_val = data.to_numpy().max()
    min_val = data.to_numpy().min()

    # 2. scale the data to fit the set upper and lower limit
    return ((data - min_val) / (max_val - min_val)) * (upper_limit - lower_limit)


def _get_bar_width_and_angles(hr_percentage_df):
    """
    calculates the bar widths and angles for circular plot
    :param hr_percentage_df: the data frame with the percentages of each heart rate class during the acquisitions
    :return: the bar width and angles for plotting the bars
    """

    # compute the width of each bar
    width = 2 * np.pi / hr_percentage_df.shape[0]

    # set the indexes for calculating the angles
    indexes = list(range(1, hr_percentage_df.shape[0] + 1))

    # the x position of the bar is set at its center, therefore half of the width needs to be
    # subtracted to get a correct positioning
    angles = [(element * width) - width / 2 for element in indexes]

    # add pi/2 for the plot to start at the top center of the circle (12 o-clock posiition)
    angles = [angle + np.pi / 2 for angle in angles]

    # reverse the angles to have the bars ordered clock-wise
    angles.reverse()

    return width, angles


def _get_next_color(cs_iterator):
    """
    returns the next color from an iterator if the iterator exists
    :param cs_iterator: the color scheme iterator
    :return: next color of iterator or None when no color scheme was provided
    """

    if cs_iterator:

        return next(cs_iterator)

    else:
        return None


def _show_day_labels(dates, sep_pos, ax, y_pos, fontweight='semibold'):
    """
    adds day labels to the plot that are centered between the day separation lines
    :param dates: the dates/ weekdays of the acquisition
    :param sep_pos: the positions of the lines that visually separate the days on the plot
    :param ax: the plot axis
    :return: none
    """

    # add the day labels to the plot
    for date, pos_start, pos_end in zip(pd.Series(dates).unique(), sep_pos[:-1], sep_pos[1:]):
        ax.text((pos_start + pos_end) / 2, y_pos, date, ha='center',
                clip_on=False, transform=ax.get_xaxis_transform(), fontweight=fontweight)


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