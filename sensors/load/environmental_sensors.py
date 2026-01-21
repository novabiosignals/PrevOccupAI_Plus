"""
Functions for loading environmental sensor data contained in 'environmental_sensors.csv'.

Available Functions
-------------------
[Public]
load_environmental_sensor_data(...): loads the environmental sensor data contained in environmental_sensors.csv into a pandas.DataFrame.
calculate_mean_illuminance(...): Calculates the mean illuminance for one subject.
get_CO2_values(...): Get the CO2 values for one subject.
get_CO_values(...): Get the CO values for one subject.
get_COV_values(...): Get the COV values for one subject.
get_PM10_values(...): Get the PM 10 value for one subject.
get_PM025_values(...): Get the PM 025 value for one subject.
get_temperature(...): Gets the temperature for one subject.
get_relative_humidity(...): Gets the relative humidity (%) for one subject.
------------------
[Private]

"""

# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import pandas as pd

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #
def load_environmental_sensor_data() -> pd.DataFrame:
    """
    loads the environmental sensor data contained in environmental_sensors.csv into a pandas.DataFrame.
    :return: DataFrame containing the environment sensor data.
    """

    return pd.read_csv('environmental_sensors.csv', sep=',', encoding='utf-8', index_col='subject_id')


def calculate_mean_illuminance(df: pd.DataFrame, subject_id: int) -> float:
    """
    Calculates the mean illuminance for one subject.
    This function first extracts the six illuminance values in environmental_sensors.csv for subject_id and returns the
    mean illuminance.
    :param df: pandas.DataFrame containing the environment sensor data.
    :param subject_id: id of the subject to calculate the mean illuminance for.
    :return: The mean illuminance.
    """

    # filter the columns and get only the ones that have 'lux' in the name
    lux_cols = df.filter(like="lux")

    # get the values for the subject and calculate the mean
    return round(lux_cols.loc[subject_id].mean(), 4)


def get_CO2_values(df: pd.DataFrame, subject_id: int) -> float:
    """
    Get the CO2 ppm value for one subject
    :param df: pandas.DataFrame containing the environment sensor data.
    :param subject_id: id of the subject.
    :return: The CO2 ppm value.
    """
    return float(df.loc[subject_id, "CO2_ppm"])


def get_CO_values(df: pd.DataFrame, subject_id: int) -> float:
    """
    Get the CO ppm value for one subject
    :param df: pandas.DataFrame containing the environment sensor data.
    :param subject_id: id of the subject.
    :return: The CO ppm value.
    """
    return float(df.loc[subject_id, "CO_ppm"])


def get_COV_values(df: pd.DataFrame, subject_id: int) -> float:
    """
    Get the COV ppm value for one subject
    :param df: pandas.DataFrame containing the environment sensor data.
    :param subject_id: id of the subject.
    :return: The COV ppm value.
    """
    return float(df.loc[subject_id, "COV_ppm"])


def get_PM10_values(df: pd.DataFrame, subject_id: int) -> float:
    """
    Get the PM 10 value for one subject.
    :param df: pandas.DataFrame containing the environment sensor data.
    :param subject_id: id of the subject.
    :return: The PM 10 particles value.
    """
    return float(df.loc[subject_id, "part_pm10_ugm3"])


def get_PM025_values(df: pd.DataFrame, subject_id: int) -> float:
    """
    Get the PM 2.5 value for one subject.
    :param df: pandas.DataFrame containing the environment sensor data.
    :param subject_id: id of the subject.
    :return: The PM 2.5 particles value.
    """
    return float(df.loc[subject_id, "part_pm025_ugm3"])


def get_temperature(df: pd.DataFrame, subject_id: int) -> float:
    """
    Get the temperature in Celsius.
    :param df: pandas.DataFrame containing the environment sensor data.
    :param subject_id: id of the subject.
    :return: The PM 10 particles value.
    """
    return float(df.loc[subject_id, "t_celsius"])


def get_relative_humidity(df: pd.DataFrame, subject_id: int) -> float:
    """
    Get the relative humidity (%) for one subject
    :param df: pandas.DataFrame containing the environment sensor data.
    :param subject_id: id of the subject.
    :return: The PM 10 particles value.
    """
    return float(df.loc[subject_id, "rel_humidity_perc"])