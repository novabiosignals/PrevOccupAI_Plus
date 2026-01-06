"""
Functions to extract, compute, and classify heart rate (HR) metrics from wearable sensor data.

Available Functions
-------------------
[Public]
get_global_heart_rate_metrics(...): Extract global HR reference metrics across all acquisitions.
get_heart_rate_metrics(...): Extract daily and per-session HR metrics from a full day of data.
-------------------

[Private]
_calculate_hr_metrics_per_acquisition(...): Compute HR metrics and class counts for one acquisition.
_calculate_hr_ratio(...): Compute heart rate ratio (HRR) and HRR class labels.
_classify_hr_ratio(...): Classify HRR values for sitting activity only.
_calculate_timeline_metrics(...): Compress HR class labels into contiguous time ranges.
_calculate_statistics(...): Compute summary statistics for a numeric column.
_calculate_heart_rate_class_proportions(...): Compute HR class proportions ignoring 'no data'.
_count_hr_classes(...): Count HR class occurrences per acquisition.
_calculate_daily_class_proportions(...): Aggregate HR class proportions across acquisitions.
_get_min_heart_rate(...): Compute minimum HR across all acquisitions.
_get_max_heart_rate(...): Estimate maximum HR from subject age.
_et_heart_rate_statistics(...): Compute basic HR and HRR statistics.
_extract_features_heart_rate(...): Extract per-acquisition HR features and class proportions.
_split_df_by_non_nan_blocks(...): Split a DataFrame into contiguous non-NaN acquisition blocks.
-------------------
"""
# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import os
from typing import Dict, List, Tuple
import pandas as pd
from utils import extract_date_from_path

# internal imports
import HAR
import sensors.load as sl
import sensors.process as sp
from constants import (ACTIVITY_COLUMN_NAME, HR_RATIO_COLUMN_NAME, HR_CLASS_COLUMN_NAME, WATCH_SUFFIX, ACC, GYR, MAG,
                       PHONE, WATCH, HEART)
from OH_profile.constants import HR_RELATIVE_BASE_KEY
# ------------------------------------------------------------------------------------------------------------------- #
# constants
# ------------------------------------------------------------------------------------------------------------------- #

# sensors to be loaded which are strictly needed for the HR plot
selected_sensors = {PHONE: [ACC, GYR, MAG], # for HAR
                    WATCH: [ACC,HEART]} # ACC to fill with NaN when the HR is not acquiring - do not remove ACC


# heart rate ratio per activity
NORMAL_RANGES = {
    0: (0.0, 30),
}

# Margin used to define "potentially abnormal" outside the normal range for heart rate ratio
POTENTIALLY_ABNORMAL_MARGIN = 9

# HR classes
NORMAL = 'Normal'
POTENTIALLY_ELEVATED = 'Ligeiramente elevado'
ELEVATED = 'Elevado'

# keys for the inner dictionaries with the HR features
HR_METRICS_SESSION = 'HR_metrics_session'
HR_PROPORTIONS_SESSION = 'HR_distributions_session'
HR_DISTRIBUTIONS_DAY = 'HR_distributions_day'
HR_TIMELINE = 'HR_timeline'
HR_RATIO_STATS = 'HR_ratio_stats'
HR_BPM_STATS = 'HR_BPM_stats'
HR_MIN = 'HR_min'
HR_MAX = 'HR_max'

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #

def get_global_heart_rate_metrics(subject_data_folder_path: str, subject_age: int) -> Dict:
    """
    Extracts global heart rate (HR) metrics for one particular subject whose data from the entire week is in subject_data_folder_path.

    This function loads the HR data from the entire week and finds the minimum HR value detected. The maximum HR value
    is calculated as follows:

    HR_max = 208 - 0.7 * age -> DOI:  10.1016/s0735-1097(00)01054-8 (https://pubmed.ncbi.nlm.nih.gov/11153730/)

    :param subject_data_folder_path: Path to the folder containing the subject data for the entire week
    :param subject_age: Age of the subject (used for calculating the HR_max)
    :return: A dictionary with the global relative metrics as follows:
                {
                  "HR_relative_base": {
                    "HR_min": ...,
                    "HR_max": ...
                  }
                }
    """

    # init dict for holding the relative HR global metrics
    relative_HR_metrics_dict = {}

    # init list for holding the dfs with the data for all existing acquisitions
    dfs_list = []

    # iterate through the folders of the several days
    for date_folder in os.listdir(subject_data_folder_path):

        # get path to the folder
        day_folder_path = os.path.join(subject_data_folder_path, date_folder)

        # load_signals all acquisitions from the same day into a nested dictionary
        df_dict = sl.load_daily_acquisitions(day_folder_path, load_devices={WATCH: [HEART]})

        # iterate through all the acquisitions in the dictionary
        for time_key, df in df_dict[WATCH].items():

            # add acquisition to list
            dfs_list.append(df)

    # init inner dict
    relative_HR_metrics_dict[HR_RELATIVE_BASE_KEY] = {}

    # calculate the minimum hr over all acquisitions and IQR bounds and add to dict
    min_HR = _get_min_heart_rate(dfs_list)
    relative_HR_metrics_dict[HR_RELATIVE_BASE_KEY][HR_MIN] = min_HR

    # calculate max HR based on the age
    max_HR = _get_max_heart_rate(subject_age)
    relative_HR_metrics_dict[HR_RELATIVE_BASE_KEY][HR_MAX] = max_HR

    return relative_HR_metrics_dict


def get_heart_rate_metrics(day_folder_path: str, hr_min: float, hr_max: float, fs: int, w_size: float) -> Dict:
    """
    Extracts the heart rate metrics for an entire day of acquisitions and returns a dictionary with daily and per session
    metrics. If phone data is missing and no activity label is present in more than 50 % of the acquisition, the acquisition
    is discarded.

    :param day_folder_path: Path to the folder containing the all the acquisitions from an entire day
    :param hr_min: Minimum heart rate for the particular subject.
    :param hr_max: Maximum heart rate for the particular subject.
    :param fs: The sampling frequency with which the data was acquired and for resampling
    :param w_size: The window size used for the human activity recognition model
    :return: A dictionary with the daily and per session metrics for this subject as follows:
    {"23-09-2025": {
                    "HR_distributions_day": {...},
                    "15-00-00": {
                        "HR_metrics_session": {
                            "HR_BPM_stats": {...},
                            "HR_ratio_stats": {...},
                            "HR_timeline": {...},
                        }
                        "HR_distributions_session": {...},
                    }
    }
    """

    # init dict
    day_metrics_dict = {}

    # load_signals all acquisitions from the same day into a nested dictionary
    df_dict = sl.load_daily_acquisitions(day_folder_path, load_devices=selected_sensors)

    # pre-process data
    processed_df_dict = sp.apply_pre_processing_pipeline(df_dict, fs_android=fs)

    # classify and synchronise predictions
    sync_df = HAR.classify_and_synchronise_predictions(processed_df_dict, w_size=w_size, fs=fs)

    # keep only the needed columns - HR and activity
    sync_df = sync_df[[ACTIVITY_COLUMN_NAME, f"{HEART}{WATCH_SUFFIX}", f"y_{ACC}{WATCH_SUFFIX}"]]

    # split into dataframes with just the watch data
    acquisitions_dfs = _split_df_by_non_nan_blocks(sync_df, column_name=f"y_{ACC}{WATCH_SUFFIX}")

    # get date from path
    date = extract_date_from_path(day_folder_path)

    # reformat to dd-mm-yyyy
    year, month, day = date.split('-')
    date = f"{day}-{month}-{year}"

    # init the dict
    day_metrics_dict[date] = {}
    day_metrics_dict[date][HR_DISTRIBUTIONS_DAY] = {}

    # init list for holding the class counts for all acquisitions
    class_counts = []

    # extract metrics from the daily acquisitions
    for acquisitions_df in acquisitions_dfs:

        # check if the activity column is nan in more than half of the acquisition - phone stopped acquiring before watch
        if acquisitions_df[ACTIVITY_COLUMN_NAME].isna().mean() > 0.5:

            print(f"No activity labels for this acquisition. Skipping...")
            continue

        # get hr features
        acquisitions_metrics, nr_classes = _calculate_hr_metrics_per_acquisition(acquisitions_df, hr_min, hr_max)

        # add to dict
        day_metrics_dict[date].update(acquisitions_metrics)

        # add class counts to the list
        class_counts.append(nr_classes)

    # calculate daily proportions
    daily_proportions_dict = _calculate_daily_class_proportions(class_counts)

    # add to the metrics dictionary
    day_metrics_dict[date][HR_DISTRIBUTIONS_DAY] = daily_proportions_dict

    return day_metrics_dict


# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #

def _calculate_hr_metrics_per_acquisition(acquisition_df: pd.DataFrame, hr_min: float, hr_max: float) -> Tuple[Dict, Tuple[int, int, int, int]]:
    """
    Calculates the heart rate metrics per acquisition.

    This function assumes that acquisition_df has a column with the activity labels and a column with the heart rate data (BPM)
    and calculates the heart rate ratio (HRR) for all data points and classifies the heart rate ratio into normal, potentially elevated,
    and elevated for only the instances when the subject is sitting (other activities are ignored).
    The HRR class distributions are also calculated for this dataframe.

    :param acquisition_df: Dataframe with the HR and activity data
    :param hr_min: minimum heart rate (used for calculating HRR)
    :param hr_max: maximum heart rate (used for calculating HRR)
    :return: A dictionary with the metrics extracted for this dataframe and a Tuple [int, int, int, int] with the total and class counts
    for the HRR classes: [total_instances, nr_normal_class, nr_potentially_elevated_class, nr_potentially_elevated_class]
    """

    # calculate hr ratio and respective classification
    acquisitions_df = _calculate_hr_ratio(acquisition_df, hr_min, hr_max)

    # get a dataframe with only the HR class column
    hr_class_df = acquisitions_df[[HR_CLASS_COLUMN_NAME]]

    # count classes
    nr_classes = _count_hr_classes(hr_class_df)

    # get dictionary with the HR features for the acquisition
    acquisition_metrics = _extract_features_heart_rate(acquisitions_df)

    return acquisition_metrics, nr_classes


def _calculate_timeline_metrics(acquisition_df: pd.DataFrame) -> Dict[str, str]:
    """
    Compress consecutive identical class labels into time-range chunks, breaking
    chunks if the class changes or if a temporal gap (discontinuity) is detected.

    The function identifies 'blocks' of data by checking two conditions:
    1. Label Continuity: The 'class' remains the same between consecutive rows.
    2. Temporal Contiguity: The rows are physically adjacent in the original
       DataFrame, ensuring that filtered 'no data' or missing timestamps
       trigger a new range.

    :param acquisition_df: pd.DataFrame where the index contains string timestamps
                           and a column (HR_CLASS_COLUMN_NAME) contains labels.
    :return: A dictionary where keys are strings in the format 'start_end'
             and values are the corresponding class labels.
    """
    # create copy
    acquisition_df = acquisition_df.copy()

    # create a column of integers to later detect gaps
    acquisition_df['_original_pos'] = range(len(acquisition_df))

    # 2. Filter out 'no data'
    df = acquisition_df[acquisition_df[HR_CLASS_COLUMN_NAME] != "no data"].copy()

    if df.empty:
        return {}

    # 3. Detect Class Change
    class_changed = df[HR_CLASS_COLUMN_NAME] != df[HR_CLASS_COLUMN_NAME].shift()

    # 4. Detect Timestamp Jumps (Contiguity)
    # check if the current 'original_pos' is NOT exactly 1 greater than the previous
    # If it's not, it means a "no data" row or a gap existed between these samples.
    pos_jumped = df['_original_pos'] != df['_original_pos'].shift() + 1

    # The first row shift() is NaN, so we ensure the first row doesn't trigger a jump
    pos_jumped.iloc[0] = False

    # 5. Create Block IDs
    # A new block starts if Class Changed OR there was a Position Jump
    df["block"] = (class_changed | pos_jumped).cumsum()

    # 6. Group and Format Output
    timeline_dict = {}
    for _, block in df.groupby("block"):
        start = block.index[0]
        end = block.index[-1]
        label = block[HR_CLASS_COLUMN_NAME].iloc[0]
        timeline_dict[f"{start}_{end}"] = label

    return timeline_dict


def _get_min_heart_rate(dfs: List[pd.DataFrame]) -> float:
    """
    Calculates the minimum heart rate (HR) across all DataFrames containing a column with HR data.

    :param dfs: List of DataFrames, each containing a 'HR' column
    :return: Single minimum HR value from all DataFrames
    """
    # Concatenate all HR values into a single Series
    all_hr = pd.concat([df[HEART] for df in dfs], ignore_index=True)

    # Return the minimum of the values
    return all_hr.min()


def _get_max_heart_rate(age: int) -> float:
    """
    Calculates the estimated maximum heart rate (HR_max) based on age using the Tanaka's formula:

        HR_max = 208 - 0.7 * age

    DOI:  10.1016/s0735-1097(00)01054-8
    https://pubmed.ncbi.nlm.nih.gov/11153730/

    :param age: Age of the individual in years (int or float)
    :return: Estimated maximum heart rate (HR_max)
    """
    return 208 - 0.7 * age


def _calculate_hr_ratio(df: pd.DataFrame, hr_min: float, hr_max: float) -> pd.DataFrame:
    """
    Calculates the heart rate ratio (HR_ratio) for each heart rate measurement in a DataFrame
    and adds it as a new column 'heart_rate_ratio', based on https://www.sciencedirect.com/science/article/abs/pii/S0031938418300179?via%3Dihub

    HR_ratio is calculated as:
        heart_rate_ratio = ((HR(t) - HR_rest) / HRR) * 100
    where:
        HRR = HR_max - HR_rest
        HR_max = 208 - 0.7 * age (DOI:  10.1016/s0735-1097(00)01054-8, link: https://pubmed.ncbi.nlm.nih.gov/11153730/)
        HR_min is the minimum HR of the entire week of acquisitions


    :param df: DataFrame containing a column 'heart_rate'
    :param hr_min: Resting heart rate (HR_min)
    :param hr_max: Maximum heart rate (HR_max)
    :return: DataFrame with a new column 'HR_ratio'
    """
    hrr = hr_max - hr_min
    if hrr <= 0:
        raise ValueError("HR_max must be greater than HR_rest")

    # copy df
    df = df.copy()

    # calculate heart rate ratio and add to dataframe
    df[HR_RATIO_COLUMN_NAME] = ((df[f"{HEART}{WATCH_SUFFIX}"] - hr_min) / hrr) * 100

    # heart rate classification
    df[HR_CLASS_COLUMN_NAME] = df.apply(lambda row: _classify_hr_ratio(
            row[ACTIVITY_COLUMN_NAME], row[HR_RATIO_COLUMN_NAME]), axis=1)

    return df


