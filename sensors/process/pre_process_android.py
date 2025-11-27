"""
Functions for pre-processing ACC, GYR, MAG, and ROTATION VECTOR signals.

Available Functions
-------------------
[Public]
_pre_process_inertial_data(...): Applies the pre-processing pipeline of "A Public Domain Dataset for Human Activity Recognition Using Smartphones".
_slerp_smoothing(...): Smooths a quaternion time series using spherical linear interpolation (SLERP).
------------------
[Private]
None
------------------
"""

# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import numpy as np
import pandas as pd
from pyquaternion import Quaternion
from tqdm import tqdm
from typing import Tuple, List, Dict
import copy

# internal imports
from .filters import median_and_lowpass_filter, gravitational_filter
from constants import ACC, MAG, GYR, ROT, PHONE, WATCH, FS_MBAN
from .pre_process_muscleban import apply_transfer_functions, resample_signals
# ------------------------------------------------------------------------------------------------------------------- #
# constants
# ------------------------------------------------------------------------------------------------------------------- #
VALID_SENSORS = [ACC, GYR, MAG, ROT]

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #

def apply_pre_processing_pipeline(daily_data_dict: Dict[str, Dict[str, pd.DataFrame]], fs_android: int = 100,
                                  downsample_muscleban: bool = True) -> Dict[str, Dict[str, pd.DataFrame]]:
    """
    This function pre-processes the inertial sensor data from the smartwatch and smartphone devices. For the muscleban,
    this function applies the transfer functions for the EMG and ACC, filters the EMG, and downsamples the muscleban
    signals if downsample_muscleban is set to True.

    :param daily_data_dict: a nested dictionary with the following format: {device_name : {acquisition_time: pd.DataFrame}}
                            (e.g., 'phone': {'09:45:00': pd.DataFrame} , 'watch': {'10:45:00': pd.DataFrame, '11:30:00': pd.DataFrame})
    :param fs_android: the sampling rate (in Hz) of the data from the smart devices. This is also the sampling frequency which
                        the muscleban signal will be downsampled to. Default = 100.
    :param downsample_muscleban: bool. If true, muscleban signals are downsampled, if not, these keep the original sampling
                                frequency
    :return: a nested dictionary with the same format as the input one, but with the preprocessed signals.
    """

    # make a copy to not overwrite the original dictionary
    processed_dict = copy.deepcopy(daily_data_dict)

    # cycle over the outer dict with the device names and acquisition data
    for device_name, acquisitions_dict in processed_dict.items():

        print(f"\n-------------------Preprocessing {device_name}-------------------\n")

        # check if it is android device
        if device_name == PHONE or device_name == WATCH:

            # cycle over the inner dict with the acquisition times and dataframes
            for acquisition_time, df in acquisitions_dict.items():

                print(f"Acquisition time: {acquisition_time}\n")

                # preprocess signals and add to dictionary
                processed_dict[device_name][acquisition_time] = _pre_process_signals(df, fs_android)

        else:

            # apply muscleban preprocessing
            # cycle over the inner dict with the acquisition times and respective dataframes
            for acquisition_time, df in acquisitions_dict.items():

                print(f"Acquisition time: {acquisition_time}")

                # convert acc and/or emg to m/s^2 and/or mV
                processed_dict[device_name][acquisition_time] = apply_transfer_functions(df)

                if downsample_muscleban:

                    # downsample ACC and/or EMG
                    processed_dict[device_name][acquisition_time] = resample_signals(df, fs=FS_MBAN, fs_new = fs_android)

    return processed_dict

# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #
def _pre_process_signals(subject_data: pd.DataFrame, fs: int) -> pd.DataFrame:
    """
    Pre-processes the sensors contained in subject_data according to their sensor type and removes samples from the
    impulse response of the filters.

    :param subject_data: pandas.DataFrame containing the sensor data
    :param fs: the sampling frequency (Hz)
    :return: the processed sensor data
    """

    # get the column names (sensor names) first row
    sensor_names = subject_data.columns.values[::]

    # pre-process the data
    sensor_data = _pre_process_sensors(subject_data.to_numpy(), sensor_names, fs=fs)

    # remove impulse response
    sensor_data = sensor_data[250:, :]

    # transform back to dataframe for easier handling of the data
    sensor_data = pd.DataFrame(sensor_data, columns=sensor_names)

    return sensor_data


def _pre_process_sensors(data_array: np.array, sensor_names: List[str], fs: int) -> np.array:
    """
    Pre-processes the sensors contained in data_array according to their sensor type.
    :param data_array: the loaded data
    :param sensor_names: the names of the sensors contained in the data array
    :return:
    """

    # make a copy to not override the original data
    processed_data = data_array.copy()

    # process each sensor
    for valid_sensor in VALID_SENSORS:

        # get the positions of the sensor in the sensor_names
        sensor_cols = [col for col, sensor_name in enumerate(sensor_names) if valid_sensor in sensor_name]

        if sensor_cols:

            print(f"--> pre-processing {valid_sensor} sensor")
            # acc pre-processing
            if valid_sensor == ACC:

                processed_data[:, sensor_cols] = _pre_process_inertial_data(processed_data[:, sensor_cols], is_acc=True,
                                                                           fs=fs)

            # gyr and mag pre-processing
            elif valid_sensor in [GYR, MAG]:

                processed_data[:, sensor_cols] = _pre_process_inertial_data(processed_data[:, sensor_cols], is_acc=False,
                                                                           fs=fs)

            # rotation vector pre-processing
            else:

                processed_data[:, sensor_cols] = _slerp_smoothing(processed_data[:, sensor_cols], 0.3,
                                                                 scalar_first=False,
                                                                 return_numpy=True, return_scalar_first=False)
        else:

            print(f"The {valid_sensor} sensor is not in the loaded data. Skipping the pre-processing of this sensor.")

    return processed_data


