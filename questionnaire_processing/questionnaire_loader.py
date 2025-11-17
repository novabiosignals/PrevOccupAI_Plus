# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import pandas as pd
import os
from typing import Dict
import json
from citric import Client
import io
from pathlib import Path

from constants import CSV, QUESTIONNAIRE_DOMAINS, AMBIENTE, PSICOSSOCIAL, CONFIG_FOLDER_NAME
from utils import create_dir, load_json_file

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
        results_df = pd.read_csv(results_path)

        # remove columns with irrelevant information (2 to 8) - limeSurvey always generates these columns
        results_df = results_df.drop(results_df.columns[2:9], axis=1)

        # get questionnaire id from the file name
        questionnaire_id = csv_file.replace(RESULTS_FILE_PREFIX, "").replace(CSV, "")

        # save do results dictionary
        results_dict[questionnaire_id] = results_df

    return results_dict

# TODO CHECK IF DOMAIN EXISTS
def generate_results_csv_files(output_folder_path: str) -> None:

    # load metadata
    meta_data_df = pd.read_csv('participants_cml.csv', sep=';', encoding='utf-8', index_col='subject_id')

    # cycle over unique groups
    for group_num in meta_data_df['group'].unique():

        # get sb dataframe with only the data from the group
        group_df = meta_data_df[meta_data_df['group'] == group_num]

        # output folder
        group_output_folder_path = create_dir(os.path.join(output_folder_path, f"group{str(group_num)}"), 'questionnaires')

        # cycle over questionnaire domains
        for domain in QUESTIONNAIRE_DOMAINS:

            # load json file with the info for the given domain
            config_dict = load_json_file(os.path.join(Path(__file__).parent, CONFIG_FOLDER_NAME, f"cfg_{domain.lower()}.json"))

            # if domain is psicossocial or ambiente json is configured slightly different
            if domain == PSICOSSOCIAL or domain == AMBIENTE:

                # get list with ids
                ids_list = [questionnaire["id"] for questionnaire in config_dict.values()]

            else:

                # get list with survey ids
                ids_list = list(config_dict.keys())

            # load all surveys from this domain
            for survey_id in ids_list:

                # generate results
                _get_ls_results(dom=domain, survey_id=survey_id, participants=group_df, data_folder=group_output_folder_path)




# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #



def _get_ls_results(dom: str, survey_id: str, participants, data_folder: str):
    """
    Function to generate a csv file with the answers exported from limesurvey questionnaires
    It is required a configuration file with the credentials to access LimeSurvey (URL, user, pass)
    :param dom: str
        domain of questionnaires to be exported (ex. "Psicossociais")
    :param survey_id: str
        id in LimeSurvey of the questionnaire to export
    :param participants: dataframe
        participants of group to export answers
    :param data_folder: str
        folder to store the data exported
    :return: no return type
        data is stored locally
    """

    # open configuration file that has the credentials to access limesurvey
    with open(os.path.join(Path(__file__).parent, CONFIG_FOLDER_NAME, "lime_survey.json"), "r") as f:
        conf = json.load(f)

    # use credentials of LimeSurvey to have access to surveys responses
    with Client(conf['LS']['LS_URL'], conf['LS']['LS_USER'], conf['LS']['LS_PASS']) as client:
        # open responses as dataframe, with the id from wordpress as index
        results = pd.read_csv(
            io.BytesIO(client.export_responses(survey_id=int(survey_id), file_format='csv')), delimiter=";",
            parse_dates=["datestamp", "startdate", "submitdate"], index_col="id.1")
        # drop id generated by limesurvey
        results = results.drop(['id'], axis=1)
        # convert index to numeric values and remove the non numeric ones
        results = results[pd.to_numeric(results.index, errors='coerce').notnull()]
        results.index = results.index.astype(int)
        # keep only the concluded questionnaires (correspond to the ones with a valid submit date)
        results = results[~pd.isna(results.submitdate)]
        # in case there is more than one answer to the same questionnaire by the same participant, keep last
        results = results[~results.index.duplicated(keep='last')]
        # keep only the responses of the participants to be analysed
        results = results[results.index.isin(participants.index.tolist())]
        # store the filtered results
        results.to_csv(data_folder + '/questionnaires/' + dom + '/results_' + str(survey_id) + '.csv')