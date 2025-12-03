"""
Functions to detect and reconstruct missing sensor acquisitions.

Available Functions
-------------------
[Public]
get_missing_data(...): Identify missing acquisition times and durations for each device.
compute_end_times(...): Compute end times by adding durations (in seconds) to corresponding start times.
-------------------

[Private]
_convert_str_to_datetime(...): convert string to datetime object
_convert_datetime_to_str(...): convert datetime object to string
_get_most_common_acquisition_times(...): Find the four most common acquisition times for a subject by scanning folder names and filtering device data.
_get_most_common_times(...): Compute the most common acquisition times from a list, with optional adjustment to merge times closer than 20 minutes.
_has_close_time(...): Check whether a given timestamp is within the tolerance window of another timestamp in a list.
_get_missing_timestamps(...): Compare expected acquisition times with actual ones to determine which are missing.
_find_unique_timestamps(...): Extract unique acquisition timestamps across devices (excluding phone), accounting for tolerance in start times.
_remove_dates(...): Remove date folder names from a folder list, keeping only acquisition time folders.
_adjust_most_common_times(...): Filter out acquisition times that are too close (< 20 minutes apart), keeping the most frequent ones.
_get_shift_from_phone_time(...): Gets the shift of the subject based on the start time of the smartphone.
_filter_shift_times(...): Filter acquisition times to keep only those that fall within the same shift as the provided phone start time.
-------------------
"""

# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import re
import os
from collections import Counter
from typing import Dict, List, Optional
from datetime import datetime, timedelta

# internal imports
from constants import PHONE, ACQUISITION_TIME_SECONDS, TIME_FORMAT, ANDROID, ANDROID_WEAR

# ------------------------------------------------------------------------------------------------------------------- #
# file specific constants
# ------------------------------------------------------------------------------------------------------------------- #
LENGTH = 'length'
START_TIMES = 'start_times'
END_TIMES = 'end_times'

SHIFTS_START_TIMES = {
    "FIRST":  ['08-00-00', '09-29-00'],
    "SECOND": ['09-30-00', '12-30-00'],
    "THIRD":  ['12-31-00', '16-00-00']
}

SHIFTS_END_TIMES = {
    "FIRST":  '15-00-00',
    "SECOND": '17-00-00',
    "THIRD":  '20-00-00'
}
TOLERANCE_CONSECUTIVE_ACQUISITIONS = 2000 # seconds (30 min)
# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #

def get_missing_data(subject_folder_path: str, acquisitions_dict: Dict[str, Dict[str, list]],
                     tolerance_seconds: int = 600) -> Dict[str, Dict[str, list]]:
    """
    Identify and return missing data (start_time and length) for each device (except the phone).

    This function assumes that the smartwatch and two muscleBAN should all acquire data at the same time, four times
    per day. Due to potential connection issues, some acquisitions may be missing. This function determines which
    timestamps are missing for each device, based on what was recorded by the others.

    In the case that all devices failed to acquire in one of these four scheduled acquisitions, this function uses the
    average acquisition times (based on the common acquisition times during the five days of acquisition of the subject),
    to get the missing timestamp.

    Steps:
    (1) Obtain all unique timestamps of all devices, except the phone. As there is always some delay, timestamps that are
        less than ten minute apart are considered to be the same one.

    (2) Compare the start_times in the acquisitions_dict with the unique timestamps to get a list with missing timestamps
        for each device.

    (3) If the length of the actual start times and the missing start times is less than four then there was one scheduled
        acquisition that either did not happen or all devices failed. In this case find the last remaining missing timestamps
        based on the average start times of the entire week.

    (4) For each missing timestamp, a default duration (20-minute acquisition) is used to calculate the end_times of
    the acquisitions

    :param subject_folder_path: Path to the folder containing all data from the subject
    :param acquisitions_dict: A dictionary where keys are device names, and values are dictionaries with two lists:
             - 'length': List of signal lengths.
             - 'start_times': List of corresponding start timestamps.
             Example:
             {
                 "phone": {"start_times": ["11:20:20.000"], "end_times": ["11:40:20.000"]},
                 "watch": {"start_times": ["10:20:50.000", "12:00:00.000"], "end_times": ["10:40:50.000", "12:20:00.000"]}
             }
    :param tolerance_seconds: Time in seconds used to consider two start times as referring to the same acquisition.
                            Default = 600. (e.g., 12:00:00 and 12:03:00 are considered to be the same start time).
    :return: A dictionary in the same format as `acquisitions_dict`, but containing only the missing acquisitions
             detected for each device.
    """

    # dictionary to store the missing data with the same format as the dictionary storing the actual acquisitions
    missing_data_dict: Dict[str, Dict[str, list]] = {}

    # check if there are missing acquisitions
    for device, data in acquisitions_dict.items():

        # skip if it's phone
        if device == PHONE:
            continue

        # if any device that is not phone didn't acquire 4 times, then it's missing
        if  len(data[START_TIMES]) < 4:

            # (1) get the unique timestamps - all timestamps of the devices that should acquire at the same time
            unique_timestamps_list = _find_unique_timestamps(acquisitions_dict, tolerance_seconds)

            # (2) compare the actual timestamps with the unique to get missing timestamps for the device
            missing_times_list = _get_missing_timestamps(unique_timestamps_list, data[START_TIMES])

            # (3) check if there are still missing timestamps - no device connected for the scheduled acquisition
            if len(data[START_TIMES]) + len(missing_times_list) < 4:

                # create list with the actual timestamps and the missing timestamps found in get_missing_time_from_device
                temp_list = data[START_TIMES] + missing_times_list

                # Get the most common expected acquisition based on the average of all days
                average_times_list = _get_most_common_acquisition_times(subject_folder_path, acquisitions_dict[PHONE][START_TIMES][0])

                # use the averages to get only the timestamps that are missing on both devices
                missing_times_list.extend(_get_missing_timestamps(average_times_list, temp_list))

                # handle the case where the acquisition time are so mismatched that data[START_TIMES] + missing_times_list > 4
                if len(data[START_TIMES]) + len(missing_times_list) > 4:

                    # iterate through the missing times list to remove the wrong ones
                    for missing_time in missing_times_list:

                        # there should be a difference of at leats 30 minutes between an actual acquisition time and the
                        # calculated missing time for it to be
                        if _has_close_time(datetime.strptime(missing_time, TIME_FORMAT),
                                           [datetime.strptime(time, TIME_FORMAT) for time in data[START_TIMES]],
                                           TOLERANCE_CONSECUTIVE_ACQUISITIONS):

                            # remove 'fake' missing time from list
                            missing_times_list.remove(missing_time)

            # initialize if device not in dict
            if device not in missing_data_dict:
                missing_data_dict[device] = {
                    START_TIMES: [],
                    END_TIMES: []
                }

                # (4) append missing timestamps + end times
                # get time to add to the start time
                durations = [ACQUISITION_TIME_SECONDS] * len(missing_times_list)

                # calculate end time
                computed_ends = compute_end_times(missing_times_list, durations)

                # add to the nested dict
                missing_data_dict[device][START_TIMES].extend(missing_times_list)
                missing_data_dict[device][END_TIMES].extend(computed_ends)

    return missing_data_dict


def compute_end_times(start_times: List[Optional[str]], lengths_seconds: List[float]) -> List[Optional[str]]:
    """
    Compute end times by adding durations (in seconds) to corresponding start times.

    :param start_times: A list of start times as strings
    :param lengths_seconds: A list of durations in seconds to add to each corresponding start time.
    :return: A list with the end times.

    """
    end_times = []

    for start, dur_sec in zip(start_times, lengths_seconds):
        if start is None:
            end_times.append(None)
            continue

        # parse HH:MM:SS or with milliseconds
        try:
            t0 = datetime.strptime(start, TIME_FORMAT)
        except ValueError:
            t0 = datetime.strptime(start, f"{TIME_FORMAT}.%f")

        t_end = (t0 + timedelta(seconds=dur_sec)).time()
        end_times.append(t_end.strftime(TIME_FORMAT))

    return end_times

# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #

def _convert_str_to_datetime(time_str: str, time_format: str) -> datetime.time:
    """
    Convert a time string into a datetime.time object.

    :param time_str: A time value represented as a string.
    :param time_format: The format pattern used to parse the string.
    :return: datetime.time object
    """
    return datetime.strptime(time_str, time_format).time()


def _convert_datetime_to_str(time: datetime, time_format: str) -> str:
    """
    Convert a datetime or datetime.time object into a formatted time string.

    :param time: datetime object to be converted.
    :param time_format: The format string used for conversion.
    :return: The formatted time string.
    """
    return time.strftime(time_format)


def _get_most_common_acquisition_times(data_path: str, phone_start_time: str) -> List[datetime]:
    """
    retrieves the four most common acquisition times found in all acquisition times for the subjects.
    The acquisition times are found by retrieving all folder names that contain a time that can be found within
    data_path.
    :param data_path: the path to the data of the current subject
    :param phone_start_time: str with the start time of the phone for the day
    :return: list with the four most common acquisition times. In case there are less than four acquisition times found,
    then only those are returned.
    """
    # list for storing the acquisition times
    acquisition_times_list = []

    # get all folder names within data path
    for root, _, files in os.walk(data_path):

        # check if any file contains '_ANDROID_WEAR_' and if no file contains '_ANDROID_' without '_WEAR_'
        # this is done to filter out the folders that contain the phone data
        contains_android_wear = any(ANDROID_WEAR in filename for filename in files)
        contains_android_only = any(ANDROID in filename and ANDROID_WEAR not in filename for filename in files)

        # filter for folders that contain EMG data (excluding folders that contain the phone data)
        if contains_android_wear and not contains_android_only:
            acquisition_times_list.append(os.path.basename(root))

    # remove all folder names that are not times (in the database structure there are date and time folders only)
    acquisition_times_list = _remove_dates(acquisition_times_list)

    # standardize the times (replacing seconds with 00)
    acquisition_times_list = [time[:-2] + '00' for time in acquisition_times_list]

    # filter list by schedule
    acquisition_times_list = _filter_shift_times(acquisition_times_list, phone_start_time)

    # find the most common times (usually 4 due to four acquisitions a day, but could also be less)
    acquisition_times_list = get_most_common_times(acquisition_times_list, adjust_close_times=True)

    return [datetime.strptime(time, TIME_FORMAT) for time in acquisition_times_list]


def get_most_common_times(acquisition_times_list, adjust_close_times=False):
    """
    gets the most common acquisition times. In case there are > 4 unique times the four most common times are return,
    otherwise just the unique acquisition times are returned.
    :param acquisition_times_list:
    :param adjust_close_times: boolean flag for adjusting times that are closer than 20 min to each other. When this
                               flag is set to True, the times in acquisition_times_list are adjusted in the following
                               way.
                               Example:
                               input:  ['10-30-00', '10-31-00', '10-35-00', '10-41-00', '11-00-00', '11-12-00']
                               output: ['10-30-00', '10-30-00', '10-30-00', '10-30-00', '11-00-00', '11-00-00']
    :return: list containing the four most common times within the passed acquisition_times_list
    """

    # check if the number of unique times is less than 4
    if len(set(acquisition_times_list)) <= 4:

        # get the unique times sorted
        most_common_times = sorted(list(set(acquisition_times_list)))

    else:

        # count the occurrences
        time_count = Counter(acquisition_times_list)

        if adjust_close_times:
            time_count = _adjust_most_common_times(time_count)

        # get the four most common times
        most_common = time_count.most_common(4)

        # Extract the times in ascending order if there's a tie
        most_common_times = sorted([time[0] for time in most_common])

    return most_common_times


