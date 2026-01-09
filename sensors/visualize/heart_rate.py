"""
Functions for plotting heart rate class timelines and distributions from wearable sensor data.

Available Functions
-------------------
[Public]
plot_hr_timeline_per_acquisition(...): Plot HR class timelines for each acquisition.
plot_weekly_hr_data(...): Generate weekly bar and circular HR distribution plots.
plot_hr_variability(...): Generate HR variability plot per week

-------------------
[Private]
_plot_hr_dist(...): Plot stacked bar charts of HR class distributions.
_plot_circular_hr_dist(...): Plot circular HR class distributions.
_plot_circ_bars(...): Draw circular stacked bars.
_dict_to_hr_percentage_df(...): Convert HR distribution dictionaries to DataFrames.
_extract_date_time(...): Extract dates and times from DataFrame indices.
_scale_data(...): Scale HR class proportions for circular visualization.
_prepare_plot_data(...): Prepare plot coordinates, items and day centers for HR bars.
_set_y_limits(...): Set Y axis limits based on min/max of HR values.
_draw_bars(...): Draw HR bars for each session, adding min/max labels.
_set_x_labels(...): Set X axis ticks and labels for sessions.
_add_weekday_labels(...): Add weekday labels below each group of sessions.
_style_plot(...): Apply styling to plot, add title/labels.
_extract_hr_min_max_by_subject_day_session(...): Extract HR min/max ranges per session (I–IV) per day
-------------------
"""
# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import os
import pandas as pd
import numpy as np
from typing import Dict
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
from matplotlib.lines import Line2D
from matplotlib.patches import Circle
from matplotlib.offsetbox import AnnotationBbox, DrawingArea
import matplotlib.transforms as mtransforms
import copy
import seaborn as sns
from collections import defaultdict
from matplotlib.patches import FancyBboxPatch

# internal imports
from sensors.metrics.heart_rate import HR_DISTRIBUTIONS_DAY, HR_TIMELINE, HR_DISTRIBUTIONS,NORMAL, POTENTIALLY_ELEVATED, ELEVATED, HR_BPM_STATS
from constants import DATE_FORMAT
from utils import create_dir
from .plot_utils import generate_grouped_legend, generate_acquisition_labels, handle_plot, plot_timeline_per_acquisition, get_weekday_name
from OH_profile.constants import HR_RELATIVE_BASE_KEY
from .constants import PALE_GREEN, YELLOW, RED, ROMAN_NUMBERS, LIGHT_RED, DEEP_RED
# ------------------------------------------------------------------------------------------------------------------- #
# file specific constants
# ------------------------------------------------------------------------------------------------------------------- #

CLASS_COLORS = {
    NORMAL: PALE_GREEN,
    POTENTIALLY_ELEVATED: YELLOW,
    ELEVATED: RED,
    'no data': 'white'
}
HR_CLASS_COLORS = {
    NORMAL: PALE_GREEN,                # green
    POTENTIALLY_ELEVATED: YELLOW,  # orange
    ELEVATED: RED,              # red
    "no data": "#E0E0E0"                 # light gray
}

LEGEND_PT = {
    NORMAL: NORMAL,
    POTENTIALLY_ELEVATED: POTENTIALLY_ELEVATED,
    ELEVATED: ELEVATED,
    "no data": "Sem dados"
}

DESIRED_ORDER = [NORMAL, POTENTIALLY_ELEVATED, ELEVATED, "no data"]

LEGEND_HANDLES = [
                Line2D([0], [0], color=CLASS_COLORS[NORMAL], lw=6, label=NORMAL),
                Line2D([0], [0], color=CLASS_COLORS[POTENTIALLY_ELEVATED], lw=6, label=POTENTIALLY_ELEVATED),
                Line2D([0], [0], color=CLASS_COLORS[ELEVATED], lw=6, label=ELEVATED),
            ]

BAR_COLOR = DEEP_RED
# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #


def plot_hr_timeline_per_acquisition(day_metrics_dict: Dict, day: str, subject: str, output_folder_path: str) -> None:
    """
    Generate HR timeline plots for a single day per subject.

    This function is a wrapper around `plot_timeline_per_acquisition specifically configured to plot HR class labels over time. It
    visualizes contiguous segments of HR classes as colored blocks along a horizontal timeline, with a legend
    describing each category.

    :param day_metrics_dict: Dictionary containing HR metrics for the day. Keys are acquisition identifiers and values
                        contain timeline metric data.
    :param day: Day of the recordings in DD-MM-YYYY format.
    :param subject: Subject identifier.
    :param output_folder_path: Path to the base folder where the generated plots will be saved.
    :return: None
    """

    # delete relative HR base key for simplicity
    del day_metrics_dict[HR_DISTRIBUTIONS_DAY]

    plot_timeline_per_acquisition(
        day_metrics_dict=day_metrics_dict,
        day=day,
        subject=subject,
        output_folder_path=output_folder_path,
        timeline_key=HR_TIMELINE,
        class_colors=CLASS_COLORS,
        legend_handles=LEGEND_HANDLES,
        filename_prefix="HR",
    )


def plot_hr_variability(day_metrics_dict: Dict, subject: str, output_folder_path: str) -> None:
    """
    Plot vertical bars representing Heart Rate (HR) ranges per session (I–IV) for each day.

    - X axis: session number (I–IV), grouped by weekday.
    - Weekday labels are shown below the sessions.
    - Y axis: BPM. Each bar spans from session min to session max.
    - Missing sessions are displayed with a 'Sem dados' placeholder.

    :param day_metrics_dict: dictionary containing HR metrics for one subject
    :param subject: subject identifier
    :param output_folder_path: root directory to save generated plots
    :return: None
    """

    # delete relative HR base key for simplicity
    del day_metrics_dict[HR_RELATIVE_BASE_KEY]

    # extract the min and max HR values per session and per day
    stats_dict = _extract_hr_min_max_by_subject_day_session(day_metrics_dict)

    # Create figure and axis
    fig, ax = plt.subplots(figsize=(max(10, len(stats_dict) * 4 * 0.6), 6))

    # Prepare plot items and day centers
    plot_items, day_centers, x_cursor = _prepare_plot_data(stats_dict, ROMAN_NUMBERS)

    # Set Y axis limits
    _set_y_limits(ax, plot_items)

    # Draw HR bars
    _draw_bars(ax, plot_items, BAR_COLOR)

    # Set X axis ticks
    _set_x_labels(ax, plot_items)

    # Add weekday labels
    _add_weekday_labels(ax, day_centers)

    # Apply styling and set X axis limit
    _style_plot(ax, x_cursor)

    # Save plot
    out_dir = os.path.join(output_folder_path, subject, "HR_variability")
    filename = f"{subject}_HR_variability.png"
    handle_plot(save_dir=out_dir, save=out_dir, filename=filename)


def plot_weekly_hr_data(oh_profile, subject: str, save_path: str, save=True):
    """
    Generates weekly plots (circular and bars) for one subject.

    :param oh_profile: Dictionary containing the metrics of the HR data
    :param subject: string with the group identifier (subject ID)
    :param save_path: Path to the folder where the plots will be saved
    :param save: boolean, if True saves the plots as png, if False closes them (default = True)
    :return:
    """
    # create copy
    oh_profile = copy.deepcopy(oh_profile)

    # delete relative HR base key for simplicity
    del oh_profile[HR_RELATIVE_BASE_KEY]

    # get only the relevant data in the following format {'date': {'acquisition_time': {proportions}}} - modify in place
    # cycle over the dates in the profile
    for date_key, day_data in oh_profile.items():

        # cycle over the inner keys with the acquisition times
        for time_key in list(day_data.keys()):

            # ignore total daily proportions
            if time_key == HR_DISTRIBUTIONS_DAY:

                del day_data[time_key]
            else:
                # keep only the proportions and ignore the remaining metrics
                day_data[time_key] = day_data[time_key][HR_DISTRIBUTIONS]

    # generate weekly bar plot
    _plot_hr_dist(distributions_dict=oh_profile, subject=subject, save=save, save_path=save_path)

    # generate weekly circular plot
    _plot_circular_hr_dist(hr_percentage=oh_profile, subject=subject, save=save, save_path=save_path)

# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #

def _plot_hr_dist(distributions_dict, subject, show_acquisition_labels=True, save=False, save_path='',
                  color_scheme=HR_CLASS_COLORS, locale_string='pt_PT.UTF-8'):
    """
    Plots a stacked bar chart of heart rate class distribution for each acquisition per day.

    :param distributions_dict: Dictionary containing percentages of each heart rate class per acquisition.
    :param subject: Subject identifier extracted from the device number (e.g., '001').
    :param show_acquisition_labels: Whether to show acquisition labels as Roman numerals below each bar. Default: True
    :param save: Whether to save the plot as a PNG. Default: False
    :param save_path: Directory to save the plot. If empty, saves in the current project folder.
    :param color_scheme: Colors used for each heart rate class. Should match the number of classes. Default: HR_CLASS_COLORS
    :param locale_string: Locale string for weekday names (used in the legend). Default: 'pt_PT.UTF-8'
    :return: None
    """
    # Convert dictionary to DataFrame
    distributions_df , activity_proportions = _dict_to_hr_percentage_df(distributions_dict)

    # Ensure consistent column order
    distributions_df = distributions_df[DESIRED_ORDER]

    # Create figure and axis
    fig, ax = plt.subplots(figsize=(16, 9))

    # Extract dates and times
    dates, times = _extract_date_time(distributions_df, date_to_weekday=False)

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
    colors = [color_scheme.get(col, '#CCCCCC') for col in distributions_df.columns]

    # Plot stacked bars manually
    bottom = np.zeros(len(x_positions))
    for col, color in zip(distributions_df.columns, colors):
        values = distributions_df[col].values
        ax.bar(x_positions, values, bottom=bottom, color=color, edgecolor="#222E35",
               linewidth=0.2, width=0.9)
        bottom += values

    # Formatting: remove left spine and rotate x-ticks
    sns.despine(left=True, ax=ax)
    ax.tick_params(axis='x', rotation=0)

    # Convert dates to day/month/year format
    dates_fmt = [pd.to_datetime(d).strftime(DATE_FORMAT) for d in dates]

    # Title, axis labels, and color legend
    title_base = f'Resumo Diário da Frequência Cardíaca | Sujeito {subject} | {dates_fmt[0]} a {dates_fmt[-1]}'

    # set titles and labels
    ax.set_title(title_base, fontsize=12, fontweight='bold', pad=40)
    plt.ylabel('Distribuição da Frequência Cardíaca (%)')

    # Create legend
    handles = [plt.Rectangle((0,0),1,1, color=color_scheme[col]) for col in distributions_df.columns]
    labels_pt = [LEGEND_PT.get(l, l) for l in distributions_df.columns]
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
    dates_week = [get_weekday_name(date, locale_string) for date in dates]

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
    if save:

        out_dir = create_dir(save_path, os.path.join(f'{subject}', "HR_distributions"))
        filename = f'HR_plot_distributions_{subject}.png'
        handle_plot(save_dir=out_dir, save=save, filename=filename)


