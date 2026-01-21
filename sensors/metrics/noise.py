"""
Functions to extract metrics from noise data (dBA).

Available Functions
-------------------
[Public]
get_noise_metrics(...): Extracts metrics from the noise data from one day and saves it in a dictionary.
-------------------

[Private]
_calculate_noise_metrics(...):  Extract features from noise data in dBA (statistics, class distributions, and durations).
_classify_noise(...): Classifies a noise level (in dBA) into noise categories (near-silent, low noise, disruptive noise, high noise)
_calculate_windowed_timeline_metrics(...): Calculates timeline metrics for noise data using a windowing approach.
"""
# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import pandas as pd
from typing import Dict

# internal imports
import HAR
import sensors.load as sl
from constants import NOISE, NOISE_CLASS_COLUMN_NAME, PHONE
from .metric_utils import calculate_statistics, calculate_class_distributions, calculate_class_durations
from utils import extract_date_from_path
from OH_profile.constants import *

# ------------------------------------------------------------------------------------------------------------------- #
# file specific constants
# ------------------------------------------------------------------------------------------------------------------- #

# noise limits dBA
SILENCE_NOISE_LIMIT_DBA = 40
LOW_NOISE_LIMIT_DBA = 60
DISTURBING_NOISE_LIMIT_DBA = 80

W_SIZE_MINUTES = 10
NOISE_TIMELINE_WLEN = f'{NOISE_TIMELINE_KEY}_wlen-{W_SIZE_MINUTES}'
# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #

def get_noise_metrics(day_folder_path: str, fs: int, w_size_min: int = W_SIZE_MINUTES) -> Dict:
    """
    Extracts metrics from the noise data from one day and saves it in a dictionary.

    :param day_folder_path: Path to the folder containing the noise data for an entire day
    :param fs: The sampling frequency of the smartphone
    :param w_size_min: window size in minutes for storing the timeline metrics
    :return: A dictionary containing the noise metrics.
    """

    # get date from path
    date = extract_date_from_path(day_folder_path)

    # reformat to dd-mm-yyyy
    year, month, day = date.split('-')
    date = f"{day}-{month}-{year}"

    # init dict
    day_metrics_dict = {date: {}}

    # load_signals all acquisitions from the same day into a nested dictionary
    df_dict = sl.load_daily_acquisitions(day_folder_path, load_devices={PHONE: [NOISE]})

    # cycle over the dictionary containing the noise data of the day (usually it is only one recording but multiple could happen)
    for acquisition_time, df in df_dict[PHONE].items():

        if not df.empty:

            # extract metrics from the noise data
            metrics_dict = _calculate_noise_metrics(df, fs=fs, start_time = acquisition_time, window_size_min=w_size_min)

        else:
            # empty metrics if there is no data
            metrics_dict = {}

        # add to daily metrics dictionary
        day_metrics_dict[date][acquisition_time] = metrics_dict

    return day_metrics_dict


# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #

def _calculate_noise_metrics(df: pd.DataFrame, fs: int, start_time: str, window_size_min: int) -> Dict:
    """
    Extract features from noise data in dBA.

    This function assumes that df has a column with noise data in dBA and calculates statistics (min, max, mean, std),
    classifies the noise values into near-silent, low noise, disruptive noise, and high noise classes and calculates
    class distributions and duration of each class in seconds. These metrics are stored in a dictionary.

    :param df: Dataframe containing the noise data
    :param fs: The sampling frequency at which the noise data was acquired.
    :return: A dictionary with the extracted metrics
    """
    # init dict to store noise metrics
    metrics_dict = {}

    # Add classification column
    df[NOISE_CLASS_COLUMN_NAME] = df[f"{NOISE}_dba"].apply(_classify_noise)

    # calculate statistics - min, max, mean, std
    stats_dict = calculate_statistics(df, f"{NOISE}_dba")

    # calculate class distributions
    class_distributions = calculate_class_distributions(df, NOISE_CLASS_COLUMN_NAME)

    # calculate class durations
    class_durations = calculate_class_durations(df, fs, class_distributions)

    # calculate timeline metrics
    timeline_metrics = _calculate_windowed_timeline_metrics(df, NOISE_CLASS_COLUMN_NAME, start_time, fs, window_size_min=window_size_min)

    # add to the dict storing the metrics
    metrics_dict.update({NOISE_STATISTICS_KEY: stats_dict})
    metrics_dict.update({NOISE_DISTRIBUTIONS_NOISE: class_distributions})
    metrics_dict.update({NOISE_DURATIONS_KEY: class_durations})
    metrics_dict.update({NOISE_TIMELINE_WLEN: timeline_metrics})

    return metrics_dict


