"""
Function to get sensor heart rate metrics

Available Functions
-------------------
[Public]
get_sensor_heart_rate_metrics(...): Gets the metrics needed for the heart rate plots.
-------------------

[Private]
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
from constants import ACTIVITY_COLUMN_NAME, HEART, HR_RATIO_COLUMN_NAME, HR_CLASS_COLUMN_NAME, WATCH_SUFFIX, ACC
from OH_profile.constants import RELATIVE_HR_BASE_KEY
# ------------------------------------------------------------------------------------------------------------------- #
# constants
# ------------------------------------------------------------------------------------------------------------------- #

# sensors to be loaded which are strictly needed for the HR plot
selected_sensors = {'phone': ['ACC', 'GYR', 'MAG'], # for HAR
                    'watch': ['ACC','HEART']} # ACC to fill with NaN when the HR is not acquiring - do not remove ACC


# heart rate ratio per activity
NORMAL_RANGES = {
    0: (0.0, 20),
    1: (20, 30),
    2: (30, 39)
}

# Margin used to define "potentially abnormal" outside the normal range for heart rate ratio
POTENTIALLY_ABNORMAL_MARGIN = 5

# HR classes
NORMAL = 'normal'
POTENTIALLY_ABNORMAL = 'potentially abnormal'
ABNORMAL = 'abnormal'

# keys for the inner dictionaries with the HR features
METRICS = 'metrics'
PROPORTIONS = 'proportions'
DAILY_PROPORTIONS = 'daily_proportions'
# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #

def get_global_heart_rate_metrics(subject_data_folder: str, subject_age: int) -> Dict:

    # init dict for holding the relative HR global metrics
    relative_HR_metrics_dict = {}

    # init list for holding the dfs with the data for all existing acquisitions
    dfs_list = []

    # iterate through the folders of the several days
    for date_folder in os.listdir(subject_data_folder):

        # get path to the folder
        day_folder_path = os.path.join(subject_data_folder, date_folder)

        # load_signals all acquisitions from the same day into a nested dictionary
        df_dict = sl.load_daily_acquisitions(day_folder_path, load_devices={'watch': ['HEART']})

        # iterate through all the acquisitions in the dictionary
        for time_key, df in df_dict['watch'].items():

            # add acquisition to list
            dfs_list.append(df)

    # init inner dict
    relative_HR_metrics_dict[RELATIVE_HR_BASE_KEY] = {}

    # calculate the minimum hr over all acquisitions of the week and add to dict
    min_HR = _get_min_heart_rate(dfs_list)
    relative_HR_metrics_dict[RELATIVE_HR_BASE_KEY]['min_HR'] = min_HR

    # calculate max HR based on the age
    max_HR = _get_max_heart_rate(subject_age)
    relative_HR_metrics_dict[RELATIVE_HR_BASE_KEY]['max_HR'] = max_HR

    return relative_HR_metrics_dict


def get_heart_rate_metrics(day_folder_path: str, hr_min: float, hr_max: float, fs: int, w_size: float) -> Dict:

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
    acquisitions_dfs = split_df_by_non_nan_blocks(sync_df, column_name=f"y_{ACC}{WATCH_SUFFIX}")

    # get date from path
    date = extract_date_from_path(day_folder_path)

    # init the dict
    day_metrics_dict[date] = {}
    day_metrics_dict[date][DAILY_PROPORTIONS] = {}

    # init list for holding the class counts for all acquisitions
    class_counts = []

    # extract metrics from the daily acquisitions
    for acquisitions_df in acquisitions_dfs:

        # get hr features
        acquisitions_metrics, nr_classes = _calculate_hr_metrics_per_acquisition(acquisitions_df, hr_min, hr_max)

        # add to dict
        day_metrics_dict[date].update(acquisitions_metrics)

        # add class counts to the list
        class_counts.append(nr_classes)

    # calculate daily proportions
    daily_proportions_dict = _calculate_daily_class_proportions(class_counts)

    # add to the metrics dictionary
    day_metrics_dict[date][DAILY_PROPORTIONS] = daily_proportions_dict

    return day_metrics_dict




# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #

def _calculate_hr_metrics_per_acquisition(acquisition_df: pd.DataFrame, hr_min: float, hr_max: float) \
        -> Tuple[Dict, Tuple[int, int, int, int]]:

    # calculate hr ratio and respective classification
    acquisitions_df = _calculate_hr_ratio(acquisition_df, hr_min, hr_max)

    # get a dataframe with only the HR class column
    hr_class_df = acquisitions_df[[HR_CLASS_COLUMN_NAME]]

    # count classes
    nr_classes = _count_hr_classes(hr_class_df)

    # get dictionary with the HR features for the acquisition
    acquisition_metrics = features_heart_rate(acquisitions_df)

    return acquisition_metrics, nr_classes


def _calculate_timeline_metrics(acquisition_df: pd.DataFrame) -> Dict[str, str]:
    """
    Compress consecutive identical class labels into time ranges,
    excluding 'no data' rows.

    The DataFrame index is assumed to contain the timestamps.

    :param acquisition_df: pd.DataFrame. Must contain a 'class' column. Index values are timestamps.
    :return:
    """
    # Remove 'no data'
    df = acquisition_df[acquisition_df[HR_CLASS_COLUMN_NAME] != "no data"].copy()

    if df.empty:
        return {}

    # Create group ids for consecutive identical classes
    df["group"] = (df[HR_CLASS_COLUMN_NAME] != df[HR_CLASS_COLUMN_NAME].shift()).cumsum()

    timeline_dict = {}
    for _, group in df.groupby("group"):
        start = group.index[0]
        end = group.index[-1]
        label = group[HR_CLASS_COLUMN_NAME].iloc[0]

        timeline_dict[f"{start}_{end}"] = label

    return timeline_dict


def _get_min_heart_rate(dfs: List[pd.DataFrame]) -> float:
    """
    Calculates the minimum heart rate (HR) across all DataFrames in the list after removing outliers.

    Outlier removal is performed using the IQR method on the combined 'HR' values from all DataFrames.

    :param dfs: List of DataFrames, each containing a 'HR' column
    :return: Single minimum HR value from all DataFrames with outliers removed
    """
    # Concatenate all HR values into a single Series
    all_hr = pd.concat([df[HEART] for df in dfs], ignore_index=True)

    # Remove outliers using IQR
    Q1 = all_hr.quantile(0.25)
    Q3 = all_hr.quantile(0.75)
    IQR = Q3 - Q1
    filtered_hr = all_hr[(all_hr >= Q1 - 1.5 * IQR) & (all_hr <= Q3 + 1.5 * IQR)]

    # Return the minimum of the filtered values
    return filtered_hr.min()


def _get_max_heart_rate(age: int) -> float:
    """
    Calculates the estimated maximum heart rate (HR_max) based on age using the Tanaka's formula:

        HR_max = 208 - 0.7 * age

    DOI:  10.1016/s0735-1097(00)01054-8

    :param age: Age of the individual in years (int or float)
    :return: Estimated maximum heart rate (HR_max)
    """
    return 208 - 0.7 * age


def _calculate_hr_ratio(df: pd.DataFrame, hr_min: float, hr_max: float) -> pd.DataFrame:
    """
    Calculates the heart rate ratio (HR_ratio) for each heart rate measurement in a DataFrame
    and adds it as a new column 'heart_rate_ratio'.

    HR_ratio is calculated as:
        heart_rate_ratio = ((HR(t) - HR_rest) / HRR) * 100
    where:
        HRR = HR_max - HR_rest

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
    df[HR_CLASS_COLUMN_NAME] = df.apply(lambda row: classify_hr_ratio(
            row[ACTIVITY_COLUMN_NAME], row[HR_RATIO_COLUMN_NAME]), axis=1)

    return df


