# -------------------------------------------------------------------------------------------------------------------- #
# imports
# -------------------------------------------------------------------------------------------------------------------- #
import os
from pathlib import Path
import pandas as pd
from typing import Tuple

# internal imports
from .questionnaire_loader import load_questionnaire_answers
from utils import load_json_file, create_dir, get_group_from_path
from constants import CONFIG_FOLDER_NAME, RESULTS_FOLDER_NAME, CSV
from .questionnaire_mappings import EV_COLUMN_NAMES_MAP, EV_ANSWERS_MAP, AF_NEW_COLUMNS, AF_OLD_COLUMNS, DD_ANSWERS_MAP, \
    AF_TIME_PAIRS, DD_COLUMN_NAMES_MAP

# -------------------------------------------------------------------------------------------------------------------- #
# constants
# -------------------------------------------------------------------------------------------------------------------- #
DADOS_DEMOGRAFICOS = "Dados Demográficos"
ESTILO_DE_VIDA = "Estilo de Vida"
ATIVIDADE_FISICA = "Atividade Física"

# -------------------------------------------------------------------------------------------------------------------- #
# public functions
# -------------------------------------------------------------------------------------------------------------------- #

def calculate_personal_scores(folder_path):

    # load results for all domain questionnaires into a dictionary
    # (keys: questionnaire id, values: dataframe with the results)
    results_dict = load_questionnaire_answers(folder_path, domain="pessoais")

    # load config json file
    config_dict = load_json_file(os.path.join(Path(__file__).parent, CONFIG_FOLDER_NAME, "cfg_pessoais.json"))

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


        # set id column to int, set as index of the dataframe, and order
        results_df['id.1'] = pd.to_numeric(results_df['id.1'], errors='coerce')
        results_df = results_df.set_index('id.1').sort_index()

        # save dataframe into a csv file
        folder_path = create_dir(Path(__file__).parent, os.path.join(RESULTS_FOLDER_NAME, get_group_from_path(folder_path),'pessoais'))
        results_df.to_csv(os.path.join(folder_path, f"{questionnaire_name}{CSV}"))


# -------------------------------------------------------------------------------------------------------------------- #
# private functions
# -------------------------------------------------------------------------------------------------------------------- #

def _get_dados_demograficos_results(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans and standardizes data for readability and consistency.
    No scores are calculated in this questionnaire.
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

    :param results_df:
    :return:
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

    :param df:
    :param prefixes:
    :return:
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

    :param df:
    :return:
    """
    df["vigorosa_met"] = 8 * df["vigorosa_dias"] * df["vigorosa_t_trunc"]
    df["moderada_met"] = 4 * df["moderada_dias"] * df["moderada_t_trunc"]
    df["caminhada_met"] = 3.3 * df["caminhada_dias"] * df["caminhada_t_trunc"]
    df["total_met"] = df["vigorosa_met"] + df["moderada_met"] + df["caminhada_met"]
    return df


def _assign_ipaq_categories(df: pd.DataFrame) -> pd.DataFrame:
    """

    :param df:
    :return:
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

    :param df:
    :return:
    """
    df["ipaq_outlier"] = 'N'
    df.loc[df["total_atividade"] > 960, "ipaq_outlier"] = 'Y'
    return df


def _compute_sitting_times(df: pd.DataFrame) -> pd.DataFrame:
    """

    :param df:
    :return:
    """
    df["sentado_semana_t"] = df["sentada_semana_horas"] * 60 + df["sentada_semana_minutos"]
    df["sentado_fds_t"] = df["sentada_fds_horas"] * 60 + df["sentada_fds_minutos"]
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

    # if the subject has entered that they worked that last 7 days, but the hours don't match 7 * 7 = 49 hours, correct
    # the input assuming that they worked 5 days and 5*7=35 hours
    if working_days == 7 and working_hours < 49:

        working_days = 5

    # correct working hours of the subject inserted daily working hours
    if working_days > 1 and working_hours < 10:

        working_hours = working_days * working_hours

    return working_days, working_hours

