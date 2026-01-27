"""

This module provides visualization utilities for time-based activity metrics.

Available Functions
-------------------
[Public]
plot_activity_proportions_per_day(...): Plots a stacked bar chart for each day of acquisition, showing proportions of walking, sitting, and standing.
plot_activity_timeline_per_day(...): Plots a timeline chart for each acquisition day, showing walking, sitting, and
    standing activities over real time.
-------------------
"""

# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from matplotlib.ticker import FuncFormatter
from matplotlib.patches import Patch, Rectangle
from babel.dates import format_datetime
import os

# internal imports
from .plot_utils import handle_plot, get_weekday_name, add_percentage_labels
from HAR.classifier import CLASS_WALK, CLASS_SIT, CLASS_STAND
from .constants import RED, YELLOW, BLUE_STATE, GREEN, SALMON, GRAY
from OH_profile.constants import HAR_DISTRIBUTIONS_KEY, HAR_TIMELINE_KEY, HAR_STEPS_KEY, HAR_DISTANCE_KEY, HAR_NUM_STEPS_KEY
from utils import create_dir
# ------------------------------------------------------------------------------------------------------------------- #
# file specific constants
# ------------------------------------------------------------------------------------------------------------------- #
WALKING_NAME = 'Andar'
STANDING_NAME = 'De pé'
SITTING_NAME = 'Sentado'
TRABALHO_PESADO = 'trabalho_pesado'

TOTAL_DURATION = 'total_duration'
ACTIVITY_MAP = {CLASS_WALK: WALKING_NAME, CLASS_SIT: SITTING_NAME, CLASS_STAND: STANDING_NAME}
SESSION_DT = 'session_dt'

activity_colors = {
    WALKING_NAME: BLUE_STATE,
    SITTING_NAME: GREEN,
    STANDING_NAME: SALMON,
}

SITTING_WARNING_COLOR = YELLOW  #orange
SITTING_RISK_COLOR = RED #red

MAX_CONTINUOUS_SITTING_S =2*60*60 # 2 hours (EU-OSHA)
WARNING_SITTING_S = 1*60*60 # 1 hour

