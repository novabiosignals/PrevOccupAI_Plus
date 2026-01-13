"""
Helper functions for extracting sensor metrics

Available Functions
-------------------
[Public]
split_df_by_non_nan_blocks(...): Split a DataFrame into contiguous non-NaN acquisition blocks.
calculate_statistics(...): Compute summary statistics for a numeric column.
calculate_class_distributions(...): Calculate class distributions for a specified column containing the class labels.
-------------------

[Private]
-------------------
"""
# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import pandas as pd
from typing import Dict, List

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #

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


def calculate_statistics(df: pd.DataFrame, column_name: str) -> Dict[str, float]:
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


def calculate_class_distributions(df: pd.DataFrame, column_name: str, nr_decimals: int = 4) -> Dict[str, float]:
    """
    Calculate class distributions for a specified column containing the class labels.

    :param df: Dataframe containing the column with the class labels.
    :param column_name: name of the column containing the labels
    :param nr_decimals: number of decimal places to round the class distributions (Default = 4).
    :return: A dictionary with the class distributions: {class_1: 0.5, class_2: 0.5}
    """

    # count the class values
    distributions = df[column_name].value_counts(normalize=True).to_dict()

    # round
    distributions = {class_name: round(distribution, nr_decimals) for class_name, distribution in distributions.items()}

    return distributions


def calculate_timeline_metrics(acquisition_df: pd.DataFrame, class_column_name: str, class_ignore: str = None) -> Dict[str, str]:
    """
    Compress consecutive identical class labels into time-range chunks, breaking
    chunks if the class changes or if a temporal gap (discontinuity) is detected.

    The function identifies 'blocks' of data by checking two conditions:
    1. Label Continuity: The 'class' remains the same between consecutive rows.
    2. Temporal Contiguity: The rows are physically adjacent in the original
       DataFrame, ensuring that filtered 'no data' or missing timestamps
       trigger a new range.

    :param acquisition_df: pd.DataFrame where the index contains string timestamps
                           and a column that contains labels.
    :param class_column_name: name of the column containing the class labels.
    :param class_ignore: class name to be ignored for the timeline metrics (example: 'no data' values), default = None.
    :return: A dictionary where keys are strings in the format 'start_end'
             and values are the corresponding class labels.
    """
    # create copy
    acquisition_df = acquisition_df.copy()

    # create a column of integers to later detect gaps
    acquisition_df['_original_pos'] = range(len(acquisition_df))

    if class_ignore is not None:

        # 2. Filter out 'no data'
        acquisition_df = acquisition_df[acquisition_df[class_column_name] != class_ignore].copy()

    if acquisition_df.empty:
        return {}

    # 3. Detect Class Change
    class_changed = acquisition_df[class_column_name] != acquisition_df[class_column_name].shift()

    # 4. Detect Timestamp Jumps (Contiguity)
    # check if the current 'original_pos' is NOT exactly 1 greater than the previous
    # If it's not, it means a "no data" row or a gap existed between these samples.
    pos_jumped = acquisition_df['_original_pos'] != acquisition_df['_original_pos'].shift() + 1

    # The first row shift() is NaN, so we ensure the first row doesn't trigger a jump
    pos_jumped.iloc[0] = False

    # 5. Create Block IDs
    # A new block starts if Class Changed OR there was a Position Jump
    acquisition_df["block"] = (class_changed | pos_jumped).cumsum()

    # 6. Group and Format Output
    timeline_dict = {}
    for _, block in acquisition_df.groupby("block"):
        start = block.index[0]
        end = block.index[-1]
        label = block[class_column_name].iloc[0]
        timeline_dict[f"{start}_{end}"] = label

    return timeline_dict