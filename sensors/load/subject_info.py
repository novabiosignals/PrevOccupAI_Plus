"""
Functions for loading the meta-data contained in 'subjects_info.csv'.

Available Functions
-------------------
[Public]
load_participants_info(...): loads the meta-data contained in subjects_info.csv into a pandas.DataFrame.
get_muscleban_side(...): get the muscleban side based on the mac address.
get_participant_id(...): gets the subject id based on the device number and group.
get_ids_per_group(...): Return a list of subject_ids belonging to a specific group.
------------------
[Private]

"""

# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import pandas as pd
from typing import List

# internal imports
from constants import MBAN_LEFT, MBAN_RIGHT
from typing import Optional

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #
def load_participants_info() -> pd.DataFrame:
    """
    loads the meta-data contained in subjects_info.csv into a pandas.DataFrame.
    :return: DataFrame containing the meta-data
    """

    return pd.read_csv('participants_info.csv', sep=';', encoding='utf-8', index_col='subject_id')


def get_muscleban_side(participants_info_df: pd.DataFrame, mac_address: str) -> Optional[str]:
    """
    Extracts the side of the muscleban from the meta_data_df based on the mac address of the device
    :param participants_info_df: pd.DataFrame containing the subject meta-data contained in subjects_info.csv
    :param mac_address: str containing the mac address without the colons
    :return: str containing the muscleban side
    """
    # Search in mBAN_left column
    if mac_address in participants_info_df[MBAN_LEFT].values:
        return MBAN_LEFT

    # Search in mBAN_right column
    elif mac_address in participants_info_df[MBAN_RIGHT].values:
        return MBAN_RIGHT

    # If not found
    return None


def get_participant_id(participants_info_df: pd.DataFrame, device_num: str, group: str) -> str:
    """
    Gets the subject id based on the device number and group.

    :param participants_info_df: DataFrame containing the participants info
    :param device_num: device number to search for in the df
    :param group: group number to search for in the df
    :return: a string with the subject id
    """

    # Filter the DataFrame for the given group and device number
    row = participants_info_df[(participants_info_df['group'] == int(group)) & (participants_info_df['device_num'] == device_num)]

    # get the id which corresponds to the index of the row
    return str(row.index[0])


def get_ids_per_group(participants_info_df: pd.DataFrame, group: str) -> List[str]:
    """
    Return a list of subject_ids belonging to a specific group.

    :param participants_info_df: DataFrame containing the participants info
    :param group: group number to search for in the df
    :return: List of subject_ids (as strings) belonging to the given group.
    """
    # Filter rows by group
    filtered = participants_info_df[participants_info_df["group"].astype(str) == str(group)]

    # Extract subject_id column and convert each to string
    return filtered["subject_id"].astype(str).tolist()