BAR_WIDTH = 0.6

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #
def plot_activity_distributions_ospaq_vs_real(personal_metrics_dict: dict,har_metrics_dict: dict,subject_id: str,
    output_folder_path: str) -> None:
    """
    Plots of the activity distributions - perceived (OSPAQ questionnaire) vs real (from sensors), side by side.

    - Left plot: single OSPAQ bar (from questionnaires), stacked: walking → standing → sitting
      The 'trabalho_pesado' is added to the walking percentage
    - Right plot: HAR real data per day, stacked: walking → standing → sitting
    - Shared y-axis
    - Percentage labels added on top of each stack using reusable function
    :param personal_metrics_dict: Dictionary containing the personal questionnaire metrics loaded from JSON.
    :param subject_id: Identifier of the subject extracted from the JSON filename
    :param output_folder_path: Directory path to save plots.
                          Sitting periods exceeding this duration are highlighted as a
                          warning (e.g., orange), but are below the maximum recommended
                          limit.
    """

    # Extract OSPAQ data
    ospaq = personal_metrics_dict["OSPAQ"]['OSPAQ_distributions'].copy()

    # extract the distributions and put in percentage
    walking = ospaq.get(WALKING_NAME, 0)*100
    sitting = ospaq.get(SITTING_NAME, 0)*100
    standing = ospaq.get(STANDING_NAME, 0)*100
    heavy = ospaq.get(TRABALHO_PESADO, 0)*100

    # add value of trabalho pesado to the walking and remove it from the dict
    walking += heavy
    ospaq.pop(TRABALHO_PESADO, None)

    # Create figure with shared y-axis
    fig, (ax_left, ax_right) = plt.subplots(1, 2, figsize=(14, 6), sharey=True)

    # ---------------- LEFT: OSPAQ (axes coordinates) ----------------
    BAR_WIDTH_AXES = 0.15  # fraction of subplot width
    X_CENTER = 0.5

    bottom = 0.0
    stacks_left = []  # to collect values for percentage labels

    segments = [
        (walking, activity_colors[WALKING_NAME]),
        (standing, activity_colors[STANDING_NAME]),
        (sitting, activity_colors[SITTING_NAME]),
    ]

    for value, color in segments:
        if value == 0:
            stacks_left.append([0])
            continue
        height = value / 100.0  # percent → fraction
        rect = Rectangle((X_CENTER - BAR_WIDTH_AXES / 2, bottom),BAR_WIDTH_AXES,height,transform=ax_left.transAxes,
            color=color)

        ax_left.add_patch(rect)
        bottom += height
        stacks_left.append([value])  # store original % for labels

    # Add percentage labels (reusable function)
    add_percentage_labels(ax_left, stacks_left, use_axes=True)

    # Format left axis
    ax_left.set_xlim(0, 1)
    ax_left.set_ylim(0, 1)
    ax_left.set_xticks([0.5])
    ax_left.set_xticklabels(["questionário"], fontsize=12)
    ax_left.set_ylabel("Percentagem de Tempo (%)", fontsize=12)
    ax_left.set_title("Resultado do questionário", fontsize=14)
    ax_left.set_axisbelow(True)

    ax_left.grid(axis='y', color='lightgray', linestyle='--', linewidth=0.7)
    for spine in ax_left.spines.values():
        spine.set_visible(False)

    # ---------------- RIGHT: REAL (HAR bars) ----------------
    plot_activity_proportions_per_day(har_metrics_dict, ax=ax_right)
    ax_right.set_title("Resultado dos sensores", fontsize=14)
    ax_right.tick_params(axis='y', left=False, labelleft=False)

    # Leave space for legend with tight_layout
    plt.tight_layout(rect=[0, 0.08, 1, 0.92])

    fig.legend(loc="upper center",bbox_to_anchor=(0.5, 0.1),  ncol=4,frameon=False,fontsize=12)

    fig.suptitle("Distribuição de atividades ao longo do dia", fontsize=16, y=0.97)

    # ---------------- SAVE ----------------
    output_path = create_dir(output_folder_path, os.path.join(subject_id, "human_activities"))
    filename = f"{subject_id}_ospaq_vs_real_activity_distribution.png"
    handle_plot(save_dir=output_path, filename=filename)


def plot_activity_proportions_per_day(har_metrics_dict: dict, ax: plt.Axes, locale='pt_PT.UTF-8') -> plt.Axes:
    """
    Plots a stacked bar chart for each day of acquisition, using HAR_distributions,
    into a provided matplotlib axis.
    """

    # Collect data per day
    dates_sorted = sorted(
        har_metrics_dict.keys(),
        key=lambda d: datetime.strptime(d, "%d-%m-%Y")
    )

    walking_props, sitting_props, standing_props = [], [], []
    date_labels = []

    for date_str in dates_sorted:
        sessions = har_metrics_dict[date_str]

        session_key = list(sessions.keys())[0]
        session_data = sessions[session_key]

        distributions = session_data.get(HAR_DISTRIBUTIONS_KEY, None)
        if not distributions:
            print(f"[WARNING] No HAR_distributions for date {date_str}")
            continue

        walking_props.append(distributions.get(WALKING_NAME, 0) * 100)
        sitting_props.append(distributions.get(SITTING_NAME, 0) * 100)
        standing_props.append(distributions.get(STANDING_NAME, 0) * 100)

        weekday_str = get_weekday_name(date_str, locale)
        date_labels.append(weekday_str)

    if not date_labels:
        print("No valid data to plot")
        return ax

    positions = list(range(len(date_labels)))

    # Walking at the bottom
    ax.bar(positions,walking_props,color=activity_colors[WALKING_NAME],label=WALKING_NAME,width=BAR_WIDTH)

    # Standing in the middle
    bottom_standing = walking_props  # bottom is walking
    ax.bar(positions,standing_props,bottom=bottom_standing,color=activity_colors[STANDING_NAME],label=STANDING_NAME,width=BAR_WIDTH)

    # Sitting on top
    bottom_sitting = [w + st for w, st in zip(walking_props, standing_props)]
    ax.bar(positions,sitting_props,bottom=bottom_sitting,color=activity_colors[SITTING_NAME],label=SITTING_NAME,width=BAR_WIDTH)

    add_percentage_labels(ax, [walking_props, standing_props, sitting_props])

    ax.set_xticks(positions)
    ax.set_xticklabels(date_labels, fontsize=12)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax.grid(axis="y", linestyle="--", linewidth=0.7, color="lightgray")
    ax.set_axisbelow(True)

    ax.set_xlim(-0.5, len(positions) - 0.5)

    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.set_title("Distribuição de Atividades por Dia", fontsize=14)

    return ax


def plot_activity_timeline_per_day(oh_profile: dict, subject_id: str, output_folder_path: str, locale='pt_PT.UTF-8') -> None:
    """
    Plot activity timelines for each subject and acquisition day.

    Each subject/day gets a timeline chart showing walking, sitting, and standing activities.
    Activities are represented by horizontal bars; X-axis is clock time.

    The default threshold for prolonged sitting (2 hours) is based on the European Agency
    for Safety and Health at Work (EU-OSHA) report: "Prolonged static sitting at work –
    Health effects and good practice advice". The report states that overall, 2 hours is
    considered the maximum time for continuous sitting as health risks may occur, in particular,
    when this 2-hour limit is exceeded regularly.

    A secondary warning threshold is included (default 1 hour) to indicate that a sitting period
    is becoming prolonged and may already be worth interrupting with movement, even if it has not
    yet reached the 2-hour risk limit.

     Health risks associated with prolonged sitting include:
        - Low back pain
        - Neck and shoulder complaints
        - Type 2 diabetes and cardiovascular disease
        - Obesity

    :param oh_profile: Dictionary containing the HAR metrics loaded from JSON.
    :param subject_id: Identifier of the subject extracted from the JSON filename
    :param output_folder_path: Directory path to save plots.
                          Sitting periods exceeding this duration are highlighted as a
                          warning (e.g., orange), but are below the maximum recommended
                          limit.
    """

    activity_names = [WALKING_NAME, STANDING_NAME, SITTING_NAME]
    y_positions = [0, 0.2, 0.4]
    bar_height = 0.1

    for date_str, sessions in oh_profile.items():

        session_key = list(sessions.keys())[0]
        session_data = sessions[session_key]

        har_timeline = session_data.get(HAR_TIMELINE_KEY, {})
        if not har_timeline:
            continue

        # ---- create segments per activity ----
        activity_segments = {name: [] for name in activity_names}
        warning_sitting_intervals = []
        risk_sitting_intervals = []

        for block_id, activity in har_timeline.items():
            start_str, end_str = block_id.split("_")
            start = datetime.strptime(start_str, "%H:%M:%S.%f")
            end = datetime.strptime(end_str, "%H:%M:%S.%f")

            activity_name = ACTIVITY_MAP.get(activity, activity)

            if activity_name not in activity_segments:
                continue

            activity_segments[activity_name].append((start, end))

            # prolonged sitting
            if activity_name == SITTING_NAME:

                total_duration = (end - start).total_seconds()

                # warning (orange)
                if total_duration > WARNING_SITTING_S:
                    warning_start = start + timedelta(seconds=WARNING_SITTING_S)
                    warning_end = min(end, start + timedelta(seconds=MAX_CONTINUOUS_SITTING_S))
                    warning_sitting_intervals.append((warning_start, warning_end))

                # risk (red)
                if total_duration > MAX_CONTINUOUS_SITTING_S:
                    risk_start = start + timedelta(seconds=MAX_CONTINUOUS_SITTING_S)
                    risk_sitting_intervals.append((risk_start, end))

        #Plot
        fig, ax = plt.subplots(figsize=(14, 4))

        for y_pos, activity_name in zip(y_positions, activity_names):
            intervals = activity_segments[activity_name]
            intervals_mpl = [
                (mdates.date2num(s), mdates.date2num(e) - mdates.date2num(s))
                for s, e in intervals
            ]
            ax.broken_barh(intervals_mpl, (y_pos - bar_height / 2, bar_height),
                           facecolors=activity_colors[activity_name])

        # warning in orange
        warning_intervals_mpl = [
            (mdates.date2num(s), mdates.date2num(e) - mdates.date2num(s))
            for s, e in warning_sitting_intervals
        ]

        ax.broken_barh(
            warning_intervals_mpl,
            (y_positions[2] - bar_height / 2, bar_height),
            facecolors=SITTING_WARNING_COLOR
        )

        # prolonged sitting in red
        risk_intervals_mpl = [
            (mdates.date2num(s), mdates.date2num(e) - mdates.date2num(s))
            for s, e in risk_sitting_intervals
        ]

        ax.broken_barh(
            risk_intervals_mpl,
            (y_positions[2] - bar_height / 2, bar_height),
            facecolors=SITTING_RISK_COLOR
        )

        # horizontal lines
        x_min, x_max = ax.get_xlim()
        for y_pos in y_positions:
            y_low = y_pos - bar_height / 2
            y_high = y_low + bar_height
            ax.hlines(y=y_low, xmin=x_min, xmax=x_max, colors="gray",
                      linestyles="dotted", alpha=0.6)
            ax.hlines(y=y_high, xmin=x_min, xmax=x_max, colors="gray",
                      linestyles="dotted", alpha=0.6)

        # axis formatting
        ax.set_yticks(y_positions)
        ax.set_yticklabels(activity_names, fontsize=12)
        ax.tick_params(axis="y", length=0)

        ax.xaxis_date()
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax.tick_params(axis="x", labelrotation=0, labelsize=12)
        ax.tick_params(axis="x", length=0)
        ax.set_xlabel("Hora do dia", fontsize=12)

        warning_patch = Patch(
            facecolor=SITTING_WARNING_COLOR,
            label=f"Sentado > {WARNING_SITTING_S / 3600:.1f} h"
        )

        risk_patch = Patch(facecolor=SITTING_RISK_COLOR,
                           label=f"Sentado > {MAX_CONTINUOUS_SITTING_S / 3600:.1f} h")

        ax.legend(handles=[warning_patch, risk_patch],loc="center left",bbox_to_anchor=(1.02, 0.5),frameon=False,fontsize=11)

        for spine in ax.spines.values():
            spine.set_visible(False)

        date_formatted = get_weekday_name(date_str, locale)

        # title
        ax.set_title(f"{date_formatted}", fontsize=14)

        plt.tight_layout()

        # generate output folder
        output_path = create_dir(output_folder_path, os.path.join(subject_id, "human_activities"))

        filename = f"{subject_id}_{date_str}_activity_timeline.png"
        handle_plot(save_dir=output_path, filename=filename)


