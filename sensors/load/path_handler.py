"""
Functions to load_signals, filter, and organize sensor acquisition file paths from multiple devices.

Available Functions
-------------------
[Public]
get_sensor_paths_per_device(...): Load, filter, and organize sensor file paths for phone, watch, and MBAN devices into a nested dictionary grouped by acquisition times.
-------------------

[Private]
_get_device_files(...): Collect file paths for a given device. For phone/watch, filters by selected sensors; for MBAN, loads all files.
_keep_largest_file_per_acquisition(...): For each acquisition time, keep only the largest file (used for MBAN data).
_filter_mban_files(...): Replace the "mban" entry with "mban_left" and "mban_right" entries, splitting by MAC address.
_group_mban_files(...): Split MBAN files into left/right groups based on MAC address and metadata.
_get_android_filepaths(...): Retrieve phone or watch sensor file paths from the folder, filtering by the requested sensors.
_get_mban_files(...): Get all MBAN files from the folder using MAC address pattern matching.
_get_file_by_sensor(...): Find and return the file corresponding to a given sensor name.
_group_files_by_acquisition(...): Group files by their acquisition folder (immediate parent folder, e.g., '10-20-00').
_validate_load_devices(...): check if input sensors and devices are valid
-------------------
"""

# -------------------------------------------------------------------------------------------------------------------- #
# imports
# -------------------------------------------------------------------------------------------------------------------- #
import re
from pathlib import Path
from typing import List, Dict
from .meta_data import load_meta_data, get_muscleban_side
from constants import PHONE, WATCH, MBAN, MAC_ADDRESS_PATTERN, PHONE_SENSORS, WATCH_SENSORS, MBAN_SENSORS

# ------------------------------------------------------------------------------------------------------------------- #
# file specific constants
# ------------------------------------------------------------------------------------------------------------------- #
MIN_BYTES = 1500

# -------------------------------------------------------------------------------------------------------------------- #
# public functions
# -------------------------------------------------------------------------------------------------------------------- #

def get_sensor_paths_per_device(folder_path: str, load_devices: Dict[str, List[str]]):
    """
    Load, filter, and organize sensor file paths for multiple devices into a nested dictionary.

    This function does the following:
      (1). Load all file paths from the input `folder_path`, grouped by device type.

         - For phone and watch devices, loads only the sensors defined in load_devices.
         - For MBAN devices, load_signals all MBAN files (from both left and right mbans).

      (1.1). If MBAN is to be loaded, split its files into separate sides ('mban_left', 'mban_right').

      (2). Group the collected file paths by acquisition time (folder names with the format hh-mm-ss).

      (2.1). For the MBAN, keep only the largest file for each acquisition.

    Final Output:
      Returns a nested dictionary in the form:
      {device_name: {
            acquisition_time: [Path, Path, ...], ...},
          ...}
    :param folder_path: Root folder containing all device acquisition data.
    :param load_devices: Dictionary with the devices and sensors to be loaded. (e.g.: {phone: [ACC, GYR, MAG], watch: [ACC]}
            Supported devices/sensors:
            {phone: [ACC, GYR, MAG, ROT, NOISE],
             watch: [ACC, GYR, MAG, ROT, HR],
             mban: [ACC, EMG]}

    :return: Nested dictionary mapping each device to its acquisition times and corresponding file paths.
    """
    # innit dict for holding the unsorted paths
    paths_dict: Dict[str, List[Path]] = {}

    # innit dictionary to hold all devices and nested acquisition times and Paths
    nested_paths_dict: Dict[str, Dict[str, List[Path]]] = {}

    # check if folder_path is a directory and if it exists
    if not Path(folder_path).is_dir():

        # if not directory or does not exist raise error
        raise NotADirectoryError(f"The path provided: {folder_path} does not exist.")

    # check load_devices
    _validate_load_devices(load_devices)

    # (1) load_signals all files from all daily acquisitions per device into a dictionary
    for device, sensor_list in load_devices.items():

        # get paths per device - paths_dict = {phone: List(Path), watch: List(Path), mban: List(Path)}
        paths_dict[device] = _get_device_files(device, sensor_list, folder_path)

    # (1.1) if mban is loaded, separate the files into mban_left files and mban_right files
    if MBAN in paths_dict:

        # remove the key 'mban' from paths_dict and add 'mBAN_left' and 'mBAN_right'
        paths_dict = _filter_mban_files(paths_dict)

    # (2) filter the file paths and group them by acquisition time
    for device, files in paths_dict.items():

        # group all files for this device by acquisition folder (e.g. {'10-20-00': List(Path), '11-45-00': List(Path)})
        grouped_acquisitions_dict = _group_files_by_acquisition(files)

        # (2.1) if it is a mban device, keep only the largest file for each acquisition
        if device not in (PHONE, WATCH):

            # group by acquisition time and keep only the largest file - per acquisition each mban will only have one path
            grouped_acquisitions_dict = _keep_largest_file_per_acquisition(grouped_acquisitions_dict)

        # add device as key and dict with the times and list of path
        # s as values
        nested_paths_dict[device] = grouped_acquisitions_dict

    return nested_paths_dict

# -------------------------------------------------------------------------------------------------------------------- #
# private functions
# -------------------------------------------------------------------------------------------------------------------- #

def _get_device_files(device: str, sensor_list: List[str], folder_path: str) -> List[Path]:
    """
    Iterates through the folder in folder_path and gets the paths for the device into a list of Paths. If the device is
    a phone or watch, gets only the paths from the sensors in sensor_list. If it is a muscleban, loads all files (both
    left and right) into a list.

    Note: for the mban, this function does not handle keeping only the selected sensors (EMG or ACC), since all data is
    in the same file. This is handled when loading the data into pandas dataframes

    :param device: str pertaining to the device name. Supported devices: 'phone', 'watch', 'mban'
    :param sensor_list: list of sensors to load_signals for each device. Supported sensors per device:
                        phone: [ACC, GYR, MAG, ROT, NOISE]
                        watch: [ACC, GYR, MAG, ROT, HR]
                        mban: [ACC, EMG]
    :param folder_path: Root folder containing all device acquisition data.
    :return: list with paths
    """
    if device in (PHONE, WATCH):

        # if it is a smart device, get file paths to a list from only the selected sensors
        return _get_android_filepaths(device, sensor_list, folder_path)

    else:

        # if device is mban, load_signals all muscleban paths (both left and right) found into a list
        return _get_mban_files(folder_path)


def _keep_largest_file_per_acquisition(grouped_acquisitions_dict: Dict[str, List[Path]]) -> Dict[str, List[Path]]:
    """
    Keeps only the largest file for each acquisition time in the dictionary.
    If the largest file is smaller than 1.5 KB, the acquisition is removed.

    :param grouped_acquisitions_dict: Dict mapping acquisition time -> list of Paths
    :return: The same dict, with only the largest file kept per acquisition,
             or no entry if the largest file is too small.
    """

    # Store acquisition times to delete later (to avoid modifying dict while iterating)
    to_delete = []

    # Loop through each acquisition time and its associated list of file paths
    for acq_time, paths in grouped_acquisitions_dict.items():

        # Ensure the list is not empty
        if paths:

            # Find the file with the largest size
            largest = max(paths, key=lambda p: p.stat().st_size)

            # Check if the largest file is >= MIN_BYTES
            if largest.stat().st_size >= MIN_BYTES:

                # Keep only the largest file
                grouped_acquisitions_dict[acq_time] = [largest]
            else:
                # Mark acquisition for deletion if largest file is too small
                to_delete.append(acq_time)

    # Remove acquisitions where the biggest file in < MIN_BYTES
    for acq_time in to_delete:
        del grouped_acquisitions_dict[acq_time]

    return grouped_acquisitions_dict


def _filter_mban_files(paths_dict: Dict[str, List[Path]]) -> Dict[str, List[Path]]:
    """
    Separates the mucleban by mac address and gets the side. Then gets, per acquisition (folder with the time) only
    the biggest file. Assumes that this dictionary has a key 'mban' and correspondent list of Paths.

    :param paths_dict:  Dictionary with the device names as keys and list of Paths as values. One of these keys is 'mban'.
    :return: The same dictionary, but no with the mBAN_right and mBAN_left entries and correspondent list of Paths.
    """

    # group muscleban file by side
    mban_dict =_group_mban_files(paths_dict)

    # delete the 'mban' entry in paths dict, to substitute with mban left and mban right
    del paths_dict[MBAN]

    # add mban_dict to paths_dict
    paths_dict.update(mban_dict)

    return paths_dict


def _group_mban_files(paths_dict: Dict[str, List[Path]]) -> Dict[str, List[Path]]:
    """
    Splits MBAN files into separate groups based on their MAC address/side (e.g., left or right).

    Workflow:
        (1). Extract all MBAN files from the input `paths_dict` under the "mban" key.
        (2). Use a regex pattern to identify the unique MAC address from each file path.
        (3). Load metadata to determine the MBAN side (e.g., left/right) for the given MAC address.
        (4). Group files into a dictionary where the key is the MBAN side and the value is the list of file paths.

    Final Output:
      Returns a dictionary structured as:
      {
          "mban_left": [Path, Path, ...],
          "mban_right": [Path, Path, ...]
      }

    :param paths_dict: Dictionary of device as keys and list of file paths as values, including a "mban" entry.
    :return: Dictionary mapping MBAN side ("mban_left", "mban_right") to their corresponding list of file paths.
    """

    # innit dict to hold the separate mban files
    grouped_by_side: Dict[str, List[Path]] = {}

    # regex for detecting the mac address
    pattern = re.compile(MAC_ADDRESS_PATTERN)

    # (1) get all mban files from paths_dict
    mban_files = paths_dict.get(MBAN, [])

    # cycle over all mban_files
    for file in mban_files:

        # (2) match the mac address pattern in the mban files
        match = pattern.search(str(file))

        # load_signals metadata
        meta_data_df = load_meta_data()

        # (3) get muscleban side based on the unique mac address
        mban_side = get_muscleban_side(meta_data_df, match.group(0))

        # add key (mac address) to dict
        if mban_side not in grouped_by_side:
            grouped_by_side[mban_side] = []

        # (4) add to dictionary were key is the ban side and value are the correspondent Paths
        grouped_by_side[mban_side].append(file)

    return grouped_by_side


