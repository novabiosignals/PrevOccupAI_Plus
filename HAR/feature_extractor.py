"""
Functions to extract and preprocess features from smartphone sensor data using the TSFEL library.

Available Functions
-------------------
[Public]
extract_features(...): Extracts time-series features from smartphone sensor data using TSFEL.
trim_data(...): Trims sensor data so that the length is compatible with full windowing.
------------------
[Private]
None
------------------
"""
# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import pandas as pd
import tsfel
import numpy as np
from typing import Tuple, List
import os
from pathlib import Path

# internal imports
from utils import load_json_file

# ------------------------------------------------------------------------------------------------------------------- #
# constants
# ------------------------------------------------------------------------------------------------------------------- #
TSFEL_CONFIG_FILE = 'cfg_file_production_model.json'


# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #
def extract_features(sensor_df: pd.DataFrame, sensors_to_load: List[str], w_size: float, fs: int) -> pd.DataFrame:
    """
    Extracts features from smartphone sensors.

    This function windows the signals and extracts features from inertial sensors using TSFEl library. This function
    requires that sensor_df has sensor data from the sensors defined in SENSORS_TO_LOAD.
    Other sensors besides SENSORS_TO_LOAD are ignored.

    :param sensor_df: pandas dataframe with the signals to extract the features from
    :param sensors_to_load: list with the sensors to extract features from
    :param w_size: the window size in seconds that should be used for windowing the data
    :param fs: the sampling rate (in Hz) of the data
    :return: a dataframe containing the extracted features
    """
    # get the features to be extracted TSFEL
    features_dict = load_json_file(os.path.join(Path(__file__).parent, TSFEL_CONFIG_FILE))

    # drop the columns that are not needed for HAR
    sensor_cols = [col for col in sensor_df.columns if any(word in col for word in sensors_to_load)]
    sensor_df = sensor_df[sensor_cols]

    # check if there are columns with the required sensors
    missing_sensors = [sensor for sensor in sensors_to_load if not any(sensor in col for col in sensor_df.columns)]
    if missing_sensors:
        raise ValueError(
            f"Missing required sensor columns for {missing_sensors}. "
            f"Expected sensors: {sensors_to_load}, got dataframe columns: {list(sensor_df.columns)}"
        )

    # convert data to numpy array
    sensor_data = sensor_df.to_numpy()

    # get the sensor names
    sensor_names = sensor_df.columns.values

    # trim data to accommodate full windowing of the signals
    sensor_data, _ = trim_data(sensor_data, w_size=w_size, fs=fs)

    # inform user
    print("-> extracting features")

    # window the signals and extract features using TSFEL
    features_df = tsfel.time_series_features_extractor(features_dict, sensor_data, window_size=int(w_size * fs), fs=fs,
                                                    header_names=sensor_names)

    return features_df


def trim_data(data: np.ndarray, w_size: float, fs: int) -> Tuple[np.ndarray, int]:
    """
    Function to get the amount that needs to be trimmed from the data to accommodate full windowing of the data
    (i.e., not excluding samples at the end).
    :param data: numpy.array containing the data
    :param w_size: Window size in seconds
    :param fs: Sampling rate
    :return: the trimmed data and the amount of samples that needed to be trimmed.
    """

    # calculate the amount that has to be trimmed of the signal
    to_trim = int(data.shape[0] % (w_size * fs))

    return data[:-to_trim, :], to_trim
