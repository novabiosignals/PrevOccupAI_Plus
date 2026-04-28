"""
Function to calculate psychosocial and environment scores

Available Functions
-------------------
[Public]
get_psychosocial_scores(...): Calculates COPSOQ and MUEQ scores for the entire population or work type.
calculate_linear_scores(...): Calculates the individual scores for the psychosocial and environment questionnaires for one group.
-------------------

[Private]
_calculate_mean_scores(...): calculates the mean of the psychosocial scores of all subjects.
_calculate_individual_scores(...): calculates the normalized individual scores for all subjects.
_assign_answer_values(...): Map questionnaire responses to scoring values.
_clean_results_dataframe(...): Cleans likert scale answers.
_create_df_from_lists(...): Merge multiple psychosocial questionnaires into a single-row DataFrame.
_get_all_psychosocial_results(...): Load and aggregate all psychosocial questionnaire results into one single dataframe.
_get_questionnaire_name_from_json(...): Extracts the questionnaire name from a JSON configuration file by matching the questionnaire id.
_check_valid_domain(...): checks if the input domain is valid
_check_valid_average_method(...): checks if the input average method is valid
-------------------
"""

# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import os
from typing import List, Optional, Dict, Any
import pandas as pd

# internal imports
from utils import load_json_file, create_dir, extract_group_from_path, find_project_root
from questionnaires.load.questionnaire_loader import load_questionnaire_answers
from constants import CONFIG_FOLDER_NAME, CSV, ENVIRONMENT, PSYCHOSOCIAL, WORK_TYPE, POPULATION

# ------------------------------------------------------------------------------------------------------------------- #
# constants
# ------------------------------------------------------------------------------------------------------------------- #
JSON_SCORES_FILENAME = 'scores.json'
LIKERT_SCALE = 'likert'
COPSOQ_RESULTS_FOLDER = 'COPSOQ_results'
NON_COPSOQ_COLUMNS = ['Autonomia', 'Qualidade das Pausas']

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #

def get_psychosocial_scores(folder_path: str, average_method: str, output_folder_path: str) -> None:
    """
    Loads psychosocial questionnaire results for all subjects, separates COPSOQ and MUEQ
    questionnaire data, computes their mean scores, and saves the results.

    :param folder_path: Path to the folder containing the raw psychosocial questionnaire result files for all subjects.
    :param average_method: Average method to be used for calculating the copsoq scores.
                            Supported methods: 'population', 'work_type'
    :param output_folder_path: Path to the folder where the scores will be saved.
    :return: None
    """
    # check if average_method is valid
    _check_valid_average_method(average_method)

    # get dataframe with the psicossocial results_questionnaires for all subjects
    all_results_df = _get_all_psychosocial_results(folder_path)

    # get only COPSOQ dataframe
    all_copsoq_df = all_results_df.drop(columns=NON_COPSOQ_COLUMNS, errors='ignore')

    # get only MUEQ dataframe and id.1 column
    all_mueq_df = all_results_df[NON_COPSOQ_COLUMNS + ["id.1"]]

    # calculate COPSOQ scores
    _calculate_mean_scores(all_copsoq_df, 'COPSOQ', average_method, output_folder_path)

    # calculate MUEQ scores
    _calculate_mean_scores(all_mueq_df, 'MUEQ', average_method, output_folder_path)


