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
from scipy.spatial.transform import Rotation as R
from scipy.signal import find_peaks
from scipy.integrate import cumulative_trapezoid as cumtrpaz
from typing import Dict, Union, Tuple

import matplotlib.pyplot as plt

# internal imports
from HAR import classify_human_activities, create_time_column_from_initial_time, CLASS_WALK, CLASS_STAND, CLASS_SIT
from HAR.classifier import BLOCK_ID_COLUMN_NAME
from OH_profile.constants import HAR_TIMELINE_KEY, HAR_DURATIONS_KEY, HAR_DISTRIBUTIONS_KEY, HAR_STEPS_KEY, \
    HAR_NUM_STEPS_KEY, HAR_DISTANCE_KEY
from constants import ACTIVITY_COLUMN_NAME, PHONE, ACC, GYR, MAG, ROT
from sensors.metrics.metric_utils import calculate_class_distributions, calculate_class_durations
from sensors.process.filters import get_envelope
from utils import extract_date_from_path
import sensors.load as sensor_loader
import sensors.process as sensor_processor


# ------------------------------------------------------------------------------------------------------------------- #
# file constants
# ------------------------------------------------------------------------------------------------------------------- #
Y_ACC_COL = f'y_{ACC}'
HEADING_ROTATION_COL = 'heading_rotation'
QUATERNION_COLUMNS = [f'x_{ROT}', f'y_{ROT}', f'z_{ROT}', f'w_{ROT}']
ACC_COLUMNS = [f'x_{ACC}', f'y_{ACC}', f'z_{ACC}']

ACTIVITY_CLASS_STRING_COLUMN = 'activity_class_name'
ACTIVITY_CLASS_MAP = {CLASS_WALK: 'Andar', CLASS_STAND: 'De pé', CLASS_SIT: 'Sentado'}
# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #
def get_human_activity_metrics(day_folder_path: str, fs: int, w_size_HAR: float,
                               peak_threshold: float = 0.6, valley_threshold: float = 0.3,
                               w_size_moving_average_s: int = 1) -> Dict:
    """
    Extracts metrics related to human activities. Before the extraction of metrics, the data is pre-processed and
    classified using a HAR  model.

    :param day_folder_path: Path to the folder containing the all the acquisitions from an entire day.
    :param fs: The sampling frequency with which the data was acquired.
    :param w_size_HAR: The window size for HAR classification in seconds.
    :param peak_threshold: the peak threshold for detecting steps. The threshold is between [0, 1] and can be seen as
                           a percentage of the average peak height during the recording. Default: 0.6
    :param valley_threshold: The valley threshold for detecting steps. The threshold is between [0, 1] and can be seen as
                             a percentage of the average peak height during the recording. Default: 0.3
    :param w_size_moving_average_s: window size for moving average smoothing (in seconds). Default: 1
    :return: dictionary containing the human activity metrics. The dictionary has the following structure:

    {"DD-MM-YYYY": {
        "HH-MM-SS": {
             "HAR_timeline: {...},
             "HAR_distributions: {...},
             "HAR_durations: {...},
             "HAR_steps: {...}
            }
    """

    # get date from path
    day_date = extract_date_from_path(day_folder_path)

    # reformate to dd-mm-yyyy
    year, month, day = day_date.split('-')
    day_date = f"{day}-{month}-{year}"

    # init dict for holding the extracted metrics
    day_metrics_dict = {day_date: {}}

    # load the acquisition(s) for the day
    df_dict, _ = sensor_loader.load_daily_acquisitions(day_folder_path, load_devices={PHONE: [ACC, GYR, MAG, ROT]})

    if len(df_dict) == 0:
        return {}

    # pre-proces the data
    processed_df_dict = sensor_processor.apply_pre_processing_pipeline(df_dict)

    # classify the data
    processed_df_dict[PHONE] = classify_human_activities(processed_df_dict[PHONE], w_size=w_size_HAR, fs=fs)

    # cycle over the dictionary containing the phone data (usually there is only one acquisition, but multiple can happen)
    for acquisition_time, df in processed_df_dict[PHONE].items():

        # check whether the DataFrame contains data
        if not df.empty:

            # extract human activities
            print("obtaining human activities and their proportions throughout the day.")
            metrics_dict = _calculate_human_activity_metrics(df, fs=fs, start_time=acquisition_time,
                                                             peak_threshold=peak_threshold,
                                                             valley_threshold=valley_threshold,
                                                             w_size_moving_average_s=w_size_moving_average_s)

        else:

            # set metrics_dict to empty if no data
            metrics_dict = {}

        # add the extracted metrics to the day_metrics dictionary
        day_metrics_dict[day_date][acquisition_time] = metrics_dict

    return day_metrics_dict


# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #
def _calculate_human_activity_metrics(df: pd.DataFrame, fs: int, start_time: str,
                                      peak_threshold: float = 0.6, valley_threshold: float = 0.3,
                                      w_size_moving_average_s: int = 1) -> Dict:
    """
    Calculates human activity metrics. The following metrics are calculated:
    (1) HAR_timeline: contains a timeline indicating for which time (start, stop) a certain human activity (either sit,
                      stand, or walk) was executed during the entire recording .
    (2) HAR_distributions: indicates the distribution (as percentage) of the human activities during the recording.
    (3) HAR_durations: indicates the total duration of the human activity during the recording.
    (4) HAR_steps: indicates the number of steps and the traverse distance (in meters) traversed during the recording.
    :param df: pandas.DataFrame containing the phone data and the corresponding HAR classification
    :param fs: the sampling frequency
    :param start_time: the time at which the acquisition started as a string (format: hh-mm-ss)
    :param peak_threshold: the peak threshold for detecting steps. The threshold is between [0, 1] and can be seen as
                           a percentage of the average peak height during the recording. Default: 0.6
    :param valley_threshold: The valley threshold for detecting steps. The threshold is between [0, 1] and can be seen as
                             a percentage of the average peak height during the recording. Default: 0.3
    :param w_size_moving_average_s: window size for moving average smoothing (in seconds). Default: 1
    :return: dictionary containing the human activity metrics. The dictionary has the following structure:

    {"HAR_timeline: {...},
     "HAR_distributions: {...},
     "HAR_durations: {...},
     "HAR_steps: {...},
    }
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
    step_metrics = _calculate_step_detection_metrics(df, fs=fs,
                                                     peak_threshold=peak_threshold,
                                                     valley_threshold=valley_threshold,
                                                     w_size_moving_average_s=w_size_moving_average_s)

    # obtain sitting metrics (posture metrics)

    # add extracted metrics to the dict
    metrics_dict.update({HAR_TIMELINE_KEY: timeline_metrics})
    metrics_dict.update({HAR_DISTRIBUTIONS_KEY: activity_distribution_metrics})
    metrics_dict.update({HAR_DURATIONS_KEY: activity_duration_metrics})
    metrics_dict.update({HAR_STEPS_KEY: step_metrics})

    return metrics_dict


def _get_human_activity_timeline(df: pd.DataFrame, fs: int, start_time: str) -> Dict[str, str]:
    """
    Obtains the human activity timeline. The timeline indicates the time (start-time_stop-time) in which the subject performed
    a certain activity, The timeline is based on the classification result of the HAR model.
    :param df: pandas.DataFrame containing the phone data and the corresponding HAR classification
    :param start_time: the time at which the acquisition started as a string (format: hh-mm-ss)
    :param fs: the sampling frequency
    :return: dictionary containing the human activity timeline. The dictionary has the following structure:

    {"HH:mm:ss.ms_HH:mm:ss.ms": "activity class",
     "HH:mm:ss.ms_HH:mm:ss.ms": "activity class",
     "HH:mm:ss.ms_HH:mm:ss.ms": "activity class",
     ...
    }


    Example:
    {"15:00:01.000_15:07:50.990": "Sentado",
     "15:07:51.000_15:07:55.990": "Andar",
     "15:07:56.000_15:12:00.990": "Sentado",
     ...
    }
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
    for _, block_df in df.groupby(BLOCK_ID_COLUMN_NAME):

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


