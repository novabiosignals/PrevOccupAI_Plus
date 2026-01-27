"""
Function to visualize the pain data

Available Functions
-------------------
[Public]
generate_pain_plots(...): Plots morning and afternoon pain lines for each day using the colors in the lines
-------------------

[Private]
_init_week_figure(...): Initialize a figure with the same number of subplots as days of pain data.
_plot_pain_lines(...): Plots all pain points on a given axis.
_plot_empty_day(...): Plots only the body silhouette when no pain points are reported.
_finalize_axis(...):Adds background image and sets the title of an axis.
_load_points(...): Safely parses and flattens multiple JSON lines containing pain points into a single list of point dictionaries.
"""
# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import os
import json
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from typing import List, Tuple

# internal imports
from utils import create_dir
import sensors.visualize as sv
from questionnaires.constants import PAIN_COLORS
from questionnaires.load.pain_lines_loader import load_pain_lines
# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #

def generate_pain_plots(folder_path: str, output_folder: str, subject_id: str) -> None:
    """
    Plots morning and afternoon pain lines for each day using the colors in the lines,
    and adds a top legend showing pain intensity.

    :param folder_path: path to the folder containing the pain files
    :param output_folder: Path to the folder where the output figure will be saved.
    :param subject_id: subject identifier
    :return:
    """
    # load lines into list
    lines_list = load_pain_lines(folder_path, subject_id)

    # number of days
    num_days = len(lines_list)

    # initialize figure with 2 rows (morning, afternoon) and one column per day
    fig, axs = _init_week_figure(num_days)

    for day_index, day_tuple in enumerate(lines_list):
        # unpack
        date, morning_lines, afternoon_lines = day_tuple

        morning_points = _load_points(morning_lines)
        afternoon_points = _load_points(afternoon_lines)

        # plot morning
        if not morning_points:
            _plot_empty_day(axs[0, day_index])
        else:
            _plot_pain_lines(axs[0, day_index], morning_points)

        # plot afternoon
        if not afternoon_points:
            _plot_empty_day(axs[1, day_index])
        else:
            _plot_pain_lines(axs[1, day_index], afternoon_points)

        # finalize
        _finalize_axis(axs[0, day_index], f"{sv.get_weekday_name(date, 'pt_PT.UTF-8', '%d-%m-%Y')} - início")
        _finalize_axis(axs[1, day_index], f"{sv.get_weekday_name(date, 'pt_PT.UTF-8', '%d-%m-%Y')} - fim")

    # add top legend showing intensity colors
    legend_handles = [Line2D([0], [0], marker='o', color=color, label=intensity,
                             markersize=8, linestyle='') for intensity, color in PAIN_COLORS.items()]

    fig.legend(handles=legend_handles,loc='upper center',ncol=len(PAIN_COLORS),fontsize=8,frameon=False,
        title="Escala de intensidade da dor")

    # adjust layout to leave space for legend
    plt.subplots_adjust(top=0.90)

    # generate output path
    output_path = create_dir(output_folder, subject_id)

    # save figure
    plt.savefig(os.path.join(output_path, f"{subject_id}_pain_plot"), bbox_inches="tight")
    plt.close('all')


# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #

def _init_week_figure(num_days: int):
    """
    Initialize a figure with the same number of subplots as days of pain data.
    :param num_days: number of days when there's pain data
    :return:
    """
    # create figure with 2 rows and num_days columns
    fig, axs = plt.subplots(2, num_days, figsize=(2 * num_days, 6))

    # return figure and axes
    return fig, axs


def _plot_pain_lines(ax: plt.Axes, pain_lines: List[dict]) -> None:
    """
    Plots all pain points on a given axis.

    :param ax: Matplotlib axis where points will be drawn.
    :param pain_lines: List of dictionaries representing pain points, each with keys:
                       'x', 'y', 'color'.
    :return: None.
    """
    # loop over each pain point
    for line in pain_lines:

        # extract and round x coordinate
        x = int(round(line["x"]))

        # extract and round y coordinate
        y = int(round(line["y"]))

        # extract color
        color = line["color"]

        # plot pain point
        ax.plot(x,y,marker='o',ms=4,color=color,alpha=1)


def _plot_empty_day(ax: plt.Axes) -> None:
    """
    Plots only the body silhouette when no pain points are reported.

    :param ax: Matplotlib axis where the silhouette will be drawn.
    :return: None.
    """

    script_dir = os.path.dirname(os.path.abspath(__file__))
    img_path = os.path.join(script_dir, "pain_figure.png")

    data = plt.imread(img_path)

    # draw image on axis
    ax.imshow(data, zorder=2)

    # hide axis
    ax.axis('off')


def _finalize_axis(ax, title: str):
    """
    Adds background image and sets the title of an axis.

    :param ax: Matplotlib axis to finalize.
    :param title: Title to set for the axis.
    :return: None.
    """

    script_dir = os.path.dirname(os.path.abspath(__file__))
    img_path = os.path.join(script_dir, "pain_figure.png")

    data = plt.imread(img_path)

    # draw image above pain points
    ax.imshow(data, zorder=2)

    # hide axis ticks and borders
    ax.axis('off')

    # set axis title
    ax.set_title(title)


def _load_points(lines):
    """
    Safely parses and flattens multiple JSON lines containing pain points into a single list of point dictionaries.

    This is needed because:

    When loading pain data from files, each line is expected to be a JSON array of point dictionaries:
        [{"x": 123, "y": 456, "color": "#cad203"}, ...]
    However, in practice, some lines can be:
      - Empty strings
      - Contain the text "No pain reported"
      - Malformed JSON (extra commas, truncated arrays, etc.)

    Directly calling json.loads on these lines can raise JSONDecodeError, which breaks plotting
    or metric calculations for certain days. Some days may have very large lines with many points,
    which can also cause "Extra data" errors if multiple JSON arrays are concatenated improperly.

    Therefore, this function:

    1. Strips whitespace from each line.
    2. Skips empty lines or lines containing "No pain reported".
    3. Tries to parse the line using json.loads:
       - If successful, it extends the `points` list with the parsed points.
       - If json.JSONDecodeError occurs, it silently skips the line.
    4. Returns a flat list of point dictionaries from all valid lines.

    Each point dictionary has the keys:
        - "x": X-coordinate of the point
        - "y": Y-coordinate of the point
        - "color": Color code representing pain intensity

    :param lines: List of strings, each representing a line from a pain file
    :return: Flattened list of point dictionaries with all valid points
    """
    points = []
    for line in lines:
        line = line.strip()
        if not line or "No pain reported" in line:
            continue
        try:
            parsed = json.loads(line)  # could be list of dicts
            points.extend(parsed)
        except json.JSONDecodeError:
            continue
    return points
