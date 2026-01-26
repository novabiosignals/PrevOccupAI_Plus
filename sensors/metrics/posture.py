"""
Functions to obtain posture related metrics, when the subject is seated at their desk

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
import os
from typing import Dict, Tuple
import pandas as pd
import numpy as np
import scipy as scp
from scipy.spatial.transform import Rotation as R
from scipy import stats

from HAR.classifier import BLOCK_ID_COLUMN_NAME
# internal imports
from constants import ACTIVITY_COLUMN_NAME, PHONE, ACC, GYR, MAG, ROT
from OH_profile.constants import POSTURE_ELLIPSE_KEY, POSTURE_SWAY_AREA_KEY, POSTURE_SWAY_VELOCITY_KEY, \
    POSTURE_SWAY_LENGTH_KEY, POSTURE_RANGE_RATIO_KEY, POSTURE_ML_RANGE_KEY, POSTURE_AP_RANGE_KEY

from HAR import classify_human_activities, CLASS_SIT
from utils import extract_date_from_path, create_dir
import sensors.load as sensor_loader
import sensors.process as sensor_processor


# ------------------------------------------------------------------------------------------------------------------- #
# file constants
# ------------------------------------------------------------------------------------------------------------------- #
QUATERNION_COLUMNS = [f'x_{ROT}', f'y_{ROT}', f'z_{ROT}', f'w_{ROT}']
STERNUM_FACTOR = 0.15
ROUND_DECIMALS = 2

DISPLACEMENT_FILE_NAME_SUFFIX = "displacements.npy"

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #
def get_posture_metrics(day_folder_path: str, fs: int, w_size_HAR: float, subject_id: str,
                        subject_height_m: float,displacement_store_path: str,
                        min_sitting_time_min = 5.0 ,yaw_range_limit_deg: float = 60.0,
                        ) -> Dict:
    """
    Extracts metrics related to seated posture. Before the extraction of metrics, the data is pre-processed and
    classified using a HAR model.
    :param day_folder_path: Path to the folder containing the all the acquisitions from an entire day.
    :param fs: The sampling frequency with which the data was acquired.
    :param w_size_HAR: The window size for HAR classification in seconds
    :param subject_id: The subject ID (as a string) as defined in the OH profile
    :param subject_height_m: The subject height in meters.
    :param min_sitting_time_min: the minimum sitting time in minutes that should be considered for performing posture analysis.
    :param yaw_range_limit_deg: the range of yaw angles to consider, to define which range is considered for posture analysis.
                                Only displacements that are within [-yaw_range, +yaw_range] in relation to the reference posture are considered.
    :param displacement_store_path: Path to the folder where the extracted displacement matrices should be stored.
    :return: dictionary containing the extracted posture metrics. The dictionary has the following structure:

    {"DD-MM-YYYY": {
        "HH-MM-SS": {
             "posture_data_path": ...,
             "posture_ap_range": ...,
             "posture_ml_range": ...,
             "posture_ratio_range": ...,
             "posture_total_sway_length": ...,
             "posture_average_sway_velocity": ...,
             "posture_sway_area_per_second": ...,
             "posture_95_confidence_ellipse_area": ...,

            }
    """

    # get date from path
    acquisition_date = extract_date_from_path(day_folder_path)

    # reformate to dd-mm-yyyy
    year, month, day = acquisition_date.split('-')
    acquisition_date = f"{day}-{month}-{year}"

    # init dict for holding the extracted metrics
    day_metrics_dict = {acquisition_date: {}}

    # load the acquisition(s) for the day
    df_dict = sensor_loader.load_daily_acquisitions(day_folder_path, load_devices={PHONE: [ACC, GYR, MAG, ROT]})

    # pre-proces the data
    processed_df_dict = sensor_processor.apply_pre_processing_pipeline(df_dict)

    # classify the data
    processed_df_dict[PHONE] = classify_human_activities(processed_df_dict[PHONE], w_size=w_size_HAR, fs=fs)

    # cycle over the dictionary containing the phone data (usually there is only one acquisition, but multiple can happen)
    for acquisition_time, df in processed_df_dict[PHONE].items():

        # check whether the DataFrame contains data
        if not df.empty:

            # extract posture metrics
            metrics_dict, displacement_matrix = _calculate_posture_metrics(df, subject_height_m=subject_height_m, fs=fs,
                                                                           min_sitting_time_min=min_sitting_time_min,
                                                                           yaw_range_limit_deg=yaw_range_limit_deg)

            # store displacement matrix
            _save_displacement_data(displacement_matrix, subject_id=subject_id,
                                    displacement_store_path=displacement_store_path,
                                    acquisition_date=acquisition_date, acquisition_time=acquisition_time)

        else:

            # set metrics_dict to empty if no data
            metrics_dict = {}

        # add the extracted metrics to the day_metrics dictionary
        day_metrics_dict[acquisition_date][acquisition_time] = metrics_dict

    return day_metrics_dict


# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #
def _calculate_posture_metrics(df: pd.DataFrame, subject_height_m: float, fs: int, min_sitting_time_min = 5.0,
                               yaw_range_limit_deg: float = 60) -> Tuple[Dict, np.ndarray]:
    """
    Calculates posture-related metrics and processes the data contained in df to store it later for more efficient
    plotting. The df should contain at least the phone's quaternion data: ['x_ROT', 'y_ROT', 'z_ROT', 'w_ROT'].
    The following metrics are calculated:
    :param df: :param df: pandas.DataFrame containing the phone data and the corresponding HAR classification
    :param fs: the sampling frequency
    :param min_sitting_time_min: the minimum sitting time in minutes that should be considered for performing posture analysis
    :param yaw_range_limit_deg: the range of yaw angles to consider, to define which range is considered for posture analysis.
                                Only displacements that are within [-yaw_range, +yaw_range] in relation to the reference posture are considered.
    :return: dictionary containing the posture related metrics. The dictionary has the following structure:

    {
    "posture_ap_range": ...,
    "posture_ml_range": ...,
    "posture_ratio_range": ...,
    "posture_total_sway_length": ...,
    "posture_average_sway_velocity": ...,
    "posture_sway_area_per_second": ...,
    "posture_95_confidence_ellipse_area": ...,
    }
    """

    # init dict for storing results
    metrics_dict: Dict[str, float] = {}

    # list to hold the displacement matrices
    displacement_matrices = []

    # filter DataFrame for sitting instances
    df_posture_analysis = df[df[ACTIVITY_COLUMN_NAME] == CLASS_SIT]

    # get quaternions from DataFrame
    quaternions = df_posture_analysis[QUATERNION_COLUMNS].values

    # obtain rotation matrices and reference rotation posture
    ref_rotation = _get_reference_rotation(quaternions)

    # counter for averaging
    num_blocks = 0

    # cycle over the block_ids to obtain metrics per activity block
    for block_num, block_df in df_posture_analysis.groupby([BLOCK_ID_COLUMN_NAME]):

        # get the quaternions of the current block
        block_quaternions = block_df[QUATERNION_COLUMNS].values

        # obtain postural displacement
        block_displacement_matrix = _calculate_postural_displacement(block_quaternions, ref_rotation,
                                                                     subject_height_m=subject_height_m,
                                                                     yaw_range_limit=yaw_range_limit_deg)

        # check whether there are values in the displacement matrix
        # this would be the case if the subject would not be facing the computer outside of yaw range limit
        if block_displacement_matrix.size * (1/fs) < min_sitting_time_min * 60:
            continue

        # extract the posture metrics from the displacement matrix
        block_metrics_dict = _extract_postural_features(block_displacement_matrix, fs=fs)

        # init the metrics dict with values of the first iteration
        if not metrics_dict:
            metrics_dict = block_metrics_dict.copy()

        # add displacement matrix to the list
        displacement_matrices.append(block_displacement_matrix)

        # update the metrics dictionary
        metrics_dict[POSTURE_AP_RANGE_KEY] = max(metrics_dict[POSTURE_AP_RANGE_KEY],
                                                 block_metrics_dict[POSTURE_AP_RANGE_KEY])
        metrics_dict[POSTURE_ML_RANGE_KEY] = max(metrics_dict[POSTURE_ML_RANGE_KEY],
                                                 block_metrics_dict[POSTURE_ML_RANGE_KEY])
        metrics_dict[POSTURE_SWAY_LENGTH_KEY] = metrics_dict[POSTURE_SWAY_LENGTH_KEY] + block_metrics_dict[
            POSTURE_SWAY_LENGTH_KEY]
        metrics_dict[POSTURE_SWAY_VELOCITY_KEY] = metrics_dict[POSTURE_SWAY_VELOCITY_KEY] + block_metrics_dict[
            POSTURE_SWAY_VELOCITY_KEY]
        metrics_dict[POSTURE_SWAY_AREA_KEY] = metrics_dict[POSTURE_SWAY_AREA_KEY] + block_metrics_dict[
            POSTURE_SWAY_AREA_KEY]
        metrics_dict[POSTURE_ELLIPSE_KEY] = metrics_dict[POSTURE_ELLIPSE_KEY] + block_metrics_dict[POSTURE_ELLIPSE_KEY]

        # update counter
        num_blocks += 1


    # calculate range ratio
    metrics_dict[POSTURE_RANGE_RATIO_KEY] = metrics_dict[POSTURE_ML_RANGE_KEY] /metrics_dict[POSTURE_AP_RANGE_KEY]

    # calculate means
    metrics_dict[POSTURE_SWAY_VELOCITY_KEY] = metrics_dict[POSTURE_SWAY_VELOCITY_KEY] / num_blocks
    metrics_dict[POSTURE_SWAY_AREA_KEY] = metrics_dict[POSTURE_SWAY_AREA_KEY] / num_blocks
    metrics_dict[POSTURE_ELLIPSE_KEY] = metrics_dict[POSTURE_ELLIPSE_KEY] / num_blocks

    # concatenate the displacement matrices
    displacement_matrix = np.concatenate(displacement_matrices, axis=0)

    # round the metrics
    _round_metrics(metrics_dict, ROUND_DECIMALS)

    return metrics_dict, displacement_matrix

def _get_reference_rotation(quaternions: np.ndarray) -> R:
    """
    Gets the reference rotation. The reference rotation is calculated as the mean of all rotations. This reference
    rotation is the estimate for the orientation in which the subject remains most of the time when sitting at the desk.

    :param quaternions: np.ndarray of shape [N, 4] containing quaternions in the order [x, y, z, w].
    :return: Tuple containing the rotation matrices corresponding to the provided quaternions and the reference rotation.
    """

    # convert quaternions to Rotation object
    rotations = R.from_quat(quaternions)

    # obtain mean rotation (as estimate for 'standard subject posture')
    ref_rotation = rotations.mean()

    return ref_rotation


def _calculate_postural_displacement(quaternions: np.ndarray, ref_rotation: R, subject_height_m: float, yaw_range_limit: float = 60.0) -> np.ndarray:
    """
    calculates displacement in anterior-posterior, mediolateral and vertical direction, from quaternions and the subject's
    torso length. The calculation of displacement is done through Euler angles obtained from the quaternions.

    Torso length is estimated from subject height as torso_length =  15 % * subject_height.
    This estimation is based on
    Bardeen, C. R. (1923). General relations of sitting height to stature and of sitting height and stature to weight.
    American Journal of Physical Anthropology, 6(4), 355–374. https://doi.org/10.1002/ajpa.1330060403
    The article states that sitting height is approx. 52% of total stature, thus, assuming that the sternum is roughly
    at the midpoint of the seated trunk, the factor is set at 15 %.


    The function makes the following assumptions:
    - quaternions contains only data corresponding to instances when the subject is sitting.
    - the phone is rigidly attached to the sternum
    - the mean of all rotation corresponds to the subject's personal 'standard posture' (posture in which the subject remains most of the time)
    - displacement calculations are made in reference to the subject's 'standard posture'
    - trunk displacement is modeled as rotation of a rigid body with the origin of rotation at the center of pressure
      when seated (i.e., pelvis)

    Given the placement of the phone on the subject's chest, the rotations are defined as follows:
    (1) x-axis: pitch
    (2) y-axis: yaw
    (3) z-axis: roll

    The displacement is calculated as follows:
    (1) medio-lateral displacement (left-right): d_ml = L * sin(roll)
    (2) anterior-posterior displacement (front-back): d_ap = L * sin(pitch)
    (3) vertical displacement (top-down): d_vert = - L * (1 - np.cos(roll) * cos(pitch))

    :param quaternions: np.ndarray of shape [N, 4] containing quaternions in the order [x, y, z, w].
    :param ref_rotation: reference rotation, corresponding to the main orientation of the subject, when sitting.
    :param subject_height_m: the subject height in meters
    :param yaw_range_limit: the range of yaw angles to consider, to define which range is considered for posture analysis.
                            Only displacements that are within [-yaw_range, +yaw_range] in relation to the reference posture are considered.
    :return: np.ndarray containing the displacement in anterior-posterior, lateral and vertical direction
    [d_AP, d_LAT, d_VERT], centered around the subjects 'standard posture'.
    """

    # estimate torso length
    trunk_length = STERNUM_FACTOR * subject_height_m

    # convert quaternions to Rotation object
    rotations = R.from_quat(quaternions)

    # invert yaw axis to have correct displacement
    #raw_euler = rotations.as_euler('xyz', degrees=False)
    #raw_euler[:, 1] = (-1) * raw_euler[:, 1]
    #rotations = R.from_euler('xyz', raw_euler, degrees=False)

    # compute relative difference between to reference orientation
    relative_rotations = ref_rotation.inv() * rotations

    # obtain euler angles
    xyz_euler_angles = relative_rotations.as_euler('yxz', degrees=False)

    # obtain pitch and roll angles
    yaw = xyz_euler_angles[:, 0]  # x-axis
    pitch = xyz_euler_angles[:, 1]  # y-axis
    roll = xyz_euler_angles[:, 2]  # z-axis

    # convert y-axis to degrees
    yaw_deg = np.rad2deg(yaw)

    # create mask to filter out all yaw angles that are outside limit
    valid_angles = np.abs(yaw_deg) < yaw_range_limit
    valid_pitch = pitch[valid_angles]
    valid_roll = roll[valid_angles]

    # calculate displacement
    #TODO add chest displacement (disance phone to spine -> the rotation axis is the spine)
    d_ap = trunk_length * np.sin(valid_pitch)
    d_lat = trunk_length * np.sin(valid_roll)
    d_vert = -trunk_length * (1.0 - np.cos(valid_roll) * np.cos(valid_pitch))

    return np.column_stack((d_ap, -d_lat, d_vert))


def _extract_postural_features(displacement_matrix: np.ndarray, fs: int) -> Dict:
     """
     Calculates several postural features based on the anterior-posterior (AP) and mediolateral (ML) displacement data \
     contained in displacement matrix. The calculated features are based on:

     Quijoux, F., Nicolaï, A., Chairi, I., Bargiotas, I., Ricard, D., Yelnik, A., ... & Audiffren, J. (2021).
     A review of center of pressure (COP) variables to quantify standing balance in elderly people:
     Algorithms and open‐access code. Physiological reports, 9(22), e15067.

     The following features are extracted:
     (1) AP-range, ML-range, range ratio (table 3)
     (2) total sway length, average sway velocity (table 4)
     (3) sway area per second (table 4)
     (4) confidence ellipse area (table 3)

     :param displacement_matrix: np.ndarray containing the anterior-posterior, medio-lateral, and vertical displacement
                                 [d_AP, d_LAT, d_VERT]
     :param fs: the sampling frequency in Hz
     :return: Dictionary containing the postural features. The dictionary has the following structure:

     """

     # define metrics dict
     metrics_dict = {}

     # calculate AP and ML range, as well as range ratio
     ap_range, ml_range, range_ratio = _get_movement_range(displacement_matrix)

     # calculate sway length and average sway velocity
     total_sway_length, average_sway_velocity = _get_total_sway_length(displacement_matrix, fs=fs)

     # calculate sway area per second
     sway_area_per_second = _get_sway_area_per_second(displacement_matrix, fs=fs)

     # calculate confidence ellipse area
     confidence_ellipse_area = _get_confidence_ellipse_area(displacement_matrix)

     # add the metrics to the dict
     metrics_dict[POSTURE_AP_RANGE_KEY] = ap_range
     metrics_dict[POSTURE_ML_RANGE_KEY] = ml_range
     metrics_dict[POSTURE_RANGE_RATIO_KEY] = range_ratio
     metrics_dict[POSTURE_SWAY_LENGTH_KEY] = total_sway_length
     metrics_dict[POSTURE_SWAY_VELOCITY_KEY] = average_sway_velocity
     metrics_dict[POSTURE_SWAY_AREA_KEY] = sway_area_per_second
     metrics_dict[POSTURE_ELLIPSE_KEY] = confidence_ellipse_area

     return metrics_dict



def _get_movement_range(displacement_matrix: np.ndarray) -> Tuple[float, float, float]:
    """
    Calculates the range of movement in anterior-posterior and mediolateral direction, as well as the ratio between them.
    These features capture:
    - extreme forward/backward or sideward leaning
    - asymmetry
    
    :param displacement_matrix: np.ndarray containing the anterior-posterior, medio-lateral, and vertical displacement
                                [d_AP, d_LAT, d_VERT]
    :return: tuple containing the AP_range, LAT_range, and the ratio between them
    """

    # get AP and ML displacement
    ap_displacement = displacement_matrix[:, 0]
    ml_displacement = displacement_matrix[:, 1]

    # calculate the range
    ap_range = np.abs(np.max(ap_displacement) - np.min(ap_displacement))
    ml_range = np.abs(np.max(ml_displacement) - np.min(ml_displacement))

    # calculate ratio
    range_ratio = ml_range / ap_range

    return ap_range, ml_range, range_ratio


def _get_total_sway_length(displacement_matrix: np.ndarray, fs: int) -> Tuple[float, float]:
    """
    Calculates the total sway length as well as the average sway velocity.

    These features capture:
    - total amount of movement
    - average distance per second

    :param displacement_matrix: np.ndarray containing the anterior-posterior, medio-lateral, and vertical displacement
                                [d_AP, d_LAT, d_VERT]
    :param fs: the sampling frequency in Hz
    :return: tuple containing the total sway length and the average sway velocity.
    """

    # get only AP and LAT columns
    ap_lat = displacement_matrix[:, :2]

    # get number of samples
    n_samples = displacement_matrix.shape[0]


    # calculate difference
    diff = np.diff(ap_lat, axis=0)

    # calculate total sway length
    total_sway_length = np.sum(np.linalg.norm(diff, axis=1))

    # calculate average sway velocity
    average_sway_velocity = total_sway_length * (fs / (n_samples - 1))

    return total_sway_length, average_sway_velocity


def _get_sway_area_per_second(displacement_matrix: np.ndarray, fs: int) -> Tuple[float]:
    """
    calculates the sway area per second.

    This feature captures:
    - dynamic postural activity

    :param displacement_matrix: np.ndarray containing the anterior-posterior, medio-lateral, and vertical displacement
                                [d_AP, d_LAT, d_VERT]
    :param fs: the sampling frequency in Hz
    :return: the sway area per second
    """

    # get AP and ML displacement
    ap_displacement = displacement_matrix[:, 0]
    ml_displacement = displacement_matrix[:, 1]

    # get number of samples
    num_samples = displacement_matrix.shape[0]

    # calculate the sway area (shoelace formula)
    sway_area = np.sum(np.abs(ml_displacement[1:] * ap_displacement[:-1] - ml_displacement[:-1] * ap_displacement[1:]))

    # calculate sway area per second
    sway_area_per_second = 0.5 * (fs / (num_samples - 1))  * sway_area

    return sway_area_per_second


def _get_confidence_ellipse_area(displacement_matrix: np.ndarray) -> float:
    """
    calculates the confidence ellipse area.

    This feature captures:
    - overall area covered in which the subject remains the majority of the time
    :param displacement_matrix: np.ndarray containing the anterior-posterior, medio-lateral, and vertical displacement
                                [d_AP, d_LAT, d_VERT]
    :return: confidence ellipse area
    """

    # get number of samples
    n_samples = displacement_matrix.shape[0]

    # define scalar
    scalar = 2 * np.pi *((n_samples - 1)/(n_samples - 2))

    # define confidence and calculate quantiles
    confidence = 0.95
    quantiles = stats.f.ppf(confidence, 2, n_samples - 2)

    # get AP and ML displacement
    ap_displacement = displacement_matrix[:, 0]
    ml_displacement = displacement_matrix[:, 1]

    # calculate covariance
    covariance = (1 / n_samples) * np.sum(ap_displacement * ml_displacement)

    # calculate RMS
    ap_rms = np.sqrt(np.mean(ap_displacement ** 2))
    ml_rms = np.sqrt(np.mean(ml_displacement ** 2))

    # calculate confidence ellipse area
    confidence_ellipse_area = scalar * quantiles * np.sqrt(ap_rms * ml_rms - covariance)

    return confidence_ellipse_area


def _save_displacement_data(displacement_matrix: np.ndarray, subject_id: str, displacement_store_path: str,
                            acquisition_date: str, acquisition_time: str) -> None:
    """
    Saves the displacement matrix for the subject. The file is stored as:
    {subject_id}_{acquisition_date}_{acquisition_time}_displacement_matrix.npy

    :param displacement_matrix: np.ndarray containing the anterior-posterior, medio-lateral, and vertical displacement
                                [d_AP, d_LAT, d_VERT].
    :param subject_id: the subject ID (as string).
    :param displacement_store_path: path to where the displacement matrix should be stored.
    :param acquisition_date: date of the acquisition (as string).
    :param acquisition_time: time of the acquisition (as string).
    :return:
    """

    # generate output path and filename
    subject_displacement_path = create_dir(displacement_store_path, subject_id)
    file_name = f"{subject_id}_{acquisition_date}_{acquisition_time}_{DISPLACEMENT_FILE_NAME_SUFFIX}"

    # inform user
    print(f"Saving displacement matrix to: {os.path.join(subject_displacement_path, file_name)}")

    # store file
    np.save(os.path.join(subject_displacement_path, file_name), displacement_matrix)


def _round_metrics(metrics_dict: Dict, decimals: int = 2) -> None:
    """
    function for rounding the metrics
    :param metrics_dict: dictionary containing the posture metrics
    :param decimals: the amount of decimals to round to
    :return: None
    """

    # round the values
    for key, value in metrics_dict.items():

        if key == POSTURE_SWAY_AREA_KEY:

            metrics_dict[key] = np.round(value, 5)

        else:
            metrics_dict[key] = np.round(value, decimals)


# TODO: remove once finished
###### test function for plotting
# function for plotting
import matplotlib.pyplot as plt
def plot_postural_displacement(displacement: np.ndarray) -> None:
    """
    Plots torso displacement projections from three standard viewpoints.

    The input array is expected to contain displacement components expressed
    in meters, ordered as:

    - Column 0: Anterior–Posterior displacement (AP)
    - Column 1: Lateral displacement (LAT)
    - Column 2: Vertical displacement (VERT)

    Three views are plotted using a 1×3 subplot layout:

    1. Top view   : AP vs LAT   (horizontal plane)
    2. Side view  : AP vs VERT  (sagittal plane)
    3. Back view  : LAT vs VERT (frontal plane)

    :param displacement: NumPy array of shape (N, 3) containing
                         [d_AP, d_LAT, d_VERT].
    """

    if displacement.ndim != 2 or displacement.shape[1] != 3:
        raise ValueError(
            "displacement must be a NumPy array of shape (N, 3) "
            "containing [d_AP, d_LAT, d_VERT]."
        )

    d_ap = displacement[:, 0]
    d_lat = displacement[:, 1]
    d_vert = displacement[:, 2]

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    # --- Top view: AP vs LAT ---
    axes[0].plot(d_lat, d_ap, linewidth=1)
    axes[0].set_title("Top View (LAT–AP)")
    axes[0].set_ylabel("Anterior–Posterior displacement [m]")
    axes[0].set_xlabel("Lateral displacement [m]")
    axes[0].axis("equal")
    axes[0].grid(True)

    # --- Side view: AP vs VERT ---
    axes[1].plot(d_ap, d_vert, linewidth=1)
    axes[1].set_title("Side View (AP–VERT)")
    axes[1].set_xlabel("Anterior–Posterior displacement [m]")
    axes[1].set_ylabel("Vertical displacement [m]")
    axes[1].axis("equal")
    axes[1].grid(True)

    # --- Back view: LAT vs VERT ---
    axes[2].plot(d_lat, d_vert, linewidth=1)
    axes[2].set_title("Back View (LAT–VERT)")
    axes[2].set_xlabel("Lateral displacement [m]")
    axes[2].set_ylabel("Vertical displacement [m]")
    axes[2].axis("equal")
    axes[2].grid(True)

    plt.tight_layout()
    plt.show()








