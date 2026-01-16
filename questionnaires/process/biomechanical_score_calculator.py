"""
Function to calculate rosa scores (pure and adapted) and to clean biomechanical questionnaire answers.

Available Functions
-------------------
[Public]
calculate_rosa_scores(...): Calculates the final pure rosa score (not normalized and min-max normalized) for each subject of one group
calculate_biomechanical_scores(...): Calculates the individual rosa scores and cleans the answers for the biomechanical questionnaires of one group.
-------------------

[Private]
_get_design_escritorio_results(...): Calculate a score results for each subject.
_get_equipamentos_results(...): Calculate b and c scores results for each subject.
_get_incapacidade_dor_results(...): Cleans the dataframe with the questionnaire answers.
-------------------
"""

# -------------------------------------------------------------------------------------------------------------------- #
# imports
# -------------------------------------------------------------------------------------------------------------------- #
import os
from pathlib import Path
import pandas as pd
from typing import List

# internal imports
from questionnaires.load.questionnaire_loader import load_questionnaire_answers
from utils import load_json_file, create_dir, extract_group_from_path, find_project_root
from constants import CONFIG_FOLDER_NAME, CSV
import questionnaires.process.rosa_tools as rt
import questionnaires.process.mappings.rosa_question_mappings as rosa_qm
from questionnaires.process.mappings.questionnaire_mappings import ID_OLD_COLUMNS, ID_NEW_COLUMNS, ID_ANSWERS_MAP, ID_PAIN_PERCEPTION_MAPPING

# -------------------------------------------------------------------------------------------------------------------- #
# constants
# -------------------------------------------------------------------------------------------------------------------- #
DESIGN_ESCRITORIO = "Design do Escritório"
EQUIPAMENTOS = "Equipamentos"
INCAPACIDADE_DOR = "Incapacidade e Sofrimento associados a Dor"

# -------------------------------------------------------------------------------------------------------------------- #
# public functions
# -------------------------------------------------------------------------------------------------------------------- #
def calculate_rosa_scores(folder_path: str, output_folder_path: str) -> None:
    """
    Calculates the final pure rosa score (not normalized and min-max normalized) for each subject of one group
    and saves them as a csv file. Assumes that the questionnaire answers are stored in a directory such as:
    '...\\group1\\biomechanical\\files.csv'.

    (scores are based on: https://www.sciencedirect.com/science/article/pii/S0003687011000433?via%3Dihub)

    :param folder_path: Path to the folder containing the several questionnaire domains (subfolders)
    :param output_folder_path: Path to the folder where the scores will be saved.
    :return: None
    """

    # load results_questionnaires for all domain questionnaires into a dictionary
    # (keys: questionnaire id, values: dataframe with the results_questionnaires)
    results_dict = load_questionnaire_answers(folder_path, domain="biomechanical")

    # get the dataframe of equipamentos and design escritório
    df_equip = results_dict['622581']
    df_design = results_dict['537796']

    # get rosa scores
    df_a_scores = _get_design_escritorio_results(df_design, pure_rosa=True)
    df_b_c_scores = _get_equipamentos_results(df_equip, pure_rosa=True)

    # get final rosa scores
    scores_df = rt.calc_final_rosa_score(df_a_scores, df_b_c_scores)

    # save dataframe into a csv file
    folder_path = create_dir(find_project_root(), os.path.join(output_folder_path, f"group{extract_group_from_path(folder_path)}"))
    scores_df.to_csv(os.path.join(folder_path, f"rosa_scores{CSV}"))


def calculate_biomechanical_scores(folder_path, pure_rosa: bool, output_folder_path: str) -> None:
    """
    Calculates the individual rosa scores and cleans the answers for the biomechanical questionnaires of one group. Assumes that
    the questionnaire answers are stored in a directory such as: '...\\group1\\biomechanical\\files.csv'
    Saves the results into a csv file. If pure_rosa = True, extra (non-rosa) answers are dropped and pure rosa scores
    are calculated. If False, adapted scores are obtained.

    :param folder_path: Path to the folder containing the several questionnaire domains (subfolders)
    :param pure_rosa: Bool if true calculate pure rosa scores, if false, calculate adapted score.
    :param output_folder_path: Path to the folder where the scores will be saved.
    :return: None
    """

    # list for holding the scores_df for all questionnaires
    list_dfs: List[pd.DataFrame] = []

    # load results_questionnaires for all domain questionnaires into a dictionary
    # (keys: questionnaire id, values: dataframe with the results_questionnaires)
    results_dict = load_questionnaire_answers(folder_path, domain="biomechanical")

    # load config json file
    config_dict = load_json_file(os.path.join(Path(__file__).parent, CONFIG_FOLDER_NAME, "cfg_biomechanical.json"))

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

        # drop submit date columns
        results_df = results_df.drop(columns=results_df.filter(regex='(?i)^submitdate$').columns)

        # add dataframe to list
        list_dfs.append(results_df)

    # concat dataframes horizontally to have all personal questionnaires
    final_df = pd.concat(list_dfs, axis=1)

    # fill NaN values with 0
    final_df.fillna('N', inplace=True)

    # save dataframe into a csv file
    folder_path = create_dir(find_project_root(), os.path.join(output_folder_path, f"group{extract_group_from_path(folder_path)}"))
    final_df.to_csv(os.path.join(folder_path, f"results_biomechanical{CSV}"))


