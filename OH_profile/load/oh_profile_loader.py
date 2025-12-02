"""
Functions for loading Occupational Health (OH) Profiles

Available Functions
-------------------
[Public]

-------------------

[Private]
_generate_OH_profile_json_skeleton(): generates the basic json skeleton for the OH profile.
-------------------
"""

# -------------------------------------------------------------------------------------------------------------------- #
# imports
# -------------------------------------------------------------------------------------------------------------------- #
import os
import json
from pathlib import Path

from typing import Dict
# -------------------------------------------------------------------------------------------------------------------- #
# constants
# -------------------------------------------------------------------------------------------------------------------- #
# file suffix
JSON_FILE_SUFFIX = '_OH_profile.json'

# json dict keys
METADATA_KEY = 'meta_data'

SINGLE_INSTANCE_QUESTIONNAIRE_KEY = 'single_instance_questionnaires'
PERSONAL_DOMAIN_KEY = 'personal'
BIOMECHANICAL_DOMAIN_KEY = 'biomechanical'
PSYCHOSOCIAL_DOMAIN_KEY = 'psychosocial'
ENVIRONMENTAL_DOMAIN_KEY = 'environmental'

DAILY_QUESTIONNAIRE_DOMAIN_KEY = 'daily_questionnaires'
WORKLOAD_DOMAIN_KEY = 'workload'
PAIN_DOMAIN_KEY = 'pain'

SENSOR_METRICS_KEY = 'sensor_metrics'
SENSOR_TIMELINE_KEY = 'sensor_timeline'
HAR_KEY = 'human_activities'
HEART_RATE_KEY = 'heart_rate'
POSTURE_KEY = 'posture'
NOISE_KEY = 'noise'
EMG_KEY = 'emg'
WRIST_KEY = 'wrist_activities'
# -------------------------------------------------------------------------------------------------------------------- #
# public functions
# -------------------------------------------------------------------------------------------------------------------- #
def get_OH_profile(folder_path: str, subject_ID: str) -> Dict:
    """
    gets the OH profile from the data path or creates the OH profile skeleton if the file does not exist.
    :param folder_path: path to the folder containing the OH profile
    :param subject_ID: the subject ID
    :return: OH profile to fill in data
    """

    # create full path to file
    folder = Path(folder_path)
    oh_profile_path = folder / f"{subject_ID}{JSON_FILE_SUFFIX}"

    # check whether the file exists
    if oh_profile_path.is_file():

        # load the json file
        with open(oh_profile_path, "r", encoding="utf-8") as json_file:
            oh_profile = json.load(json_file)

    else: # the oh-profile does not exist yet

        # generate empty OH profile skeleton
        oh_profile = _generate_OH_profile_json_skeleton()

    return oh_profile


# -------------------------------------------------------------------------------------------------------------------- #
# private functions
# -------------------------------------------------------------------------------------------------------------------- #
def _generate_OH_profile_json_skeleton() -> Dict:
    """
    generates the basic json skeleton for the OH profile. This skeleton is can be subsequently filled with the
    corresponding data using the respective keys
    :return: the json/dictionary representation of the OH profile skeleton (empty dictionary with all necessary keys)
    """

    # define json skeleton (as dictionary)
    oh_profile = {
        METADATA_KEY: {},

        SINGLE_INSTANCE_QUESTIONNAIRE_KEY: {
            PERSONAL_DOMAIN_KEY: {},
            BIOMECHANICAL_DOMAIN_KEY: {},
            PSYCHOSOCIAL_DOMAIN_KEY: {},
            ENVIRONMENTAL_DOMAIN_KEY: {}
        },

        DAILY_QUESTIONNAIRE_DOMAIN_KEY: {
            WORKLOAD_DOMAIN_KEY: {},
            PAIN_DOMAIN_KEY: {}
        },

        SENSOR_METRICS_KEY: {
            SENSOR_TIMELINE_KEY: {},
            HAR_KEY: {},
            HEART_RATE_KEY: {},
            POSTURE_KEY: {},
            NOISE_KEY: {},
            EMG_KEY: {},
            WRIST_KEY: {}
        }
    }

    return oh_profile