def _get_android_filepaths(device_name: str, sensor_list: List[str], folder_path: str) -> List[Path]:
    """
    Retrieves alL Android sensor file paths (phone or watch) from a given folder path. Keeps only te paths from the
    sensor in sensor_list.

    :param device_name: str pertaining to the device name (phone or watch)
    :param sensor_list: list with the sensor to find. Supported sensors per device:
                        phone: [ACC, GYR, MAG, ROT, NOISE]
                        watch: [ACC, GYR, MAG, ROT, HR]
    :param folder_path: Root folder containing all device acquisition data.
    :return: List with the Paths
    """

    # check which regular expression to search for given the device
    if device_name == PHONE:

        # check for the string ANDROID but can not have WEAR
        files = [file for file in Path(folder_path).resolve().glob("**/*ANDROID*") if "WEAR" not in file.name
                 and file.stat().st_size >= MIN_BYTES]

    else:

        # check for the string ANDROID but can not have WEAR
        files = [file for file in Path(folder_path).resolve().glob("**/*WEAR*") if file.stat().st_size >= MIN_BYTES]

    # get only the files from the sensors in sensor_list
    if sensor_list:

        # init list for holding the sensor files
        selected_files = []

        # cycle over the input sensor list
        for sensor in sensor_list:

            # collect all files that correspond to this sensor
            sensor_files = [f for f in files if sensor in f.name]

            # add them if any found
            selected_files.extend(sensor_files)

        return selected_files

    # if sensor_list is empty, load_signals all sensors
    return files


def _get_mban_files(folder_path: str) -> List[Path]:
    """
    Gets all mban files inside folder_path into a list.
    :param folder_path: Root folder containing all device acquisition data.
    :return: List with the paths
    """

    # get regex
    pattern = re.compile(MAC_ADDRESS_PATTERN)

    # get all files that have mac addresses
    files = [file for file in Path(folder_path).resolve().glob("**/*") if file.is_file() and pattern.search(file.name)]

    return files


def _group_files_by_acquisition(files: List[Path]) -> Dict[str, List[Path]]:
    """
    Groups files by their acquisition folder (the immediate parent folder, e.g. '10-20-00').

    :param files: List of Path objects
    :return: Dict mapping acquisition folder name -> list of Paths
    """
    # innit dict to hold the acquisition times and correspondent list of Paths
    grouped_acquisitions_dict: Dict[str, List[Path]] = {}

    # iterate over all provided file paths
    for file in files:

        # get the immediate parent folder name of the file (e.g. "10-20-00")
        acquisition_folder = file.parent.name

        # if this acquisition folder hasn't been added yet, initialize it with an empty list
        if acquisition_folder not in grouped_acquisitions_dict:
            grouped_acquisitions_dict[acquisition_folder] = []

        # add the file to the corresponding acquisition folder entry
        grouped_acquisitions_dict[acquisition_folder].append(file)

    return grouped_acquisitions_dict


def _validate_load_devices(load_devices: Dict[str, List[str]]) -> None:
    """
    Validates the load_devices dictionary to ensure that:
      - Devices are valid (must be one of {phone, watch, mban}).
      - Each device's sensors are valid for that device.
      - Sensors are unique and properly formatted.

    :param load_devices: Dictionary mapping device names to lists of sensor abbreviations.
                         Example: {"phone": ["ACC", "GYR"], "watch": ["HR"], "mban": ["EMG"]}
    :raises ValueError: If the dictionary contains invalid devices or sensors.
    """

    # Define valid devices and their allowed sensors
    valid_sensors_per_device = {
        PHONE: PHONE_SENSORS,
        WATCH: WATCH_SENSORS,
        MBAN: MBAN_SENSORS
    }

    # Check each device in the provided dict
    for device, sensors in load_devices.items():
        if device not in valid_sensors_per_device:
            raise ValueError(
                f"Invalid device '{device}'. Supported devices are: {list(valid_sensors_per_device.keys())}"
            )

        # Normalize to uppercase in case user provided lowercase
        sensors = [s.upper() for s in sensors]

        # Check for duplicates
        if len(sensors) != len(set(sensors)):
            raise ValueError(f"Duplicate sensors found for device '{device}': {sensors}")

        # Check if sensors are valid for the given device
        invalid_sensors = [s for s in sensors if s not in valid_sensors_per_device[device]]
        if invalid_sensors:
            raise ValueError(
                f"Invalid sensors for device '{device}': {invalid_sensors}. "
                f"Valid options are: {valid_sensors_per_device[device]}"
            )