def _calculate_step_detection_metrics(df: pd.DataFrame, fs: int,
                                      peak_threshold: float = 0.6, valley_threshold: float = 0.3,
                                      w_size_moving_average_s: int = 1.5) -> Dict[str, Union[int, float]]:
    """
    Calculates step detection metrics. The following metrics are calculated:
    (1) HAR_num-steps: the number of detected steps during the recording.
    (2) HAR_distance_walked_m: the distance (in meters) traversed during the recording.
    :param df: pandas.DataFrame containing the phone data and the corresponding HAR classifications
    :param fs: the sampling frequency
    :param peak_threshold: the peak threshold for detecting steps. The threshold is between [0, 1] and can be seen as
                           a percentage of the average peak height during the recording. Default: 0.6
    :param valley_threshold: The valley threshold for detecting steps. The threshold is between [0, 1] and can be seen as
                             a percentage of the average peak height during the recording. Default: 0.3
    :param w_size_moving_average_s: window size for moving average smoothing (in seconds). Default: 1
    :return: dictionary containing the step detection metrics. The dictionary has the following structure:

    {"num_steps: ...,
     "distance_walked_m: ...
    }

    """

    # make a copy of the dataFrame
    df_step_detection = df.copy()

    # init dict for storing the results
    metrics_dict: Dict[str, Union[int, float]] = {}

    # init variable for storing the number of steps and distance walked
    num_steps = 0
    distance_walked_m = 0

    # check input validity for peak and valley thresholds
    if not (0 <= peak_threshold <= 1):
        raise ValueError(f"Invalid peak_threshold: {peak_threshold}. It must be in the interval [0, 1].")

    if not (0 <= valley_threshold <= 1):
        raise ValueError(f"Invalid valley_threshold: {valley_threshold}. It must be between 0 and 1.")

    # filter DataFrame for walking instances
    df_step_detection = df_step_detection[df_step_detection[ACTIVITY_COLUMN_NAME] == CLASS_WALK]

    # cycle over the block_ids to obtain metrics per activity bloc
    for _, block_df in df_step_detection.groupby(BLOCK_ID_COLUMN_NAME):

        # detect steps and estimate the walked distance
        num_steps_block, distance_walked_m_block, _ = _step_detection(block_df, fs=fs,
                                                                      peak_threshold=peak_threshold,
                                                                      valley_threshold=valley_threshold,
                                                                      w_size_moving_average_s=w_size_moving_average_s)


        # update the number of steps
        num_steps += num_steps_block
        distance_walked_m += distance_walked_m_block


    # create dictionary for holding the metrics
    metrics_dict[HAR_NUM_STEPS_KEY] = num_steps
    metrics_dict[HAR_DISTANCE_KEY] = np.round(distance_walked_m, 4)

    return metrics_dict