def calculate_linear_scores(folder_path: str, domain: str, output_folder_path: str) -> None:
    """
    Calculates the individual scores for the psychosocial and environment questionnaires for one group. Assumes that
    the questionnaire answers are stored in a directory such as: '...\\group1\\psychosocial(environment)\\files.csv'
    Saves the results into a csv file.

    :param folder_path: Path to the folder containing the several questionnaire domains (subfolders)
    :param domain: The domain of the questionnaires, which should be the name of the folder that contains the csv files.
                    For this function, only psychosocial and environment are available
    :param output_folder_path: Path to the folder where the scores will be saved.
    :return: None
    """
    # check if input domain is valid for this function
    _check_valid_linear_domain(domain)

    # list for holding the scores_df for all questionnaires
    list_dfs: List[pd.DataFrame] = []

    # load results_questionnaires for all domain questionnaires into a dictionary
    # (keys: questionnaire id, values: dataframe with the results_questionnaires)
    results_dict = load_questionnaire_answers(folder_path, domain)

    # load json file with the info for the given domain
    config_dict = load_json_file(os.path.join(find_project_root(), 'questionnaires', 'process', CONFIG_FOLDER_NAME, f"cfg_{domain.lower()}.json"))

    # load json file with the scores info
    scores_dict = load_json_file(os.path.join(find_project_root(), 'questionnaires', 'process', CONFIG_FOLDER_NAME, JSON_SCORES_FILENAME))

    # iterate through the results_questionnaires of the psicossocial questionnaires
    for questionnaire_id, results_df in results_dict.items():

        # create a scores dataframe for this questionnaire
        questionnaire_scores_df = pd.DataFrame()

        # get questionnaire name from the id
        questionnaire_name = _get_questionnaire_name_from_json(config_dict, questionnaire_id)

        # iterate through topics of the questionnaire
        domain_topics = config_dict[questionnaire_name]['topics']
        for topic_name, subtopics_dict in domain_topics.items():

            # get the columns of the dataframe related to the topic (ex: freqExigencias....)
            topic_cols = [col for col in results_df.columns if topic_name in col]
            topic_df = results_df[topic_cols]

            # iterate over the matrix topics (S1, S2, ...)
            for matrix_id, matrix_info in subtopics_dict.items():

                # get a dataframe with only the columns from the same topic and matrix (ex: freqExigenciasS1|1, freqExigenciasS1|2)
                subtopic_cols = [col for col in topic_df.columns if matrix_id in col]
                subtopic_df = topic_df[subtopic_cols]

                # get the same of the sub topic and the scale type
                subtopic_name = matrix_info["name"]
                questionnaire_scale = matrix_info["type"]

                # filter answers based on scale type
                subtopic_df = _clean_results_dataframe(questionnaire_scale, subtopic_df)

                # find calculation method, values, and the inverted scores in the scores json file
                calculation_method = scores_dict[subtopic_name]["calculation"]
                values = scores_dict[subtopic_name]["values"]
                inverted = scores_dict[subtopic_name]["inverted"]
                scale = scores_dict[subtopic_name]["scale"]
                max_value = scores_dict[subtopic_name]["max"]

                # calculate scores
                scores_series = _calculate_individual_scores(domain, subtopic_df, calculation_method, scale, values, inverted, max_value)

                # add subject id column and scores
                if not 'id' in questionnaire_scores_df.columns:

                    # get the id column from the results_questionnaires df - column name starts with id
                    id_col = results_df.filter(regex='id', axis=1).iloc[:, 0]

                    # add id column to the scores df
                    questionnaire_scores_df['id.1'] = id_col

                questionnaire_scores_df[subtopic_name] = scores_series

        # set id column to int, set as index of the dataframe, and order
        questionnaire_scores_df['id.1'] = questionnaire_scores_df['id.1'].apply(pd.to_numeric, errors='coerce')
        questionnaire_scores_df = questionnaire_scores_df.set_index('id.1').sort_index()

        # drop submit date columns
        questionnaire_scores_df = questionnaire_scores_df.drop(columns=questionnaire_scores_df.filter(regex='(?i)^submitdate$').columns)

        # add dataframe to list
        list_dfs.append(questionnaire_scores_df)


    # concat dataframes horizontally to have all psychosocial/environment questionnaires
    final_df = pd.concat(list_dfs, axis=1)

    # fill NaN values with 0
    final_df.fillna(0, inplace=True)

    # save dataframe into a csv file
    folder_path = create_dir(find_project_root(), os.path.join(output_folder_path, f"group{extract_group_from_path(folder_path)}"))
    final_df.to_csv(os.path.join(folder_path, f"results_{domain}{CSV}"))

# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #

def _calculate_mean_scores(all_results_df: pd.DataFrame, score_type: str, average_method: str,
                           output_folder_path: str) -> None:
    """
    Calculate pure COPSOQ or MUEQ scores. This function assumes that the psicossocial results_questionnaires have
    already been obtained for all groups. There are two averaging methods available.
    - 'all': obtains the copsoq scores by calculating the mean scores over all subjects
    - 'atendimento': obtains the copsoq scores by calculating the mean scores over front and back office subjects

    Saves the results_questionnaires in a csv file.

    :param all_results_df: Dataframe with th psychosocial scores for all participants
    :param score_type: Type of score: 'COPSOQ' or 'MUEQ'. Used for output filename only.
    :param average_method: Average method to be used for calculating the copsoq scores.
                        Supported methods: 'all', 'atendimento'
    :param output_folder_path: Path to the folder where the scores will be saved.
    :return: None
    """

    if average_method == POPULATION:

        # drop id column
        all_results_df = all_results_df.drop(columns=['id.1'], errors='ignore')

        scores_df = pd.DataFrame([all_results_df.mean().round(2)], index=['mean'])

    # it's average by work_type
    elif average_method == WORK_TYPE:

        # load subject info
        subjects_info_df = pd.read_csv((os.path.join(find_project_root(), 'participants_info.csv')), sep=';')

        # get list with subject ids for Front/Back office
        fo_subjects = subjects_info_df.loc[subjects_info_df['work_type'] == 'FO', 'subject_id'].tolist()
        bo_subjects = subjects_info_df.loc[subjects_info_df['work_type'] == 'BO', 'subject_id'].tolist()

        # Filter all_results_df for FO/BO subjects
        fo_df = all_results_df[all_results_df['id.1'].isin(fo_subjects)].copy()
        bo_df = all_results_df[all_results_df['id.1'].isin(bo_subjects)].copy()

        # drop id columns
        fo_df = fo_df.drop(columns=['id.1'], errors='ignore')
        bo_df = bo_df.drop(columns=['id.1'], errors='ignore')

        # calculate statistics and save in a dataframe
        scores_df = pd.DataFrame([fo_df.mean().round(4), bo_df.mean().round(4)], index=['mean_FO', 'mean_BO'])

    else:
        raise ValueError(
            f"The following average method is not supported. \nSupported methods are 'population' and 'work_type'")

    # save dataframe into a csv file
    scores_df.to_csv(os.path.join(output_folder_path, f"results_{score_type}_{average_method}{CSV}"))


def _calculate_individual_scores(domain:str, results_df: pd.DataFrame, calculation_method: str, scale: List[int], values: List[int],
                                 inverted: List[Optional[int]], max_value: int) -> pd.Series:
    """
    Calculate normalized domain scores for each participant.

    This function converts questionnaire responses into numeric values, applies scoring rules (including inverted
    questions), computes either a sum or mean score for each topic, and then normalizes
    the scores to a 0–1 range (min-max).

    :param results_df: Questionnaire domain. Supported domains are 'psicosocial' and 'ambiente'.
    :param calculation_method: Scoring method: either 'sum' or 'mean'.
    :param scale: List of possible answer values present in the DataFrame.
    :param values: List of scoring values to map each element of `scale` onto.
    :param inverted: List of column indices that must be scored in reverse order.
    :param max_value: The maximum possible score, used for normalization.
    :return: A pandas series containing the normalized score for each participant.
    """

    # convert all columns to numeric
    results_df = results_df.apply(pd.to_numeric, errors='coerce')

    # assign respective values to the given answers
    results_df = _assign_answer_values(results_df, scale, values, inverted)

    if calculation_method == 'sum':

        # sum all values per row and normalize
        scores_series = results_df.sum(axis=1)
        scores_series_norm = ((scores_series - min(values))/(max_value - min(values))).round(4)

    elif calculation_method == 'mean':

        # calculate the mean of all values per row and normalize
        scores_series = results_df.mean(axis=1)

        if domain == ENVIRONMENT:

            # normalize
            scores_series_norm = ((scores_series - min(values)) / (max_value - min(values))).round(4)

        else:

            scores_series_norm = ((scores_series - min(scale)) / (max_value - min(scale))).round(4)

    else:
        raise ValueError(f"The calculation method {calculation_method} does not exist.")

    return scores_series_norm


