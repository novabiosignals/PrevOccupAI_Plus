"""
Function to get questionnaire metrics

Available Functions
-------------------
[Public]
get_single_instance_questionnaire_metrics(...): Load questionnaire scores from a CSV file and return all metrics of
a specific subject as a dictionary.
get_domain_key_from_filename(...): Given a results file name, return the corresponding OH domain key.
get_psychosocial_metrics(...): Loads a psychosocial scores CSV file and returns a dictionary with the scores
-------------------

[Private]
-------------------
"""

# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import pandas as pd
from typing import Dict

# internal imports
from constants import ENVIRONMENT, PERSONAL, BIOMECHANICAL, ROSA, COPSOQ, POPULATION
from OH_profile.constants import *

# ------------------------------------------------------------------------------------------------------------------- #
# file specific constants
# ------------------------------------------------------------------------------------------------------------------- #

KEY_DOMAIN_MAPPING = {PERSONAL: PERSONAL_DOMAIN_KEY,
                      BIOMECHANICAL: BIOMECHANICAL_DOMAIN_KEY, ENVIRONMENT: ENVIRONMENTAL_DOMAIN_KEY,
                      ROSA: BIOMECHANICAL_DOMAIN_KEY}

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #

def get_single_instance_questionnaire_metrics(scores_csv_file: str, subject_id: int) -> Dict:
    """
    Load questionnaire scores from a CSV file and return all metrics of a specific subject as a dictionary.

    The function extracts the row corresponding to the given subject_id and converts it into a dictionary
    where keys are column names and values are the subject's questionnaire scores.

    :param scores_csv_file: Path to the CSV file containing questionnaire scores.
    :param subject_id: Integer ID of the subject whose metrics should be retrieved.
    :return: A dictionary mapping each metric/column name to the subject's value.
            (example: {'age': 46, 'height': 154, 'weight': 65 ....})
    """

    # load questionnaire results into a dataframe
    # subject id is the index of this dataframe
    scores_df = pd.read_csv(scores_csv_file, index_col=0)

    # get only the row correspondent to the subject id
    subject_results = scores_df.loc[subject_id]

    # convert the row to a dictionary
    metrics_dict = subject_results.to_dict()

    return metrics_dict


def get_daily_workload_metrics(scores_csv_file: str, subject_id: int) -> Dict:
    """
    Extracts daily workload metrics for a specific subject from a CSV file containing questionnaire results.

    The CSV file is expected to have the subject ID as the first column (index), a 'submitdate' column
    containing date and time strings in the format 'dd/mm/yyyy HH:MM', and several workload-related metric columns.
    If a subject has multiple submissions on different dates, each date will be a key in the returned dictionary.

    :param scores_csv_file: Path to the CSV file containing questionnaire results.
    :param subject_id: The ID of the subject for which metrics should be extracted.
    :return: A dictionary where each key is a date string ('dd/mm/yyyy') and each value is
             another dictionary of metric names and their corresponding values for that date.
             Example:
             {
                 '24/09/2025': {'focus_and_mental_strain': 5, 'heavy_workload': 4, ...},
                 '25/09/2025': {'focus_and_mental_strain': 5, 'heavy_workload': 4, ...},
                 ...
             }
    """
    # init metrics dictionary
    metrics_dict = {}

    # load questionnaire results into a dataframe
    # subject id is the index of this dataframe
    scores_df = pd.read_csv(scores_csv_file, index_col=0)

    # get a sub dataframe with the data from the particular subject only
    subject_results = scores_df.loc[subject_id]

    # if only one row is returned, make it a DataFrame
    if isinstance(subject_results, pd.Series):
        subject_results = subject_results.to_frame().T

    # cycle over the rows of the dataframe
    for idx, row in subject_results.iterrows():

        # get the submit date (e.g., '24/09/2025 13:29')
        submitdate_str = row['submitdate']

        # extract only the date part (dd/mm/yyyy)
        date = submitdate_str.split(' ')[0]

        # convert row to dictionary except submit date
        row_dict = row.drop('submitdate').to_dict()

        # add to metrics dictionary
        metrics_dict[date] = row_dict

    return metrics_dict


def get_domain_key_from_filename(results_file: str) -> str:
    """
    Given a results file name, return the corresponding OH domain key.
    The file name is expected to contain one of the domain identifiers
    (e.g., PSYCHOSOCIAL, PERSONAL, BIOMECHANICAL, ENVIRONMENT, ROSA).
    :param results_file: Path to the results file.
    :return: The OH domain key.
    """
    # cycle over the domains and respective keys
    for domain_name, domain_key in KEY_DOMAIN_MAPPING.items():

        # find the key in the results file name
        if domain_name.lower() in results_file.lower():

            # get the key
            return domain_key

    raise ValueError(f"Could not determine domain for file: {results_file}")


def get_psychosocial_metrics(scores_csv_file: str) -> Dict:
    """
    Loads a psychosocial scores CSV file and returns a dictionary with the scores
    organized by questionnaire type (COPSOQ or MUEQ) and averaging method
    (population or work type).

    The function determines the correct dictionary key based on the file name
    containing `COPSOQ` or `MUEQ` and `POPULATION` or work-type indicator.

    :param scores_csv_file: Path to the CSV file containing psychosocial questionnaire scores.
                            The file name should indicate the questionnaire type and averaging method.
    :return: A dictionary where the key corresponds to the questionnaire type and
            averaging method (e.g., `PSYCHOSOCIAL_COPSOQ_POPULATION_KEY`) and
            the value is a nested dictionary representation of the CSV data.
    """

    # init metrics dict
    metrics_dict = {}

    # load results to a dataframe
    scores_df = pd.read_csv(scores_csv_file, index_col=0)

    # Determine questionnaire type
    is_copsoq = COPSOQ in scores_csv_file
    is_population = POPULATION in scores_csv_file

    # Select correct output key
    if is_copsoq:
        key = (PSYCHOSOCIAL_COPSOQ_POPULATION_KEY if is_population else PSYCHOSOCIAL_COPSOQ_WORK_TYPE_KEY)

    # it's MUEQ
    else:
        key = (PSYCHOSOCIAL_MUEQ_POPULATION_KEY if is_population else PSYCHOSOCIAL_MUEQ_WORK_TYPE_KEY)

    # add results with the correct key to the dictionary
    metrics_dict[key] = scores_df.to_dict()

    return metrics_dict