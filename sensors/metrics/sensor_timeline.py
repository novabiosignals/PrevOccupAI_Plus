"""
Function to get sensor timeline metrics

Available Functions
-------------------
[Public]
get_sensor_timeline_metrics(...): Gets the metrics needed for the sensor timeline plot for one day.
-------------------

[Private]
-------------------
"""
# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import os
from typing import Dict

# internal imports
import sensors.visualize as sv
import sensors.impute as si
from OH_profile.constants import SENSOR_TIMELINE_MISSING_TIMES_KEY, SENSOR_TIMELINE_TIMES_KEY
from utils import extract_date_from_path

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #

def get_sensor_timeline_metrics(day_folder_path: str, fs: int) -> Dict:
    """
    Gets the metrics needed for the sensor timeline plot for one day.

    From the available data, this function generates a dictionary with the following format:
    e.g.
    Example:
    {'25-09-2025': {
            'metadata': {
                'phone': {
                    'start_times': ['09-30-00'], 'end_times': ['17-30-00']},
                'watch': {
                    'start_times': ['09-30-00', '10-00-00', '11-00-00', '12-00-00'], 'end_times':   ['09-50-00', '10-20-00', '11-20-00', '12-20-00']},
                'mban_right': {
                    'start_times': ['09-30-00', '10-00-00', '11-00-00', '12-00-00'], 'end_times':   ['09-50-00', '10-20-00', '11-20-00', '12-20-00']},
                'mban_left': {
                    'start_times': ['09-30-00', '10-00-00', '11-00-00'], 'end_times':   ['09-50-00', '10-20-00', '11-20-00']},
            'missing_data': {
                'mban_left': {
                    'start_times': ['12-00-00'],'end_times':   ['12-20-00']}
            }
        }
    }

    :param day_folder_path: Path to the folder containing the data from one day
    :param fs: the sampling frequency
    :return: A dictionary with the metrics
    """

    acquisition_date = extract_date_from_path(day_folder_path)

    # init dictionary for holding the metrics for one day
    day_metrics_dict = {acquisition_date: {}}

    # get daily metadata needed for the plot
    daily_meta_data_dict = sv.get_daily_acquisitions_metadata(day_folder_path, fs=fs)

    # get daily missing data
    daily_missing_data_dict = si.get_missing_data(os.path.dirname(day_folder_path), daily_meta_data_dict)

    # add to dict
    day_metrics_dict[acquisition_date][SENSOR_TIMELINE_TIMES_KEY] = daily_meta_data_dict
    day_metrics_dict[acquisition_date][SENSOR_TIMELINE_MISSING_TIMES_KEY] = daily_missing_data_dict

    return day_metrics_dict
