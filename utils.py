"""
Utility Functions

Available Functions
-------------------
[Public]
load_json_file(...): Loads a json file to a dictionary.
create_dir(...): Creates a new directory in the specified path.
extract_group_from_path(...): Gets the group number from the data path.
extract_device_num_from_path(...): Gets the device number from the data path.
find_project_root(...): Gets the project root directory.
extract_date_from_path(...): Gets the date from the data path.
-------------------

[Private]
None
-------------------
"""

# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import json
from typing import Dict, Any, Optional, Union
import os
import re
from pathlib import Path

# internal imports

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #

def load_json_file(json_path: str) -> Dict[Any, Any]:
    """
    Loads a json file.
    :param json_path: str
            Path to the json file
    :return: Dict[Any,Any]
    Dictionary containing the features from TSFEL
    """

    # read json file to a features dict
    with open(json_path, "r", encoding='utf-8') as file:
        json_dict = json.load(file)

    return json_dict


def create_dir(path: Union[str, Path], folder_name: str) -> str:
    """
    creates a new directory in the specified path
    :param path: the path in which the folder_name should be created
    :param folder_name: the name of the folder that should be created
    :return: the full path to the created folder
    """

    # join path and folder
    new_path = os.path.join(path, folder_name)

    # check if the folder does not exist yet
    if not os.path.exists(new_path):
        # create the folder
        os.makedirs(new_path)

    return new_path


def extract_group_from_path(folder_path: str) -> str:
    """
    Extracts the group number as a string from a path.
    Assumes that in this path there has to be a folder with the following format: 'group1'
    :param folder_path: Path to the folder
    :return: The group number
    """

    # find group pattern
    # folder name starts with 'group' (i.e.: group1, group2, group3...)
    match = re.search(r'group(\d+)', folder_path)
    if match:
        return match.group(1)  # returns only the digits
    return 'no_group'


def find_project_root(path: Path = Path(__file__)) -> Path:
    """
    Attempt to detect the root directory of the project by looking
    for common root markers such as a `.git` folder or `pyproject.toml`.

    :param path: Path to start searching from (defaults to current file).
    :return: The directory determined to be the project root.
    :raises RuntimeError: If no project root marker is found.
    """

    # Loop through the current path and all its parent directories
    # Example: file.py -> src -> project_root
    for parent in [path, *path.parents]:

        # Check for Git repository marker or Python project configuration file
        if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
            # Found a likely project root — return it
            return parent

    # If we reach here, no marker was found → raise an error
    raise RuntimeError("Project root not found")


def extract_device_num_from_path(folder_path: str) -> Optional[str]:
    """
    Extracts the device number from a path.
    Assumes that in this path there has to be a folder with the following format: 'LIBPhys #001'
    :param folder_path: Path to the folder
    :return: a str with the device number (example: #001)
    """

    # folder name starts with 'LIBPhys' (i.e.: LIBPhys #001, LIBPhys #002, LIBPhys #003...)
    if match := re.search(r'LIBPhys (#\d+)', folder_path):

        # returns #001
        return match.group(1)

    else:
        return None


def extract_date_from_path(folder_path: str) -> Optional[str]:
    """
    Extracts the date from a path.
    Assumes that in this path there has to be a folder with the following format: '2025-09-24'
    :param folder_path: Path to the folder
    :return: a str with the date (example: 2025-09-24)
    """

    # find the date in the folder path (yyyy-mm-dd)
    if match := re.search(r'\b(\d{4}-\d{2}-\d{2})\b', folder_path):

        return match.group(1)

    else:
        return None

