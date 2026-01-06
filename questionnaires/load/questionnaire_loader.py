"""
Function to load raw questionnaire answers

Available Functions
-------------------
[Public]
load_questionnaire_answers(...):  Loads the answers of all questionnaires from a given domain into a
Dictionary where the keys are the questionnaire ids and the values are the dataframes with the loaded answers.
-------------------

[Private]
_check_valid_domain(...): checks if the input domain is valid.
-------------------
"""
# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import pandas as pd
import os
from typing import Dict

# internal imports
from constants import CSV, QUESTIONNAIRE_DOMAINS

# ------------------------------------------------------------------------------------------------------------------- #
# constants
# ------------------------------------------------------------------------------------------------------------------- #
RESULTS_FILE_PREFIX = 'results_'

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #

def load_questionnaire_answers(folder_path: str, domain: str) -> Dict[str, pd.DataFrame]:
    """
    Loads the answers of all questionnaires from a given domain (psychosocial, biomechanical, environment, or personal) into a
    Dictionary where the keys are the questionnaire ids and the values are the dataframes with the loaded answers.
    The columns 1 through 8 (inclusive) are removed so that the dataframe contains only the columns correspondent to the
    id and the questionnaire items.

    :param folder_path: Path to the folder containing the several questionnaire domains (subfolders)
    :param domain: The domain of the questionnaires, which should be the name of the folder that contains the csv files
    :return: A dictionary with where the keys are the questionnaire ids and the values are the pandas dataframes.
    """
    # check if domain is valid
    _check_valid_domain(domain)

    # init dictionary to hold all results_questionnaires from the questionnaires of the given domain
    results_dict: Dict[str, pd.DataFrame] = {}

    # iterate through the multiple csv files containing the results_questionnaires of the questionnaires from the domain
    for csv_file in os.listdir(os.path.join(folder_path, domain)):

        # generate path to the csv file
        results_path = os.path.join(os.path.join(folder_path, domain, csv_file))

        # load results_questionnaires to a dataframe
        results_df = pd.read_csv(results_path, index_col=0)

        # get questionnaire id from the file name
        questionnaire_id = csv_file.replace(RESULTS_FILE_PREFIX, "").replace(CSV, "")

        # save do results_questionnaires dictionary
        results_dict[questionnaire_id] = results_df

    return results_dict


# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #

def _check_valid_domain(domain: str) -> None:
    """
    Checks that the given domain is valid.
    :param domain: the input domain
    :return: None
    """

    if domain not in QUESTIONNAIRE_DOMAINS:
        raise ValueError(
            f"Invalid domain '{domain}'. Expected one of: {', '.join(QUESTIONNAIRE_DOMAINS)}."
        )