# -------------------------------------------------------------------------------------------------------------------- #
# private functions
# -------------------------------------------------------------------------------------------------------------------- #

def _get_design_escritorio_results(results_df: pd.DataFrame, pure_rosa: bool) -> pd.DataFrame:
    """
    Calculate a score results for each subject. If pure_rosa = True, calculates the pure a-score from
    https://www.sciencedirect.com/science/article/pii/S0003687011000433?via%3Dihub
    If pure_rosa = False, the extra (non-ROSA) questions are kept and an adapted a-score (chair) is calculated.
    The scores are min-max normalized.

    :param results_df: Dataframe with the questionnaire results.
    :param pure_rosa: bool if true calculate pure rosa scores, if false, calculate adapted score.
    :return: DataFrame with the results
    """

    # copy df
    df = results_df.copy()

    # replace limesurvey values of multiple choice questions with the ROSA values
    df = rt.pre_process_rosa(df, [rosa_qm.rosa_mappings_section_a])

    # calculate scores for section a - chair
    df = rt.calc_a_score(df, pure_rosa=pure_rosa)

    return df


def _get_equipamentos_results(results_df: pd.DataFrame, pure_rosa: bool) -> pd.DataFrame:
    """
    Calculate b and c scores results for each subject. If pure_rosa = True, calculates the pure a score from
    https://www.sciencedirect.com/science/article/pii/S0003687011000433?via%3Dihub
    If pure_rosa = False, the extra (non-ROSA) questions are kept and adapted scores for monitor, phone, mouse, and keyboard
    are calculated. The scores are min-max normalized.

    :param results_df: a dataframe with the questionnaire results.
    :param pure_rosa: bool if true calculate pure rosa scores, if false, calculate adapted scores.
    :return: DataFrame with the results
    """

    # copy original df
    df = results_df.copy()

    # replace limesurvey values of multiple choice and special yes/no questions with the ROSA values
    df = rt.pre_process_rosa(df, [rosa_qm.rosa_mappings_section_b, rosa_qm.rosa_mappings_section_c])

    # calculate score for section b and c
    df = rt.calc_b_c_scores(df, pure_rosa=pure_rosa)

    return df


def _get_incapacidade_dor_results(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans the dataframe with the questionnaire answers.
    This functions changes the column names and answers from codes to readable text.
    :param results_df: The dataframe with the raw questionnaire answers.
    :return: A pandas DataFrame with cleaned questionnaire answers.
    """
    # create copy
    df = results_df.copy()

    # rename incapacidade / sofrimento / intensidade columns
    for old, new in zip(ID_OLD_COLUMNS, ID_NEW_COLUMNS):
        mask = df.columns.str.contains(old) & (
                df.columns.str.contains('incapacidade', case=False) |
                df.columns.str.contains('sofrimento', case=False) |
                df.columns.str.contains('intensidade', case=False) |
                df.columns.str.contains('tempo', case=False) |
                df.columns.str.contains('localizacao', case=False)
        )
        df.columns = df.columns.where(~mask, df.columns.str.replace(old, new, regex=False))

    # rename pain perception columns
    df.rename(columns=ID_PAIN_PERCEPTION_MAPPING, inplace=True)

    # replace missing values with '0'
    df = df.fillna('N')

    # iterate through the columns
    for col in df.columns:

        # if column name has 'incapacidade' or 'sofrimento'
        if 'incapacidade' in col.lower() or 'sofrimento' in col.lower() or 'intensidade' in col.lower():

            # clean answers
            df[col] = df[col].replace(ID_ANSWERS_MAP["incapacidade_sofrimento"])

        # if column name has 'tempo'
        elif 'tempo' in col:

            # clean tempo
            df[col] = df[col].replace(ID_ANSWERS_MAP["tempo"])

    return df
