"""
Functions to calculate wrist significant movements.

Available Functions
-------------------
[Public]
get_wrist_activity_metrics(...): Extracts the wrist movement metrics for an entire day of acquisitions
-------------------

[Private]
_calculate_significant_movements(...): Calculates the percentage of significant wrist movements (acceleration and rotation) for one acquisition.
_calculate_significant_wrist_acceleration(...): Calculates significant accelerations of the wrist.
_calculate_significant_wrist_rotation(...): Calculates significant rotations of the wrist.
"""

# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import os
from typing import Dict
import pandas as pd
from scipy.signal import detrend
import numpy as np

# internal imports
import HAR
import sensors.load as sl
import sensors.process as sp
from constants import ACTIVITY_COLUMN_NAME, WATCH_SUFFIX, ACC, GYR, MAG, PHONE, WATCH
from OH_profile.constants import *
from .metric_utils import split_df_by_non_nan_blocks
from utils import extract_date_from_path
# ------------------------------------------------------------------------------------------------------------------- #
# constants
# ------------------------------------------------------------------------------------------------------------------- #

# sensors to be loaded which are strictly needed for the HR plot
selected_sensors = {PHONE: [ACC, GYR, MAG], # for HAR
                    WATCH: [ACC,GYR]}

WINDOW_SECONDS = 2  # window size in seconds for moving average

# Thresholds (mean + 2*std)
ACC_MEAN = 0.43
ACC_STD = 0.24
ACC_THRESHOLD = ACC_MEAN + 2 * ACC_STD

WINDOW_DIFF_SECONDS = 0.5          # window size for angle-difference evaluation
SIGNIFICANT_THRESHOLD = 30         # degrees for event detection
# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #
def get_wrist_activity_metrics(day_folder_path: str, fs: int, w_size: float) -> Dict:
    """
    Extracts the wrist movement metrics for an entire day of acquisitions and returns a dictionary with per session
    metrics. If phone data is missing and no activity label is present in more than 50 % of the acquisition, the acquisition
    is discarded.

    :param day_folder_path: Path to the folder containing the all the acquisitions from an entire day
    :param fs: The sampling frequency with which the data was acquired and for resampling
    :param w_size: The window size used for the human activity recognition model
    :return: A dictionary with the daily and per session metrics for this subject as follows:
    {"23-09-2025": {
                    "15-00-00": {
                            "significant_acceleration_percentage": ...,
                            "significant_rotation_percentage": ...,
                    }
    }
    """

    # init dict
    day_metrics_dict = {}

    # load_signals all acquisitions from the same day into a nested dictionary
    df_dict = sl.load_daily_acquisitions(day_folder_path, load_devices=selected_sensors)

    # pre-process data
    processed_df_dict = sp.apply_pre_processing_pipeline(df_dict, fs_android=fs)

    # classify and synchronise predictions
    sync_df = HAR.classify_and_synchronise_predictions(processed_df_dict, w_size=w_size, fs=fs)

    # keep only the needed columns - HR and activity
    sync_df = sync_df[[ACTIVITY_COLUMN_NAME, f"x_{ACC}{WATCH_SUFFIX}", f"x_{GYR}{WATCH_SUFFIX}"]]

    # split into dataframes with just the watch data
    acquisitions_dfs = split_df_by_non_nan_blocks(sync_df, column_name=f"x_{ACC}{WATCH_SUFFIX}")

    # get date from path
    date = extract_date_from_path(day_folder_path)

    # reformat to dd-mm-yyyy
    year, month, day = date.split('-')
    date = f"{day}-{month}-{year}"

    # init the dict
    day_metrics_dict[date] = {}

    # extract metrics from the different sessions
    for acquisitions_df in acquisitions_dfs:

        # check if the activity column is nan in more than half of the acquisition - phone stopped acquiring before watch
        if acquisitions_df[ACTIVITY_COLUMN_NAME].isna().mean() > 0.5:
            print(f"No activity labels for this acquisition. Skipping...")
            continue

        # calculate significant movements
        metrics_dict = _calculate_significant_movements(acquisitions_df, fs=fs)

        # add metrics for the session to the daily dictionary
        day_metrics_dict[date].update(metrics_dict)

    return day_metrics_dict

# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #

def _calculate_significant_movements(df: pd.DataFrame, fs: int) -> Dict[str, Dict[str, float]]:
    """
    Calculates the percentage of significant wrist movements (acceleration and rotation) for one acquisition. These
    metrics are calculated only for when the subject is sitting.

    :param df: pandas.DataFrame containing the x ACC, x GYR, and activity data for one session
    :param fs: the sampling frequency of the signal
    :return: a dictionary with the percentage of significant wrist movements, for example:
    {
                    "15-00-00": {
                            "significant_acceleration_percentage": ...,
                            "significant_rotation_percentage": ...,
                    }
    """

    # Get acquisition start and end time
    start_time = df.index[0]

    # Strip milliseconds
    start_time_str = str(start_time).split(".")[0]

    # generate a key to identify which acquisition is being handled
    key = f"{start_time_str.replace(":", "-")}"

    # init dict to store the metrics
    metrics_dict = {key: {}}

    # calculate significant movements - rotation and acceleration
    sign_mov_rotation_perc = _calculate_significant_wrist_rotation(df, fs=fs)
    sign_mov_acc_perc = _calculate_significant_wrist_acceleration(df, fs=fs)

    # add metrics to the dict
    metrics_dict[key].update({WRIST_SIGNIFICANT_ROT_PERC_KEY: sign_mov_rotation_perc})
    metrics_dict[key].update({WRIST_SIGNIFICANT_ACC_PERC_KEY: sign_mov_acc_perc})

    return metrics_dict