def _classify_noise(dba_value: float) -> str:
    """
    Classifies a noise level (in dBA) into a noise category based on EU Directive 2003/10/EC ([1] https://eur-lex.europa.eu/eli/dir/2003/10/)
    exposure limits and on disruptive noise thresholds for enclosed office environments, as described in
    [2] https://www.sciencedirect.com/science/article/pii/S0360132324011557.

    Given the office context, noise levels above 80 dBA are classified as "high noise" according to the EU directive.
    Prolonged and consistent exposure to such levels may require preventive measures to avoid hearing impairment.
    Higher exposure limits defined in the EU directive (85 dBA and 87 dBA) are not considered in this work, as such levels are not realistically
    encountered in typical office environments and are more commonly associated with heavy industrial machinery. Noise levels
    under 40 dBA are considered near-silent.

    Considering these two references, the following classes were derived:
        - ≤ 40 dBA: NEAR_SILENCE_NOISE -> Near-silent room
        - 40-60 dBA: LOW_NOISE -> low, non-disruptive noise [2]
        - 60–80 dBA: DISRUPTIVE_NOISE -> Disruptive background noise that heavily impacts a worker's concentration and emotional arousal levels. [2]
        - ≥ 80 dBA: HIGH_NOISE -> High noise level that may require preventive action to avoid hearing impairment during prolonged exposure. [1]

    :param dba_value: A-weighted decibel value (dBA).
    :return: Noise class.
    """
    # check for near silence noise values
    if dba_value < SILENCE_NOISE_LIMIT_DBA:
        return NOISE_NEAR_SILENCE_KEY

    # check for low noise limit
    elif dba_value <= LOW_NOISE_LIMIT_DBA:
        return NOISE_LOW_KEY

     # check for disruptive noise values
    elif dba_value <= DISTURBING_NOISE_LIMIT_DBA:
        return NOISE_DISTURBING_KEY

    # else it's high noise ≥ 80
    else:
        return NOISE_HIGH_KEY

def _calculate_windowed_timeline_metrics(df: pd.DataFrame, column_name: str, start_time: str, fs: int,
                                         window_size_min: int) -> Dict[str, str]:
    """
    Calculates timeline metrics for noise data using a windowing approach.

    Generates a timestamp column from the initial start time of the acquisition and calculates the timeline metrics.

    :param df: pandas DataFrame containing the noise data
    :param column_name: Name of the column containing the class labels
    :param start_time: The start time of the acquisition in the format: HH-MM-SS
    :param fs: The sampling frequency of the noise recorder
    :return: A dictionary with the timeline metrics
    """
    # init dict to store metrics
    timeline_metrics: Dict[str, str] = {}

    # generate real time column from the acquisition start time
    time_col = HAR.create_time_column_from_initial_time(initial_time=start_time, signal_size=df.shape[0], fs=fs)

    # add time column to df
    df['timestamps'] = time_col.values

    # make timestamps the index
    df = df.set_index("timestamps")

    # convert Index to DatetimeIndex object for the resample function
    df.index = pd.to_datetime(df.index, format="%H:%M:%S.%f")

    # window dataframe
    for window_start, window_df in df.resample(f"{window_size_min}min"):

        # most common class (mode returns a pandas.Series with the most common class -> 0 class_A)
        most_common_class = window_df[column_name].mode()

        # get the most common class in this window
        most_common_class = most_common_class.iloc[0]

        # get start and end timestamps
        window_start = window_df.index[0]
        window_end = window_df.index[-1]

        key = (
            f"{window_start.strftime('%H:%M:%S.%f')[:-3]}"
            f"_{window_end.strftime('%H:%M:%S.%f')[:-3]}"
        )

        timeline_metrics[key] = most_common_class

    return timeline_metrics