def _has_close_time(time: datetime, time_list_dt: List[datetime], tolerance_seconds: int) -> bool:
    """
    Check whether a given timestamp is within the tolerance window of any timestamp in a list.

    This function is used to determine if an acquisition time is "close enough"
    to another (i.e., represents the same scheduled acquisition).

    :param time: A datetime object to compare.
    :param time_list_dt: List of datetime objects representing existing acquisition times.
    :param tolerance_seconds: Time difference (in seconds) allowed for considering two times as the same.
    :return: True if `time` is within the tolerance of any timestamp in `time_list_dt`, otherwise False.
    """
    return any(abs((time - t).total_seconds()) <= tolerance_seconds for t in time_list_dt)


def _get_missing_timestamps(unique_timestamps_list: List[datetime], acquisitions_times_list: List[str],
                            tolerance_seconds=600) -> List[str]:
    """
    Identify which expected acquisition times are missing for a device.

    This function compares the unique expected acquisition times (found with the devices that acquired data) against the actual
    acquisition times recorded by a device (that had missing acquisitions), and returns those that are missing.

    :param unique_timestamps_list: List of datetime objects representing all expected acquisitions.
    :param acquisitions_times_list: List of acquisition start times (string format) for the device.
    :param tolerance_seconds: Allowed deviation (in seconds) for considering times as equal. Default = 600 seconds (10 min).
    :return: List of missing acquisition times (string format, TIME_FORMAT).
    """

    # innit list to store the missing times
    missing_times: List[str] = []

    # change the sensor start times to datetime
    device_timestamp_dt = [datetime.strptime(timestamp, TIME_FORMAT) for timestamp in acquisitions_times_list]

    # iterate through the unique timestamps
    for timestamp in unique_timestamps_list:

        # check if there is a timestamp that is NOT similar to the one in unique_timestamps_list
        if not _has_close_time(timestamp,device_timestamp_dt, tolerance_seconds):

            # add to the list with missing times in the correct format
            missing_times.append(timestamp.strftime(TIME_FORMAT))

    return missing_times


def _find_unique_timestamps(acquisitions_dict: Dict[str, Dict[str, list]], tolerance_seconds: int) -> List[datetime]:
    """
    Finds a set of start times that are expected for all devices, except the smartphone. this is done by getting the
    unique timestamps for all three devices (watch, mBAN right, and mBAN left), with a tolerance, since the devices don't start
    acquiring exactly at the same time.

    :param acquisitions_dict: Dictionary with device acquisition data.
                              Each entry contains 'start_times' and 'length'.
    :param tolerance_seconds: Allowed deviation (in seconds) for considering timestamps as the same acquisition.
    :return: A list of unique acquisition times (datetime objects).
    """

    # list for holding all timestamps found for the 3 devices that acquire at the same time
    all_daily_timestamps: List[datetime] = []

    for device, data in acquisitions_dict.items():

        # skip if its phone
        if device == PHONE:
            continue

        # change to datetime objects to perform mathematics
        acquisition_times_dt = [datetime.strptime(time, TIME_FORMAT) for time in data[START_TIMES]]
        all_daily_timestamps.extend(acquisition_times_dt)

    # since these devices don't start exactly at the same time, remove the timestamps that are very similar based on tolerance_seconds
    # list for holding the unique timestamps
    filtered_timestamps: List[datetime] = []

    # iterate through the sorted list
    for timestamp in sorted(all_daily_timestamps):

        # if list is empty add the first timestamp
        if not filtered_timestamps:

            filtered_timestamps.append(timestamp)

        else:
            # check if this timestamp is similar to the previous value add only if it's not
            if not _has_close_time(timestamp, filtered_timestamps, tolerance_seconds):
                filtered_timestamps.append(timestamp)


    return filtered_timestamps


