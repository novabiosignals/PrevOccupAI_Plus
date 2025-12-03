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
from datetime import datetime
from typing import Tuple
from matplotlib.legend_handler import HandlerBase
from matplotlib.lines import Line2D

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