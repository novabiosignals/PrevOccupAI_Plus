"""
Functions for writing to Occupational Health (OH) Profiles

Available Functions
-------------------
[Public]

-------------------

[Private]

-------------------
"""

# -------------------------------------------------------------------------------------------------------------------- #
# imports
# -------------------------------------------------------------------------------------------------------------------- #
import json
from pathlib import Path
from typing import Dict

from OH_profile.load.oh_profile_loader import JSON_FILE_SUFFIX


# -------------------------------------------------------------------------------------------------------------------- #
# constants
# -------------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------------- #
# public functions
# -------------------------------------------------------------------------------------------------------------------- #

def save_OH_profile(path: str, subject_ID: str, oh_profile: Dict) -> None:
    """
    Saves an updated OH profile dictionary to a JSON file.

    :param path: Path to the folder where the OH profile should be stored.
    :param subject_ID: Subject identifier used as filename prefix.
    :param oh_profile: Dictionary containing the OH profile data.
    :return: None
    """
    folder = Path(path)
    json_path = folder / f"{subject_ID}{JSON_FILE_SUFFIX}"

    # Ensure target folder exists
    folder.mkdir(parents=True, exist_ok=True)

    # Serialize and write JSON
    json_path.write_text(
        json.dumps(oh_profile, indent=4, ensure_ascii=False),
        encoding="utf-8"
    )


def write_to_OH_profile(oh_profile: Dict, main_outer_key: str, main_inner_key: str, dict_to_write: Dict) -> Dict:
    """
    Writes the metrics in a dictionary into the OH profile by updating the pre-existing dictionary.

    :param main_inner_key:
    :param main_outer_key:
    :param oh_profile: Dictionary
    :param dict_to_write:
    :return:
    """
    oh_profile[main_outer_key][main_inner_key].update(dict_to_write)

    return oh_profile
# -------------------------------------------------------------------------------------------------------------------- #
# private functions
# -------------------------------------------------------------------------------------------------------------------- #