def classify_hr_ratio(activity: int, hr_ratio: float) -> str:
    """
    Classifies heart rate ratio into 'normal', 'potentially abnormal', or 'abnormal'
    based on the type of activity and defined normal ranges.

    Source for the heart rate ratio range for light exercise (considered as walking):
    ACSM’s Guidelines for Exercise Testing and Prescription, 11th Editions - Chapter 5 "General
    Principles of Exercise Prescription"

    Normal heart rate ratio ranges (%):
        Sitting: 0-20%
        Standing: 20-30% # TODO REMOVE STANDING AND WALKING
        Walking: 30-39% # TODO CHANGE NAMING OF ABNORMAL

    Classification:
        - 'normal': within the normal range
        - 'potentially abnormal': up to POTENTIALLY_ABNORMAL_MARGIN outside the normal range
        - 'abnormal': more than POTENTIALLY_ABNORMAL_MARGIN outside the normal range

    :param activity: activity label
    :param hr_ratio: heart rate ratio value (float)
    :return: one of NORMAL, POTENTIALLY_ABNORMAL, ABNORMAL, or 'no data'
    """
    # add 'no data' if values are Nan
    if pd.isna(hr_ratio):

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
        return POTENTIALLY_ABNORMAL

    # remaining is abnormal
    return ABNORMAL


