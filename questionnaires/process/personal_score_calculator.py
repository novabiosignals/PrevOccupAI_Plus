"""
Function to calculate IPAQ scores and to clean personal questionnaire answers.

Available Functions
-------------------
[Public]
calculate_personal_scores(...): Calculates the IPAQ scores and cleans the answers for the personal questionnaires of one group.
-------------------

[Private]
_get_dados_demograficos_results(...): Cleans column names and answers for readability and consistency of the 'dados demograficos' questionnaire.
_get_estilo_vida_results(...): Cleans column names and answers for readability and consistency of the 'estilo de vida' questionnaire.
_get_atividade_fisica_results(...): Processes physical activity questionnaire data according to IPAQ guidelines and calculates IPAQ scores.
_calculate_total_time_and_truncate(...): Calculates total activity time in minutes and applies truncation rules.
_calculate_met_scores(...): Calculates MET (Metabolic Equivalent of Task) scores for physical activities.
_assign_ipaq_categories(...): Assigns IPAQ physical activity categories.
_outlier_detection(...): Flags IPAQ outliers based on total activity time.
_compute_sitting_times(...): Computes total sitting time in minutes for weekdays and weekends.
_correct_false_input(...): Corrects wrong time inputs.
_correct_false_working_time(...): Corrects inconsistent working days and working hours inputs.
-------------------
"""
# -------------------------------------------------------------------------------------------------------------------- #
# imports
# -------------------------------------------------------------------------------------------------------------------- #
import os
from pathlib import Path
import pandas as pd
from typing import Tuple, List

# internal imports
from questionnaires.load.questionnaire_loader import load_questionnaire_answers
from utils import load_json_file, create_dir, extract_group_from_path, find_project_root
from constants import CONFIG_FOLDER_NAME, CSV
from questionnaires.process.mappings.questionnaire_mappings import *

# -------------------------------------------------------------------------------------------------------------------- #
# constants
# -------------------------------------------------------------------------------------------------------------------- #
DADOS_DEMOGRAFICOS = "Dados Demográficos"
ESTILO_DE_VIDA = "Estilo de Vida"
ATIVIDADE_FISICA = "Atividade Física"

# -------------------------------------------------------------------------------------------------------------------- #
# public functions
# -------------------------------------------------------------------------------------------------------------------- #

def calculate_personal_scores(folder_path: str, output_folder_path: str) -> None:
    """
    Calculates the IPAQ scores and cleans the answers for the personal questionnaires of one group. Assumes that
    the questionnaire answers are stored in a directory such as: '...\\group1\\personal\\files.csv'
    Saves the results into a csv file.

    :param folder_path: Path to the folder containing the several questionnaire domains (subfolders)
    :param output_folder_path: Path to the folder where the scores will be saved.
    :return: None

    """

    # list for holding the scores_df for all questionnaires
    list_dfs: List[pd.DataFrame] = []

    # load results_questionnaires for all domain questionnaires into a dictionary
    # (keys: questionnaire id, values: dataframe with the results_questionnaires)
    results_dict = load_questionnaire_answers(folder_path, domain="personal")

    # load config json file
    config_dict = load_json_file(os.path.join(Path(__file__).parent, CONFIG_FOLDER_NAME, "cfg_personal.json"))

    for questionnaire_id, answers_df in results_dict.items():

        # Check if the questionnaire_id exists in config_dict
        if questionnaire_id not in config_dict:
            print(f"Warning: questionnaire_id {questionnaire_id} not found in config. Skipping...")
            continue  # skip to the next one

        # get questionnaire name from config
        questionnaire_name = config_dict[questionnaire_id]

        if questionnaire_name == DADOS_DEMOGRAFICOS:

            results_df = _get_dados_demograficos_results(answers_df)

        elif questionnaire_name == ESTILO_DE_VIDA:

            results_df = _get_estilo_vida_results(answers_df)

        # it's atividade fisica
        else:
            results_df = _get_atividade_fisica_results(answers_df)

            # keep only the relevant columns
            results_df = results_df[AF_FINAL_RESULTS_COLUMNS]


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
    final_df.fillna(0, inplace=True)

    # save dataframe into a csv file
    folder_path = create_dir(find_project_root(), os.path.join(output_folder_path, extract_group_from_path(folder_path)))
    final_df.to_csv(os.path.join(folder_path, f"results_personal{CSV}"))


