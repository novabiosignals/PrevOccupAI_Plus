"""
Function to get questionnaire metrics

Available Functions
-------------------
[Public]
get_single_instance_questionnaire_metrics(...): Load questionnaire scores from a CSV file and return all metrics of
a specific subject as a dictionary.
get_domain_key_from_filename(...): Given a results file name, return the corresponding OH domain key.
get_psychosocial_metrics(...): Loads a psychosocial scores CSV file and returns a dictionary with the scores
get_metadata_metrics(...): Get metadata metrics for the OH profile.
-------------------

[Private]
_get_missing_workload_dates(...): gets the missing workload questionnaire dates based on the start date and the existing acquisition dates
-------------------
"""
# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import pandas as pd
from typing import Dict, List
from datetime import datetime, timedelta

# internal imports
from constants import ENVIRONMENT, PERSONAL, BIOMECHANICAL, ROSA, COPSOQ, POPULATION
from OH_profile.constants import *
import sensors.load as sl

# ------------------------------------------------------------------------------------------------------------------- #
# file specific constants
# ------------------------------------------------------------------------------------------------------------------- #

KEY_DOMAIN_MAPPING = {PERSONAL: PERSONAL_DOMAIN_KEY,
                      BIOMECHANICAL: BIOMECHANICAL_DOMAIN_KEY, ENVIRONMENT: ENVIRONMENTAL_DOMAIN_KEY,
                      ROSA: BIOMECHANICAL_DOMAIN_KEY}

# columns from personal questionnaire results
META_DATA_COLUMNS = ['idade', 'sexo', 'altura', 'peso', 'mao']

DATE_FORMAT = "%d-%m-%Y"

SCORING_KEY = 'scoring'
SCORING_VALUE = '1_completely-disagree_5_completely-agree'
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

    Fills in missing acquisition dates with 'No data available'

    :param scores_csv_file: Path to the CSV file containing questionnaire results.
    :param subject_id: The ID of the subject for which metrics should be extracted.
    :return: A dictionary where each key is a date string ('dd/mm/yyyy') and each value is
             another dictionary of metric names and their corresponding values for that date.
             Example:
             {
                 '24-09-2025': {'focus_and_mental_strain': 5, 'heavy_workload': 4, ...},
                 '25-09-2025': {'focus_and_mental_strain': 5, 'heavy_workload': 4, ...},
                 '26-09-2025': 'No data available',
                 ...
             }
    """
    # init metrics dictionary
    metrics_dict = {}

    # load questionnaire results into a dataframe
    # subject id is the index of this dataframe
    scores_df = pd.read_csv(scores_csv_file, index_col=0, dtype={'submitdate': str})

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

        # replace / with -
        date = date.replace('/', '-')

        # convert row to dictionary except submit date
        row_dict = row.drop('submitdate').to_dict()

        # add to metrics dictionary
        metrics_dict[date] = row_dict

    # check if there are less than 6 entries (5 working days + scoring information) - if so, add missing data
    if len(metrics_dict) < 6:

        # get start_date
        start_date = sl.get_participant_start_date(sl.load_participants_info(), subject_id)

        # get missing dates list
        missing_dates = _get_missing_workload_dates(start_date, list(metrics_dict.keys()))

        # add missing entries
        for missing_date in missing_dates:
            metrics_dict.update({missing_date: 'No data available'})

        # sort metrics_dict by date keys
        metrics_dict = dict(sorted(metrics_dict.items(), key=lambda x: datetime.strptime(x[0], DATE_FORMAT)))

    # add scoring information
    metrics_dict[SCORING_KEY] = SCORING_VALUE

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


def get_psychosocial_metrics(scores_csv_file: str, subject_id: int) -> Dict:
    """
    Loads a psychosocial scores CSV file and returns a dictionary with the scores
    organized by questionnaire type (COPSOQ or MUEQ) and averaging method
    (population or work type).

    The function determines the correct dictionary key based on the file name
    containing 'COPSOQ' or 'MUEQ' and 'population' or 'work_type' strings.

    :param scores_csv_file: Path to the CSV file containing psychosocial questionnaire scores.
                            The file name should indicate the score type and averaging method.
    :param subject_id: The ID of the subject for which metrics should be extracted.
    :return: A dictionary where the key corresponds to the questionnaire type and
            averaging method (e.g., `PSYCHOSOCIAL_COPSOQ_POPULATION_KEY`) and
            the value is a nested dictionary representation of the CSV data.
    """

    # init metrics dict
    metrics_dict = {}

    # check the work_type of the subject
    work_type = sl.get_participant_work_type(sl.load_participants_info(), subject_id)

    # load results to a dataframe
    scores_df = pd.read_csv(scores_csv_file, index_col=0)

    # Determine questionnaire type
    is_copsoq = COPSOQ in scores_csv_file
    is_population = POPULATION in scores_csv_file

    # it it's a work_type mean score
    if not is_population:

        # remove the index (work_type mean) that does not correspond to the worker's type
        scores_df = scores_df[scores_df.index.str.contains(work_type)]

    # Select correct output key
    if is_copsoq:
        key = (PSYCHOSOCIAL_COPSOQ_POPULATION_KEY if is_population else PSYCHOSOCIAL_COPSOQ_WORK_TYPE_KEY)

    # it's MUEQ
    else:
        key = (PSYCHOSOCIAL_MUEQ_POPULATION_KEY if is_population else PSYCHOSOCIAL_MUEQ_WORK_TYPE_KEY)

    # add results with the correct key to the dictionary
    metrics_dict[key] = scores_df.to_dict()

    return metrics_dict


def get_metadata_metrics(personal_scores_csv_file: str, subject_id: int) -> Dict:
    """
    Get metadata metrics for the OH profile.
    :param personal_scores_csv_file: Path to the CSV file containing personal questionnaire results.
    :param subject_id: The ID of the subject for which metrics should be extracted.
    :return: A dictionary mapping each metric/column name to the subject's value.
            (example: {'age': 46, 'height': 154, 'weight': 65 ....})
    """

    # load results to a dataframe
    scores_df = pd.read_csv(personal_scores_csv_file, index_col=0)

    # get a sub dataframe with the data from the particular subject only and only the relevant columns
    subject_results = scores_df.loc[subject_id, META_DATA_COLUMNS]

    # get work type and start date from participants info
    work_type = sl.get_participant_work_type(sl.load_participants_info(), subject_id)
    start_date = sl.get_participant_start_date(sl.load_participants_info(), subject_id)

    # turn df into a dict
    metrics_dict = subject_results.to_dict()

    # add work type and start date to metrics
    metrics_dict['work_type'] = work_type
    metrics_dict['start_date'] = start_date
    metrics_dict['subject_id'] = subject_id

    return metrics_dict


# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #

def _get_missing_workload_dates(start_date: str, acquisition_dates: List[str]) -> List[str]:
    """
    Return the missing workload dates within a 5-day window starting from a given date.

    The function generates a list of expected dates consisting of the start date
    and the following four consecutive days, then compares it against the provided
    acquisition dates and returns the dates that are missing.
    Date strings should have the format as in DATE_FORMAT.

    :param start_date: The start date of the acquisitions
    :param acquisition_dates: List of dates where data exists
    :return: List of missing data strings
    """

    # parse string to date
    start_date = datetime.strptime(start_date, DATE_FORMAT)

    # generate 5 dates (start date + next 4 days)
    expected_dates = [(start_date + timedelta(days=i)).strftime(DATE_FORMAT) for i in range(5)]

    # find missing dates
    missing_dates = [date for date in expected_dates if date not in acquisition_dates]

    return missing_dates