def _classify_hr_ratio(activity: int, hr_ratio: float) -> str:
    """
    Classifies heart rate ratio (HRR) when sitting into 'normal', 'potentially elevated', or 'elevated'.
    It uses the HRR and activity at the same time point to assign a classification.

    Source for the heart rate ratio range for light exercise (considered as walking):
    ACSM’s Guidelines for Exercise Testing and Prescription, 11th Editions - Chapter 5 "General
    Principles of Exercise Prescription"
    (https://acsm.org/education-resources/books/guidelines-exercise-testing-prescription/).

    This function follows the following reasoning:
        - A normal HRR for light exercise is between 30 % to 39 % (from the reference above)
        - For the sitting class it is considered normal if HRR < 30 %, potentially elevated if 30 < HRR (%) < 39, and
        elevated if HRR > 39 %.
        - HRR values from activities such as walking or standing are classified as 'no data' as these are not relevant for this study.

    :param activity: activity label (0: sitting, 1: standing, 2: walking)
    :param hr_ratio: heart rate ratio value (float)
    :return: one of NORMAL, POTENTIALLY_ELEVATED, ELEVATED, or 'no data'
    """
    # add 'no data' if values are Nan or if the activity is not 0 (sitting)
    if pd.isna(hr_ratio) or activity != 0:

        return 'no data'

    # get range based on activity
    low, high = NORMAL_RANGES[activity]

    # check normal range
    if low <= hr_ratio <= high:
        return NORMAL

    # check potentially abnormal range
    if (
        low - POTENTIALLY_ABNORMAL_MARGIN <= hr_ratio < low
        or high < hr_ratio <= high + POTENTIALLY_ABNORMAL_MARGIN
    ):
        return POTENTIALLY_ELEVATED

    # remaining is abnormal
    return ELEVATED


def _split_df_by_non_nan_blocks(df: pd.DataFrame, column_name: str) -> List[pd.DataFrame]:
    """
    Split a DataFrame into contiguous blocks where 'column' is not NaN.

    :param df: pandas DataFrame to be split
    :param column_name: nameof the column to be used as reference
    :return: List of DataFrames, each corresponding to a continuous non-NaN block of 'column'
    """
    # Boolean mask: True where column is not NaN
    mask = df[column_name].notna()

    # Identify block changes (each time mask changes value)
    block_id = mask.ne(mask.shift()).cumsum()

    # Keep only blocks where mask is True
    blocks = [
        group.copy()
        for key, group in df.groupby(block_id)
        if mask[group.index].iloc[0]
    ]

    return blocks


def _extract_features_heart_rate(acquisition_df: pd.DataFrame) -> Dict:
    """
    Extracts features such as min, max, mean, std, and heart rate ration proportions from one dataframe (one acquisition
     of the day) into a dictionary where:

      - The key is the acquisition time interval: "HH:MM:SS_HH:MM:SS"
      - The value is a dictionary with HR metrics + class proportions.

    :param acquisition_df:
                      where each DataFrame contains columns HR_RATIO_COLUMN_NAME and HR_CLASS_COLUMN_NAME and where the
                      index is the time in the format hh:mm:ss.mmm
    :return: dict ->
    """
    # init dict to store the features
    acquisition_metrics = {}

    # Get acquisition start and end time
    start_time = acquisition_df.index[0]

    # Strip milliseconds
    start_time_str = str(start_time).split(".")[0]

    # generate a key to identify which acquisition is being handled
    key = f"{start_time_str.replace(":", "-")}"

    # get hr statistics and ratio proportions
    combined_stats = {
        HR_METRICS_SESSION: get_heart_rate_statistics(acquisition_df),
        HR_PROPORTIONS_SESSION: _calculate_heart_rate_class_proportions(acquisition_df)
    }

    acquisition_metrics[key] = combined_stats

    return acquisition_metrics


def get_heart_rate_statistics(df: pd.DataFrame) -> Dict:
    """
    Compute basic statistics (min, max, mean, std) for two heart-rate-related columns:
    one containing the Heart Rate Ratio and another containing the raw BPM value.

    :param df: DataFrame containing heart rate data
    :return: dict with statistics for both columns
    """

    # Return the features for the bpm and hr ratio columns
    return {
        HR_BPM_STATS: _calculate_statistics(df, f"{HEART}{WATCH_SUFFIX}"),
        HR_RATIO_STATS: _calculate_statistics(df, HR_RATIO_COLUMN_NAME),
        HR_TIMELINE: _calculate_timeline_metrics(df),
    }


