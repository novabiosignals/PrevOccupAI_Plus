"""
Functions to load raw sensor data

Available Functions
-------------------
[Public]
load_data_from_same_recording(...): Loads and synchronizes raw sensor data (phone, watch, or MuscleBan) from a folder.
-------------------

[Private]
_load_raw_data(...): Loads and cleans multiple raw sensor data files from a folder.
_load_sensor_file(...): Loads a single raw sensor file and applies necessary preprocessing steps.
_load_muscleban_data(...): Loads EMG and ACC data from MuscleBan device files, filtering out unreliable data.
_get_largest_file(...): Selects the largest file (by size) among a list of files in a directory.
-------------------
"""

# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import os
import pandas as pd
from typing import List, Tuple, Dict, Any
from pathlib import Path

# internal imports
from sensors.load.daily_data_loader import _pad_data, _re_sample_data, _remove_non_unit_quaternion, _clean_df
from sensors.load.parser import get_file_paths_by_device, extract_sensor_from_filename
from sensors.process.interpolate import resample_signals
from constants import ROT, PHONE, WATCH, NOISE, HEART, TIME_COLUMN_NAME, VALID_MBAN_DATA, FS_MBAN

# ------------------------------------------------------------------------------------------------------------------- #
# file specific constants
# ------------------------------------------------------------------------------------------------------------------- #

# padding types
PADDING_SAME = 'same'
PADDING_ZERO = 'zero'
VALID_PADDING_TYPES = ['same', 'zero']

# sensor data dictionary keys
LOADED_SENSORS = 'loaded sensors'
STARTING_TIMES = 'starting times'
STOPPING_TIMES = 'stopping times'

ROUNDING_FACTOR = 1000 # sampling rate times 10
MIN_BYTES = 1000000 # 1mb
# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #
def load_data_from_same_recording(folder_path: str, fs: int = 100, padding_type: str = PADDING_SAME) -> Dict[str, pd.DataFrame]:
    """
    Function to load sensor data from the same recording into a single DataFrame. This can be used to load
    Android sensor data and MuscleBan (Plux Wireless Biosignals) data, if acquired using the OpenSignals application.

    The function assumes that files stored at the provided path belong to the same recording. Alignment (in time) of
    the files is done based on the last sensor to start and the first to stop, meaning that data is only considered
    while all sensors are recording at the same time. The data is re-sampled to the sampling rate given by 'fs'.
    The resampling is necessary as the Android OS does not ensure equidistant sampling at a fixes rate. Downsampling
    is also need for the muscleban data, which is acquired ar 1000 Hz

    :param folder_path: the path to the folder containing the sensor files.
    :param fs: the sampling rate to which all sensors should be re-sampled to. Default: 100 (Hz)
    :param padding_type: padding which should be used to ensure that all sensors start and stop at the same time. The
                         following padding types are supported: 'same', 'zero'. Default: 'same'
    :return: pandas.DataFrame containing all sensors aligned in time and re-sampled to the same sampling rate.
    """
    # innit dict to store the data for each device
    device_data_dict = {}

    # get the sensor file for each device in the folder
    paths_dict = get_file_paths_by_device(folder_path)

    for device, sensor_path_list in paths_dict.items():

        # if the device is a muscleban the loading is handled differently
        if device != PHONE and device != WATCH:

            # get the largest file only as the mbans generate multiple sometimes
            file_path = _get_largest_file(folder_path, sensor_path_list)

            # convert to Path object
            file_path = Path(file_path)

            # check minimum size
            if file_path.stat().st_size <= MIN_BYTES:

                # skip acquisition if the largest file is too short
                continue

            # load emg and acc data
            muscleban_sensor_data = _load_all_muscleban_data(file_path)

            # the muscleban signals are already aligned in time
            # downsample muscleban data to 100 Hz
            resampled_muscleban_data = resample_signals(muscleban_sensor_data, fs=FS_MBAN, fs_new=fs)

            # add to the dictionary
            device_data_dict[device] = resampled_muscleban_data

        else:

            # load the data
            sensor_data, report = _load_raw_sensor_data(folder_path, sensor_path_list)

            # align the data
            # (1) pad the data (all sensors start and stop at the same timestep)
            padded_data = _pad_data(sensor_data, report, padding_type)

            # (2) resample the data to 100 Hz
            interpolated_data = _re_sample_data(padded_data, report, fs=fs)

            # (3) create a DataFrame containing all the data and sort
            aligned_sensor_df = pd.concat(interpolated_data, axis=1)
            aligned_sensor_df = aligned_sensor_df.sort_index()

            # add to the dictionary
            device_data_dict[device] = aligned_sensor_df

    return device_data_dict


