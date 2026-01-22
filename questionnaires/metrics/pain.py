"""
Function to extract metrics from the pain data

Available Functions
-------------------
[Public]
get_pain_metrics_per_day(...): Computes pain intensity metrics per body part, separated by day and by period
-------------------

[Private]

None
"""
# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import json
from typing import Dict

# internal imports
from questionnaires.constants import BODY_PART_MAPPING, PAIN_COLORS
from questionnaires.load.pain_lines_loader import load_pain_lines

# ------------------------------------------------------------------------------------------------------------------- #
# constants
# ------------------------------------------------------------------------------------------------------------------- #
SHIFT_START = 'shift_start'
SHIFT_END = 'shift_end'

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #

def get_pain_metrics_per_day(folder_path: str, subject_id: str) -> Dict:
    """
    Computes pain intensity metrics per body part, separated by day and by period
    (morning and afternoon).

    For each day, pain points are processed independently for:
      - "start_shift"
      - "end_shift"

    Each pain point is:
      1. Parsed from JSON.
      2. Assigned to a body part using coordinate bounds.
      3. Converted from color to numeric pain intensity.
      4. Accumulated per body part.

    If no pain is reported for a given period, the value for that period
    will be the string "no pain".

    :param folder_path: path to the folder containing the pain files
    :param subject_id: subject identifier
    :return: Nested dictionary as follows:
                {
                    "2025_10_07": {
                                    "shift_start": "no pain",
                                    "shif_end": {
                                                    "Head (front)": 4,
                                                    "Right Shin (front)": 6
                                    }
                    }
    },
    """

    lines_list = load_pain_lines(folder_path, subject_id)
    metrics_per_day = {}

    for date, morning_lines, afternoon_lines in lines_list:
        daily_metrics = {}
        shift_mapping = {"shift_start": morning_lines, "shift_end": afternoon_lines}

        for shift_name, shift_lines in shift_mapping.items():

            # If no lines or "No pain reported" in first line
            if not shift_lines or "No pain reported" in shift_lines[0]:
                daily_metrics[shift_name] = "no pain"
                continue

            # Each line is a JSON array of points
            points = []
            for line in shift_lines:
                line = line.strip()
                if not line or "No pain reported" in line:
                    continue
                try:
                    parsed_points = json.loads(line)  # returns list of dicts
                    points.extend(parsed_points)
                except json.JSONDecodeError:
                    continue  # skip malformed lines

            if not points:
                daily_metrics[shift_name] = "no pain"
                continue

            # Initialize body-part metrics
            shift_metrics = {bp: 0 for bp in BODY_PART_MAPPING.keys()}

            # cycle over the points
            for point in points:

                # get the coordinates
                x, y = int(round(point["x"])), int(round(point["y"]))

                # get the color of the point
                color = point["color"]

                # get the pain intensity based on the color
                pain_intensity = next((i for i, c in PAIN_COLORS.items() if c == color), 0)

                # cycle over the body mapping
                for bodypart, ((x_min, y_min), (x_max, y_max)) in BODY_PART_MAPPING.items():

                    # check in which body part the point falls into
                    if x_min <= x <= x_max and y_min <= y <= y_max:

                        # when drawing a line, multiple points are in the same area. Just take the first point that appears
                        # in the area of the body
                        if shift_metrics[bodypart] == 0:  # only take the first point

                            # add to the metrics of that shift start/end
                            shift_metrics[bodypart] = int(pain_intensity)
                        break  # stop at first matching body part

            # Remove zero-intensity body parts
            shift_metrics = {bp: val for bp, val in shift_metrics.items() if val > 0}
            daily_metrics[shift_name] = shift_metrics if shift_metrics else "no pain"

        metrics_per_day[date] = daily_metrics

    return metrics_per_day