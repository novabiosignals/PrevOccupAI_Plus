"""
Functions to preprocess MuscleBAN sensor data, including applying transfer functions and resampling signals.

Available Functions
-------------------
[Public]
apply_transfer_functions(...): Applies transfer functions to accelerometer data and EMG data from the muscleBAN.
resample_signals(...): Resamples all sensor signals to a new sampling frequency using polyphase filtering.
-------------------
[Private]
_emg_transfer_function(...): Converts raw EMG ADC values to millivolts.
_acc_transfer_function(...): Converts raw accelerometer ADC values to m/s².
_generate_time_column_from_samples(...): Generates a time axis in seconds based on the number of samples and sampling frequency.
"""
# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import pandas as pd
import numpy as np
from scipy.signal import resample_poly

# internal imports
from constants import TIME_COLUMN_NAME, ACC, EMG

# ------------------------------------------------------------------------------------------------------------------- #
# constants
# ------------------------------------------------------------------------------------------------------------------- #
N_BITS = 16
GRAVITATIONAL_ACC = 9.81

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #
def apply_transfer_functions(muscleban_df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply transfer functions to muscleban data.
    This function cycles over the columns of the dataframe containing the muscleban data and when it finds accelerometer
    and EMG columns, applies the respective transfer functions to convert to m/s^2 and mV respectively.
    :param muscleban_df: pd.DataFrame containing the muscleban data
    :return: pd.DataFrame with the converted acc and emg signals.
    """
    # get copy of the dataframe to not overwrite the data
    processed_df = muscleban_df.copy()

    print("Applying transfer functions to muscleban data")

    # cycle over the columns of the muscleban dataframe
    for column in processed_df.columns:

        # if it's ACC column
        if ACC in column:

            # apply ACC transfer function
            processed_df[column] = _acc_transfer_function(processed_df[column])

        # if it is emg column
        elif EMG in column:

            # apply EMG transfer function
            processed_df[column] = _emg_transfer_function(processed_df[column])

    return processed_df


def resample_signals(sensor_df: pd.DataFrame, fs: int, fs_new: int) -> pd.DataFrame:
    """
    Function to resample signals using polyphase filtering. If fs_new > fs, the function upsamples the signal.
    If fs_new < fs, this function downsamples the signals. This function also generates a time axis in seconds based
    on the length of the signals and on the new sampling frequency. The first column of sensor_df is considered to be
    a time-axis (or an index column) and the remaining columns are considered signals.

    :param sensor_df: A DataFrame containing timestamps or indices in first column and sensor data in the remaining columns.
    :param fs: The original sampling frequency.
    :param fs_new: The target sampling frequency in Hz.
    :return: A DataFrame where the first column is the timestamps in seconds and the remaining are resampled data.
    """
    print(f"Resampling data to {fs_new} Hz\n")

    # list for holding the resampled signals
    resampled_signals = []

    # extract signals (and cast to numpy.array)
    signals = sensor_df.iloc[:, 1:].values

    # calculate resampling factor based on original fs and the new fs
    if fs > fs_new:
        factor = round(fs/fs_new)
        resample = 'down'

    else:
        factor = round(fs_new/fs)
        resample = 'up'

    # cycle over the signal channels
    for channel in range(signals.shape[1]):

        if resample == 'up':

            # upsample signals using polyphase filtering
            resampled_signal = resample_poly(signals[:, channel], up=factor, down=1)

        else:

            # downsample signals using polyphase filtering
            resampled_signal = resample_poly(signals[:, channel], up=1, down=factor)

        # append to resample signals
        resampled_signals.append(resampled_signal)

    # generate new time axis with the new sampling frequency
    time_axis_inter = _generate_time_column_from_samples(resampled_signals[0].shape[0], fs_new)

    # create interpolated DataFrame and change time column name
    resampled_df = pd.DataFrame(np.column_stack([time_axis_inter] + resampled_signals),
                                   columns=[TIME_COLUMN_NAME] + list(sensor_df.columns[1:]))

    return resampled_df

# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #

def _emg_transfer_function(emg_series: pd.Series) -> pd.Series:
    """
    Convert EMG ADC output to mV
    :param emg_series: pd.series with the EMG data before conversion
    :return: converted data
    """
    return (((emg_series / (2 ** 16 - 1.0)) - 0.5) * 2500) / 1100


def _acc_transfer_function(acc_series: pd.Series) -> pd.Series:
    """
    Convert ADC output to m/s^2.
    :param acc_series: pd.series with the accelerometer data before conversion
    :return: converted acc data
    """
    # convert ADC output to g
    acc_series = (acc_series - (2 ** N_BITS / 2)) * (16 / (2 ** N_BITS))

    # convert to m/s^2
    acc_series = acc_series.multiply(GRAVITATIONAL_ACC).round(2)

    return acc_series


def _generate_time_column_from_samples(signal_size: int, fs: int) -> np.ndarray:
    """
    Generates a time axis in seconds based on the number of samples and sampling frequency.

    :param signal_size: size of the signal in samples
    :param fs: the sampling frequency of the signal in Hz
    :return: The generated time axis
    """

    # get time (seconds) between each sample
    delta_t = 1/fs

    # generate time column in seconds
    time_column = np.arange(signal_size) * delta_t

    return time_column