def _assign_answer_values(results_df: pd.DataFrame, scale: List[int], values: List[int], inverted: List[int]) -> pd.DataFrame:
    """
    Map questionnaire responses to scoring values.

    This function replaces each answer in the DataFrame according to the
    provided scale and scoring values. Columns listed in `inverted` use
    the reversed scoring order.

    :param results_df: DataFrame containing questionnaire answers.
    :param scale: List of possible answer values present in the DataFrame.
    :param values: List of scoring values to map each element of `scale` onto.
    :param inverted: List of column indices that must be scored in reverse order.
    :return:  A DataFrame with answers mapped to scoring values.
    """

    # create copy to avoid warnings
    results_df = results_df.copy()

    # iterate through the column indices
    for column_index in range(len(results_df.columns)):

        # if the column index matches the ones in inverted
        if column_index in inverted:

            # assign values and invert results_questionnaires
            results_df[results_df.columns[column_index]] = results_df[results_df.columns[column_index]].replace(scale, values[::-1])

        else:

            # assign values without inverting
            results_df[results_df.columns[column_index]] = results_df[results_df.columns[column_index]].replace(scale, values)

    return results_df


def _clean_results_dataframe(scale_type: str, subtopic_df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean questionnaire responses based on the scale type. Currently, supports the Likert scale by removing the prefix 'A'
    from all answer values (e.g., converting 'A1' → '1').

    :param scale_type: The type of scale used for the questions ('likert').
    :param subtopic_df: DataFrame containing raw answer strings for a specific subtopic.
    :return: A cleaned DataFrame with standardized answer formats.
    """
    # create copy to avoid warnings
    subtopic_df = subtopic_df.copy()

    for col in subtopic_df.columns:

        if scale_type == LIKERT_SCALE:

            # remove the prefix 'A' from
            subtopic_df[col] = subtopic_df[col].str.replace("^A", "", regex=True)

    return subtopic_df


def _create_df_from_lists(column_names_list: List[List[str]], list_sums_total: List[List[float]]):
    """
    Merge multiple psychosocial questionnaires into a single-row DataFrame.

    Each questionnaire is represented by a list of column names and a list of summed values.
    This function combines all questionnaires into one pandas DataFrame with:
    - Columns: all unique column names from every questionnaire
    - One row: summed values aligned with their respective columns

    :param column_names_list:  A list containing the column names for each questionnaire.
                                Example: [["A", "B", "C"], ["D", "E"]]
    :param list_sums_total: A list containing summed values for each questionnaire, aligned with the corresponding column names.
                            Example: [[10, 20, 30], [5, 15]]
    :return:  A single-row DataFrame with all columns from all questionnaires. Columns not present in a questionnaire
                will have their values in that row.
                Example output:

                    A     B     C     D     E
                0  10    20    30     5    15
    """
    # init pandas series to hold all summed values
    combined_series = pd.Series(dtype=float)

    # Loop over each questionnaire's columns and summed values
    for cols, sums in zip(column_names_list, list_sums_total):

        # Create a Series for this questionnaire (index = column names, data = summed values)
        s = pd.Series(data=sums, index=cols)

        # Append this Series to the combined_series - merges all questionnaires into a long single series
        combined_series = combined_series.append(s)

    # Convert the combined Series into a one-row DataFrame
    final_df = combined_series.to_frame().T

    # Return the resulting one-row DataFrame
    return final_df


def _get_all_psychosocial_results(folder_path: str) -> pd.DataFrame:
    """
    Load and aggregate psychosocial questionnaire results from all groups into one single dataframe.

    This function navigates through a directory where each group has its own folder,
    and within each group folder exists a `psychosocial` subfolder containing exactly
    one CSV file with questionnaire results_questionnaires. It loads each of these CSV files into a
    DataFrame and concatenates them vertically into a single DataFrame.

    Directory structure example
    ---------------------------
    folder_path/
        group_1/
            psychosocial/
                results_questionnaires.csv
        group_2/
            psychosocial/
                results_questionnaires.csv
        ...
    :param folder_path: The root directory containing group folders. Each group folder must contain
            a subfolder named `psychosocial` with exactly one CSV file.
    :return: A DataFrame containing all psychosocial questionnaire results_questionnaires stacked vertically,
            with original indices preserved. Each row corresponds to a subject, and each
            column represents a questionnaire item.
    """

    # init list to hold the dfs for all groups
    list_group_dfs: List[pd.DataFrame] = []

    # cycle over the groups
    for group_folder in os.listdir(folder_path):

        group_folder_path = os.path.join(folder_path, group_folder)

        # check if it's a folder (skip files)
        if os.path.isdir(group_folder_path):

            # cycle over the questionnaire folders
            for questionnaire_file in os.listdir(group_folder_path):

                # filter only the psychosocial questionnaires
                if PSYCHOSOCIAL in questionnaire_file:

                    # get full path to the csv file
                    file_path = os.path.join(group_folder_path, questionnaire_file)

                    # load df
                    results_df = pd.read_csv(file_path)

                    # add df to the list
                    list_group_dfs.append(results_df)

    # concat vertically to have the results_questionnaires of all subjects keeping original index (which are the subject ids)
    final_df = pd.concat(list_group_dfs, axis=0)

    return final_df


def _get_questionnaire_name_from_json(config_dict: Dict[str, Dict[str, Any]], questionnaire_id: str) -> str:
    """
    Extracts the questionnaire name from a JSON configuration file by matching the questionnaire id.
    :param config_dict: The config dictionary for the given questionnaire domain.
    :param questionnaire_id: The unique id of the questionnaire.
    :return: The questionnaire name
    """

    # iterate through the several questionnaires in the config dict
    for questionnaire_name, questionnaire_info in config_dict.items():

        # check which id matches
        if questionnaire_info.get('id') == questionnaire_id:

            # return the name of the questionnaire with the given id
            return questionnaire_name

    raise ValueError(f"No questionnaire found with id: {questionnaire_id}")


def _check_valid_linear_domain(domain: str) -> None:
    """
    Checks that the given domain is valid.
    :param domain: the input domain
    :return: None
    """

    if domain not in (PSYCHOSOCIAL, ENVIRONMENT):
        raise ValueError(
            f"Invalid domain. Expected {PSYCHOSOCIAL} or {ENVIRONMENT}, but got {domain}."
        )


def _check_valid_average_method(average_method: str) -> None:
    """
    Checks that the given average_method is valid.
    :param average_method: the input domain
    :return: None
    """

    if average_method not in (POPULATION, WORK_TYPE):
        raise ValueError(
            f"Invalid domain. Expected {POPULATION} or {WORK_TYPE}, but got {average_method}."
        )
# ------------------------------------------------------------------------------------------------------------------- #
# old functions
# ------------------------------------------------------------------------------------------------------------------- #

# import glob

# BEM_ESTAR = 'Bem-Estar Geral.csv'
# EXIGENCIAS = 'Exigências Laborais.csv'
# ORGANIZACAO = 'Organização do Trabalho e Conteúdo.csv'
# RELACOES = 'Relações Sociais e Liderança.csv'
# VALORES = 'Valores no Local de Trabalho.csv'
# PSICOSSOCIAL_QUESTIONNAIRES = [BEM_ESTAR, EXIGENCIAS, ORGANIZACAO, RELACOES, VALORES]

# def calculate_copsoq_scores(folder_path: str) -> pd.DataFrame:
#
#     # init lists to hold the column names of all questionnaires and the sums of the columns
#     column_names_list = []
#     list_sums_total = []
#
#     # init counter for the total number of subjects
#     total_subjects = 0
#
#     for q_index, questionnaire_name in enumerate(PSICOSSOCIAL_QUESTIONNAIRES):
#
#         files = glob.glob(os.path.join(folder_path, "**", questionnaire_name), recursive=True)
#
#         list_sums_questionnaire = []
#
#         for file_num, file in enumerate(files):
#
#             # load df
#             results_df = pd.read_csv(file)
#
#             # drop non copsoq questions from exigências questionnaire
#             if questionnaire_name == EXIGENCIAS:
#                 results_df = results_df.drop(columns=NON_COPSOQ_COLUMNS)
#
#             # count total number of subjects only on the first questionnaire
#             if q_index == 0:
#                 total_subjects += len(results_df)
#
#             # store column names only once per questionnaire
#             if file_num == 0:
#                 column_names_list.append(results_df.columns.tolist())
#
#             # sum values for this file
#             values_list = results_df.sum().tolist()
#
#             # store these sums
#             list_sums_questionnaire.append(values_list)
#
#         # sum values across all files for this questionnaire
#         total_summed_questionnaire = [sum(x) for x in zip(*list_sums_questionnaire)]
#
#         # add to list containing the sums of all psicossocial questionnaires
#         list_sums_total.append(total_summed_questionnaire)
#
#     # get final dataframe with the summed scores
#     final_df = _create_df_from_lists(column_names_list, list_sums_total)
#
#     # get mean
#     final_df = final_df/total_subjects
#
#     return final_df