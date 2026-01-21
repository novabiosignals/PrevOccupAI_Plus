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
from babel.dates import format_datetime
from matplotlib.patches import Patch


# internal imports
from .plot_utils import handle_plot
from constants import WALKING, STANDING, SITTING

# ------------------------------------------------------------------------------------------------------------------- #
# file specific constants
# ------------------------------------------------------------------------------------------------------------------- #
WALKING_NAME = 'walking'
SITTING_NAME = 'sitting'
STANDING_NAME = 'standing_name'
TOTAL_DURATION = 'total_duration'
ACTIVITY_MAP = {WALKING: WALKING_NAME, SITTING: SITTING_NAME, STANDING: STANDING_NAME}
SESSION_DT = 'session_dt'

activity_colors = {
    WALKING_NAME: '#8FBCE6',   #blue
    SITTING_NAME: '#81C784',   #green
    STANDING_NAME: '#C8A165'   #castanho
}

SITTING_WARNING_COLOR = "#FFA726"  #orange
SITTING_RISK_COLOR = '#EF9A9A' #red

MAX_CONTINUOUS_SITTING_S =2*60*60 # 2 hours (EU-OSHA)
WARNING_SITTING_S = 1*60*60 # 1 hour
# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #


def plot_activity_proportions_per_day(all_metrics: dict, subject_id: str, show: bool, save: bool, save_dir: str) -> None:
    """
    Plots a stacked bar chart for each day of acquisition, using HAR_distributions.

    :param all_metrics: Dictionary containing the metrics loaded from JSON.
    :param subject_id: Identifier of the subject extracted from the JSON filename
    :param show: Whether to display the plot.
    :param save: Whether to save the plot to disk.
    :param save_dir: Directory path to save plots.
    """

    print(f"[INFO] Generating activity proportions plots for {subject_id}")

    human_activities = all_metrics["sensor_metrics"]["human_activities"]

    # Collect data per day
    dates_sorted = sorted(
        human_activities.keys(),
        key=lambda d: datetime.strptime(d, "%d-%m-%Y")
    )

    walking_props, sitting_props, standing_props = [], [], []
    date_labels = []

    for date_str in dates_sorted:
        sessions = human_activities[date_str]

        # Since there is only one session per day, take the first one
        session_key = list(sessions.keys())[0]
        session_data = sessions[session_key]

        distributions = session_data.get("HAR_distributions", None)
        if not distributions:
            print(f"[WARNING] No HAR_distributions for date {date_str}")
            continue

        # Convert to percentage
        walking_props.append(distributions.get("Andar", 0) * 100)
        sitting_props.append(distributions.get("Sentado", 0) * 100)
        standing_props.append(distributions.get("De pé", 0) * 100)

        # Format date for x-axis
        try:
            weekday_str = format_datetime(datetime.strptime(date_str, "%d-%m-%Y"), "EEEE", locale="pt_PT")
        except Exception:
            weekday_str = date_str
        date_labels.append(weekday_str)

    if not date_labels:
        print("[INFO] No valid data to plot")
        return

    # Define week range for suptitle
    first_date = datetime.strptime(dates_sorted[0], "%d-%m-%Y")
    last_date = datetime.strptime(dates_sorted[-1], "%d-%m-%Y")
    first_weekday = format_datetime(first_date, "EEEE", locale="pt_PT")
    last_weekday = format_datetime(last_date, "EEEE", locale="pt_PT")
    main_title_range = f"{first_weekday} ({first_date.strftime('%d/%m/%y')}) - {last_weekday} ({last_date.strftime('%d/%m/%y')})"

    # Plotting
    fig, ax = plt.subplots(figsize=(12, 6))
    positions = list(range(len(date_labels)))

    ax.bar(positions, walking_props, color=activity_colors[WALKING_NAME], label=WALKING_NAME)
    ax.bar(positions, sitting_props, bottom=walking_props, color=activity_colors[SITTING_NAME], label=SITTING_NAME)

    bottom = [w + s for w, s in zip(walking_props, sitting_props)]
    ax.bar(positions, standing_props, bottom=bottom, color=activity_colors[STANDING_NAME], label=STANDING_NAME)

    for i, (w, s, st) in enumerate(zip(walking_props, sitting_props, standing_props)):
        # integer values for display
        w_int = round(w)
        s_int = round(s)

        # ensure total 100 by fixing the last category
        st_int = 100 - (w_int + s_int)

        # if rounding makes it negative, adjust
        if st_int < 0:
            st_int = 0
            s_int = 100 - w_int

        # label positions
        if w >= 4:
            ax.text(i, w / 2, f"{w_int}%", ha='center', va='center', color='black', fontsize=10)
        else:
            ax.text(i, w + 1, f"{w_int}%", ha='center', va='bottom', color='black', fontsize=10)

        if s >= 4:
            ax.text(i, w + s / 2, f"{s_int}%", ha='center', va='center', color='black', fontsize=10)
        else:
            ax.text(i, w + s + 1, f"{s_int}%", ha='center', va='bottom', color='black', fontsize=10)

        if st >= 4:
            ax.text(i, w + s + st / 2, f"{st_int}%", ha='center', va='center', color='black', fontsize=10)
        else:
            ax.text(i, w + s + st + 1, f"{st_int}%", ha='center', va='bottom', color='black', fontsize=10)


    ax.set_xticks(positions)
    ax.set_xticklabels(date_labels, rotation=0, ha='center', fontsize=12)
    ax.set_ylabel("Percentagem de Tempo (%)", fontsize=12)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.0f}%"))

    ax.grid(axis="y", color="lightgray", linestyle="--", linewidth=0.7)
    ax.set_axisbelow(True)

    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.set_title(
        f"Sujeito: {subject_id} | Distribuição de Atividades por Dia \n{main_title_range}",
        fontsize=14, pad=20
    )
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=3, frameon=False, fontsize=12)

    plt.tight_layout()

    filename = f"{subject_id}_activity_distribution_per_day.png"
    handle_plot(save_dir=save_dir, save=save, filename=filename)