# -------------------------------------------------------------------------------------------------------------------- #
# private functions
# -------------------------------------------------------------------------------------------------------------------- #

def _get_dados_demograficos_results(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans column names and answers for readability and consistency of the 'dados demograficos' questionnaire.

    This function:
    - Renames columns to human-readable names
    - Replaces coded answers with readable text
    - Corrects common input errors (e.g. height entered in meters instead of centimeters,
      working hours entered as daily hours instead of weekly hours)

    No scores are calculated for this questionnaire.

    :param results_df: Raw demographic questionnaire results.
    :return: Cleaned demographic results.
    """
    # create copy to avoid warnings
    df = results_df.copy()

    df.rename(columns=DD_COLUMN_NAMES_MAP, inplace=True)

    # replace coded answers with readable text
    for col, mapping in DD_ANSWERS_MAP.items():
        if col in df.columns:
            df[col] = df[col].replace(mapping)

    # correct height values (entered in meters instead of cm)
    if 'altura' in df.columns:
        df.loc[df['altura'] < 10, 'altura'] *= 100

    # correct weekly working hours (entered as daily hours * 5)
    if 'horasTrabalho' in df.columns:
        df.loc[df['horasTrabalho'] < 10, 'horasTrabalho'] *= 5

    return df


def _get_estilo_vida_results(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans column names and answers for readability and consistency of the 'estilo de vida' questionnaire.

    This function:
    - Renames existing columns to readable names
    - Replaces coded answers with readable text
    - Cleans and converts numeric time-related responses to proper numeric values

    No scores are calculated for this questionnaire.

    :param results_df: Raw lifestyle questionnaire results.
    :return: Cleaned and standardized lifestyle results.
    """

    # create copy to avoid warnings
    df = results_df.copy()

    # rename only the columns that actually exist
    existing_rename_map = {old_name: new_name for old_name, new_name in EV_COLUMN_NAMES_MAP.items() if old_name in df.columns}
    df.rename(columns=existing_rename_map, inplace=True)

    # replace the answers to a more readable format
    for col, mapping in EV_ANSWERS_MAP.items():

        # find column in df columns
        if col in df.columns:

            # replace with the answers according to the mapping
            df[col] = df[col].replace(mapping)

    # Clean numeric answers
    for col in ['tempo', 'tempo_passado']:
        if col in df.columns:

            # Ensure values are strings, replace commas with dots for decimals, and extract only numeric portions
            df[col] = (df[col].astype(str).str.replace(',', '.', regex=False).str.extract(r'(\d+(?:\.\d+)?)')[0])

            # convert to numeric type
            df[col] = pd.to_numeric(df[col], errors='coerce')

    return df


def _get_atividade_fisica_results(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    Processes physical activity questionnaire data according to IPAQ guidelines and calculates IPAQ scores.

    This function:
    - Cleans and renames columns
    - Corrects inconsistent or false time inputs
    - Calculates total activity time and MET scores
    - Assigns IPAQ activity categories (Alta, Moderada, Baixa)
    - Flags outliers and computes sitting times

    :param results_df: Raw physical activity questionnaire results.
    :return: Processed dataframe with activity totals, MET scores, IPAQ categories, and flags.
    """
    # Safe copy to avoid modifying original dataframe
    df = results_df.copy()

    # Rename columns for readability and fill NaN values with 0
    df.rename(columns=dict(zip(AF_OLD_COLUMNS, AF_NEW_COLUMNS)), inplace=True)
    df.fillna(0, inplace=True)

    # Correct false/wrong inputs in time-related columns
    for hours_col, minutes_col in AF_TIME_PAIRS:
        df[minutes_col] = df.apply(lambda x: _correct_false_input(x[hours_col], x[minutes_col]), axis=1)

    # correct working days/hours
    df[["dias_trabalho_semana", "horas_trabalho_semana"]] = df.apply(
        lambda row: pd.Series(_correct_false_working_time(row["dias_trabalho_semana"], row["horas_trabalho_semana"])),
        axis=1
    )

    # Calculate total time and truncate activity durations
    df = _calculate_total_time_and_truncate(df, ['vigorosa', 'moderada', 'caminhada'])

    # create total activity columns
    # raw total
    df["total_atividade"] = (df["vigorosa_t"] + df["moderada_t"] + df["caminhada_t"])

    # total activity column after truncating (max 180 min of the activity)
    df["total_atividade_ed"] = (df["vigorosa_t_trunc"] + df["moderada_t_trunc"] + df["caminhada_t_trunc"])

    # Calculate MET scores
    df = _calculate_met_scores(df)

    # Assign IPAQ categories (Alta / Moderada / Baixa)
    df = _assign_ipaq_categories(df)

    # Outlier detection based on activity totals
    df = _outlier_detection(df)

    # Compute sitting times in minutes
    df = _compute_sitting_times(df)

    return df


def _calculate_total_time_and_truncate(df: pd.DataFrame, prefixes: list) -> pd.DataFrame:
    """
    Calculates total activity time in minutes and applies truncation rules.

    For each activity prefix, total time is calculated as:
    hours * 60 + minutes.

    Activity durations are truncated to a maximum of 180 minutes per activity.
    Values below 10 minutes are set to 0.

    :param df: Dataframe containing activity hour and minute columns.
    :param prefixes: List of activity prefixes (e.g. ['vigorosa', 'moderada', 'caminhada']).
    :return: Dataframe with total and truncated activity time columns added.

    """
    # iterate through the prefixes
    for prefix in prefixes:

        # get column name
        total_time_col = f"{prefix}_t"

        # get total time in minutes
        df[total_time_col] = df[f"{prefix}_horas"] * 60 + df[f"{prefix}_minutos"]

        trunc_col = f"{prefix}_t_trunc"

        # truncate scores between 10 and 180.
        df[trunc_col] = df[total_time_col].clip(lower=10, upper=180)

        # if less than 10 assign 0
        df.loc[df[total_time_col] < 10, trunc_col] = 0

    return df


def _calculate_met_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates MET (Metabolic Equivalent of Task) scores for physical activities.

    MET values used:
    - Vigorous: 8.0
    - Moderate: 4.0
    - Walking: 3.3

    :param df: Dataframe containing activity days and truncated time columns.
    :return: Dataframe with MET scores and total MET added.
    """
    df["vigorosa_met"] = 8 * df["vigorosa_dias"] * df["vigorosa_t_trunc"]
    df["moderada_met"] = 4 * df["moderada_dias"] * df["moderada_t_trunc"]
    df["caminhada_met"] = 3.3 * df["caminhada_dias"] * df["caminhada_t_trunc"]
    df["total_met"] = df["vigorosa_met"] + df["moderada_met"] + df["caminhada_met"]
    return df


def _assign_ipaq_categories(df: pd.DataFrame) -> pd.DataFrame:
    """
    Assigns IPAQ physical activity categories.

    Categories are assigned based on IPAQ scoring rules:
    - Alta (High)
    - Moderada (Moderate)
    - Baixa (Low)

    :param df: Dataframe containing activity totals and MET scores.
    :return: Dataframe with IPAQ category flags and final category column.
    """
    # Initialize all flags to 'N'
    for col in ["atividade_elevada_3", "atividade_elevada_7",
                "atividade_moderada_3", "atividade_moderada_5", "atividade_moderada_5+"]:
        df[col] = 'N'

    # Apply 'Alta' (high activity) criteria
    df.loc[(df["vigorosa_dias"] >= 3) & (df["total_met"] >= 1500), "atividade_elevada_3"] = 'Y'
    df.loc[(df["vigorosa_dias"] + df["moderada_dias"] + df["caminhada_dias"] >= 7) & (df["total_met"] >= 3000), "atividade_elevada_7"] = 'Y'

    # Apply 'Moderada' activity criteria
    df.loc[(df["vigorosa_dias"] >= 3) & (df["vigorosa_t"] >= 20), "atividade_moderada_3"] = 'Y'
    df.loc[((df["moderada_t"] >= 30) & (df["moderada_dias"] >= 5)) |
           ((df["caminhada_t"] >= 30) & (df["caminhada_dias"] >= 5)) |
           ((df["moderada_t"] >= 30) & (df["caminhada_t"] >= 30) & (df["moderada_dias"] + df["caminhada_dias"] >= 5)),
           "atividade_moderada_5"] = 'Y'

    df.loc[(df["vigorosa_dias"] + df["moderada_dias"] + df["caminhada_dias"] >= 5) & (df["total_met"] >= 600), "atividade_moderada_5+"] = 'Y'

    # Assign final IPAQ category
    df["ipaq"] = "Baixa"
    df.loc[(df["atividade_moderada_3"] == 'Y') | (df["atividade_moderada_5"] == 'Y') | (df["atividade_moderada_5+"] == 'Y'), "ipaq"] = "Moderada"
    df.loc[(df["atividade_elevada_3"] == 'Y') | (df["atividade_elevada_7"] == 'Y'), "ipaq"] = "Alta"

    return df


def _outlier_detection(df: pd.DataFrame) -> pd.DataFrame:
    """
    Flags IPAQ outliers based on total activity time.

    Participants with more than 960 minutes of total activity
    are flagged as outliers.

    :param df: Dataframe containing total activity time.
    :return: Dataframe with an outlier flag column added.
    """
    df["ipaq_outlier"] = 'N'
    df.loc[df["total_atividade"] > 960, "ipaq_outlier"] = 'Y'
    return df


def _compute_sitting_times(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes total sitting time in minutes for weekdays and weekends.

    :param df: Dataframe containing sitting time hours and minutes.
    :return: Dataframe with total sitting time columns added.
    """
    df["sentado_semana_total_min"] = df["sentada_semana_horas"] * 60 + df["sentada_semana_minutos"]
    df["sentado_fds_total_min"] = df["sentada_fds_horas"] * 60 + df["sentada_fds_minutos"]
    return df

def _correct_false_input(hours, minutes):
    """
    Corrects the input by the user if
    1. The user has inserted the same amount of time (only converted) for both hours and minutes
    (e.g. hours = 2, minutes = 120)
    2. the user has inserted an amount of time for hours AND an amount of time for minutes that is above 60 mintues
    (e.g. hours 4, minutes= 470)
    In both cases the amount of minutes is set to 0.0 as the input is regared as falsely inserted by the user.

    When the user has ONLY inserted an amount of time for minutes and it is above 60 minutes it is still accepted
    as input as here it is assumed that the user has just given the entire time as minutes (i.e. already has done
    the addition of hours and minutes)
    :param hours: the amount of hours inserted by the user
    :param minutes: the amount of mintues inserted by the user
    :return: returns the corrected minutes accorind to the rules stated above
    """

    # convert hours to minutes
    hours = hours * 60

    # check if the subject has entered any hours
    if hours > 0.0:

        # check if the subject has entered anything above or equal to 60.00 minutes
        if minutes >= 60.0:

            # set the minutes to zero as this input is invalid
            return 0.0
        else:

            # input valid, just return the input
            return minutes
    else:

        # here it is assumed that the subject inserted the physical activity ONLY as minutes, meaning that even values
        # above 60.0 are valid
        return minutes


def _correct_false_working_time(working_days: float, working_hours: float) -> Tuple[float, float]:
    """
    Corrects inconsistent working days and working hours inputs.

    Corrections applied:
    - If 7 working days are reported but weekly hours are unrealistically low,
      the input is corrected to 5 working days.
    - If daily working hours are entered instead of weekly hours,
      total weekly hours are recalculated.

    :param working_days: Number of working days reported.
    :param working_hours: Number of working hours reported.
    :return: Corrected working days and weekly working hours.
    """
    # if the subject has entered that they worked that last 7 days, but the hours don't match 7 * 7 = 49 hours, correct
    # the input assuming that they worked 5 days and 5*7=35 hours
    if working_days == 7 and working_hours < 49:

        working_days = 5

    # correct working hours of the subject inserted daily working hours
    if working_days > 1 and working_hours < 10:

        working_hours = working_days * working_hours

    return working_days, working_hours

