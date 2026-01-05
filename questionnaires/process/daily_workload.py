"""
Function to clean the daily workload questionnaires

Available Functions
-------------------
[Public]
clean_daily_workload(...): Cleans the dataframe with the daily workload questionnaire answers.
-------------------

[Private]
None
-------------------
"""
# -------------------------------------------------------------------------------------------------------------------- #
# imports
# -------------------------------------------------------------------------------------------------------------------- #
import os

# internal imports
from utils import find_project_root, create_dir, extract_group_from_path
from questionnaires.load.questionnaire_loader import load_questionnaire_answers
from constants import WORKLOAD, CSV
from questionnaires.process.mappings.questionnaire_mappings import WORKLOAD_COLUMN_NAMES_MAP

# -------------------------------------------------------------------------------------------------------------------- #
# public functions
# -------------------------------------------------------------------------------------------------------------------- #

def clean_daily_workload(folder_path: str, output_folder_path: str) -> None:
    """
    Cleans the dataframe with the daily workload questionnaire answers. Cleans the column names to be more readable and
    likert scale from A1, A2, A3, A4, A5 -> 1,2,3,4,5.

    :param folder_path: Path to the folder containing the several questionnaire domains (subfolders)
    :param output_folder_path: Path to the folder where the cleaned answers will be saved.
    :return: None
    """

    # load results_questionnaires for all domain questionnaires into a dictionary
    # (keys: questionnaire id, values: dataframe with the results_questionnaires)
    results_dict = load_questionnaire_answers(folder_path, domain=WORKLOAD)

    # get the only item of the dictionary - there is only one workload questionnaire
    (questionnaire_id, results_df), = results_dict.items()

    # clean column names
    results_df.rename(columns=WORKLOAD_COLUMN_NAMES_MAP, inplace=True)

    # remove 'A' from likert scale answers (except last question which is open)
    for col in results_df.columns[2:-1]:

        # remove the prefix 'A' from
        results_df[col] = results_df[col].str.replace("^A", "", regex=True)

    # set id column to int, set as index of the dataframe, and order
    results_df = results_df.set_index('id.1').sort_index()

    results_df = results_df.astype(str)

    # save dataframe into a csv file
    folder_path = create_dir(find_project_root(),
                             os.path.join(output_folder_path, extract_group_from_path(folder_path)))
    results_df.to_csv(os.path.join(folder_path, f"workload{CSV}"))
