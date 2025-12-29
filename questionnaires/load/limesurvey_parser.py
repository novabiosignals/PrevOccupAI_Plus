"""
Function to generate the questionnaires dataset

Available Functions
-------------------
[Public]
generate_questionnaires_dataset(...): Generates the questionnaire dataset by organizing the raw files by group and questionnaire domain, downloaded from limesurvey.
-------------------

[Private]
_load_and_clean_limesurvey_results(...): Loads a raw LimeSurvey CSV file, filters it to keep only the list of ids in subject_ids, and cleans the data.
_clean_limesurvey_files(...): Cleans the limesurvey dataframe by removing irrelevant columns.
_find_survey_path(...): finds the path with a given survey id in the filename
-------------------
"""
# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import pandas as pd
import os
import re

# internal imports
from constants import CSV, QUESTIONNAIRE_DOMAINS, ENVIRONMENT, PSYCHOSOCIAL, CONFIG_FOLDER_NAME, WORKLOAD
from utils import create_dir, load_json_file, find_project_root
import sensors.load as sl

# ------------------------------------------------------------------------------------------------------------------- #
# constants
# ------------------------------------------------------------------------------------------------------------------- #
OUTPUT_FOLDER_NAME = 'questionnaires'

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #


def generate_questionnaires_dataset(file_paths_dir: str, output_folder_path: str) -> None:
    """
    Generates the questionnaire dataset by organizing the raw files by group and questionnaire domain, downloaded from limesurvey.
    Each file should have the questionnaire id in the filename and should have the answers from all subjects.
    All raw files (from all questionnaires of the valid domains) should be in a folder in file_paths_dir.
    This function then organizes the answers by group and domain, generating csv files with only the results of the subjects
    of the same group.

    Saves the results as follows: (example) 'output_folder_path/questionnaires/group1/psychosocial/results_279517.csv'

    :param file_paths_dir: Path to the folder containing all raw limesurvey files for all questionnaires.
    :param output_folder_path: Path to the folder where to save the generated dataset.
    :return: None
    """
    # load metadata
    meta_data_df = sl.load_participants_info()

    # cycle over unique groups
    for group_num in meta_data_df['group'].unique():

        # get sb dataframe with only the data from the group
        group_df = meta_data_df[meta_data_df['group'] == group_num]

        # output folder
        group_output_folder_path = create_dir(os.path.join(output_folder_path, f"group{str(group_num)}"),OUTPUT_FOLDER_NAME)

        # cycle over questionnaire domains
        for domain in QUESTIONNAIRE_DOMAINS:

            # load json file with the info for the given domain
            config_dict = load_json_file(os.path.join(find_project_root(), 'questionnaires', 'process', CONFIG_FOLDER_NAME, f"cfg_{domain.lower()}.json"))

            # if domain is psicossocial or ambiente json is configured slightly different
            if domain == PSYCHOSOCIAL or domain == ENVIRONMENT:

                # get list with ids
                survey_ids_list = [questionnaire["id"] for questionnaire in config_dict.values()]

            else:

                # get list with survey ids
                survey_ids_list = list(config_dict.keys())

            # load all surveys from this domain
            for survey_id in survey_ids_list:

                # get list of dir
                file_paths_list = os.listdir(file_paths_dir)

                # find id in the list with paths
                survey_filename = _find_survey_path(file_paths_list, str(survey_id))

                # load, clean results_questionnaires df, and save in appropriate folders
                group_survey_df = _load_and_clean_limesurvey_results(os.path.join(file_paths_dir, survey_filename), group_df.index, domain)

                # generate path to folder with domain name
                domain_path = create_dir(group_output_folder_path, domain)

                # save csv_file
                group_survey_df.to_csv(os.path.join(domain_path, f"results_{str(survey_id)}{CSV}"))


# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #

def _load_and_clean_limesurvey_results(limesurvey_csv_path: str, subject_ids: pd.Series, domain: str) -> pd.DataFrame:
    """
    Loads a raw LimeSurvey CSV file, filters it to keep only the list of ids in subject_ids, and cleans the data.

    :param limesurvey_csv_path: Path to the raw LimeSurvey CSV file.
    :param subject_ids: Series of subject IDs to keep in the dataset.
    :param domain: Questionnaire domain, used to customize cleaning.
    :return: Cleaned dataframe with only the relevant subjects and columns.
    """

    # load raw limesurvey csv
    limesurvey_df = pd.read_csv(limesurvey_csv_path)

    # Keep only rows with IDs present in the given series
    group_df = limesurvey_df[limesurvey_df['hiddenid'].isin(subject_ids)]

    # reset df index
    group_df = group_df.reset_index(drop=True)

    # clean df
    group_df = _clean_limesurvey_files(group_df, domain)

    return group_df


def _clean_limesurvey_files(df: pd.DataFrame, domain: str) -> pd.DataFrame:
    """
    Cleans a LimeSurvey dataframe by renaming columns, dropping irrelevant columns,
    converting submission dates, and keeping the most recent submission per participant.

    :param df: Raw LimeSurvey dataframe.
    :param domain: Questionnaire domain, used to determine cleaning rules.
    :return: The cleaned dataframe.
    """
    # rename hiddenid column to just id
    df = df.rename(columns={'hiddenid': 'id.1'})

    # drop all irrelevant initial columns except submitdate and the hidden ids
    df = df.drop(df.columns[[0, *range(2, 9)]], axis=1)

    # define columns to drop which have irrelevant info in between pages
    cols_to_drop = df.filter(regex='(?i)(interviewtime|groupTime|hiddenTime)').columns

    # drop those columns
    df = df.drop(columns=cols_to_drop)

    # drop submissions with no submitdate
    df = df.dropna(subset=['submitdate'])

    if domain != WORKLOAD:

        # convert submitdate to real datetime
        df['submitdate'] = pd.to_datetime(df['submitdate'], errors='coerce')

        # sort by submitdate, then keep only the most recent submission per participant
        df = (df.sort_values('submitdate').drop_duplicates(subset=['id.1'], keep='last').reset_index(drop=True))

    return df

def _find_survey_path(paths: list[str], survey_id: str) -> str:
    """
    Finds the file path with the survey_id in the filename.

    Searches in a list of file paths if one of them contain the survey ID in the filename.
    Raises an error if no paths or multiple paths match.

    :param paths: List of file paths to search.
    :param survey_id: Survey ID to locate in the file paths.
    :return: The single path that contains the survey ID.
    """
    # Find all paths that contain the substring
    matching_paths = [path for path in paths if survey_id in path]

    # raise error if none was found
    if len(matching_paths) == 0:
        raise ValueError(f"No paths found containing '{survey_id}'.")

    # raise error if multiple were found
    elif len(matching_paths) > 1:
        raise ValueError(f"Multiple paths found containing '{survey_id}': {matching_paths}")

    # Exactly one match, return it
    return matching_paths[0]