def _plot_circular_hr_dist(hr_percentage, subject, lower_limit=30, upper_limit=70,
                           show_acquisition_labels=True, save=False, save_path='',
                           color_scheme=HR_CLASS_COLORS, locale_string='pt_PT.UTF-8'):
    """
    Plots a circular representation of heart rate class distribution for each acquisition per day.

    :param hr_percentage: Dictionary containing percentages of each heart rate class per acquisition.
    :param subject: Subject identifier extracted from the device number (e.g., '001').
    :param lower_limit: Lower bound for scaling the bar lengths. Default: 30
    :param upper_limit: Upper bound for scaling the bar lengths. Default: 70
    :param show_acquisition_labels: Whether to show acquisition labels as Roman numerals. Default: True
    :param save: Whether to save the plot as a PNG. Default: False
    :param save_path: Directory to save the plot. If empty, saves in the current project folder.
    :param color_scheme: Colors used for each heart rate class. Should match the number of classes. Default: HR_CLASS_COLORS
    :param locale_string: Locale string for weekday names (used in the legend). Default: 'pt_PT.UTF-8'
    :return: None
    """

    # Convert dictionary to a DataFrame
    hr_percentage , activity_proportions = _dict_to_hr_percentage_df(hr_percentage)

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
    dates_fmt = [pd.to_datetime(d).strftime(DATE_FORMAT) for d in dates]

    # Title
    plt.title('Distribuição circular das classes de Frequência Cardíaca | Sujeito {} | {} a {}'.format(subject, dates_fmt[0], dates_fmt[-1]))

    # Add color legend
    handles, labels = ax.get_legend_handles_labels()
    labels_pt = [LEGEND_PT.get(l, l) for l in labels]
    ax.legend(handles, labels_pt, loc='center', fontsize=8)

    # Convert dates to weekdays
    dates_week = [get_weekday_name(date, locale_string) for date in dates]

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
    if save:

        out_dir = create_dir(save_path, os.path.join(f'{subject}', "HR_distributions"))
        filename = f'HR_plot_circular_{subject}.png'
        handle_plot(save_dir=out_dir, save=save, filename=filename)


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
        dates = [get_weekday_name(date, locale_string) for date in dates]

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

    # add pi/2 for the plot to start at the top center of the circle (12 o-clock position)
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
    :param ax: plot axis
    :return: none
    """

    # add the day labels to the plot
    for date, pos_start, pos_end in zip(pd.Series(dates).unique(), sep_pos[:-1], sep_pos[1:]):
        ax.text((pos_start + pos_end) / 2, y_pos, date, ha='center',
                clip_on=False, transform=ax.get_xaxis_transform(), fontweight=fontweight)


def _extract_hr_min_max_by_subject_day_session(hr_metrics: dict) -> Dict:
    """
    Extract HR min→max ranges per session (I–IV) for each day.

    - keys are date strings extracted from the session identifier
    - values are dictionaries with session numbers in Roman numerals ("I", "II", "III", "IV")
      mapped to (min_bpm, max_bpm) tuples.
    - Missing or invalid sessions (None or NaN) are ignored.

    :param hr_metrics: Containing the HR metrics for all available days
    :return: dictionary: weekday → session → (min, max)
    """

    # subject -> date (weekday) -> session_roman -> (min, max)
    hr_stats_dict = defaultdict(lambda: defaultdict(dict))

    # cycle over the multiple days
    for date_key, acquisition_metrics_dict in hr_metrics.items():

        # delete key with daily
        del acquisition_metrics_dict[HR_DISTRIBUTIONS_DAY]

        # get day of the week from the date string
        weekday = get_weekday_name(date_key, 'pt_PT.UTF-8')

        # get number of acquisition of the day
        if len(acquisition_metrics_dict) > 4:
            raise ValueError(f"Only a maximum of 4 acquisitions are allowed for this plot. Detected {len(acquisition_metrics_dict)}")

        # Initialize all four sessions as missing (I, II, III, IV)
        for r in ROMAN_NUMBERS:
            hr_stats_dict[weekday][r] = (None, None)

        for i, (acquisition_time_key, metrics_dict) in enumerate(acquisition_metrics_dict.items()):

            # get bpm statistics
            statistics_dict = metrics_dict[HR_BPM_STATS]

            # extract min and max values from the dictionary
            min_hr = float(statistics_dict['min'])
            max_hr = float(statistics_dict['max'])

            # add to final dictionary
            if min_hr is not None and max_hr is not None:

                hr_stats_dict[weekday][ROMAN_NUMBERS[i]] = (min_hr, max_hr)

    return hr_stats_dict


def _prepare_plot_data(days: dict, roman: list):
    """
    Prepare plot coordinates, items and day centers for HR bars.

    :param days: dictionary of day → session → (min, max)
    :param roman: list of session labels ["I","II","III","IV"]
    :return: tuple (plot_items, day_centers, x_cursor)
        - plot_items: list of (x, session_label, min, max)
        - day_centers: list of (x_center, weekday) for labeling
        - x_cursor: final X position after last bar
    """
    plot_items = []
    day_centers = []

    x_offset = 1  # initial X position
    day_gap = 0.8  # gap between days
    x_cursor = x_offset

    # Loop through weekdays
    for weekday in days.keys():
        sessions = days[weekday]
        day_start_x = x_cursor

        # Loop through sessions I–IV
        for r in roman:
            mn, mx = sessions.get(r)
            plot_items.append((x_cursor, r, mn, mx))
            x_cursor += 1

        day_end_x = x_cursor - 1
        day_centers.append(((day_start_x + day_end_x) / 2, weekday))
        x_cursor += day_gap

    return plot_items, day_centers, x_cursor


def _set_y_limits(ax, plot_items):
    """
    Set Y axis limits based on min/max of HR values.
    - If data is available, sets limits with padding.
    - If no data is available, sets default Y-axis from 0 to 100 BPM.

    :param ax: matplotlib axis
    :param plot_items: list of (x, session_label, min, max)
    """
    mins = [mn for (_, _, mn, _) in plot_items if mn is not None]
    maxs = [mx for (_, _, _, mx) in plot_items if mx is not None]

    if mins and maxs:
        # Compute the overall minimum and maximum HR values
        y_min = min(mins)
        y_max = max(maxs)

        # Calculate padding: 15% of the range or minimum of 1.0
        y_pad = max(1.0, 0.15 * (y_max - y_min)) if y_max > y_min else 1.0

        # Set Y-axis limits with padding, ensuring lower limit is not negative
        ax.set_ylim(max(0, y_min - y_pad), y_max + y_pad)
    else:
        # If no valid data is available, set default limits from 0 to 100 BPM
        ax.set_ylim(0, 100)


def _draw_bars(ax, plot_items, bar_color):
    """
    Draw HR bars for each session, adding min/max labels.
    - If minimum or maximum heart rate data is not available for that session, displays a "Sem dados" placeholder.
    :param ax: matplotlib axis
    :param plot_items: list of (x, session_label, min, max)
    :param bar_color: color for the bars
        """
    bar_width_pts = 18

    for x, session_label, mn, mx in plot_items:

        ylim = ax.get_ylim()

        if mn is None or mx is None:
            # No data
            y_text = ylim[0] + 0.03 * (ylim[1] - ylim[0])
            ax.text(x, y_text, "Sem dados", ha='center', va='bottom', fontsize=8)
            continue

        if mx <= mn:
            mx = mn + 0.5

        # Draw pill shaped vertical box
        ax.plot([x, x], [mn, mx], color=bar_color, linewidth=bar_width_pts, solid_capstyle='round', zorder=2)

        for y, value in [(mn, mn), (mx, mx)]:
            # Create a fixed-size circle in points
            da = DrawingArea(bar_width_pts, bar_width_pts, 0, 0)
            circle = Circle(
                (bar_width_pts / 2, bar_width_pts / 2),
                radius=bar_width_pts / 2 - 1,
                facecolor=LIGHT_RED,
                edgecolor=bar_color,
                linewidth=1.2
            )
            da.add_artist(circle)

            # Place the circle at the bar end
            ab = AnnotationBbox(da,(x, y), frameon=False, box_alignment=(0.5, 0.5), pad=0, zorder=3)
            ax.add_artist(ab)

            # Text centered in the circle
            ax.text(x, y, f"{value:.0f}", ha='center', va='center',fontsize=7,zorder=4)
    # circle_diameter_pts = bar_width_pts -2  # same as pill cap
    #
    # for x, session_label, mn, mx in plot_items:
    #     if mn is None or mx is None:
    #         y_text = ax.get_ylim()[0] + 0.03 * (ax.get_ylim()[1] - ax.get_ylim()[0])
    #         ax.text(x, y_text, "Sem dados", ha='center', va='bottom', fontsize=8)
    #         continue
    #
    #     if mx <= mn:
    #         mx = mn + 0.5
    #
    #     # Pill bar
    #     ax.plot(
    #         [x, x],
    #         [mn, mx],
    #         color=bar_color,
    #         linewidth=bar_width_pts,
    #         solid_capstyle='round',
    #         zorder=2
    #     )
    #
    #     for y, value in [(mn, mn), (mx, mx)]:
    #         # Drawing area in points
    #         da = DrawingArea(circle_diameter_pts, circle_diameter_pts, 0, 0)
    #
    #         circle = Circle(
    #             (circle_diameter_pts / 2, circle_diameter_pts / 2),
    #             radius=circle_diameter_pts / 2,
    #             facecolor=LIGHT_RED,
    #             edgecolor=bar_color,
    #             linewidth=1.2
    #         )
    #         da.add_artist(circle)
    #
    #         ab = AnnotationBbox(
    #             da,
    #             (x, y),
    #             frameon=False,
    #             box_alignment=(0.5, 0.5),
    #             zorder=3
    #         )
    #         ax.add_artist(ab)
    #
    #         # Text centered on top
    #         ax.text(
    #             x,
    #             y,
    #             f"{value:.0f}",
    #             ha='center',
    #             va='center',
    #             fontsize=7,
    #             zorder=4
    #         )


def _set_x_labels(ax, plot_items):
    """
    Set X axis ticks and labels for sessions.

    :param ax: matplotlib axis
    :param plot_items: list of (x, session_label, min, max)
    """
    # Extract X positions for each session to use as tick locations
    x_ticks = [x for (x, _, _, _) in plot_items]

    # Extract session labels (I, II, III, IV) for each X position
    x_labels = [lbl for (_, lbl, _, _) in plot_items]

    # Set the X-axis ticks at the specified positions
    ax.set_xticks(x_ticks)

    # Set the corresponding labels for each tick
    ax.set_xticklabels(x_labels)


def _add_weekday_labels(ax, day_centers):
    """
    Add weekday labels below each group of sessions.

    :param ax: matplotlib axis
    :param day_centers: list of (x_center, weekday)
    """
    # Calculate the Y position below the bottom of the plot
    y_text = ax.get_ylim()[0] - 0.08 * (ax.get_ylim()[1] - ax.get_ylim()[0])

    # Loop through each day center and add the corresponding weekday label
    for x_center, weekday in day_centers:
        ax.text(x_center, y_text, weekday, ha='center', va='top', fontsize=9)


def _style_plot(ax, x_cursor):
    """
    Apply styling to plot, add title/labels.

    :param ax: matplotlib axis
    :param x_cursor: final X position after last bar
    """
    # set y label
    ax.set_ylabel("Ritmo Cardíaco (BPM)")

    # Set plot title
    ax.set_title(f"Intervalo de Ritmo Cardíaco")

    # Enable horizontal grid lines for Y-axis
    ax.yaxis.grid(True, linestyle='--', linewidth=0.5, alpha=0.7)

    # Hide all spines
    for spine in ax.spines.values():
        spine.set_visible(False)

    # Fix last bar cutoff
    ax.set_xlim(0, x_cursor + 0.1)

    plt.tight_layout()