# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import pandas as pd
from typing import Dict
import copy


# internal imports
from .classifier import classify_human_activities
from constants import PHONE, WATCH, MBAN_LEFT, MBAN_RIGHT, WATCH_SUFFIX, MBAN_L_SUFFIX, MBAN_R_SUFFIX


# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #

def classify_and_synchronise_predictions(daily_data_dict: Dict[str, Dict[str, pd.DataFrame]], w_size: float = 5.0,
                                         fs: int = 100) -> pd.DataFrame:
    """
    Classify and synchronise activity predictions across multiple devices.

    This function takes a nested dictionary of daily sensor acquisitions
    (e.g., 'phone': {'09:45:00': pd.DataFrame} , 'watch': {'10:45:00': pd.DataFrame, '11:30:00': pd.DataFrame}),
    classifies human activities using the smartphone data, and then synchronises the predictions across all devices,
    using a sliding window approach.

    :param daily_data_dict: a nested dictionary with the following format: {device_name : {acquisition_time: pd.DataFrame}}
                            (e.g., 'phone': {'09:45:00': pd.DataFrame} , 'watch': {'10:45:00': pd.DataFrame, '11:30:00': pd.DataFrame})
    :param w_size: the window size in seconds that should be used for windowing the data
    :param fs: the sampling rate (in Hz) of the data
    :return: a dataframe with all synchronised signals
    """
    daily_dict = copy.deepcopy(daily_data_dict)

    # if no phone data was loaded raise exception
    if PHONE not in daily_data_dict.keys():
        raise KeyError(f"Key '{PHONE}' not found in dictionary. Load smartphone data to classify the activities.")

    # classify human activities using only the phone
    daily_dict[PHONE] = classify_human_activities(daily_data_dict[PHONE], w_size=w_size, fs=fs)

    # cycle over the outer dictionary
    for device_name, acquisitions_dict in daily_dict.items():

        # cycle over the inner dict with the acquisition data
        for acquisition_time, sensor_df in acquisitions_dict.items():

            # add suffix to distinguish same sensors from different device
            sensor_df = _add_suffix_to_column_name(device_name, sensor_df)

            # create time column using the acquisition time and sampling frequency
            time_col = _create_time_column_from_initial_time(acquisition_time, sensor_df.shape[0], fs)

            # add time column to the sensor_df
            sensor_df['time'] = time_col

            # set time column as index
            sensor_df = sensor_df.set_index('time')

            # add replace in the dictionary
            acquisitions_dict[acquisition_time] = sensor_df

        # get list with all dataframes from the device
        list_df = list(acquisitions_dict.values())

        # concat all dataframes from the same device into one
        daily_dict[device_name] = pd.concat(list_df, axis=0)

    # concat all devices dataframes into one
    list_device_df = list(daily_dict.values())

    # concat all devices dataframes into one
    complete_df = pd.concat(list_device_df, axis=1)

    return complete_df

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #

def _create_time_column_from_initial_time(initial_time: str, signal_size: int, fs: int) -> pd.Series:
    """
    Generate a time column, starting from a given clock time.

    This function creates a sequence of times in the format "HH:MM:SS.sss"
    (hours, minutes, seconds, milliseconds) sampled at a specified frequency.
    The time column is returned as a pandas Series of strings.

    :param initial_time: The starting time of the sequence, in the format "HH-MM-SS" (e.g., "10-30-00").
    :param signal_size: The number of time samples to generate
    :param fs: The sampling frequency in Hz. The interval between consecutive times is computed as 1/fs.
    :return: The generate time column
    """

    # Parse start time as datetime with milliseconds
    start_time = pd.to_datetime(initial_time + '.000', format='%H-%M-%S.%f')

    # delta t in seconds
    dt = 1 / fs

    # Generate DatetimeIndex
    time_index = pd.date_range(start=start_time, periods=signal_size, freq=pd.Timedelta(seconds=dt))

    # Convert to string 'HH:MM:SS.sss'
    time_series = pd.Series([t.strftime('%H:%M:%S.%f')[:-3] for t in time_index])

    return time_series


def _add_suffix_to_column_name(device_name: str, df: pd.DataFrame) -> pd.DataFrame:
    """
    Add suffixes to the column names to differentiate the same sensors from different devices
    :param device_name: Name of the device
    :param df: pandas dataframe with the signal pertaining for that device
    :return: the dataframe with the added suffixes
    """

    if device_name == WATCH:
        return df.add_suffix(WATCH_SUFFIX)

    elif device_name == MBAN_LEFT:
        return df.add_suffix(MBAN_L_SUFFIX)

    elif device_name == MBAN_RIGHT:
        return df.add_suffix(MBAN_R_SUFFIX)
    else:
        return df
