"""
Functions to obtain human activity related metrics

Available Functions
-------------------
[Public]

-------------------

[Private]
-------------------
"""
# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import numpy as np
import pandas as pd
from scipy.fft import fft, fftfreq
from scipy.signal import detrend
from typing import Dict

# internal imports
from HAR import classify_human_activities, create_time_column_from_initial_time, CLASS_WALK, CLASS_STAND, CLASS_SIT
from HAR.classifier import BLOCK_ID_COLUMN_NAME
from OH_profile.constants import HAR_TIMELINE_KEY, HAR_DURATIONS_KEY, HAR_DISTRIBUTIONS_KEY
from constants import ACTIVITY_COLUMN_NAME, PHONE, ACC, GYR, MAG, ROT
from sensors.metrics.metric_utils import calculate_class_distributions, calculate_class_durations
from utils import extract_date_from_path
import sensors.load as sensor_loader
import sensors.process as sensor_processor


# ------------------------------------------------------------------------------------------------------------------- #
# file constants
# ------------------------------------------------------------------------------------------------------------------- #
Y_ACC_COL = 'y_ACC'

ACTIVITY_CLASS_STRING_COLUMN = 'activity_class_name'
ACTIVITY_CLASS_MAP = {CLASS_WALK: 'Andar', CLASS_STAND: 'De pé', CLASS_SIT: 'Sentado'}
# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #
def get_human_activity_metrics(day_folder_path: str, fs: int, w_size: float) -> Dict:
    """

    :param day_folder_path: Path to the folder containing the all the acquisitions from an entire day.
    :param fs: The sampling frequency with which the data was acquired.
    :param w_size: The window size for HAR classification in seconds.
    :return:
    """

    # get date from path
    day_date = extract_date_from_path(day_folder_path)

    # reformate to dd-mm-yyyy
    year, month, day = day_date.split('-')
    day_date = f"{day}-{month}-{year}"

    # init dict for holding the extracted metrics
    day_metrics_dict = {day_date: {}}

    # load the acquisition(s) for the day
    df_dict = sensor_loader.load_daily_acquisitions(day_folder_path, load_devices={PHONE: [ACC, GYR, MAG, ROT]})

    # pre-proces the data
    processed_df_dict = sensor_processor.apply_pre_processing_pipeline(df_dict)

    # classify the data
    processed_df_dict[PHONE] = classify_human_activities(processed_df_dict[PHONE], w_size=w_size, fs=fs)

    # cycle over the dictionary containing the phone data (usually there is only one acquisition, but multiple can happen)
    for acquisition_time, df in processed_df_dict[PHONE].items():

        # check whether the DataFrame contains data
        if not df.empty:

            # extract human activities
            print("obtaining human activities and their proportions throughout the day.")
            metrics_dict = _calculate_human_activity_metrics(df, fs=fs, start_time=acquisition_time)

        else:

            # set metrics_dict to empty if no data
            metrics_dict = {}

        # add the extracted metrics to the day_metrics dictionary
        day_metrics_dict[day_date][acquisition_time] = metrics_dict

    return day_metrics_dict


# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #
def _calculate_human_activity_metrics(df: pd.DataFrame, fs: int, start_time: str) -> Dict:
    """

    :param df: pandas.DataFrame containing the phone data and the corresponding HAR classification
    :param fs: the sampling frequency
    :param start_time: the time at which the acquisition started as a string (format: hh-mm-ss)
    :return:
    """

    # init dict to store human activity metrics
    metrics_dict = {}

    # add column containing the activities as strings
    df[ACTIVITY_CLASS_STRING_COLUMN] = df[ACTIVITY_COLUMN_NAME].map(ACTIVITY_CLASS_MAP)

    # obtain human activity timeline metrics
    timeline_metrics = _get_human_activity_timeline(df[[ACTIVITY_CLASS_STRING_COLUMN, BLOCK_ID_COLUMN_NAME]], fs, start_time)

    # obtain activity distribution
    activity_distribution_metrics = calculate_class_distributions(df, column_name=ACTIVITY_CLASS_STRING_COLUMN)

    # obtain activity durations
    activity_duration_metrics = calculate_class_durations(df, fs=fs, class_distributions=activity_distribution_metrics)

    # obtain step detection metrics

    # obtain sitting metrics (posture metrics)

    # add extracted metrics to the dict
    metrics_dict.update({HAR_TIMELINE_KEY: timeline_metrics})
    metrics_dict.update({HAR_DISTRIBUTIONS_KEY: activity_distribution_metrics})
    metrics_dict.update({HAR_DURATIONS_KEY: activity_duration_metrics})

    return metrics_dict


