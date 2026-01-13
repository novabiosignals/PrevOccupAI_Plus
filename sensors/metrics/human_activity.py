"""
Functions to obtain human activity related metrics

Available Functions
-------------------
[Public]

-------------------

[Private]
-------------------
"""
# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import numpy as np
import pandas as pd
from scipy.fft import fft, fftfreq
from scipy.signal import detrend
from typing import Dict

# internal imports
from HAR import CLASS_WALK
from constants import ACTIVITY_COLUMN_NAME, PHONE, ACC, GYR, MAG, ROT
from utils import extract_date_from_path
import sensors.load as sensor_loader
import sensors.process as sensor_processor

# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
Y_ACC_COL = 'y_ACC'
# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #
def get_human_activity_metrics(day_folder_path: str, fs: int) -> Dict:
    """

    :param day_folder_path: Path to the folder containing the all the acquisitions from an entire day
    :param fs: The sampling frequency with which the data was acquired
    :return:
    """

    # get date from path
    day_date = extract_date_from_path(day_folder_path)

    # reformate to dd-mm-yyyy
    year, month, day = day_date.split('-')
    day_date = f"{day}-{month}-{year}"

    # init dict for holding the extracted metrics
    day_metrics_dict = {day_date: {}}

    # load the acquisition(s) for the day
    df_dict = sensor_loader.load_daily_acquisitions(day_folder_path, load_devices={PHONE: [ACC, GYR, MAG, ROT]})

    # pre-proces the data
    processed_df_dict = sensor_processor.apply_pre_processing_pipeline(df_dict)

    # cycle over the dictionary containing the phone data (usually there is only one acquisition, but multiple can happen)
    for acquisition_time, df in processed_df_dict[PHONE].items():

        # check whether the DataFrame contains data
        if not df.empty:

            # extract human activities
            print("classifying human activities and obtaining their proportions throughout the day.")

            # update dict

            # extract walking metrics (step detection)


    return day_metrics_dict







# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #
def _calculate_dominant_walking_frequency(data: pd.DataFrame, fs: int = 100) -> int:
    """
    Estimates the dominant frequency of a filtered acceleration signal using FFT,
    restricted to periods when the person is walking (activity == 2).

    Uses the Fourier transform on the 'y_ACC' column to find the frequency
    with the highest magnitude during walking segments only. Also calculates a
    minimum interval between peaks based on this dominant frequency.

    :return:
        - dominant_freq: Estimated dominant frequency in Hz.
        - minimum_interval: Minimum interval between peaks in samples (int).
    """

    # obtain only data segments where the subject's activity was classified as walking
    walking_data = data[data[ACTIVITY_COLUMN_NAME] == CLASS_WALK]

    # TODO: check with Mariana. This gives 50 Hz not 2 Hz
    if len(walking_data) < fs * 2:
        print("Not enough walking data to compute frequency.")
        return int(fs * 0.5)  # Default fallback (0.5s = ~2Hz)

    # Detrend the walking signal to remove drift
    acc_y = detrend(walking_data[Y_ACC_COL].values)

    # obtain number of samples and sampling interval (T)
    num_samples = len(acc_y)
    T = 1 / fs

    # calculate FFT
    yf = fft(acc_y)
    xf = fftfreq(num_samples, T)

    # obtain single sided FFT
    xf = xf[:num_samples // 2]
    yf = (2.0 / num_samples) * np.abs(yf[:num_samples // 2])

    # obtain the dominant frequency and its magnitude (Ignore frequency = 0 Hz)
    max_index = np.argmax(yf[1:]) + 1
    dominant_freq = xf[max_index]
    magnitude_max = yf[max_index]

    print(f"Dominant frequency during walking: {dominant_freq:.2f} Hz (Magnitude: {magnitude_max:.2f})")

    # Convert to minimum interval between peaks
    interval = fs / dominant_freq
    minimum_interval = int(interval * 0.5) # TODO: check with Mariana why * 0.5

    return minimum_interval