def _load_raw_sensor_data(folder_path: str, sensor_filenames: List[str]) -> Tuple[List[pd.DataFrame], Dict[str, Any]]:
    """
    Loads sensor data contained in 'folder_path' into a list of pandas DataFrames. Each element in the list sensor_filenames corresponds
    to a sensor's data.A dictionary is also returned containing the loaded sensors and the timestamps when each sensor
    started and stopped recording.

    General data cleaning includes:
    (1) Removal of NaN values
    (2) Removal of duplicates
    (3) Resetting of DataFrame index

    :param folder_path: The path to the folder containing sensor data files.
    :param sensor_filenames: A list with the names of the files to be loaded.
    :return: A tuple where the first element is a list of pandas DataFrames for each sensor's data, and the second
             element is a dictionary containing sensor start/stop timestamps and order information.
    """

    # list for holding the loaded DataFrames
    sensor_data = []

    # list for holding the sensor names
    loaded_sensors = []

    # list for holding starting and stopping timestamps
    start_times = []
    stop_times = []


    # cycle of the sensor data of one device
    for sensor_filename in sensor_filenames:

        # get sensor name from the path
        sensor_name = extract_sensor_from_filename(sensor_filename)

        # load the data
        sensor_df = _load_sensor_data_file(folder_path, sensor_filename, sensor_name)

        # append the data to sensor_data
        sensor_data.append(sensor_df)

        # append the sensor to loaded_sensors
        loaded_sensors.append(sensor_name)

        # append the start and stop times
        start_times.append(sensor_df[TIME_COLUMN_NAME].iloc[0])
        stop_times.append(sensor_df[TIME_COLUMN_NAME].iloc[-1])

    # create dictionary
    report = {
        LOADED_SENSORS: loaded_sensors,
        STARTING_TIMES: start_times,
        STOPPING_TIMES: stop_times,
    }

    return sensor_data, report


def _load_sensor_data_file(folder_path: str, file_name: str, sensor_name: str) -> pd.DataFrame:
    """
    Load a sensor file into a pandas DataFrame and cleans it.

    This function reads a sensor data file located in the specified folder, performs initial cleanup
    by removing unnecessary columns, and assigns appropriate column names. For rotation vector data,
    additional steps are taken to ensure that only valid unit quaternions are kept.

    :param folder_path: The directory where the sensor file is located.
    :param file_name: The name of the sensor file to be loaded.
    :param sensor_name: The name of the sensor, used to define appropriate column names and handle
                        sensor-specific preprocessing.
    :return: A cleaned pandas DataFrame containing the sensor data with appropriate column names.
    """

    # create full file path
    file_path = os.path.join(folder_path, file_name)

    # read the file
    sensor_df = pd.read_csv(file_path, delimiter='\t', header=None, skiprows=3)

    # remove nan column (the loading of the opensignals sensor file through read_csv(...) generates a nan column
    sensor_df.dropna(axis=1, how='all', inplace=True)

    # column names if it is heart rate sensor
    if sensor_name == HEART:

        col_names = [TIME_COLUMN_NAME, f'{sensor_name}']

    # column names if it is heart rate sensor
    elif sensor_name == NOISE:

        col_names = [TIME_COLUMN_NAME, f'{sensor_name}_db', f'{sensor_name}_dba']

    # perform extra steps for rotation vector
    elif sensor_name == ROT:

        # rotation vector from the smartwatch has an extra column (estimated heading) to be removed
        if len(sensor_df.columns) > 5:

            sensor_df = sensor_df.drop(sensor_df.columns[-1], axis=1)

        # add fourth column name
        col_names = [TIME_COLUMN_NAME, f'x_{sensor_name}', f'y_{sensor_name}', f'z_{sensor_name}', f'w_{sensor_name}']

        # remove samples that are not unit vectors
        sensor_df = _remove_non_unit_quaternion(sensor_df)

    # is imu sensor
    else:

        # define column names depending on sensor name
        col_names = [TIME_COLUMN_NAME, f'x_{sensor_name}', f'y_{sensor_name}', f'z_{sensor_name}']

    # add column names
    sensor_df.columns = col_names

    # remove nan values and duplicates + reset index
    sensor_df = _clean_df(sensor_df)

    return sensor_df


def _load_all_muscleban_data(file_path: Path) -> pd.DataFrame:
    """
    Loads MuscleBan data into a DataFrame.
    Loads only EMG and accelerometer (x, y, z) signals, removing MAG sensor as it is unreliable.

    :param file_path: Path to the muscleban file to be loaded.
    :return:  A DataFrame containing the EMG and ACC data from the muscleban
    """
    # load data into a csv file
    sensor_df = pd.read_csv(file_path, delimiter = '\t', header=None, skiprows=3)

    # remove Nan column that is generated when using pd.read_csv
    sensor_df = sensor_df.dropna(axis=1, how="all")

    # if there are 9 column then the second column is only zeros (happens in some firmware versions)
    if len(sensor_df.columns) > 8:

        # remove zero column
        sensor_df = sensor_df.drop(sensor_df.columns[1], axis=1)

    # remove MAG which are the last three channels
    sensor_df = sensor_df.drop(sensor_df.columns[-3:], axis=1)

    # add column names
    sensor_df.columns = VALID_MBAN_DATA

    return sensor_df


def _get_largest_file(folder_path, filenames: List[str]) -> str:
    """
    Returns the path to the largest file in the given list.

    Compares file sizes in bytes and returns the path of the file with the largest size.

    :param folder_path: Path to the folder containing the file.
    :param filenames: List with filenames from the same sensor
    :return:
    """
    # list for holding the paths
    file_paths = []

    for filename in filenames:

        # generate full path
        file_path = os.path.join(folder_path, filename)

        # add to list
        file_paths.append(file_path)

    return max(file_paths, key=lambda f: os.path.getsize(f))