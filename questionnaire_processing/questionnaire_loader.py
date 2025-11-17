# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import pandas as pd
import os
from typing import Dict

# internal imports
from constants import CSV

# ------------------------------------------------------------------------------------------------------------------- #
# constants
# ------------------------------------------------------------------------------------------------------------------- #
RESULTS_FILE_PREFIX = 'results_'

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #

def load_questionnaire_answers(folder_path: str, domain: str) -> Dict[str, pd.DataFrame]:
    """
    Loads the answers of all questionnaires from a given domain (Psicossocial, Biomecanico, Ambiente, or Pessoais) into a
    Dictionary where the keys are the questionnaire ids and the values are the dataframes with the loaded answers.
    The columns 1 through 8 (inclusive) are removed so that the dataframe contains only the columns correspondent to the
    id and the questionnaire items.

    :param folder_path: Path to the folder containing the several questionnaire domains (subfolders)
    :param domain: The domain of the questionnaires, which should be the name of the folder that contains the csv files
    :return: A dictionary with where the keys are the questionnaire ids and the values are the pandas dataframes.
    """

    # init dictionary to hold all results from the questionnaires of the given domain
    results_dict: Dict[str, pd.DataFrame] = {}

    # iterate through the multiple csv files containing the results of the questionnaires from the domain
    for csv_file in os.listdir(os.path.join(folder_path, domain)):

        # generate path to the csv file
        results_path = os.path.join(os.path.join(folder_path, domain, csv_file))

        # load results to a dataframe
        results_df = pd.read_csv(results_path, index_col=0)

        # get questionnaire id from the file name
        questionnaire_id = csv_file.replace(RESULTS_FILE_PREFIX, "").replace(CSV, "")

        # save do results dictionary
        results_dict[questionnaire_id] = results_df

    return results_dict

# TODO CHECK IF DOMAIN EXISTS