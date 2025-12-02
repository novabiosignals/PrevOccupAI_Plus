"""
Functions for loading the meta-data contained in 'subjects_info.csv'.

Available Functions
-------------------
[Public]
load_participants_info(...): loads the meta-data contained in subjects_info.csv into a pandas.DataFrame.
get_muscleban_side(...): get the muscleban side based on the mac address.
get_participant_id(...): gets the subject id based on the device number and group.
------------------
[Private]

"""

# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
<<<<<<< HEAD:sensors/load/meta_data.py
from pathlib import Path
from typing import List

=======
>>>>>>> 58897cc208aeb431c54b8da5519e53d947b1d242:sensors/load/subject_info.py
import pandas as pd

# internal imports
from constants import MBAN_LEFT, MBAN_RIGHT
from typing import Optional

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #
<<<<<<< HEAD:sensors/load/meta_data.py
def load_meta_data(csv_path: str | Path = 'participants_info.csv') -> pd.DataFrame:
    """Load the participant metadata CSV into a convenient dataframe.

    :param csv_path: Path to the metadata CSV file. Defaults to 'participants_info.csv'.
    :return: DataFrame containing the meta-data indexed by subject_id.
=======
def load_participants_info() -> pd.DataFrame:
    """
    loads the meta-data contained in subjects_info.csv into a pandas.DataFrame.
    :return: DataFrame containing the meta-data
>>>>>>> 58897cc208aeb431c54b8da5519e53d947b1d242:sensors/load/subject_info.py
    """

    path = Path(csv_path)
    return pd.read_csv(path, sep=';', encoding='utf-8', index_col='subject_id')


<<<<<<< HEAD:sensors/load/meta_data.py
def get_muscleban_side(meta_data_df: pd.DataFrame, mac_address: str) -> str | None:
    """Return ``mBAN_left`` or ``mBAN_right`` based on the MAC address lookup.

    :param meta_data_df: DataFrame returned by :func:`load_meta_data`.
    :param mac_address: Hexadecimal MAC without separators, matching the filenames.
    :return: Side label or ``None`` when the MAC cannot be found.
=======
def get_muscleban_side(participants_info_df: pd.DataFrame, mac_address: str) -> Optional[str]:
    """
    Extracts the side of the muscleban from the meta_data_df based on the mac address of the device
    :param participants_info_df: pd.DataFrame containing the subject meta-data contained in subjects_info.csv
    :param mac_address: str containing the mac address without the colons
    :return: str containing the muscleban side
>>>>>>> 58897cc208aeb431c54b8da5519e53d947b1d242:sensors/load/subject_info.py
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