def _step_detection(df_walk: pd.DataFrame, fs: int = 100,
                    peak_threshold: float = 0.6, valley_threshold: float = 0.3,
                    w_size_moving_average_s: int = 1.5) -> Tuple[int, float, Tuple[np.ndarray, np.ndarray]]:
    """
    Step detection algorithm for identifying the number of steps during the recording, as well as estimating the
    :param df_walk: pandas.DataFrame containing the phone's y-ACC, the corresponding HAR classification, as well as the
                    block_ids for identifying continuous blocks of an activity. The df should only contain walking data
                    corresponding to a continuous block of walking.
                    The implemented algorithm is based on the article:
                    Ho, N. H., Truong, P. H., & Jeong, G. M. (2016). Step-detection and adaptive step-length estimation
                    for pedestrian dead-reckoning at various walking speeds using a smartphone. Sensors, 16(9), 1423.

    :param fs: the sampling frequency
    :param peak_threshold: the peak threshold for detecting steps. The threshold is between [0, 1] and can be seen as
                           a percentage of the average peak height during the recording. Default: 0.6
    :param valley_threshold: The valley threshold for detecting steps. The threshold is between [0, 1] and can be seen as
                             a percentage of the average peak height during the recording. Default: 0.3
    :param w_size_moving_average_s: window size for moving average smoothing (in seconds). Default: 1
    :return: dictionary containing the step detection metrics. The dictionary has the following structure:
    :return:
    """

    # check whether the data comes from a continuous block (the block_id should be unique)
    if df_walk[BLOCK_ID_COLUMN_NAME].nunique() != 1:
        raise ValueError(f"The DataFrame must contain only walking data from a continuous block of walking."
                         f"\nObtained block_ids: {df_walk[BLOCK_ID_COLUMN_NAME].unique()}")

    # check whether there is any data that is not related to walking
    if (df_walk[ACTIVITY_COLUMN_NAME] != CLASS_WALK).any():
        raise ValueError(f"The DataFrame must contain only walking data."
                         f"\nObtained activities: {df_walk[ACTIVITY_COLUMN_NAME].unique()}")

    # copy the DataFrame
    df = df_walk.copy()

    # estimate the dominant frequency
    min_step_period = _calculate_minimum_step_period(df, fs=fs)

    # calculate heading changes (in degrees)
    # df[HEADING_ROTATION_COL] = _calculate_heading_rotational_changes(df)  # (currently not needed)

    # detect potential step candidates through peak and valley detection using the y-ACC
    peaks_idx, valleys_idx = _get_step_candidates(df[Y_ACC_COL].values, min_step_period=min_step_period,
                                                  peak_threshold=peak_threshold, valley_threshold=valley_threshold,
                                                  w_size_moving_average_s=w_size_moving_average_s)

    # check whether no peaks or valleys have been detected
    if len(peaks_idx) == 0 or len(valleys_idx) == 0:

        # set distance_walked and num_steps to zero
        distance_walked = 0
        num_steps = 0

    else:

        # apply valley correction to obtain valley-peak-valley pattern
        valleys_idx = _apply_valley_correction(df[Y_ACC_COL].values, peaks=peaks_idx, valleys=valleys_idx, min_step_period=min_step_period)

        # rotate acc data device- to world-frame
        xyz_acc = _rotate_device_to_world(df)

        # compute distance walked and number of steps
        distance_walked = _calculate_distance_walked(xyz_acc, peaks_idx=peaks_idx, valleys_idx=valleys_idx, fs=fs)
        num_steps = len(peaks_idx)


    return num_steps, distance_walked, (peaks_idx, valleys_idx)


def _calculate_minimum_step_period(df_walk: pd.DataFrame, fs: int = 100) -> int:
    """
    Obtains the minimum step period (in samples), by estimating the dominant walking frequency from the data contained
    in df. The dominant walking frequency is obtained through FFT.

    :param df_walk: pandas.DataFrame containing the phone's y-ACC, the corresponding HAR classification, as well as the
    block_ids for identifying continuous blocks of an activity. The df should only contain walking data corresponding
    to a continuous block of walking.
    :param fs: the sampling frequency
    :return: the minimum step period (in samples).
    """

    # check whether there is enough data
    if len(df_walk) < 2 * fs:

        print("Not enough walking data to compute frequency.")
        return int(fs * 0.5)  # Default fallback (0.5s = ~2Hz)

    # Detrend the walking signal to remove drift
    acc_y = detrend(df_walk[Y_ACC_COL].values)

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

    # Convert to minimum interval between peaks
    interval = fs / dominant_freq
    minimum_interval = int(interval * 0.5) # multiplying with 0.5 to also catch peaks in case the walking frequency increases during the recording

    return minimum_interval


def _calculate_heading_rotational_changes(df_walk: pd.DataFrame) -> np.ndarray:
    """
    Calculates the heading rotational changes (in degrees) for the walking data contained in df_walk.
    :param df_walk: pandas.DataFrame containing the phone's quaternion data for a continuous block of walking. The columns
                    of the quaternions contained in df_walk are expected to be [x, y, z, w].
    :return: pandas.Series containing the heading rotational changes (in degrees).
    """

    # convert quaternions to Rotation objects (from_quaternion expects x, y, z, w)
    rotations = R.from_quat(df_walk[QUATERNION_COLUMNS].values)

    # obtain the initial quaternion as the reference
    init_rotation = rotations[0]

    # compute relative difference between initial orientation and all subsequent
    relative_rotations = init_rotation.inv() * rotations

    # extract yaw rotation about the y-axis
    yaw = relative_rotations.as_euler('yxz', degrees=True)[:, 0]

    return yaw


