"""
EMG Signal Preprocessing Functions

This module contains functions for preprocessing raw EMG signals:
- Loading OpenSignals .txt files
- Applying transfer function (raw ADC → millivolts)
- Bandpass filtering
- Rectification
- Smoothing (envelope extraction)
"""

import json
from pathlib import Path
from typing import Tuple, List

import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d
from scipy.signal import butter, filtfilt


# -------------------------------------------------------------------------------------------------------------------- #
# File Loading Functions
# -------------------------------------------------------------------------------------------------------------------- #

def load_opensignals_txt(path: str) -> Tuple[pd.DataFrame, dict, float]:
    """
    Load an OpenSignals .txt file with its metadata and sampling rate.

    :param path: Path to the OpenSignals .txt file.
    :return: Tuple of (dataframe, metadata_dict, sampling_rate).
    """
    path_obj = Path(path)

    # Find the JSON metadata line (starts with "# {")
    json_line = None
    with path_obj.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if line.startswith("# {"):
                json_line = line[1:].strip()
                break

    if json_line is None:
        raise ValueError(f"Missing metadata header in {path_obj}")

    # Parse metadata
    meta_all = json.loads(json_line)
    dev_key = next(iter(meta_all.keys()))
    meta = meta_all[dev_key]
    columns = meta.get("column", [])

    # Get sampling rate
    fs_raw = meta.get("sampling rate")
    try:
        fs = float(fs_raw)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid sampling rate '{fs_raw}' in file {path_obj}")

    # Find EMG columns
    emg_indices = [i for i, col in enumerate(columns) if "emg" in str(col).lower()]
    if not emg_indices:
        usecols = None
        selected_names = columns
    else:
        usecols = emg_indices
        selected_names = [columns[i] for i in emg_indices]

    # Load data
    df = pd.read_csv(
        path_obj,
        sep="\t",
        comment="#",
        header=None,
        engine="c",
        usecols=usecols,
        names=selected_names,
    )

    if usecols is None and len(columns) == df.shape[1]:
        df.columns = columns

    return df, meta, fs


def load_emg_channel(df: pd.DataFrame) -> np.ndarray:
    """
    Extract the first EMG-related column from a dataframe.

    :param df: DataFrame loaded from OpenSignals file.
    :return: 1D array of EMG values.
    """
    for column in df.columns:
        column_name = str(column)
        if "emg" in column_name.lower():
            return df[column].to_numpy()

    # Fallback to second column (common for MVC files)
    return df.iloc[:, 1].to_numpy()


# -------------------------------------------------------------------------------------------------------------------- #
# Signal Processing Functions
# -------------------------------------------------------------------------------------------------------------------- #

def transfer_emg(raw_emg: np.ndarray) -> np.ndarray:
    """
    Convert raw 16-bit EMG samples to millivolts using the device transfer function.

    Formula: ((raw / 2^15) - 0.5) * 2500 / 1100

    :param raw_emg: Array of raw ADC values.
    :return: Array of EMG values in millivolts.
    """
    return (((raw_emg / (2 ** (16 - 1.0))) - 0.5) * 2500) / 1100


def bandpass_filter(signal: np.ndarray, fs: float, lowcut: float = 10.0,
                    highcut: float = 500.0, order: int = 4) -> np.ndarray:
    """
    Apply a Butterworth bandpass filter to remove noise and motion artifacts.

    :param signal: Input signal array.
    :param fs: Sampling frequency in Hz.
    :param lowcut: Lower cutoff frequency in Hz (default: 10 Hz).
    :param highcut: Upper cutoff frequency in Hz (default: 500 Hz).
    :param order: Filter order (default: 4).
    :return: Filtered signal.
    """
    nyquist = 0.5 * fs
    low = max(lowcut / nyquist, 0.001)
    high = min(highcut / nyquist, 0.999)
    b, a = butter(order, [low, high], btype="band", output="ba")
    return filtfilt(b, a, signal)


def preprocess_emg(emg_mv: np.ndarray, fs: float, lowcut: float = 10.0,
                   highcut: float = 500.0, smooth_sigma_ms: float = 50.0) -> np.ndarray:
    """
    Full EMG preprocessing pipeline: de-mean → bandpass filter → rectify → smooth.

    :param emg_mv: EMG signal in millivolts.
    :param fs: Sampling frequency in Hz.
    :param lowcut: Lower bandpass cutoff in Hz.
    :param highcut: Upper bandpass cutoff in Hz.
    :param smooth_sigma_ms: Gaussian smoothing sigma in milliseconds.
    :return: Processed EMG envelope.
    """
    # Remove DC offset
    emg_dc = emg_mv - np.mean(emg_mv)

    # Bandpass filter
    emg_filt = bandpass_filter(emg_dc, fs, lowcut=lowcut, highcut=highcut)

    # Full-wave rectification
    emg_rect = np.abs(emg_filt)

    # Gaussian smoothing to get the envelope
    sigma_samples = (smooth_sigma_ms / 1000.0) * fs
    envelope = gaussian_filter1d(emg_rect, sigma=sigma_samples)

    return envelope


# -------------------------------------------------------------------------------------------------------------------- #
# Session Processing Functions
# -------------------------------------------------------------------------------------------------------------------- #

def process_emg_session(emg_files: List[str], mvc_file: str, lowcut: float = 10.0,
                        highcut: float = 500.0, smooth_sigma_ms: float = 50.0
                        ) -> Tuple[np.ndarray, float, float]:
    """
    Process a complete EMG session: load files, preprocess, and normalize to %MVC.

    :param emg_files: List of paths to OpenSignals files for this session.
    :param mvc_file: Path to the MVC recording file for normalization.
    :param lowcut: Lower bandpass cutoff in Hz.
    :param highcut: Upper bandpass cutoff in Hz.
    :param smooth_sigma_ms: Smoothing sigma in milliseconds.
    :return: Tuple of (percent_mvc_signal, sampling_rate, mvc_peak_value).
    """
    envelopes = []
    fs_session = None

    # Process each EMG file in the session
    for file_path in emg_files:
        df, _, fs = load_opensignals_txt(file_path)
        emg_mv = transfer_emg(load_emg_channel(df))
        envelope = preprocess_emg(emg_mv, fs, lowcut=lowcut, highcut=highcut,
                                  smooth_sigma_ms=smooth_sigma_ms)
        envelopes.append(envelope)

        if fs_session is None:
            fs_session = fs
        elif not np.isclose(fs_session, fs):
            print(f"[process_emg_session] Warning: Sampling rate mismatch in {file_path}")

    if not envelopes:
        raise ValueError("No EMG files provided for session processing")

    # Concatenate all envelopes from the session
    session_envelope = np.concatenate(envelopes)

    # Process MVC file
    df_mvc, _, fs_mvc = load_opensignals_txt(mvc_file)
    mvc_mv = transfer_emg(load_emg_channel(df_mvc))
    mvc_envelope = preprocess_emg(mvc_mv, fs_mvc, lowcut=lowcut, highcut=highcut,
                                  smooth_sigma_ms=smooth_sigma_ms)
    mvc_peak = float(np.max(mvc_envelope))

    if mvc_peak <= 0:
        raise ValueError(f"MVC peak is non-positive for file {mvc_file}")

    if fs_session is None:
        fs_session = fs_mvc

    # Normalize to %MVC
    percent_signal = (session_envelope / mvc_peak) * 100.0

    return percent_signal, fs_session, mvc_peak