def _calculate_statistics(df: pd.DataFrame, column_name: str) -> Dict[str, float]:
    """
    Calculate summary statistics for a specified numeric column.

    Computes the minimum, maximum, arithmetic mean, and standard deviation
    of the data, rounding all results to two decimal places.

    :param df: pd.DataFrame containing the data to analyze.
    :param column_name: The name of the numeric column to process.
    :return: A dictionary containing 'min', 'max', 'mean', and 'std' keys
             with their respective float values.
    :param df:
    :param column_name:
    :return:
    """

    # Calculate min max, mean, and std
    minimum = round(float(df[column_name].min()), 4)
    maximum = round(float(df[column_name].max()), 4)
    mean = round(float(df[column_name].mean()), 4)
    std = round(float(df[column_name].std()), 4)

    return {'min': minimum, 'max': maximum, 'mean': mean, 'std': std}


def _calculate_heart_rate_class_proportions(df: pd.DataFrame) -> Dict[str, float]:
    """
    Compute the proportions of each heart rate class in a DataFrame,
    ignoring rows labeled as 'no data'.

    :param df: DataFrame containing a column with HR classes
    :return: dict with class proportions (values sum to 1.0)
    """
    # get only the rows that have HR data
    filtered_df = df[df[HR_CLASS_COLUMN_NAME] != "no data"]

    # count the class values
    proportions = filtered_df[HR_CLASS_COLUMN_NAME].value_counts(normalize=True).to_dict()

    # round
    proportions = {hr_class: round(proportion, 4) for hr_class, proportion in proportions.items()}

    return proportions


def _count_hr_classes(hr_class_df: pd.DataFrame) -> Tuple[int, int, int, int]:
    """
    Count HR class instances, ignoring 'no data'.

    :param hr_class_df: DataFrame with a single column containing HR class labels.
    :return: Tuple[int, int, int, int]
        total_count (int): Number of instances excluding 'no data'
        normal_count (int): Number of 'NORMAL' instances
        potentially_abnormal_count (int): Number of 'POTENTIALLY_ELEVATED' instances
        abnormal_count (int): Number of 'ELEVATED' instances
    """
    # Filter out 'no data'
    filtered = hr_class_df[hr_class_df.iloc[:, 0] != 'no data']

    # Count occurrences of each class
    counts = filtered.iloc[:, 0].value_counts()

    # count values
    total_count = counts.sum()
    normal_count = counts.get(NORMAL, 0)
    potentially_abnormal_count = counts.get(POTENTIALLY_ELEVATED, 0)
    abnormal_count = counts.get(ELEVATED, 0)

    return total_count, normal_count, potentially_abnormal_count, abnormal_count


def _calculate_daily_class_proportions(totals: List[Tuple[int, int, int, int]]) -> Dict[str, float]:
    """
    Calculate overall class proportions from a list of counts per dataframe.

    :param totals: List[Tuple[int, int, int, int]]
                Each tuple contains:
                (total_count, normal_count, potentially_elevated_count, elevated_count)
    :return: Dict[str, float]
        Keys are class names, values are proportions (0-1)
    """
    # Sum totals across all acquisitions
    total_count = sum(t[0] for t in totals)
    normal_total = sum(t[1] for t in totals)
    potentially_abnormal_total = sum(t[2] for t in totals)
    abnormal_total = sum(t[3] for t in totals)

    # Avoid division by zero
    if total_count == 0:
        return {NORMAL: 0.0, POTENTIALLY_ELEVATED: 0.0, ELEVATED: 0.0}

    # Calculate proportions and round
    return {
        NORMAL: round((normal_total / total_count), 4),
        POTENTIALLY_ELEVATED: round((potentially_abnormal_total / total_count), 4),
        ELEVATED: round((abnormal_total / total_count), 4)
    }