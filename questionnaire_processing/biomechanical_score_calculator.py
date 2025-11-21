# -------------------------------------------------------------------------------------------------------------------- #
# imports
# -------------------------------------------------------------------------------------------------------------------- #
import os
from pathlib import Path
import pandas as pd
from typing import List

# internal imports
from .questionnaire_loader import load_questionnaire_answers
from utils import load_json_file, create_dir, get_group_from_path
from constants import CONFIG_FOLDER_NAME, RESULTS_FOLDER_NAME, CSV
import questionnaire_processing.rosa.rosa_tools as rt
import questionnaire_processing.rosa.rosa_question_mappings as rosa_qm
from .questionnaire_mappings import ID_OLD_COLUMNS, ID_NEW_COLUMNS, ID_ANSWERS_MAP


# -------------------------------------------------------------------------------------------------------------------- #
# constants
# -------------------------------------------------------------------------------------------------------------------- #
DESIGN_ESCRITORIO = "Design do Escritório"
EQUIPAMENTOS = "Equipamentos"
INCAPACIDADE_DOR = "Incapacidade e Sofrimento associados a Dor"

# -------------------------------------------------------------------------------------------------------------------- #
# public functions
# -------------------------------------------------------------------------------------------------------------------- #
def calculate_rosa_scores(folder_path: str):

    # load results for all domain questionnaires into a dictionary
    # (keys: questionnaire id, values: dataframe with the results)
    results_dict = load_questionnaire_answers(folder_path, domain="biomecanico")

    # get the dataframe of equipamentos and design escritório
    df_equip = results_dict['622581']
    df_design = results_dict['537796']

    # get rosa scores
    df_a_scores = _get_design_escritorio_results(df_design, pure_rosa=True)
    df_b_c_scores = _get_equipamentos_results(df_equip, pure_rosa=True)

    # get final rosa scores
    scores_df = rt.calc_final_rosa_score(df_a_scores, df_b_c_scores)

    # save dataframe into a csv file
    folder_path = create_dir(Path(__file__).parent,
                             os.path.join(RESULTS_FOLDER_NAME, get_group_from_path(folder_path)))
    scores_df.to_csv(os.path.join(folder_path, f"rosa_scores{CSV}"))


def calculate_biomechanical_scores(folder_path, pure_rosa: bool):

    # list for holding the scores_df for all questionnaires
    list_dfs: List[pd.DataFrame] = []

    # load results for all domain questionnaires into a dictionary
    # (keys: questionnaire id, values: dataframe with the results)
    results_dict = load_questionnaire_answers(folder_path, domain="biomecanico")

    # load config json file
    config_dict = load_json_file(os.path.join(Path(__file__).parent, CONFIG_FOLDER_NAME, "cfg_biomecanico.json"))

    for questionnaire_id, answers_df in results_dict.items():

        # Check if the questionnaire_id exists in config_dict
        if questionnaire_id not in config_dict:
            print(f"Warning: questionnaire_id {questionnaire_id} not found in config. Skipping...")
            continue  # skip to the next one

        # get questionnaire name from config
        questionnaire_name = config_dict[questionnaire_id]

        if questionnaire_name == DESIGN_ESCRITORIO:

            results_df = _get_design_escritorio_results(answers_df, pure_rosa=pure_rosa)

        elif questionnaire_name == EQUIPAMENTOS:

            results_df = _get_equipamentos_results(answers_df, pure_rosa=pure_rosa)

        # it's incapacidade....
        else:
            results_df = _get_incapacidade_dor_results(answers_df)


        # set id column to int, set as index of the dataframe, and order
        results_df['id.1'] = pd.to_numeric(results_df['id.1'], errors='coerce')
        results_df = results_df.set_index('id.1').sort_index()

        # add dataframe to list
        list_dfs.append(results_df)

    # concat dataframes horizontally to have all personal questionnaires
    final_df = pd.concat(list_dfs, axis=1)

    # save dataframe into a csv file
    folder_path = create_dir(Path(__file__).parent,
                             os.path.join(RESULTS_FOLDER_NAME, get_group_from_path(folder_path)))
    final_df.to_csv(os.path.join(folder_path, f"results_biomecanico{CSV}"))


# -------------------------------------------------------------------------------------------------------------------- #
# private functions
# -------------------------------------------------------------------------------------------------------------------- #

def _get_design_escritorio_results(results_df: pd.DataFrame, pure_rosa: bool) -> pd.DataFrame:

    # copy df
    df = results_df.copy()

    # replace limesurvey values of multiple choice questions with the ROSA values
    df = rt.pre_process_rosa(df, [rosa_qm.rosa_mappings_section_a])

    # calculate scores for section a - chair
    df = rt.calc_a_score(df, pure_rosa=pure_rosa)

    return df


def _get_equipamentos_results(results_df: pd.DataFrame, pure_rosa: bool) -> pd.DataFrame:

    # copy original df
    df = results_df.copy()

    # replace limesurvey values of multiple choice and special yes/no questions with the ROSA values
    df = rt.pre_process_rosa(df, [rosa_qm.rosa_mappings_section_b, rosa_qm.rosa_mappings_section_c])

    # calculate score for section b and c
    df = rt.calc_b_c_scores(df, pure_rosa=pure_rosa)

    return df


def _get_incapacidade_dor_results(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans and standardizes data for readability and consistency.
    No scores are calculated in this questionnaire.

    :return:
    """
    # create copy
    df = results_df.copy()

    # Replace any column substring "SQ00X" with the new descriptive name
    for old, new in zip(ID_OLD_COLUMNS, ID_NEW_COLUMNS):
        df.columns = df.columns.str.replace(old, new, regex=False)

    # replace missing values with '0'
    df = df.fillna('0')

    # iterate through the columns
    for col in df.columns:

        # if column name has 'incapacidade' or 'sofrimento'
        if 'incapacidade' in col or 'sofrimento' in col:

            # clean answers
            df[col] = df[col].replace(ID_ANSWERS_MAP["incapacidade_sofrimento"])

        # if column name has 'tempo'
        elif 'tempo' in col:

            # clean tempo
            df[col] = df[col].replace(ID_ANSWERS_MAP["tempo"])

    return df
