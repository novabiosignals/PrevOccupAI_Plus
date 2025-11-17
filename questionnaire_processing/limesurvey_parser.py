# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import pandas as pd
import os
from pathlib import Path

from constants import CSV, QUESTIONNAIRE_DOMAINS, AMBIENTE, PSICOSSOCIAL, CONFIG_FOLDER_NAME
from utils import create_dir, load_json_file

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #


def generate_questionnaires_dataset(file_paths_dir: str, output_folder_path: str) -> None:
    # load metadata
    meta_data_df = pd.read_csv('participants_info.csv', sep=';', encoding='utf-8')

    # cycle over unique groups
    for group_num in meta_data_df['group'].unique():

        # get sb dataframe with only the data from the group
        group_df = meta_data_df[meta_data_df['group'] == group_num]

        # output folder
        group_output_folder_path = create_dir(os.path.join(output_folder_path, f"group{str(group_num)}"),'questionnaires')

        # cycle over questionnaire domains
        for domain in QUESTIONNAIRE_DOMAINS:

            # load json file with the info for the given domain
            config_dict = load_json_file(os.path.join(Path(__file__).parent, CONFIG_FOLDER_NAME, f"cfg_{domain.lower()}.json"))

            # if domain is psicossocial or ambiente json is configured slightly different
            if domain == PSICOSSOCIAL or domain == AMBIENTE:

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

                # load, clean results df, and save in appropriate folders
                group_survey_df = _load_and_clean_limesurvey_results(os.path.join(file_paths_dir, survey_filename), group_df['subject_id'])

                # generate path to folder with domain name
                domain_path = create_dir(group_output_folder_path, domain)

                # save csv_file
                group_survey_df.to_csv(os.path.join(domain_path, f"results_{str(survey_id)}{CSV}"))


# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #

def _load_and_clean_limesurvey_results(limesurvey_csv_path: str, subject_ids: pd.Series):

    # load raw limesurvey csv
    limesurvey_df = pd.read_csv(limesurvey_csv_path)

    # Keep only rows with IDs present in the given series
    group_df = limesurvey_df[limesurvey_df['hiddenid'].isin(subject_ids)]

    # reset df index
    group_df = group_df.reset_index(drop=True)

    # clean df
    group_df = _clean_limesurvey_files(group_df)


    return group_df


def _clean_limesurvey_files(df: pd.DataFrame):

    # rename hiddenid column to just id
    df = df.rename(columns={'hiddenid': 'id.1'})

    # drop all irrelevant initial columns except submitdate and the hidden ids
    df = df.drop(df.columns[[0, *range(2, 9)]], axis=1)

    # define columns to drop which have irrelevant info in between pages
    cols_to_drop = df.filter(regex='(?i)(interviewtime|groupTime|hiddenTime)').columns

    # drop those columns
    df = df.drop(columns=cols_to_drop)

    # convert submitdate to real datetime
    df['submitdate'] = pd.to_datetime(df['submitdate'], errors='coerce')

    # drop submissions with no submitdate
    df = df.dropna(subset=['submitdate'])

    # sort by submitdate, then keep only the most recent submission per participant
    df = (df.sort_values('submitdate').drop_duplicates(subset=['id'], keep='last').reset_index(drop=True))

    return df


def _find_survey_path(paths: list[str], survey_id: str) -> str:
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