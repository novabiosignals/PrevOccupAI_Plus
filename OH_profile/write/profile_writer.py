"""
Functions for writing to Occupational Health (OH) Profiles

Available Functions
-------------------
[Public]
save_OH_profile(...): Saves an updated OH profile dictionary to a JSON file.
write_to_OH_profile(...): Writes the metrics in a dictionary into the OH profile by updating the pre-existing dictionary.
-------------------

[Private]

-------------------
"""

# -------------------------------------------------------------------------------------------------------------------- #
# imports
# -------------------------------------------------------------------------------------------------------------------- #
import json
from pathlib import Path
from typing import Dict, Optional

# internal imports
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


def write_to_OH_profile(oh_profile: Dict, main_outer_key: str, main_inner_key: Optional[str], dict_to_write: Dict) -> Dict:
    """
    Writes the metrics in a dictionary into the OH profile by updating the pre-existing dictionary.


    :param main_outer_key: str pertaining to the main outer jey (example: SENSOR_TIMELINE_KEY).
    :param main_inner_key: Optional. str pertaining to the main inner jey (example: SENSOR_METRICS_KEY)
                            Can be None for example for the metadata
    :param oh_profile: Dictionary containing the OH profile.
    :param dict_to_write: Dictionary to be added after the main outer key.
            (example: OH_profile = {SENSOR_METRICS_KEY: {SENSOR_TIMELINE_KEY: dict_to_write}})
    :return: The updated oh profile dictionary
    """

    if main_inner_key is None:
        # write directly under outer key
        oh_profile[main_outer_key].update(dict_to_write)
    else:
        # add inner key
        oh_profile[main_outer_key][main_inner_key].update(dict_to_write)

    return oh_profile


def clear_dict_entries(oh_profile: dict, key_to_clear: str) -> dict:
    """
    Recursively searches for `key_to_clear` in a nested dictionary
    and clears its contents (if it's a dict) or sets it to None otherwise.

    :param oh_profile: The main dictionary to modify
    :param key_to_clear: The key name to search for and clear
    :return: The modified dictionary
    """
    for key, value in oh_profile.items():
        if key == key_to_clear:
            if isinstance(oh_profile[key], dict):
                oh_profile[key].clear()  # clear all items but keep the key
            else:
                oh_profile[key] = None  # set non-dict value to None

        elif isinstance(value, dict):

            # recurse into nested dictionary
            clear_dict_entries(value, key_to_clear)
    return oh_profile
# -------------------------------------------------------------------------------------------------------------------- #
# private functions
# -------------------------------------------------------------------------------------------------------------------- #