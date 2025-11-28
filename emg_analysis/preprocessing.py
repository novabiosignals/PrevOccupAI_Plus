from __future__ import annotations

from pathlib import Path
from typing import Iterable, Tuple

import json
import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d
from scipy.signal import butter, filtfilt


def load_opensignals_txt(path: Path | str) -> tuple[pd.DataFrame, dict, float]:
    """Load an OpenSignals ``.txt`` file together with metadata and sampling rate."""

    path = Path(path)
    json_line = None
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if line.startswith("# {"):
                json_line = line[1:].strip()
                break
    if json_line is None:
        raise ValueError(f"Missing metadata header in {path}")

    meta_all = json.loads(json_line)
    dev_key = next(iter(meta_all.keys()))
    meta = meta_all[dev_key]
    columns = meta.get("column", [])
    fs_raw = meta.get("sampling rate")
    try:
        fs = float(fs_raw)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid sampling rate '{fs_raw}' in file {path}")

    emg_indices = [i for i, col in enumerate(columns) if "emg" in str(col).lower()]
    if not emg_indices:
        usecols = None
        selected_names = columns
    else:
        usecols = emg_indices
        selected_names = [columns[i] for i in emg_indices]

    df = pd.read_csv(
        path,
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


def transfer_emg(raw_emg: np.ndarray) -> np.ndarray:
    """Convert raw 16-bit samples to millivolts using the device transfer function."""

    return (((raw_emg / (2 ** (16 - 1.0))) - 0.5) * 2500) / 1100


def bandpass_filter(signal: np.ndarray, fs: float, lowcut: float = 10.0, highcut: float = 500.0, order: int = 4) -> np.ndarray:
    """Apply a Butterworth band-pass filter to the EMG signal."""

    nyquist = 0.5 * fs
    low = max(lowcut / nyquist, 0.001)
    high = min(highcut / nyquist, 0.999)
    b, a = butter(order, [low, high], btype="band")
    return filtfilt(b, a, signal)


def preprocess_emg(emg_mv: np.ndarray, fs: float, lowcut: float = 10.0, highcut: float = 500.0,
                   smooth_sigma_ms: float = 50.0) -> np.ndarray:
    """Full EMG preprocessing pipeline: de-mean, band-pass, rectify, smooth."""

    emg_dc = emg_mv - np.mean(emg_mv)
    emg_filt = bandpass_filter(emg_dc, fs, lowcut=lowcut, highcut=highcut)
    emg_rect = np.abs(emg_filt)
    sigma_samples = (smooth_sigma_ms / 1000.0) * fs
    return gaussian_filter1d(emg_rect, sigma=sigma_samples)


def load_emg_channel(df: pd.DataFrame) -> np.ndarray:
    """Extract the first EMG-related column from the dataframe."""

    for column in df.columns:
        column_name = str(column)
        if "emg" in column_name.lower():
            return df[column].to_numpy()
    # fall back to the second column (common for MVC files)
    return df.iloc[:, 1].to_numpy()


def process_session(emg_files: Iterable[Path | str], mvc_file: Path | str,
                    lowcut: float = 10.0, highcut: float = 500.0, smooth_sigma_ms: float = 50.0
                    ) -> Tuple[np.ndarray, float, float]:
    """Convert raw EMG session files to a percent-of-MVC envelope.

    :param emg_files: Iterable of OpenSignals files belonging to the same session.
    :param mvc_file: The MVC recording used for normalization.
    :return: Tuple containing (session_percent_signal, sampling_rate, mvc_peak_value).
    """

    envelopes: list[np.ndarray] = []
    fs_session: float | None = None

    for file_path in emg_files:
        df, _, fs = load_opensignals_txt(file_path)
        emg_mv = transfer_emg(load_emg_channel(df))
        envelopes.append(preprocess_emg(emg_mv, fs, lowcut=lowcut, highcut=highcut, smooth_sigma_ms=smooth_sigma_ms))
        fs_session = fs if fs_session is None else fs_session
        if fs_session is not None and not np.isclose(fs_session, fs):
            print(f"[process_session] Sampling rate mismatch in {file_path}: {fs} vs {fs_session}")

    if not envelopes:
        raise ValueError("No EMG files provided for session processing")

    session_envelope = np.concatenate(envelopes)

    df_mvc, _, fs_mvc = load_opensignals_txt(mvc_file)
    mvc_mv = transfer_emg(load_emg_channel(df_mvc))
    mvc_envelope = preprocess_emg(mvc_mv, fs_mvc, lowcut=lowcut, highcut=highcut, smooth_sigma_ms=smooth_sigma_ms)
    mvc_peak = float(np.max(mvc_envelope))
    if mvc_peak <= 0:
        raise ValueError(f"MVC peak is non-positive for file {mvc_file}")

    if fs_session is None:
        fs_session = fs_mvc

    percent_signal = (session_envelope / mvc_peak) * 100.0
    return percent_signal, fs_session, mvc_peak
