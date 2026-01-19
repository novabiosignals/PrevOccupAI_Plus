"""
Functions to load_signals JSON configuration files and trained machine learning models for HAR.

Available Functions
-------------------
[Public]
load_json_file(...): Loads a JSON file from into a dictionary.
load_production_model(...): Loads a trained Random Forest model and returns the model object and the list of features it was trained on.
-------------------
[Private]
None
------------------
"""
# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
from typing import Tuple, List
import joblib
from sklearn.ensemble import RandomForestClassifier

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #

def load_production_model(model_path: str, print_model_info: bool=False) -> Tuple[RandomForestClassifier, List[str]]:
    """
    Loads the production model
    :param model_path: path o the model
    :return: a tuple containing the model and the list of features used
    """
    # load_signals the classifier
    har_model = joblib.load(model_path)

    # get the features that the model was trained with
    feature_names = har_model.feature_names_in_

    # print model name
    print(f"\n--> using model: {type(har_model).__name__}")

    # print model information
    if print_model_info:
        print("\nmodel info: ")
        print(f"\nclasses: {har_model.classes_}")
        print(f"\nhyperparameters: {har_model.get_params()}")
        print(f"\nnumber of features: {len(feature_names)}")
        print(f"features: {feature_names}")

    return har_model, feature_names