def _get_step_candidates(y_acc: np.ndarray, min_step_period: int, fs=100, peak_threshold: float = 0.6, valley_threshold: float = 0.3,
                         w_size_moving_average_s: int = 1.5) -> Tuple[np.ndarray, np.ndarray]:
    """
    Performs a peak and valley detection on the y-ACC signal as initial candidates for step-detection. The algorithm performs
    the following steps:

    (1) Signal rectification
    (2) Application of moving average smoothing to obtain envelope
    (3) Calculation of height threshold for peak and valley detection
    (4) Peak detection
    (5) Valley detection

    Steps (1) and (2) are performed to obtain a threshold for peak and valley detection. The detection of peaks and
    valleys is performed in the unprocessed y-ACC signal.

    :param y_acc: y-acc signal corresponding to a continuous block of walking.
    :param min_step_period: the minimum period between two steps.
    :para fs: the sampling frequency of the signal (in Hz)
    :param peak_threshold: the peak threshold for detecting steps. The threshold is between [0, 1] and can be seen as
                           a percentage of the average peak height during the recording. Default: 0.6
    :param valley_threshold: The valley threshold for detecting steps. The threshold is between [0, 1] and can be seen as
                             a percentage of the average peak height during the recording. Default: 0.3
    :param w_size_moving_average_s: window size for moving average smoothing (in seconds). Default: 1
    :return: indices corresponding to the peaks and valley detection results on the y-ACC signal.
    """

    # (1) rectify signal
    y_acc_processed = abs(y_acc)

    # (2) apply moving average filter
    y_acc_processed = get_envelope(y_acc_processed, envelope_type='MA', type_param=int(w_size_moving_average_s * fs))

    # (3) calculate thresholds (adapt thresholds to envelope max)
    peak_threshold = np.max(y_acc_processed) * peak_threshold
    valley_threshold = np.max(y_acc_processed) * valley_threshold

    # (4) detect peaks and valleys on original signal
    peaks, _ = find_peaks(y_acc, height=peak_threshold, distance=min_step_period)
    valleys, _ = find_peaks((-1) * y_acc, height=valley_threshold, distance=min_step_period)

    # map the peaks and valleys to the original values
    return peaks, valleys