def _remove_dates(folder_list: List[str]) -> List[str]:
    """
    removes date folder names from the folder_list, thus only time folder names are kept.
    :param folder_list: a list containing all sub-folder names for a subject in the database
    :return: list with only acquisition time folder names
    """
    # Regular expression to match date patterns (HH-MM-SS)
    date_pattern = re.compile(r'\d{2}-\d{2}-\d{2}')

    # Filter out strings that don't match the date pattern
    result = [item for item in folder_list if re.match(date_pattern, item)]

    return result


def _adjust_most_common_times(counter: Counter) -> Counter:
    """
    Filter times that are too close to each other, keeping only those at least ACQUISITION_TIME_SECONDS apart.
    :param counter: Counter object with times as keys and occurrences as values.
    :return: Counter object with filtered times.
    """

    # Convert time strings to datetime objects and sort by occurrences and then by time
    times = [(datetime.strptime(time, TIME_FORMAT), time, count) for time, count in counter.items()]
    times.sort(key=lambda x: (-x[2], x[0]))  # Sort by occurrences (desc) and then by time (asc)

    # List to keep the filtered times
    filtered_times = []

    # Iterate and filter times
    for i in range(len(times)):

        current_time, current_time_str, current_count = times[i]

        # Check if the current time is too close to any already accepted time
        too_close = False
        for filtered_time, _, _ in filtered_times:
            if abs((current_time - filtered_time).total_seconds()) < ACQUISITION_TIME_SECONDS:
                too_close = True
                break

        # If not too close, add to filtered times
        if not too_close:
            filtered_times.append(times[i])

    # Convert back to Counter
    result_counter = Counter({time_str: count for _, time_str, count in filtered_times})

    return result_counter


def _get_shift_from_phone_time(phone_start_time: str) -> str:
    """
    Identify the shift of a particular subject based on the start time of the smartphone
    :param phone_start_time: string with the phone start time
    :return: string with the shift name
    """

    phone_start_time = _convert_str_to_datetime(phone_start_time, TIME_FORMAT)

    # iterate through the shift times
    for shift_name, (start_time, end_time) in SHIFTS_START_TIMES.items():

        # convert to datetime
        start_time = _convert_str_to_datetime(start_time, TIME_FORMAT)
        end_time = _convert_str_to_datetime(end_time, TIME_FORMAT)

        # check if the phone start time is in the shift interval
        if start_time <= phone_start_time <= end_time:

            return shift_name

    raise ValueError(f"Phone start time does not fit the defined shift times")


def _filter_shift_times(times_list: List[str], phone_start_time: str) -> List[str]:
    """
    Filter acquisition times to keep only those that fall within the same shift as the provided phone start time.

    The function identifies which shift the phone start time belongs to, then obtains the corresponding shift end time.
    It returns a list of acquisition times (as strings) that lie between the phone start time and that shift's end time.

    :param times_list: A list of acquisition times as strings
    :param phone_start_time:
    :return:
    """
    # init list to store the acquisition times to keep
    valid_times = []

    # get shift from start time
    shift = _get_shift_from_phone_time(phone_start_time)

    # convert to dt
    phone_start_time = _convert_str_to_datetime(phone_start_time, TIME_FORMAT)

    # get end time from shift
    end_time = SHIFTS_END_TIMES[shift]
    end_time = _convert_str_to_datetime(end_time, TIME_FORMAT)

    # iterate through all acquisition times of the week
    for acquisition_time in times_list:

        # convert to datetime
        acquisition_time = _convert_str_to_datetime(acquisition_time, TIME_FORMAT)

        # check if it's in the interval
        if phone_start_time <= acquisition_time <= end_time:

            # convert back to string - fits the remaining functions better
            acquisition_time = _convert_datetime_to_str(acquisition_time, TIME_FORMAT)

            # add to valid times
            valid_times.append(acquisition_time)

    return valid_times
