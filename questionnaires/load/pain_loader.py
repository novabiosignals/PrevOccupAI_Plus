# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import os
from typing import List, Tuple

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #


# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #

def _filter_subject_files_by_date(folder_path: str, subject_id: str) -> List[str]:

    # init list for holding the organized data
    organized_list = []

    # get paths for the subject only
    filenames_list = _get_pain_paths_per_subject(folder_path, subject_id)

    # cycle over the subject files
    for filename in filenames_list:

        # get date and hour from path
        date, hour = _extract_date_and_hour_from_pain_filename(filename)














def _get_pain_paths_per_subject(folder_path: str, subject_id: str) -> List[str]:
    """

    :param folder_path:
    :param subject_id:
    :return:
    """
    # init list for holding the paths for one subject only
    subject_paths_list: List[str] = []

    # cycle over the folder containing all pain files from all subjects
    for filename in os.listdir(folder_path):

        # decompose the file name and get the first string - subject ID, and check if it matches
        if filename.split('_')[0] == subject_id:

            # add to list
            subject_paths_list.append(filename)

    return subject_paths_list


def _extract_date_and_hour_from_pain_filename(pain_filename: str) -> Tuple[str, str]:
    """

    :param pain_filename:
    :return:
    """

    # split string
    filename_strings = pain_filename.split('_')

    return f"{filename_strings[1]}_{filename_strings[2]}_{filename_strings[3]}", filename_strings[4]