def plot_activity_timeline_per_day(all_metrics: dict,
                                  subject_id: str,
                                  show: bool,
                                  save: bool,
                                  save_dir: str,
                                  warning_sitting_s: float = 60*60,
                                  max_continuous_sitting_s: float = 2 * 60 * 60):
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

    :param all_metrics: Dictionary containing the metrics loaded from JSON.
    :param subject_id: Identifier of the subject extracted from the JSON filename
    :param show: Whether to display the plot.
    :param save: Whether to save the plot to disk.
    :param save_dir: Directory path to save plots.
    :param max_continuous_sitting_s: Maximum allowed duration (in seconds) for continuous sitting. Default is 2 hours (EU-OSHA).
    :param warning_sitting_s: Warning threshold (in seconds) for continuous sitting.
                          Sitting periods exceeding this duration are highlighted as a
                          warning (e.g., orange), but are below the maximum recommended
                          limit.
    """

    print(f"[INFO] Generating activity timeline plots {subject_id}")

    human_activities = all_metrics["sensor_metrics"]["human_activities"]
    activity_names = [WALKING_NAME, SITTING_NAME, STANDING_NAME]
    y_positions = [0, 0.2, 0.4]
    bar_height = 0.1

    for date_str, sessions in human_activities.items():

        session_key = list(sessions.keys())[0]
        session_data = sessions[session_key]

        har_timeline = session_data.get("HAR_timeline", {})
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
                if total_duration > warning_sitting_s:
                    warning_start = start + timedelta(seconds=warning_sitting_s)
                    warning_end = min(end, start + timedelta(seconds=max_continuous_sitting_s))
                    warning_sitting_intervals.append((warning_start, warning_end))

                # risk (red)
                if total_duration > max_continuous_sitting_s:
                    risk_start = start + timedelta(seconds=max_continuous_sitting_s)
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
            (y_positions[1] - bar_height / 2, bar_height),
            facecolors=SITTING_WARNING_COLOR
        )

        # prolonged sitting in red
        risk_intervals_mpl = [
            (mdates.date2num(s), mdates.date2num(e) - mdates.date2num(s))
            for s, e in risk_sitting_intervals
        ]

        ax.broken_barh(
            risk_intervals_mpl,
            (y_positions[1] - bar_height / 2, bar_height),
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
            label=f"Sentado > {warning_sitting_s / 3600:.1f} h"
        )

        risk_patch = Patch(
            facecolor=SITTING_RISK_COLOR,
            label=f"Excedido o tempo sentado \nrecomendado (> {max_continuous_sitting_s / 3600:.1f} h)"
        )

        ax.legend(
            handles=[warning_patch, risk_patch],
            loc="center left",
            bbox_to_anchor=(1.02, 0.5),
            frameon=False,
            fontsize=11
        )

        for spine in ax.spines.values():
            spine.set_visible(False)

        try:
            date_obj = datetime.strptime(date_str, "%d-%m-%Y")
            date_formatted = format_datetime(
                date_obj,
                "dd/MM/yyyy (EEEE)",
                locale="pt_PT"
            )
        except Exception:
            date_formatted = date_str

        # title
        ax.set_title(f"Sujeito: {subject_id} | {date_formatted}", fontsize=14)

        plt.tight_layout()
        filename = f"{subject_id}_{date_str}_activity_timeline.png"
        handle_plot(save_dir=save_dir, save=save, filename=filename)