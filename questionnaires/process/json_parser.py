# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
from typing import Dict, Any

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #

def filter_config_dict_by_id(config_dict: Dict[str, Dict[str, Any]], questionnaire_id: str) -> Dict[str, Any]:

    # get only the information regarding the questionnaire with the given id
    filtered_config = {
        questionnaire_name: questionnaire_info for questionnaire_name, questionnaire_info in config_dict.items()
        if questionnaire_info.get("id") == questionnaire_id}

    # raise exception if id was not found
    if not filtered_config:
        raise ValueError(f"No questionnaire found with id {questionnaire_id}")

    # Return only the questionnaire's info
    return next(iter(filtered_config.values()))


def get_questionnaire_name_from_json(config_dict: Dict[str, Dict[str, Any]], questionnaire_id: str) -> str:

    # iterate through the several questionnaires in the config dict
    for questionnaire_name, questionnaire_info in config_dict.items():

        # check which id matches
        if questionnaire_info.get('id') == questionnaire_id:

            # return the name of the questionnaire with the given id
            return questionnaire_name

    raise ValueError(f"No questionnaire found with id: {questionnaire_id}")

# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #


