"""
Functions for extracting environmental sensor data contained in 'environmental_sensors.csv'.

Available Functions
-------------------
[Public]
get_environmental_sensors_metrics(...): Get the environmental sensor metrics for the subject with subject_id.

------------------
[Private]
"""

# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
from typing import Dict

# internal imports
import sensors.load as sl
from OH_profile.constants import *
# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #

def get_environmental_sensors_metrics(subject_id: int) -> Dict[str, float]:
    """
    Get the environmental sensor metrics for the subject with subject_id.
    :param subject_id: The id of the subject to get the metrics for.
    :return: A dictionary with the environmental sensor metrics.
    """

    # load environmental sensor data
    env_df = sl.load_environmental_sensor_data()

    # get env sensor metrics
    env_metrics_dict = {ENV_ILLUMINANCE_KEY: sl.calculate_mean_illuminance(env_df, subject_id),
                        ENV_CO2_KEY: sl.get_CO2_values(env_df, subject_id),
                        ENV_CO_KEY: sl.get_CO_values(env_df, subject_id),
                        ENV_COV_KEY: sl.get_COV_values(env_df, subject_id),
                        ENV_PM10_KEY: sl.get_PM10_values(env_df, subject_id),
                        ENV_PM025_KEY: sl.get_PM025_values(env_df, subject_id),
                        ENV_TEMPERATURE_KEY: sl.get_temperature(env_df, subject_id),
                        ENV_REL_HUMIDITY_KEY: sl.get_relative_humidity(env_df, subject_id)
    }

    return env_metrics_dict