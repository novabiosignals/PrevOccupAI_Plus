# -------------------------------------------------------------------------------------------------------------------- #
# imports
# -------------------------------------------------------------------------------------------------------------------- #
import os
from pathlib import Path
import pandas as pd

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
def calculate_biomechanical_scores(folder_path):

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

            results_df = _get_design_escritorio_results(answers_df)

        elif questionnaire_name == EQUIPAMENTOS:

            results_df = _get_equipamentos_results(answers_df)

        # it's incapacidade....
        else:
            results_df = _get_incapacidade_dor_results(answers_df)


        # set id column to int, set as index of the dataframe, and order
        results_df['id.1'] = pd.to_numeric(results_df['id.1'], errors='coerce')
        results_df = results_df.set_index('id.1').sort_index()

        # save dataframe into a csv file
        folder_path = create_dir(Path(__file__).parent, os.path.join(RESULTS_FOLDER_NAME, get_group_from_path(folder_path),'biomecanico'))
        results_df.to_csv(os.path.join(folder_path, f"{questionnaire_name}{CSV}"))


# -------------------------------------------------------------------------------------------------------------------- #
# private functions
# -------------------------------------------------------------------------------------------------------------------- #

def _get_design_escritorio_results(results_df: pd.DataFrame) -> pd.DataFrame:

    # copy df
    df = results_df.copy()

    # replace limesurvey values of multiple choice questions with the ROSA values
    df = rt.pre_process_rosa(df, [rosa_qm.rosa_mappings_section_a])

    # calculate scores for section a - chair
    rt.calc_a_score(df)

    # keep only the relevant columns
    scores_df = df[['id.1', 'score_a_normalized']]

    # rename scores column name
    scores_df.rename(columns={"score_a_normalized": "cadeira"})

    return scores_df


def _get_equipamentos_results(results_df: pd.DataFrame) -> pd.DataFrame:

    # copy original df
    df = results_df.copy()

    # replace limesurvey values of multiple choice and special yes/no questions with the ROSA values
    df = rt.pre_process_rosa(df, [rosa_qm.rosa_mappings_section_b, rosa_qm.rosa_mappings_section_c])

    # calculate score for section b and c
    rt.calc_b_c_scores(df)

    # keep only the relevant columns with the scores
    scores_df = df[['id.1', 'monitor_score', 'phone_score', 'mouse_score', 'keyboard_score']]

    # rename for easier read and portuguese
    scores_df = scores_df.rename(columns={"monitor_score": "Monitor", "phone_score": "Telefone", "mouse_score": "Rato", "keyboard_score": "Teclado"})

    return scores_df


def _get_incapacidade_dor_results(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans and standardizes data for readability and consistency.
    No scores are calculated in this questionnaire.

    :return:
    """
    # create copy
    df = results_df.copy()

    # Rename columns for readability
    rename_map = dict(zip(ID_OLD_COLUMNS, ID_NEW_COLUMNS))
    df.rename(columns=rename_map)

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
