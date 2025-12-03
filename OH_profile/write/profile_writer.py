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
from typing import Dict

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


def write_to_OH_profile(oh_profile: Dict, main_outer_key: str, main_inner_key: str, dict_to_write: Dict) -> Dict:
    """
    Writes the metrics in a dictionary into the OH profile by updating the pre-existing dictionary.

    :param main_inner_key: str pertaining to the main inner jey (example: SENSOR_METRICS_KEY)
    :param main_outer_key: str pertaining to the main outer jey (example: SENSOR_TIMELINE_KEY)
    :param oh_profile: Dictionary containing the OH profile.
    :param dict_to_write: Dictionary to be added after the main outer key.
            (example: OH_profile = {SENSOR_METRICS_KEY: {SENSOR_TIMELINE_KEY: dict_to_write}})
    :return: The updated oh profile dictionary
    """
    oh_profile[main_outer_key][main_inner_key].update(dict_to_write)

    return oh_profile
# -------------------------------------------------------------------------------------------------------------------- #
# private functions
# -------------------------------------------------------------------------------------------------------------------- #