def _calculate_significant_wrist_acceleration(df: pd.DataFrame, fs: int) -> float:
    """
    Calculates significant accelerations of the wrist. Significant accelerations are only calculated when the subject is sitting.
     This function does the following:

    (1) Smooth the x-axis of the watch's acc signal by computing a moving mean.
    (2) Keep only the instances where the subject is sitting.
    (3) For each instance, check if the acceleration is > ACC_THRESHOLD, if so, it is a significant acceleration.
    (4) Calculate the % of significant rotations

    The threshold was defined based on Cheryl Fairfield Estill's study.
    DOI: 10.1080/001401300421842

    :param df: pandas DataFrame containing an accelerometer column.
    :param fs: sampling frequency of the sensor in Hertz.
    :return: percentage of significant acceleration events (float between 0 and 1).
    """

    # Compute moving-window size (in samples)
    window_size = int(WINDOW_SECONDS * fs)

    # (1) Apply a centered rolling mean to smooth the signal
    df["x_ACC_wear_mov_avg"] = df[f"x_{ACC}{WATCH_SUFFIX}"].rolling(window_size, center=True).mean()

    # (2) only samples with ACTIVITY == 0 (sitting) and valid moving mean
    valid_mask = (df[ACTIVITY_COLUMN_NAME] == 0) & (df["x_ACC_wear_mov_avg"].notna())

    # (3) Count significant movements
    significant_movements = ((df.loc[valid_mask, "x_ACC_wear_mov_avg"] > ACC_THRESHOLD).sum())

    # Total number of valid samples
    total = valid_mask.sum()

    # (4) Percentage of significant events
    significant_percentage = round(((significant_movements / total) * 100 if total > 0 else 0), 4)

    return significant_percentage


def _calculate_significant_wrist_rotation(df: pd.DataFrame, fs: int) -> float:
    """
    Calculates significant rotations of the wrist. Significant rotations are only calculated when the subject is sitting.
     This function does the following:

    (1) Compute he angles by integrating the x-axis of the watch's gyroscope.
    (2) Smooth the angles by computing the moving mean.
    (3) Detrend the smoothed angle signal
    (4) Segment the clean angle signal into windows of WINDOW_SECONDS seconds. Keep only the windows where all instances are sitting instances
    (5) For each window, calculate the angle difference between consecutive instances and sum to obtain the total rotation for the window.
    (6) Count the number of significant rotations - when the total rotation of the window is > SIGNIFICANT_THRESHOLD degrees.
    (7) Calculate the % of significant rotations

    :param df: pandas DataFrame containing at least one gyroscope column
               representing angular velocity (e.g., 'x_GYR').
    :param fs: sampling frequency of the sensor in Hertz.
    :return: percentage of windows that represent significant rotation events.
    """

    # (1) Integration step: convert angular velocity to angle in degrees
    dt = 1.0 / fs
    angle = np.cumsum(df[f"x_{GYR}{WATCH_SUFFIX}"].values) * dt
    angle = np.rad2deg(angle)
    df["angle"] = angle

    # (2) Moving average (smoothing)
    window_size = int(WINDOW_SECONDS * fs)
    df["ANGLE_MAVG"] = df["angle"].rolling(window_size, center=True).mean()

    # (3) Apply detrending to the smoothed angle signal
    clean_angle = detrend(df["ANGLE_MAVG"].fillna(method="bfill").fillna(method="ffill"))
    df["ANGLE_DETRENDED"] = clean_angle

    # Assign window IDs
    diff_window = int(WINDOW_DIFF_SECONDS * fs)
    df["WINDOW_ID"] = np.arange(len(df)) // diff_window

    # (4) Keep only windows where all samples are seated
    valid_mask = df.groupby("WINDOW_ID")[ACTIVITY_COLUMN_NAME].transform("max") == 0
    df_valid = df[valid_mask].copy()

    # (5) Compute absolute consecutive differences within each window
    df_valid["ABS_DIFF"] = df_valid.groupby("WINDOW_ID")["ANGLE_DETRENDED"].diff().abs()

    # Sum angle differences per window
    total_rotations = df_valid.groupby("WINDOW_ID")["ABS_DIFF"].sum()

    # (6) Count significant events
    significant_events = (total_rotations > SIGNIFICANT_THRESHOLD).sum()

    # (7) Percentage of significant events
    significant_percent = round((significant_events / len(total_rotations) * 100) if len(total_rotations) > 0 else 0, 4)

    return significant_percent