"""
Utils for the visualizations functions

Available Functions
-------------------
[Class]
HandlerRefLine(HandlerBase): overrides method in HandleBase for drawing horizontal lines with vertical ticks

-------------------
[Public]
get_day_string(...): Gets the day as a string (i.e. Mon, Tue, Wednesday, etc.) from a date string in the language of the defined locale

-------------------
[Private]

-------------------
"""
# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import locale
from datetime import datetime, timedelta
from typing import Tuple
from matplotlib.legend_handler import HandlerBase
from matplotlib.lines import Line2D
from typing import List
from collections import defaultdict


# ------------------------------------------------------------------------------------------------------------------- #
# constants
# ------------------------------------------------------------------------------------------------------------------- #

ROMAN_NUMBERS = ["I", "II", "III", "IV"]

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
                idx = t.split("_")[1]
                labels.append(f"Sem dados")
            else:
                # start time in format H
                # H:MM - string
                start_str = t[:5]
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