def _apply_valley_correction(y_acc: np.ndarray, peaks: np.ndarray, valleys: np.ndarray, min_step_period: int) -> np.ndarray:
     """
     Valley correction to obtain a valley-peak-valley structure in the obtained peak and valley candidates for step
     detection. The function handles the following cases:

     (1) Valley removal (two consecutive valleys without a peak in between):
         --> replace the two valleys by a one "new valley" that lies at the middle point between them

     (2) Valley insertion (two consecutive peaks with no valley in between):
         --> find the minimum between the two peaks and set it as the new valley

     :param y_acc: y-acc signal corresponding to a continuous block of walking.
     :param peaks: the peak candidates
     :param valleys: the valley candidates
     :param min_step_period: the minimum period between two steps.
     :return: numpy.array containing the corrected valley candidates.
     """

     # init list to hold the corrected valleys
     corrected_valleys = []

     # init the peak and valley index
     curr_peak_idx = 0
     curr_valley_idx = 0

     # get the number of detected peaks and valleys
     num_peaks = len(peaks)
     num_valleys = len(valleys)

     # cycle over the valleys
     while curr_valley_idx < num_valleys - 1:

         # obtain the next two valleys
         valley_1 = valleys[curr_valley_idx]
         valley_2 = valleys[curr_valley_idx + 1]

         # check whether the current peak is before the first valley
         while curr_peak_idx < num_peaks and peaks[curr_peak_idx] < valley_1:

             # go to the next peak index
             curr_peak_idx += 1

         # init the peak search
         start_peak_idx = curr_peak_idx

         # collect peaks until the next valley
         while curr_peak_idx < num_peaks and peaks[curr_peak_idx] < valley_2:
             curr_peak_idx += 1

         # obtain all peaks that lie between the two valleys
         peaks_between = peaks[start_peak_idx:curr_peak_idx]

         # case (1): no peak between valleys
         if len(peaks_between) == 0:

             # replace the two valleys by the midpoint between them
             corrected_valleys.append((valley_1 + valley_2) // 2)

             # update the valley index (skip the two valleys)
             curr_valley_idx += 2

         # case (2): two peaks between valleys
         if len(peaks_between) == 2 and (valley_2 - valley_1) > 2 * min_step_period:

             # get the corresponding peaks
             peak_1, peak_2 = peaks_between

             # obtain the corresponding signal segment
             signal_segment = y_acc[peak_1:peak_2 + 1]

             # find the minimum between the two peaks
             local_idx = np.argmin(signal_segment)

             # add the new valley to the corrected valleys
             corrected_valleys.append(peak_1 + local_idx)

             # update the valley index (skip the two valleys)
             curr_valley_idx += 2

         # normal case (just one peak between the two valleys
         else:

             # just add the first valley
             corrected_valleys.append(valley_1)

             # update the valley to the next valley
             curr_valley_idx += 1

     # append the last valley
     corrected_valleys.append(valleys[-1])

     return np.array(corrected_valleys)


def _rotate_device_to_world(df_walk: pd.DataFrame) -> np.ndarray:
    """
    Rotates the acceleration data contained in df_walk from the phone's coordinates to the world coordinates using
    the phone's quaternions for transformation. Since Android's rotation vector provides quaternions from representing
    the rotation from world to device, the inverse is applied to map the acceleration from phone to world-frame coordinates.
    :param df_walk: pandas.DataFrame containing the phone's ACC and ROT data corresponding to a continuous block of walking.
    :return: np.ndarray containing the rotated acceleration data.
    """

    # extract quaternions and acceleration as numpy arrays
    quats = df_walk[QUATERNION_COLUMNS].values
    accs = df_walk[ACC_COLUMNS].values

    # create rotation objects from quaternions
    rotations = R.from_quat(quats)

    # apply inverse rotation: phone -> world frame
    acc_world = rotations.inv().apply(accs)

    return acc_world


def _calculate_distance_walked(xyz_acc: np.ndarray, peaks_idx: np.ndarray, valleys_idx: np.ndarray, fs: int) -> float:
    """
    Estimate distance walked by integrating the data contained in xyz_acc for each performed step.

    For each step (defined as the interval between two consecutive valleys), the function:
    1. Integrates acceleration to obtain velocity of each axis
    2. Computes average velocity components
    3. Computes the velocity magnitude
    4. Derives the adaptive coefficient K_vel
    5. Estimates step length using the acceleration amplitude model

    :param xyz_acc: np.ndarray of shape [N, 3] containing the world-frame acceleration data corresponding to a continuous block of walking.
    :param peaks_idx: the indices of the detected peaks.
    :param valleys_idx: the indices of the detected valleys.
    :param fs: the sampling frequency in Hz.
    :return: the estimated distance walked for the provided data.
    """

    # init list for holding the estimated step lengths
    step_lengths = []

    # cycle over the valleys
    for pos in range(len(valleys_idx) - 1):

        # get two consecutive valleys
        valley_start = valleys_idx[pos]
        valley_end = valleys_idx[pos + 1]

        # check if there is really a peak between the two valleys (sanity check)
        peaks_between = peaks_idx[(peaks_idx > valley_start) & (peaks_idx < valley_end)]

        # skip over this segment in case there is no peak in between
        if len(peaks_between) == 0:
            continue


        # extract the segment of the acc data
        acc_step = xyz_acc[valley_start:valley_end + 1, :]

        # arrange time axis for integration
        t = np.arange(0, acc_step.shape[0]) / fs

        # integrate acceleration to obtain velocity
        v_step = cumtrpaz(acc_step, t, axis=0, initial=0.0)

        # calculate average velocity per axis
        v_avg_xyz = np.mean(v_step, axis=0)

        # calculate velocity magnitude
        v_avg = np.linalg.norm(v_avg_xyz)

        # calculate adaptive K_vel (equation 12 of the article)
        K_vel = 0.68 - 0.37 * v_avg + 0.15 * v_avg ** 2

        # obtain acceleration on the vertical axes (perpendicular to the floor, in PrevOccupAI it is the y-axis)
        acc_vertical = acc_step[:, 1]

        # compute A_max and A_min
        A_max = np.max(acc_vertical)
        A_min = np.min(acc_vertical)

        # calculate step length
        step_length = K_vel * (A_max - A_min) * 0.25

        # add step_length to the list
        step_lengths.append(step_length)

    # return the total distance walked (sum of step lengths)
    return np.sum(step_lengths)





