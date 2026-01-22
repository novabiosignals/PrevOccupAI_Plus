# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import itertools
import json
import math
import os
from typing import List, Tuple
from collections import defaultdict
from datetime import datetime

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #

def load_pain_lines(folder_path: str, subject_id: str) -> List[Tuple[str, List[str], List[str]]]:
    """
    Processes all pain files for a specific subject and returns a structured list of pain lines per day.

    This function:
    1. Filters all files for the given subject and pairs them by date.
    2. Extracts and cleans the lines from the paired files.
    3. Returns a list of tuples with the format:
       (date, morning_lines, afternoon_lines)

    :param folder_path: Path to the folder containing pain files for all subjects.
    :param subject_id: ID of the subject to process.
    :return: A list of tuples where each tuple corresponds to a day:
             (date, list of morning lines, list of afternoon lines)
    """

    # Get all files for this subject, paired by date as follows
    # [(date1, filename_start1, filename_end1), (date2, filename_start2, filename_end2), ....]
    filenames_list = _filter_subject_files_to_pairs(folder_path, subject_id)

    # extract and clean the pain lines, following format
    # [(date1, list of morning lines1, list of afternoon lines1), (date2, list of morning lines2, list of afternoon lines2)...]
    lines_list = _get_joint_lines(folder_path, filenames_list)

    return lines_list


# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #

def _get_joint_lines(folder_path: str, filenames_list: List[Tuple[str, str, str]]) -> List[Tuple[str, List[str], List[str]]]:
    """
    Reads and cleans lines from paired pain files.

    :param folder_path: Folder where the pain files are stored.
    :param filenames_list: List of tuples containing (date, first_file, second_file).
    :return: List of tuples for each day: (date, cleaned_lines_before, cleaned_lines_after)
    """
    # init list for storing the lines and dates
    lines_list = []

    # cycle over the list
    for date_i, first_file, second_file in filenames_list:

        first_filepath = os.path.join(folder_path, first_file)
        second_filepath = os.path.join(folder_path, second_file)

        # Read raw lines from files
        lines_before = _clean_lines(_get_lines_from_filename(first_filepath))
        lines_after = _clean_lines(_get_lines_from_filename(second_filepath))

        # Append cleaned lines for this day
        lines_list.append((date_i, lines_before, lines_after))

    return lines_list


def _clean_lines(lines: List[str]) -> List[str]:
    """
    Cleans a list of pain line strings by removing redundant points that are very close together.

    This helps to speed up processing and reduce unnecessary duplicates.

    :param lines: List of JSON strings representing pain points.
    :return: A cleaned list of pain line JSON strings.
    """
    new_lines: List[str] = lines.copy()

    for l1, l2 in itertools.combinations(lines, 2):
        if "No pain reported" not in l1 and "No pain reported" not in l2:
            line_dict_1 = json.loads(l1)
            line_dict_2 = json.loads(l2)
            xy_1 = [int(round(line_dict_1["x"])), int(round(line_dict_1["y"]))]
            xy_2 = [int(round(line_dict_2["x"])), int(round(line_dict_2["y"]))]
            # Remove l1 if it's very close to l2
            if math.dist(xy_1, xy_2) < 3 and l1 in new_lines:
                new_lines.remove(l1)

    return new_lines



def _get_lines_from_filename(file_path: str) -> List[str]:
    """
    Reads lines from a text file.

    :param file_path: Path to a text file containing pain line data.
    :return: List of strings, each representing a line from the file.
    """
    lines: List[str] = []

    if os.path.isfile(file_path):
        with open(file_path, 'r') as txt_file:
            lines = txt_file.readlines()

    return lines


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
    Extracts date and hour from a filename and corrects the month.

    :param pain_filename: Filename in format like '80_2025_8_26_15_39_lines'
    :return: Tuple of date in dd-mm-yyyy format and hour
    """
    # split string
    filename_strings = pain_filename.split('_')

    # extract year, month, day, hour
    year = int(filename_strings[1])
    month = int(filename_strings[2])
    day = int(filename_strings[3])
    hour = filename_strings[4]

    # correct month by adding 1
    month += 1
    if month > 12:
        month = 1
        year += 1

    # format date as dd-mm-yyyy with leading zeros
    date_str = f"{day:02d}-{month:02d}-{year}"

    return date_str, hour


def _filter_subject_files_to_pairs(folder_path: str, subject_id: str) -> List[Tuple[str, str, str]]:
    """
    Returns a list of tuples: (date, file_earlier, file_later) for the subject, sorted by date.

    :param folder_path: path to folder containing all pain files
    :param subject_id: ID of the subject to filter
    :return: list of tuples (date, earlier_file, later_file), sorted by date
    """

    # get all files for the subject
    filenames_list: List[str] = _get_pain_paths_per_subject(folder_path, subject_id)

    # init dictionary to group files by date
    files_by_date: defaultdict = defaultdict(list)

    # cycle over the subject's files
    for filename in filenames_list:
        # extract the date and hour from the filename
        date_str, hour = _extract_date_and_hour_from_pain_filename(filename)

        # add the file to the list of files for that date
        files_by_date[date_str].append((hour, filename))

    # initialize list to hold the final paired tuples
    paired_files: List[Tuple[str, str, str]] = []

    # cycle over each date and its files
    for date_str, hour_file_list in files_by_date.items():

        # sort the files for this date by hour (earlier -> later)
        hour_file_list.sort(key=lambda x: int(x[0]))  # hour as integer

        # only consider dates with at least 2 files
        if len(hour_file_list) >= 2:
            first_file = hour_file_list[0][1]
            second_file = hour_file_list[1][1]

            # append a tuple (date, first_file, second_file) to the results
            paired_files.append((date_str, first_file, second_file))

    # sort the final list by date
    paired_files.sort(key=lambda x: datetime.strptime(x[0], "%d-%m-%Y"))

    return paired_files

