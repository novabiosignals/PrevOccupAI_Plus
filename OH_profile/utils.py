"""
Utility functions for Occupational Health (OH) Profiles

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
# -------------------------------------------------------------------------------------------------------------------- #
# private functions
# -------------------------------------------------------------------------------------------------------------------- #