def split_df_by_non_nan_blocks(df: pd.DataFrame, column_name: str) -> List[pd.DataFrame]:
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


def features_heart_rate(acquisition_df: pd.DataFrame) -> Dict:
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
    end_time = acquisition_df.index[-1]

    # generate a key to identify which acquisition is being handled
    key = f"{start_time}_{end_time}"

    # get hr statistics and ratio proportions
    combined_stats = {
        METRICS: get_heart_rate_statistics(acquisition_df),
        PROPORTIONS: _calculate_heart_rate_class_proportions(acquisition_df)
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
        "heart_rate_bpm": _calculate_statistics(df, f"{HEART}{WATCH_SUFFIX}"),
        "heart_rate_ratio": _calculate_statistics(df, HR_RATIO_COLUMN_NAME),
        "timeline_metrics": _calculate_timeline_metrics(df),
    }


def _calculate_statistics(df: pd.DataFrame, column_name: str) -> Dict[str, float]:

    # Calculate min max, mean, and std
    minimum = round(float(df[column_name].min()), 2)
    maximum = round(float(df[column_name].max()), 2)
    mean = round(float(df[column_name].mean()), 2)
    std = round(float(df[column_name].std()), 2)

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
    proportions = {hr_class: round(proportion, 2) for hr_class, proportion in proportions.items()}

    return proportions


def _count_hr_classes(hr_class_df: pd.DataFrame) -> Tuple[int, int, int, int]:
    """
    Count HR class instances, ignoring 'no data'.

    :param hr_class_df: DataFrame with a single column containing HR class labels.
    :return: Tuple[int, int, int, int]
        total_count (int): Number of instances excluding 'no data'
        normal_count (int): Number of 'NORMAL' instances
        potentially_abnormal_count (int): Number of 'POTENTIALLY_ABNORMAL' instances
        abnormal_count (int): Number of 'ABNORMAL' instances
    """
    # Filter out 'no data'
    filtered = hr_class_df[hr_class_df.iloc[:, 0] != 'no data']

    # Count occurrences of each class
    counts = filtered.iloc[:, 0].value_counts()

    # count values
    total_count = counts.sum()
    normal_count = counts.get(NORMAL, 0)
    potentially_abnormal_count = counts.get(POTENTIALLY_ABNORMAL, 0)
    abnormal_count = counts.get(ABNORMAL, 0)

    return total_count, normal_count, potentially_abnormal_count, abnormal_count


def _calculate_daily_class_proportions(totals: List[Tuple[int, int, int, int]]) -> Dict[str, float]:
    """
    Calculate overall class proportions from a list of counts per dataframe.

    :param totals: List[Tuple[int, int, int, int]]
                Each tuple contains:
                (total_count, normal_count, potentially_abnormal_count, abnormal_count)
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
        return {NORMAL: 0.0, POTENTIALLY_ABNORMAL: 0.0, ABNORMAL: 0.0}

    # Calculate proportions and round
    return {
        NORMAL: round((normal_total / total_count), 2),
        POTENTIALLY_ABNORMAL: round((potentially_abnormal_total / total_count), 2),
        ABNORMAL: round((abnormal_total / total_count), 2)
    }