def plot_steps_and_distance_per_day(har_metrics_dict: dict, subject_id: str, output_folder_path: str, age:int, locale='pt_PT.UTF-8'):
    """
    Plot daily step counts per acquisition day and annotate walked distance in meters.

    The bar chart displays the total number of steps per day.
    The walked distance is shown as a text annotation (in meters) next to each bar,
    avoiding the use of a secondary axis.

    Although 10 000 steps per day are widely promoted as an optimal target for health,
    recent evidence suggests that the number of steps associated with reduced all-cause
    mortality depends on age.

    According to a large meta-analysis of 15 international cohorts
        (Paluch et al., 2022, The Lancet Public Health, doi: https://doi.org/10.1016/S2468-2667(21)00302-9),
    the risk of all-cause mortality decreases progressively with increasing daily step counts up to approximately
    8 000–10 000 steps per day in adults younger than 60 years, and up to
    6 000–8 000 steps per day in adults aged 60 years and older.

    :param har_metrics_dict: Dictionary containing the HAR metrics loaded from JSON.
    :param subject_id: Identifier of the subject extracted from the JSON filename.
    :param output_folder_path: Directory path to save plots.
    :param age: Age of the subject (in years), used to determine the recommended
            daily number of steps based on age-dependent evidence.
    """

    # Collect data
    dates = []
    steps = []
    distances = []
    date_objs = []

    # Iterate through each day and session to sum steps and distance
    for date_str, sessions in har_metrics_dict.items():

        total_steps = 0
        total_distance = 0.0

        for session_key, session_data in sessions.items():
            har_steps = session_data.get(HAR_STEPS_KEY)
            if not har_steps:
                continue
            # Sum steps and distance for the day
            total_steps += har_steps.get(HAR_NUM_STEPS_KEY, 0)
            total_distance += har_steps.get(HAR_DISTANCE_KEY, 0.0)

        weekday = get_weekday_name(date_str, locale)
        date_obj = datetime.strptime(date_str, "%d-%m-%Y")


        # Only include days with steps > 0
        if total_steps > 0:
            dates.append(weekday)
            steps.append(total_steps)
            distances.append(total_distance)
            date_objs.append(date_obj)

    if not steps:
        print("[WARNING] No HAR_steps data found. Plot will not be generated.")
        return

    # Determine recommended steps based on age
    if age < 60:
        recommended_steps = 9000  # in the middle of 8k-10k
    else:
        recommended_steps = 7000  # in the middle of 6k-8k

    # Plot
    fig = plt.figure(figsize=(12, 5), constrained_layout=True)
    gs = fig.add_gridspec(1, 2, width_ratios=[4, 1], wspace=0.05)
    ax = fig.add_subplot(gs[0, 0])
    ax_dist = fig.add_subplot(gs[0, 1])

    # Gray bar = recommended steps (capped at recommended_steps)
    ax.barh(dates, [recommended_steps] * len(dates),
            color=GRAY, edgecolor="none", label=f"Passos diários recomendados para uma pessoa de {age} anos: {recommended_steps}")

    # Blue bar = real steps (cortada ao recommended_steps)
    steps_capped = [min(s, recommended_steps) for s in steps]
    bars_blue = ax.barh(dates, steps_capped,
            color=BLUE_STATE, edgecolor="none", label="Passos diários no local de trabalho")

    # Add step count label at the end of each blue bar
    for bar, real_steps in zip(bars_blue, steps):
        ax.text(
            bar.get_width() - 200,  # position near end of blue bar
            bar.get_y() + bar.get_height() / 2,
            f"{real_steps}",
            va="center",
            ha="right",
            fontsize=14,
            color="white",
            fontweight="bold"
        )

    # Vertical line showing recommended steps
    ax.axvline(
        recommended_steps,
        linestyle="--",
        linewidth=1,
        color="gray"
    )

    # Label for recommended steps value
    ax.text(
        recommended_steps,
        -0.6,  # position above the first bar
        f"{recommended_steps}",
        ha="center",
        va="bottom",
        fontsize=10,
        color="black"
    )

    # Reverse y-axis so first day appears on top
    ax.invert_yaxis()

    # Formatting main axis
    ax.set_xlabel("Número de passos", fontsize=12)
    #ax.set_ylabel("Dia", fontsize=12)
    # ax.set_title(f"Passos e distância percorrida", fontsize=14, pad=35)
    ax.tick_params(axis="x", labelsize=11)
    ax.tick_params(axis="y", labelsize=11)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.12), ncol=2, fontsize=12)

    # Distance column (right)
    ax_dist.set_xlim(0, 1)
    # Match y-limits to main axis so days align correctly
    ax_dist.set_ylim(ax.get_ylim())

    ax_dist.set_xticks([])
    ax_dist.set_yticks(range(len(dates)))
    ax_dist.set_yticklabels([])

    # Add distance labels (in km) aligned with each day
    for i, distance in enumerate(distances):
        ax_dist.text(0.5, i, f"{distance / 1000:.1f} km", va="center", ha="center", fontsize=13, color="black")

    ax_dist.set_title("Distância percorrida\nno local de trabalho", fontsize=13)

    for spine in ax_dist.spines.values():
        spine.set_visible(False)

    # generate output folder
    output_path = create_dir(output_folder_path, os.path.join(subject_id, "human_activities"))

    # Save / Show plot
    filename = f"{subject_id}_daily_steps_distance.png"
    handle_plot(save_dir=output_path, filename=filename)