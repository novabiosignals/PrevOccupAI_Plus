"""
Functions to classify human activities from smartphone sensor data using a trained Random Forest model.

Available Functions
-------------------
[Public]
classify_human_activities(...): Classifies human activities from smartphone sensor data.
-------------------
[Private]
_apply_classification_pipeline(...): Applies the full classification pipeline, including threshold tuning and heuristics-based label correction.
_threshold_tuning(...): Adjusts model predictions to reduce confusion between 'stand' and 'sit' based on a probability threshold.
_heuristics_correction(...): Post-processes predicted labels to correct short-duration segments.
_expand_classification(...): Expands windowed predictions to match the original signal length.
_correct_short_segments(...): Replaces short segments of a specific class with the most frequent neighboring class.
_find_class_segments(...): Finds contiguous segments of a target class in a prediction array.
"""
# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from typing import Tuple, List, Dict, Union
from collections import Counter
import pandas as pd
import copy
from pathlib import Path
import os

# internal imports
from .feature_extractor import extract_features, trim_data
from .load import load_production_model
from constants import ACC, GYR, MAG, ACTIVITY_COLUMN_NAME

# ------------------------------------------------------------------------------------------------------------------- #
# constants
# ------------------------------------------------------------------------------------------------------------------- #
SENSORS_TO_LOAD = [ACC, GYR, MAG] # sensors to extract features from

HAR_MODEL = "HAR_model_500.joblib"
BLOCK_ID_COLUMN_NAME = 'block_id'  # TODO move this to constants

CLASS_WALK = 2
CLASS_STAND = 1
CLASS_SIT = 0

PROB_THRESHOLD = 0.85 # threshold for probability thresholding
MIN_DURATIONS = {0: 20, 1: 30, 2: 5} # durations for 0 (sitting), 1 (standing), 2 (walking)

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #
def classify_human_activities(phone_data_dict: Dict[str, pd.DataFrame], w_size: float = 5.0,
                              fs: int = 100) -> Dict[str, pd.DataFrame]:
    """
    Classifies human activities from smartphone sensor data.

    This function iterates over a dictionary of daily acquisitions, extracts features
    from each dataframe using TSFEL, and classifies the data. Classes are: 0 (sitting), 1 (standing), 2 (walking).
    After classification, a column with the prediction is added to the original dataframe with the smartphone signals.

    :param phone_data_dict: Dictionary with the acquisition time as keys and the sensor dataframes as values
    :param w_size: the window size in seconds that should be used for windowing the data. Default: 5.0
    :param fs: the sampling rate (in Hz) of the data
    :return: Dictionary with the acquisition times as keys and the sensor dataframes with the added prediction column
            as values.
    """
    # create copy of the dictionary to avoid overwriting any results_questionnaires
    classified_dict = copy.deepcopy(phone_data_dict)

    # inform user
    print("\n# ------------------------------------------------------------------------ #")
    print(f"# ------------------ performing HAR classification  ------------------- #")
    print("# ------------------------------------------------------------------------ #")
    # load HAR the model
    model, model_features = load_production_model(os.path.join(Path(__file__).parent, HAR_MODEL))

    # cycle over the dictionary with the daily acquisitions for the phone
    for acquisition_time, df in phone_data_dict.items():

        # extract features using TSFEL
        features_df = extract_features(df, sensors_to_load=SENSORS_TO_LOAD,w_size=w_size, fs=fs)

        # check if there are any missing features required for the classifier
        missing_features = [f for f in model_features if f not in features_df.columns]
        if missing_features:
            raise ValueError(f"Missing required features for the model: {missing_features}. ")

        # inform user
        print(f"--> classifying data (acquisition time: {acquisition_time})")

        # classify activities
        _, y_pred_exp = _apply_classification_pipeline(features_df[model_features], model, w_size=w_size, fs=fs,
                                                       threshold=PROB_THRESHOLD, min_durations=MIN_DURATIONS)

        # trim df with the phone signals to add the prediction column
        sensor_data, _ = trim_data(df.to_numpy(), w_size=w_size, fs=fs)

        # convert back to pandas dataframe
        df = pd.DataFrame(sensor_data, columns=df.columns)

         # add column to dataframe
        df[ACTIVITY_COLUMN_NAME] = y_pred_exp

        # add block IDs based on changes in activity
        df[BLOCK_ID_COLUMN_NAME] =  (df[ACTIVITY_COLUMN_NAME] != df[ACTIVITY_COLUMN_NAME].shift()).cumsum()

        # add to dict
        classified_dict[acquisition_time] = df

    return classified_dict


# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #
def _apply_classification_pipeline(features: np.ndarray, har_model: RandomForestClassifier, w_size: float,
                                   fs: int, threshold: float, min_durations: Dict[int, int]) -> Tuple[np.ndarray, List[int]]:
    """
    Applies classification pipeline. The classification pipeline consists of:

    1. Perform classification using a Random Forest
    2. Apply threshold tuning label correction
    3. Apply heuristics-based label correction

    :param features: numpy.array of shape (n_samples, n_features) containing the features
    :param har_model: object from RandomForestClassifier
    :param w_size: window size in seconds
    :param fs: the sampling frequency
    :param threshold: The probability margin threshold for adjusting predictions. Default is 0.1.
    :param min_durations: Dictionary mapping each class label to its minimum segment duration in seconds.
    :return: A tuple containing:
        - List[int]: Labels for each window.
        - List[int]: Labels expanded to the original sampling frequency
    """

    # classify the data - vanilla model
    y_pred = har_model.predict(features)

    # get class probabilities
    y_pred_proba = har_model.predict_proba(features)

    # apply threshold tuning
    y_pred_tt = _threshold_tuning(y_pred_proba, y_pred, 0, 1, threshold)

    # combine tt with heuristics
    y_pred_tt_heur = _heuristics_correction(y_pred_tt, w_size, min_durations)

    # expand the predictions to the size of the original signal
    y_pred_tt_heur_expanded = _expand_classification(y_pred_tt_heur, w_size=w_size, fs=fs)

    return y_pred_tt_heur, y_pred_tt_heur_expanded


def _threshold_tuning(probabilities: np.ndarray, y_pred: Union[np.ndarray, list],
                     sit_label: int = 0, stand_label: int = 1, threshold: float = 0.1) -> np.ndarray:
    """
    Adjusts predictions for a classifier by reducing confusion between 'stand' and 'sit'.

    If the model predicts 'stand' (class 1) and the difference in predicted probability
    between 'stand' and 'sit' (class 0) is less than the given threshold, the prediction
    is changed to 'sit'.

    :param probabilities: numpy.array of shape (n_samples, n_classes) containing the predicted probabilities
    :param y_pred: array containing the predicted class labels (as integers)
    :param sit_label: Class label for 'sit'. Default is 0.
    :param stand_label: Class label for 'stand'. Default is 1.
    :param threshold: The probability margin threshold for adjusting predictions. Default is 0.1.
    :return: numpy.ndarray containing the adjusted class label predictions
    """
    adjusted = []
    for i, probs in enumerate(probabilities):
        pred = y_pred[i]

        # Apply adjustment only if model predicted 'stand'
        if pred == stand_label:
            p_stand = probs[stand_label]
            p_sit = probs[sit_label]
            if (p_stand - p_sit) < threshold:
                pred = sit_label  # Change prediction to 'sit'

        adjusted.append(pred)

    return np.array(adjusted)


def _heuristics_correction(predictions: np.ndarray, window_size: float, min_durations: Dict[int, float]) -> np.ndarray:
    """
    Apply post-processing to correct short activity segments for each class.

    :param predictions: 1D array of predicted class labels.
    :param window_size: Duration of each prediction window in seconds.
    :param min_durations: Dictionary mapping each class label to its minimum segment duration in seconds.
    :return: Post-processed prediction array with short segments corrected.
    """
    corrected = predictions.copy()

    # Apply correction for each class using the specified minimum duration
    for class_id, min_duration in min_durations.items():
        corrected = _correct_short_segments(corrected, class_id, min_duration, window_size)

    return corrected


def _expand_classification(clf_result: np.ndarray, w_size: float, fs: int) -> List[int]:
    """
    Converts the time column from the android timestamp which is in nanoseconds to seconds.
    Parameters.
    :param clf_result: list with the classifier prediction where each entry is the prediction made for a window.
    :param w_size: the window size in samples that was used to make the classification.
    :param fs: the sampling frequency of the signal that was classified.
    :return: the expanded classification results_questionnaires.
    """

    expanded_clf_result = []

    # cycle over the classification results_questionnaires list
    for i, p in enumerate(clf_result):
        expanded_clf_result += [p] * int(w_size * fs)

    return expanded_clf_result


def _correct_short_segments(predictions: np.ndarray, class_id: int, min_duration: float, window_size: float) -> np.ndarray:
    """
    Replace segments of a specific class that are shorter than a given duration.

    The replacement class is chosen as the most frequent class from neighboring values.

    :param predictions: 1D array of predicted class labels.
    :param class_id: Class to check for short-duration segments.
    :param min_duration: Minimum acceptable duration for a segment in seconds.
    :param window_size: Duration of each prediction window in seconds.
    :return: Updated prediction array with short segments replaced.
    """

    # get the segments for the class
    segments = _find_class_segments(predictions, class_id)
    corrected = predictions.copy()

    # cycle over the segments
    for start, end in segments:

        # calculate the segment lengths in seconds
        duration = (end - start + 1) * window_size

        # check whether the segment needs to be corrected (too short)
        if duration < min_duration:
            # Get neighbor classes
            left = predictions[start - 1] if start > 0 else None
            right = predictions[end + 1] if end < len(predictions) - 1 else None

            neighbors = [c for c in (left, right) if c is not None]
            if neighbors:

                # in case the left and the right neighbor are from different
                # classes then the left neighbor (i.e., the previous activity - chronologically) is chosen
                replacement = Counter(neighbors).most_common(1)[0][0]
                corrected[start:end + 1] = replacement

    return corrected


def _find_class_segments(predictions: np.ndarray, target_class: int) -> List[Tuple[int, int]]:
    """
    Find start and end indices of contiguous segments belonging to the target class.

    :param predictions: 1D array of predicted class labels.
    :param target_class: Class label to find segments for.
    :return: List of tuples, where each tuple is (start_idx, end_idx) of a segment.
    """

    # list for holding the segments
    segments = []

    # init variables
    in_segment = False
    start = 0

    # cycle over the predictions
    for i, pred in enumerate(predictions):

        # check whether current prediction corresponds to the target class
        if pred == target_class:

            # start counting the segment
            if not in_segment:
                in_segment = True
                start = i
        else:
            # end the segment
            if in_segment:
                segments.append((start, i - 1))
                in_segment = False

    # when reaching the end, assign the end of the prediction array as the stop
    if in_segment:
        segments.append((start, len(predictions) - 1))

    return segments