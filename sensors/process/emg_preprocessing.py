"""
EMG Signal Preprocessing Functions

This module contains functions for preprocessing raw EMG signals:
- Loading OpenSignals .txt files
- Applying transfer function (raw ADC → millivolts)
- Bandpass filtering
- Rectification
- Smoothing (envelope extraction)
"""
# external imports
import json
from pathlib import Path
from typing import Tuple, List
import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d
from scipy.signal import butter, filtfilt

# internal imports
from sensors.emg_pipeline import PreprocessConfig


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


# -------------------------------------------------------------------------------------------------------------------- #
# Signal Processing Functions
# -------------------------------------------------------------------------------------------------------------------- #
def _compute_envelope(
    df: pd.DataFrame,
    config: PreprocessConfig,
    return_raw: bool = False,
    return_raw_adc: bool = False,
) -> np.ndarray | tuple[np.ndarray, np.ndarray] | tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Transform a raw session dataframe into an EMG envelope (and optionally raw signal).

    :param df: DataFrame that still contains nSeq + EMG (and possibly ACC) columns.
    :param config: Frequency-domain configuration shared across sessions.
    :param return_raw: When ``True`` also returns the unfiltered EMG trace for plotting.
    :param return_raw_adc: When ``True`` also returns raw ADC values for saturation checks.
    :returns: Envelope-only array, ``(envelope, raw_mv)`` tuple when ``return_raw`` is set,
              or ``(envelope, raw_mv, raw_adc)`` when both flags are set.
    """

    if return_raw_adc:
        emg_mv, raw_adc = _extract_emg_mv(df, return_raw_adc=True)
    else:
        emg_mv = _extract_emg_mv(df)
        raw_adc = None
    
    envelope = preprocess_emg(emg_mv, config["fs"], config["lowcut"], config["highcut"], config["smooth_sigma_ms"]) 
    
    if return_raw and return_raw_adc:
        return envelope, emg_mv, raw_adc
    if return_raw:
        return envelope, emg_mv
    return envelope


def _extract_emg_mv(df: pd.DataFrame, return_raw_adc: bool = False) -> np.ndarray | tuple[np.ndarray, np.ndarray]:
    """Locate the EMG column, convert it to millivolts, and guard against empty recordings.

    :param df: Session dataframe containing EMG plus optional auxiliary channels.
    :param return_raw_adc: When True, also returns raw ADC values for saturation checks.
    :returns: One-dimensional NumPy array with values expressed in millivolts,
              or tuple (emg_mv, raw_adc) if return_raw_adc is True.
    """

    emg_cols = [col for col in df.columns if "emg" in str(col).lower()]
    target_col = None
    if emg_cols:
        target_col = emg_cols[0]
    elif len(df.columns) > 1:
        target_col = df.columns[1]
    else:
        raise ValueError("No EMG column available")

    raw_values = df[target_col].to_numpy()
    if raw_values.size == 0:
        raise ValueError("Empty EMG column")
    
    emg_mv = _to_millivolts(raw_values)
    if return_raw_adc:
        return emg_mv, raw_values
    return emg_mv


def _to_millivolts(raw_values: np.ndarray) -> np.ndarray:
    """Convert EMG samples to millivolts, respecting files that are already scaled.

    :param raw_values: EMG samples straight from disk (could be ints or floats, scaled or not).
    :returns: Array of EMG values in millivolts.
    """

    arr = np.asarray(raw_values)

    # Raw OpenSignals files store EMG as unsigned integers; StudioData MVC files are floats in mV already.
    if np.issubdtype(arr.dtype, np.integer):
        return transfer_emg(arr.astype(float))

    arr = arr.astype(float)
    finite = arr[np.isfinite(arr)]
    max_abs = float(np.max(np.abs(finite))) if finite.size else 0.0

    # Values below ~10 mV typically indicate that the file is already calibrated; avoid double-scaling.
    if max_abs <= 10.0:
        return arr

    return transfer_emg(arr)

def transfer_emg(raw_emg: np.ndarray) -> np.ndarray:
    """
    Convert raw 16-bit EMG samples to millivolts using the muscleBAN transfer function.

    MuscleBAN-specific formula: ((ADC / (2^16 - 1)) - 0.5) * VCC / Gain
    For muscleBAN EMG sensor: VCC = 2500 mV, Gain = 1100, n = 16 bits

    :param raw_emg: Array of raw ADC values.
    :return: Array of EMG values in millivolts.
    """
    return (((raw_emg / (2 ** 16 - 1.0)) - 0.5) * 2500) / 1100


def compute_mvc_peak_rms(
    emg_mv: np.ndarray,
    fs: float,
    lowcut: float = 10.0,
    highcut: float = 500.0,
    window_ms: float = 250.0,
) -> float:
    """Compute MVC peak using peak-centered RMS on bandpass-filtered, rectified signal.

    This method:
    1. Bandpass filters the raw EMG (no smoothing)
    2. Rectifies (absolute value)
    3. Finds the peak location
    4. Computes RMS in a window centered on the peak

    This provides a robust MVC estimate that:
    - Preserves peak amplitude (no smoothing attenuation)
    - Resists noise spikes (RMS averaging)

    :param emg_mv: Raw EMG signal in millivolts.
    :param fs: Sampling frequency in Hz.
    :param lowcut: Lower bandpass cutoff in Hz.
    :param highcut: Upper bandpass cutoff in Hz.
    :param window_ms: RMS window duration in milliseconds (centered on peak).
    :returns: MVC peak value in millivolts (RMS of peak window).
    """
    # Step 1: Bandpass filter (no smoothing)
    emg_dc = emg_mv - np.mean(emg_mv)
    emg_filt = bandpass_filter(emg_dc, fs, lowcut=lowcut, highcut=highcut)

    # Step 2: Rectify
    emg_rect = np.abs(emg_filt)

    # Step 3: Find peak location
    peak_idx = int(np.argmax(emg_rect))

    # Step 4: Compute RMS in window centered on peak
    half_window = int((window_ms / 1000.0) * fs / 2)
    start = max(0, peak_idx - half_window)
    end = min(len(emg_rect), peak_idx + half_window)
    window_data = emg_rect[start:end]

    if len(window_data) == 0:
        return float(np.max(emg_rect))  # Fallback to max if window is empty

    mvc_peak = float(np.sqrt(np.mean(window_data ** 2)))
    return mvc_peak


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

def tkeo(x: np.ndarray, rectify: bool = True) -> np.ndarray:
    """Teager-Kaiser Energy Operator.
    
    Computes instantaneous energy: Ψ[n] = x[n]² - x[n-1]·x[n+1]
    
    Note: The discrete TKEO can produce negative values for real signals.
    Clamping to zero is a pragmatic rectification step commonly applied
    for EMG onset detection, but is not a mathematical property of TKEO.
    
    Reference: Solnik et al. (2008) "Teager-Kaiser Operator improves the
    accuracy of EMG onset detection independent of signal-to-noise ratio"
    
    :param x: Input signal (typically bandpass-filtered EMG).
    :param rectify: If True, clamp negative values to 0 (default for EMG).
    :returns: TKEO energy signal.
    """
    x = np.asarray(x, dtype=float)
    n = len(x)
    psi = np.zeros_like(x)
    if n >= 3:
        psi[1:-1] = x[1:-1]**2 - x[:-2] * x[2:]
        if rectify:
            psi[psi < 0] = 0.0
    return psi


def compute_tkeo_envelope(
    emg_filt: np.ndarray, 
    fs: float, 
    smooth_cutoff_hz: float = 50.0,
) -> np.ndarray:
    """Compute TKEO energy envelope from already-filtered EMG.
    
    Pipeline: TKEO → 6th-order low-pass smoothing
    
    This follows Solnik et al. (2008) Conditioning 2, but expects the input
    to already be bandpass-filtered (their Step 2). Do not call bandpass_filter
    again if your signal is already filtered.
    
    Note: The paper used a 50 Hz low-pass for smoothing the TKEO output,
    which is different from Gaussian smoothing with σ=50ms.
    
    :param emg_filt: Bandpass-filtered EMG signal (NOT raw, NOT envelope).
    :param fs: Sampling frequency in Hz.
    :param smooth_cutoff_hz: Low-pass cutoff for smoothing TKEO output (default 50 Hz).
    :returns: Smoothed TKEO energy envelope.
    """
    # Apply TKEO to filtered signal
    energy = tkeo(emg_filt, rectify=True)
    
    # Low-pass smoothing (6th order as per paper)
    nyq = 0.5 * fs
    cutoff_norm = min(smooth_cutoff_hz / nyq, 0.99)  # Guard against edge cases
    b, a = butter(6, cutoff_norm, btype='low')
    envelope = filtfilt(b, a, energy)
    
    return envelope