def _get_human_activity_timeline(df: pd.DataFrame, fs: int, start_time: str) -> Dict[str, str]:
    """

    :param df:
    :param start_time:
    :param fs:
    :return:
    """

    # init dict to store metrics
    timeline_metrics: Dict[str, str] = {}

    # generate real time column from the acquisition start time
    time_col = create_time_column_from_initial_time(initial_time=start_time, signal_size=df.shape[0], fs=fs)

    # add time column to df
    df['timestamps'] = time_col.values

    # set timestamps as index
    df = df.set_index('timestamps')

    # cycle over continuous blocks of an activity
    for block_id, block_df in df.groupby(BLOCK_ID_COLUMN_NAME):

        # obtain start and end time
        t_start = block_df.index[0]
        t_end = block_df.index[-1]

        # obtain class from the block (since each block just contains one activity using .iloc[0] is valid)
        activity_class = block_df[ACTIVITY_CLASS_STRING_COLUMN].iloc[0]

        # generate key for the dictionary
        dict_key = f"{t_start}_{t_end}"

        # add the extracted metric to the dictionary
        timeline_metrics[dict_key] = activity_class

    return timeline_metrics


def _calculate_dominant_walking_frequency(data: pd.DataFrame, fs: int = 100) -> int:
    """
    Estimates the dominant frequency of a filtered acceleration signal using FFT,
    restricted to periods when the person is walking (activity == 2).

    Uses the Fourier transform on the 'y_ACC' column to find the frequency
    with the highest magnitude during walking segments only. Also calculates a
    minimum interval between peaks based on this dominant frequency.

    :return:
        - dominant_freq: Estimated dominant frequency in Hz.
        - minimum_interval: Minimum interval between peaks in samples (int).
    """

    # obtain only data segments where the subject's activity was classified as walking
    walking_data = data[data[ACTIVITY_COLUMN_NAME] == CLASS_WALK]

    # TODO: check with Mariana. This gives 50 Hz not 2 Hz
    if len(walking_data) < fs * 2:
        print("Not enough walking data to compute frequency.")
        return int(fs * 0.5)  # Default fallback (0.5s = ~2Hz)

    # Detrend the walking signal to remove drift
    acc_y = detrend(walking_data[Y_ACC_COL].values)

    # obtain number of samples and sampling interval (T)
    num_samples = len(acc_y)
    T = 1 / fs

    # calculate FFT
    yf = fft(acc_y)
    xf = fftfreq(num_samples, T)

    # obtain single sided FFT
    xf = xf[:num_samples // 2]
    yf = (2.0 / num_samples) * np.abs(yf[:num_samples // 2])

    # obtain the dominant frequency and its magnitude (Ignore frequency = 0 Hz)
    max_index = np.argmax(yf[1:]) + 1
    dominant_freq = xf[max_index]
    magnitude_max = yf[max_index]

    print(f"Dominant frequency during walking: {dominant_freq:.2f} Hz (Magnitude: {magnitude_max:.2f})")

    # Convert to minimum interval between peaks
    interval = fs / dominant_freq
    minimum_interval = int(interval * 0.5) # TODO: check with Mariana why * 0.5

    return minimum_interval