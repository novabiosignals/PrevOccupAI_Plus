"""
Functions for loading the meta-data contained in 'subjects_info.csv'.

Available Functions
-------------------
[Public]
load_meta_data(...): loads the meta-data contained in subjects_info.csv into a pandas.DataFrame.
get_muscleban_side(...): get the muscleban side based on the mac address
------------------
[Private]

"""

# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
from pathlib import Path

import pandas as pd
from constants import MBAN_LEFT, MBAN_RIGHT

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


def get_muscleban_side(meta_data_df: pd.DataFrame, mac_address: str) -> str | None: # I'm not using this function
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


# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #
