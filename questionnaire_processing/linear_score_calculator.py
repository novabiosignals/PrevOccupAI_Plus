# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
from pathlib import Path
import os
from typing import List, Optional
import pandas as pd

# internal imports
from utils import load_json_file, create_dir, get_group_from_path
from .questionnaire_loader import load_questionnaire_answers
from .json_parser import get_questionnaire_name_from_json
from constants import CONFIG_FOLDER_NAME, RESULTS_FOLDER_NAME, CSV, AMBIENTE

# ------------------------------------------------------------------------------------------------------------------- #
# constants
# ------------------------------------------------------------------------------------------------------------------- #
JSON_SCORES_FILENAME = 'scores.json'

LIKERT_SCALE = 'likert'
# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #

def calculate_linear_scores(folder_path: str, domain: str) -> None:
    """
    Calculates the scores for the Psicossocial and Ambiente questionnaires and saves the results into a csv file
    :param folder_path: Path to the folder containing the several questionnaire domains (subfolders)
    :param domain: The domain of the questionnaires, which should be the name of the folder that contains the csv files.
                    For this function, only Psicosocial and Ambiente are available #todo check this
    :return: None
    """

    # load results for all domain questionnaires into a dictionary
    # (keys: questionnaire id, values: dataframe with the results)
    results_dict = load_questionnaire_answers(folder_path, domain)

    # load json file with the info for the given domain
    config_dict = load_json_file(os.path.join(Path(__file__).parent, CONFIG_FOLDER_NAME, f"cfg_{domain.lower()}.json"))

    # load json file with the scores info
    scores_dict = load_json_file(os.path.join(Path(__file__).parent, CONFIG_FOLDER_NAME, JSON_SCORES_FILENAME))

    # iterate through the results of the psicossocial questionnaires
    for questionnaire_id, results_df in results_dict.items():

        # create a scores dataframe for this questionnaire
        questionnaire_scores_df = pd.DataFrame()

        # get questionnaire name from the id
        questionnaire_name = get_questionnaire_name_from_json(config_dict, questionnaire_id)

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
                scores_series = _calculate_scores(domain, subtopic_df, calculation_method, scale, values, inverted, max_value)

                # add subject id column and scores
                if not 'id' in questionnaire_scores_df.columns:

                    # get the id column from the results df - column name starts with id
                    id_col = results_df.filter(regex='id', axis=1).iloc[:, 0]

                    # add id column to the scores df
                    questionnaire_scores_df['id'] = id_col

                questionnaire_scores_df[subtopic_name] = scores_series

        # set id column to int, set as index of the dataframe, and order
        questionnaire_scores_df = questionnaire_scores_df.apply(pd.to_numeric, errors='coerce')
        questionnaire_scores_df = questionnaire_scores_df.set_index('id').sort_index()

        # save dataframe into a csv file
        folder_path = create_dir(Path(__file__).parent, os.path.join(RESULTS_FOLDER_NAME, get_group_from_path(folder_path), domain))
        questionnaire_scores_df.to_csv(os.path.join(folder_path, f"{questionnaire_name}{CSV}"))

# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #

def _calculate_scores(domain:str, results_df: pd.DataFrame, calculation_method: str, scale: List[int], values: List[int],
                      inverted: List[Optional[int]], max_value: int) -> pd.Series:
    """

    :param results_df:
    :param calculation_method:
    :return:
    """

    # convert all columns to numeric
    results_df = results_df.apply(pd.to_numeric, errors='coerce')

    # assign respective values to the given answers
    results_df = _assign_answer_values(results_df, scale, values, inverted)

    if calculation_method == 'sum':

        # sum all values per row and normalize
        scores_series = results_df.sum(axis=1)
        scores_series_norm = ((scores_series - min(values))/(max_value - min(values))).round(2)

    elif calculation_method == 'mean':

        # calculate the mean of all values per row and normalize
        scores_series = results_df.mean(axis=1)

        if domain == AMBIENTE:

            # normalize
            scores_series_norm = ((scores_series - min(values)) / (max_value - min(values))).round(2)

        else:

            scores_series_norm = ((scores_series - min(scale)) / (max_value - min(scale))).round(2)

    else:
        raise ValueError(f"The calculation method {calculation_method} does not exist.")

    return scores_series_norm


def _assign_answer_values(results_df, scale, values, inverted):

    # create copy to avoid warnings
    results_df = results_df.copy()

    # iterate through the column indices
    for column_index in range(len(results_df.columns)):

        # if the column index matches the ones in inverted
        if column_index in inverted:

            # assign values and invert results
            results_df[results_df.columns[column_index]] = results_df[results_df.columns[column_index]].replace(scale, values[::-1])

        else:

            # assign values without inverting
            results_df[results_df.columns[column_index]] = results_df[results_df.columns[column_index]].replace(scale, values)

    return results_df


def _clean_results_dataframe(scale_type: str, subtopic_df):
    # create copy to avoid warnings
    subtopic_df = subtopic_df.copy()

    for col in subtopic_df.columns:

        if scale_type == LIKERT_SCALE:

            # remove the prefix 'A' from
            subtopic_df[col] = subtopic_df[col].str.replace("^A", "", regex=True)


        else:
            # TODO implement other scales
            pass

    return subtopic_df
