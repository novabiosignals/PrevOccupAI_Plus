"""
Functions for loading the meta-data contained in 'subjects_info.csv'.

Available Functions
-------------------
[Public]
load_meta_data(...): loads the meta-data contained in subjects_info.csv into a pandas.DataFrame.
get_muscleban_side(...): get the muscleban side based on the mac address
get_expected_devices(...)
------------------
[Private]

"""

# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
from pathlib import Path
from typing import List

import pandas as pd

# internal imports
from constants import MBAN_LEFT, MBAN_RIGHT, PHONE, WATCH

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #
def load_meta_data(csv_path: str | Path = 'participants_info.csv') -> pd.DataFrame:
    """Load the participant metadata CSV into a convenient dataframe.

    :param csv_path: Path to the metadata CSV file. Defaults to 'participants_info.csv'.
    :return: DataFrame containing the meta-data indexed by subject_id.
    """

    path = Path(csv_path)
    return pd.read_csv(path, sep=';', encoding='utf-8', index_col='subject_id')


def get_muscleban_side(meta_data_df: pd.DataFrame, mac_address: str) -> str | None:
    """Return ``mBAN_left`` or ``mBAN_right`` based on the MAC address lookup.

    :param meta_data_df: DataFrame returned by :func:`load_meta_data`.
    :param mac_address: Hexadecimal MAC without separators, matching the filenames.
    :return: Side label or ``None`` when the MAC cannot be found.
    """
    # Search in mBAN_left column
    if mac_address in meta_data_df[MBAN_LEFT].values:
        return MBAN_LEFT

    # Search in mBAN_right column
    elif mac_address in meta_data_df[MBAN_RIGHT].values:
        return MBAN_RIGHT

    # If not found
    return None


def get_expected_devices(meta_data_df, group: str, device_num: str) -> List[str]:

    # list with expected device - phone and watch are added manually as they are not on the metadata df
    expected_devices = [PHONE, WATCH]

    # Filter the DataFrame for the given group and device number
    row = meta_data_df[(meta_data_df['group'] == group) & (meta_data_df['device_num'] == device_num)]

    # get the mac address of the musclebans
    mban_left = row.iloc[0][MBAN_LEFT]
    mban_right = row.iloc[0][MBAN_RIGHT]

    # muscleban mac addresses to the list
    expected_devices.extend([mban_left, mban_right])

    return expected_devices