def _pre_process_inertial_data(sensor_data: np.array, is_acc: bool = False, fs: int = 100, normalize: bool = False) -> np.array:
    """
    Applies the pre-processing pipeline of "A Public Domain Dataset for Human Activity Recognition Using Smartphones"
    (https://www.esann.org/sites/default/files/proceedings/legacy/es2013-84.pdf). The pipeline consists of:
    (1) applying a median filter
    (2) applying a 3rd order low-pass filter with a cut-off at 20 Hz

    in case the sensor data belongs to an ACC sensor the following additional steps are performed.
    (3) applying a 3rd order low-pass filter with a cut-off at 0.3 Hz to obtain gravitational component
    (4) subtract gravitational component from ACC signal

    :param sensor_data: the sensor data.
    :param is_acc: boolean indicating whether the sensor is an accelerometer.
    :param fs: the sampling frequency of the sensor data (in Hz).
    :param normalize: boolean to indicate whether the data should be normalized (division by the max)
    :return: numpy.array containing the pre-processed data.
    """

    # apply median and lowpass filter
    filtered_data = median_and_lowpass_filter(sensor_data, fs=fs)

    # check if signal is supposed to be normalized
    if normalize:
        # normalize the signal
        filtered_data = filtered_data / np.max(filtered_data)

    # check if sensor is ACC (additional steps necessary
    if is_acc:
        # print('Applying additional processing steps')

        # get the gravitational component
        gravitational_component = gravitational_filter(filtered_data, fs=fs)

        # subtract the gravitational component
        filtered_data = filtered_data - gravitational_component

    return filtered_data


def _slerp_smoothing(quaternion_array: np.array, smooth_factor: float = 0.5, scalar_first: bool = False,
                     return_numpy: bool = True, return_scalar_first: bool = False) -> np.array:
    """
    Smooths a quaternion time series using spherical linear interpolation (SLERP).

    This function applies SLERP to smooth a sequence of quaternions by interpolating
    between consecutive quaternions with a specified smoothing factor. The method follows
    the approach described in:
    https://www.mathworks.com/help/fusion/ug/lowpass-filter-orientation-using-quaternion-slerp.html

    :param quaternion_array: 2D numpy.array of shape (N, 4) containing a sequence of quaternions. The quaternions can
                             be represented in either scalar-first (w, x, y, z) or scalar-last (x, y, z, w) notation.
    :param smooth_factor: the interpolation factor for SLERP, controlling how much smoothing is applied. The value must
                          be between [0, 1]. Values closer to 0 increase smoothing, while values closer to 1 retain the
                          original sequence.
    :param scalar_first: boolean indicating the notation that is used. Default: False
    :param return_numpy: boolean indicating, whether a numpy.array should be returned. If false an array containing
                         pyquaternion.Quaternion objects are returned.
    :param return_scalar_first: boolean indicating the notation for the return type. Default: False
    :return: returns quaternions in either scalar first (w, x, y, z) or scalar last notation (x, y, z, w), depending on
             the parameter settings of the boolean parameters.
    """

    # check range of smooth factor
    if not (0 <= smooth_factor <= 1):
        raise ValueError(f"The smooth factor has to be between [0, 1]. Provided smooth factor: {smooth_factor}")

    # change quaternion notation to scalar first notation (w, x, y, z)
    # this is needed as pyquaternion assumes this notation
    if not scalar_first:

        quaternion_array = np.hstack((quaternion_array[:, -1:], quaternion_array[:, :-1]))

    # get the number of rows
    num_rows = quaternion_array.shape[0]

    # array for holding the result
    smoothed_quaternion_array = np.zeros(num_rows, dtype=object)

    # initialize the first quaternion
    smoothed_quaternion_array[0] = Quaternion(quaternion_array[0])

    # cycle over the quaternion series
    for row in tqdm(range(1, num_rows), ncols=50, bar_format="{l_bar}{bar}| {percentage:3.0f}% {elapsed}"):

        # get the previous and the current quaternion
        q_prev = smoothed_quaternion_array[row - 1]
        q_curr = Quaternion(quaternion_array[row])

        # perform SLERP
        q_slerp = Quaternion.slerp(q_prev, q_curr, smooth_factor)

        # add the quaternion to the smoothed series
        smoothed_quaternion_array[row] = q_slerp

    # return as numpy array
    if return_numpy:

        # transform the output into a 2D numpy array
        smoothed_quaternion_series_numpy = np.zeros_like(quaternion_array)

        for row, quat in enumerate(smoothed_quaternion_array):

            smoothed_quaternion_series_numpy[row] = quat.elements

        # return in (x, y, z, w) notation
        if not return_scalar_first:

            smoothed_quaternion_series_numpy = np.hstack((smoothed_quaternion_series_numpy[:, 1:],
                                                          smoothed_quaternion_series_numpy[:, :1]))

        return smoothed_quaternion_series_numpy

    return smoothed_quaternion_array


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