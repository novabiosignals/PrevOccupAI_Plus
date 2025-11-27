# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import json
from typing import Dict, Any
import os
import re
from pathlib import Path

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


def create_dir(path, folder_name):
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


def get_group_from_path(folder_path: str) -> str:

    # find group pattern
    match = re.search(r'group\d+', folder_path)

    if match:

        # get first and only match
        return match.group()

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