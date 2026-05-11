"""
EMG Signal Quality Assessment Functions.

This module provides quality assessment checks for EMG signals at different
processing stages. Functions are designed to detect:
- Defective sensors (faulty mBAN)
- ADC saturation/clipping
- Powerline interference (50 Hz)
- Hardware artifacts (20, 200, 400 Hz noise)

The checks return quality issue dictionaries compatible with the data_quality module.

References:
- Adapted from prevOccupAI_EMG_analysis noise_detection.py
- Veiersted et al. (2013) for EMG quality standards
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

import numpy as np
from scipy import signal as sp_signal

from constants import FS_MBAN


if TYPE_CHECKING:
    import matplotlib.figure


# Type alias for quality issue (avoid circular import with data_quality)
QualityIssue = Dict[str, str]  # {"code": str, "message": str}


def _create_quality_issue(code: str, message: str) -> QualityIssue:
    """Create a quality issue dict (local version to avoid circular import)."""
    return {"code": code, "message": message}


# -------------------------------------------------------------------------------------------------------------------- #
# Constants - ADC and Hardware Limits
# -------------------------------------------------------------------------------------------------------------------- #
# MuscleBAN uses 16-bit ADC (0 to 65535)
ADC_MIN = 0
ADC_MAX = 65520  # Practical max (65535 - margin for noise)
ADC_SATURATION_THRESHOLD = 0.01  # 1% of samples at limits = saturation

# -------------------------------------------------------------------------------------------------------------------- #
# Constants - PSD Noise Detection (hardcoded from experimental tuning)
# -------------------------------------------------------------------------------------------------------------------- #
# Target noise frequencies
PEAK_20_HZ = 20
PEAK_50_HZ = 50
PEAK_200_HZ = 200
PEAK_400_HZ = 400

# Peak detection parameters
PEAK_PROMINENCE_LOW_FREQ = 0.1    # For 20/50 Hz peaks (10% of normalized PSD)
PEAK_PROMINENCE_HIGH_FREQ = 0.05  # For 200/400 Hz peaks (5% of normalized PSD)
FREQ_TOLERANCE_LOW = 4.0          # Hz tolerance for 20/50 Hz matching
FREQ_TOLERANCE_HIGH = 10.0        # Hz tolerance for 200/400 Hz matching

# Minimum normalized power at 200 Hz to flag as hardware noise
# Based on empirical analysis: 0.30 threshold gives ~50 exclusions
# 0.20 was still too aggressive (105 exclusions, 52% borderline)
MIN_200HZ_POWER_FOR_NOISE = 0.30

# Area-under-PSD thresholds (0-180 Hz, normalized PSD)
AREA_MIN = 45.0          # Below = poor signal quality
AREA_MAX = 115.0         # Above = unusual power concentration
AREA_CRITICAL = 20.0     # Below with 50 Hz peak = definitely discard

# Peak width threshold (narrow peak = interference, not muscle activity)
# Using 4x freq_res to account for Welch PSD frequency resolution smoothing
PEAK_WIDTH_FACTOR = 4.0  # Peak width < 4 * freq_resolution = too narrow


# -------------------------------------------------------------------------------------------------------------------- #
# Raw ADC Checks (before any processing)
# -------------------------------------------------------------------------------------------------------------------- #
def detect_adc_saturation(
    raw_adc: np.ndarray,
    saturation_threshold: float = ADC_SATURATION_THRESHOLD,
) -> Optional[QualityIssue]:
    """
    Detect ADC saturation/clipping in raw EMG signal.
    
    Saturation occurs when the signal hits the ADC limits (0 or 65520),
    indicating either electrode issues or excessive signal amplitude.
    
    :param raw_adc: Raw ADC values (16-bit integers before mV conversion).
    :param saturation_threshold: Fraction of samples at limits to flag (default 1%).
    :returns: QualityIssue if saturation detected, None otherwise.
    """
    arr = np.asarray(raw_adc).flatten()
    if arr.size == 0:
        return None
    
    # Count samples at ADC limits
    at_min = np.sum(arr <= ADC_MIN + 10)  # Small margin for noise
    at_max = np.sum(arr >= ADC_MAX - 10)
    total_clipped = at_min + at_max
    clip_ratio = total_clipped / arr.size
    
    if clip_ratio > saturation_threshold:
        return _create_quality_issue(
            "adc-saturation",
            f"{clip_ratio:.1%} of samples at ADC limits (clipping detected). "
            f"Low: {at_min}, High: {at_max}"
        )
    return None


# -------------------------------------------------------------------------------------------------------------------- #
# Post-Transfer Checks (after mV conversion, before filtering)
# -------------------------------------------------------------------------------------------------------------------- #
def is_faulty_mban(emg_mv: np.ndarray) -> Optional[QualityIssue]:
    """
    Check if muscleBAN sensor was defective.
    
    Some muscleBANs produce signals where ALL values are either positive
    or negative, which is uncharacteristic for bipolar EMG recordings.
    This indicates a hardware defect.
    
    :param emg_mv: EMG signal in millivolts (after transfer function).
    :returns: QualityIssue if sensor is faulty, None otherwise.
    """
    arr = np.asarray(emg_mv).flatten()
    if arr.size == 0:
        return None
    
    # Check if ALL values have the same sign
    all_positive = np.all(arr > 0)
    all_negative = np.all(arr < 0)
    
    if all_positive or all_negative:
        sign = "positive" if all_positive else "negative"
        return _create_quality_issue(
            "faulty-mban",
            f"Defective sensor: all EMG values are {sign} (bipolar signal expected)"
        )
    return None


# -------------------------------------------------------------------------------------------------------------------- #
# Post-Filter Checks (after bandpass filtering)
# -------------------------------------------------------------------------------------------------------------------- #
def detect_psd_noise(
    emg_filtered: np.ndarray,
    fs: float = FS_MBAN,
) -> Tuple[bool, List[QualityIssue]]:
    """
    Detect noise contamination using Power Spectral Density analysis.
    
    Checks for:
    - 20 Hz noise (often with 50 Hz, unknown cause)
    - 50 Hz powerline interference (electrode contact loss)
    - 200/400 Hz peaks (hardware artifacts)
    
    The signal is classified as noisy (should be discarded) if:
    - 20 Hz peak detected (with or without 50 Hz)
    - 50 Hz peak with very low PSD area (< 20)
    - 200/400 Hz peaks with PSD area outside normal range
    
    :param emg_filtered: Bandpass-filtered EMG signal.
    :param fs: Sampling frequency in Hz.
    :returns: Tuple of (is_noisy, list of QualityIssue).
              is_noisy=True means signal should be discarded.
    """
    issues: List[QualityIssue] = []
    
    arr = np.asarray(emg_filtered).flatten()
    if arr.size < 1024:  # Need sufficient samples for PSD
        return False, issues
    
    # Compute PSD using Welch's method
    psd_freqs, psd = sp_signal.welch(arr, fs=fs, nperseg=min(1024, len(arr)))
    
    if psd.max() == 0:
        return False, issues
    
    # Normalize PSD for consistent threshold application
    psd_norm = psd / np.max(psd)
    
    # Check for 20/50 Hz noise
    is_noisy_20_50, issue_20_50 = _check_20_50hz_noise(psd_freqs, psd_norm)
    if issue_20_50:
        issues.append(issue_20_50)
    
    if is_noisy_20_50:
        return True, issues
    
    # Check for 200/400 Hz noise
    is_noisy_200_400, issue_200_400 = _check_200_400hz_noise(psd_freqs, psd_norm)
    if issue_200_400:
        issues.append(issue_200_400)
    
    return is_noisy_200_400, issues


def _check_20_50hz_noise(
    psd_freqs: np.ndarray,
    psd_norm: np.ndarray,
) -> Tuple[bool, Optional[QualityIssue]]:
    """
    Check for 20 Hz and/or 50 Hz noise in the PSD.
    
    :returns: Tuple of (is_noisy, QualityIssue or None).
    """
    # Threshold PSD to frequencies <= 180 Hz
    mask = psd_freqs <= 180
    freqs_low = psd_freqs[mask]
    psd_low = psd_norm[mask]
    
    if len(psd_low) < 10:
        return False, None
    
    # Find the two highest peaks
    peak_positions = _get_n_highest_peaks(psd_low, n=2, prominence=PEAK_PROMINENCE_LOW_FREQ)
    
    if len(peak_positions) == 0:
        return False, None
    
    peak_freqs = freqs_low[peak_positions]
    
    # Check if peaks are close to 20 Hz and/or 50 Hz
    is_close_20hz = any(math.isclose(f, PEAK_20_HZ, abs_tol=FREQ_TOLERANCE_LOW) for f in peak_freqs)
    is_close_50hz = any(math.isclose(f, PEAK_50_HZ, abs_tol=FREQ_TOLERANCE_LOW) for f in peak_freqs)
    
    # Case 1: Both 20 Hz and 50 Hz peaks → always noisy (characteristic pattern)
    if is_close_20hz and is_close_50hz:
        return True, _create_quality_issue(
            "psd-20-50hz-noise",
            "20 Hz and 50 Hz noise peaks detected (signal not recoverable)"
        )
    
    # Case 2: Only 20 Hz peak → be VERY conservative since single 20 Hz peaks occur in random noise
    # Only flag if 20 Hz peak has exceptionally high prominence (> 0.5) indicating true interference
    if is_close_20hz and not is_close_50hz:
        # Find the 20 Hz peak specifically and check its prominence
        peaks, props = sp_signal.find_peaks(psd_low, prominence=PEAK_PROMINENCE_LOW_FREQ)
        if len(peaks) > 0:
            peak_freqs_all = freqs_low[peaks]
            for i, f in enumerate(peak_freqs_all):
                if math.isclose(f, PEAK_20_HZ, abs_tol=FREQ_TOLERANCE_LOW):
                    # Require very high prominence (> 0.5) for single 20 Hz detection
                    # Random noise typically has prominences < 0.3
                    if props['prominences'][i] > 0.5:
                        return True, _create_quality_issue(
                            "psd-20hz-noise",
                            f"Strong 20 Hz noise peak detected (prominence={props['prominences'][i]:.2f})"
                        )
                    break
    
    # Case 3: Only 50 Hz peak → check PSD area to determine severity
    if is_close_50hz:
        area = _calc_psd_area(freqs_low, psd_low)
        freq_res = freqs_low[1] - freqs_low[0] if len(freqs_low) > 1 else 1.0
        
        # Find the 50 Hz peak and calculate its width
        idx_50hz = np.argmin(np.abs(peak_freqs - PEAK_50_HZ))
        peak_width = _calc_peak_width(psd_low, peak_positions[idx_50hz], freq_res)
        
        # Narrow peak + low area → severe powerline interference
        if peak_width < PEAK_WIDTH_FACTOR * freq_res and area < AREA_CRITICAL:
            return True, _create_quality_issue(
                "psd-50hz-noise",
                f"50 Hz powerline noise with low signal content (area={area:.1f} < {AREA_CRITICAL})"
            )
        
        # 50 Hz detected but signal may still be usable - just warn
        if peak_width < PEAK_WIDTH_FACTOR * freq_res:
            return False, _create_quality_issue(
                "psd-50hz-warning",
                f"50 Hz peak detected but signal content acceptable (area={area:.1f})"
            )
    
    return False, None


def _check_200_400hz_noise(
    psd_freqs: np.ndarray,
    psd_norm: np.ndarray,
) -> Tuple[bool, Optional[QualityIssue]]:
    """
    Check for 200 Hz and/or 400 Hz noise in the PSD.
    
    This hardware artifact typically produces BOTH 200 Hz and 400 Hz peaks.
    To avoid false positives from random noise, we require:
    - BOTH 200 Hz AND 400 Hz peaks for definitive noise detection
    - Single peak only generates warning if area is also anomalous
    
    :returns: Tuple of (is_noisy, QualityIssue or None).
    """
    # Threshold PSD to frequencies > 180 Hz
    mask = psd_freqs > 180
    freqs_high = psd_freqs[mask]
    psd_high = psd_norm[mask]
    
    if len(psd_high) < 10:
        return False, None
    
    # Calculate minimum peak distance between 200 and 400 Hz
    freq_res = freqs_high[1] - freqs_high[0] if len(freqs_high) > 1 else 1.0
    min_peak_dist = max(1, int((PEAK_400_HZ - PEAK_200_HZ) / freq_res / 2))
    
    # Find peaks
    peak_positions = _get_n_highest_peaks(
        psd_high, n=2, 
        prominence=PEAK_PROMINENCE_HIGH_FREQ,
        min_distance=min_peak_dist
    )
    
    if len(peak_positions) == 0:
        return False, None
    
    peak_freqs = freqs_high[peak_positions]
    
    # Check if peaks are close to 200 Hz and/or 400 Hz
    is_close_200hz = any(math.isclose(f, PEAK_200_HZ, abs_tol=FREQ_TOLERANCE_HIGH) for f in peak_freqs)
    is_close_400hz = any(math.isclose(f, PEAK_400_HZ, abs_tol=FREQ_TOLERANCE_HIGH) for f in peak_freqs)
    
    if not (is_close_200hz or is_close_400hz):
        return False, None
    
    # Get actual normalized power at 200 Hz (not just peak detection)
    idx_200 = np.argmin(np.abs(psd_freqs - PEAK_200_HZ))
    power_200hz = psd_norm[idx_200]
    
    # Calculate area under PSD (0-180 Hz) for signal quality assessment
    mask_low = psd_freqs <= 180
    area = _calc_psd_area(psd_freqs[mask_low], psd_norm[mask_low])
    
    # Area outside normal range
    area_out_of_range = not (AREA_MIN <= area <= AREA_MAX)
    
    # BOTH 200 Hz AND 400 Hz → check if 200 Hz power is significant
    # Require MIN_200HZ_POWER_FOR_NOISE to avoid flagging borderline cases
    if is_close_200hz and is_close_400hz:
        if power_200hz < MIN_200HZ_POWER_FOR_NOISE:
            # Borderline case - warn but don't exclude
            return False, _create_quality_issue(
                "psd-200-400hz-warning",
                f"200/400 Hz peaks detected but weak (200Hz power={power_200hz:.2f} < {MIN_200HZ_POWER_FOR_NOISE})"
            )
        return True, _create_quality_issue(
            "psd-200-400hz-noise",
            f"200 Hz and 400 Hz hardware noise detected (200Hz power={power_200hz:.2f}, area={area:.1f})"
        )
    
    # Single peak only - warn if area is also anomalous
    detected = "200 Hz" if is_close_200hz else "400 Hz"
    if area_out_of_range:
        return False, _create_quality_issue(
            "psd-200-400hz-warning",
            f"{detected} peak with abnormal PSD area ({area:.1f}, expected {AREA_MIN}-{AREA_MAX})"
        )
    
    # Single peak with normal area - no issue (likely random noise)
    return False, None


# -------------------------------------------------------------------------------------------------------------------- #
# MVC-Specific Quality Checks
# -------------------------------------------------------------------------------------------------------------------- #
def assess_mvc_signal_quality(
    emg_mv: np.ndarray,
    fs: float = FS_MBAN,
    min_duration_s: float = 8.0,
    min_amplitude_mv: float = 0.05,
) -> List[QualityIssue]:
    """
    Assess quality of an MVC recording.
    
    Checks:
    - Minimum duration
    - Minimum amplitude (to detect very weak/failed MVCs)
    - Signal variance (flat signals)
    
    :param emg_mv: MVC signal in millivolts.
    :param fs: Sampling frequency in Hz.
    :param min_duration_s: Minimum required duration in seconds.
    :param min_amplitude_mv: Minimum peak amplitude in mV.
    :returns: List of QualityIssue (empty if all checks pass).
    """
    issues: List[QualityIssue] = []
    
    arr = np.asarray(emg_mv).flatten()
    duration_s = len(arr) / fs
    
    # Duration check
    if duration_s < min_duration_s:
        issues.append(_create_quality_issue(
            "mvc-too-short",
            f"MVC recording too short: {duration_s:.1f}s < {min_duration_s}s minimum"
        ))
    
    if arr.size == 0:
        return issues
    
    # Amplitude check
    max_amplitude = float(np.max(np.abs(arr)))
    if max_amplitude < min_amplitude_mv:
        issues.append(_create_quality_issue(
            "mvc-low-amplitude",
            f"MVC amplitude very low: {max_amplitude:.4f} mV < {min_amplitude_mv} mV minimum"
        ))
    
    # Variance check (flat signal)
    std_val = float(np.std(arr))
    if std_val < 1e-6:
        issues.append(_create_quality_issue(
            "mvc-flat-signal",
            "MVC signal has near-zero variance (flat/saturated)"
        ))
    
    return issues


# -------------------------------------------------------------------------------------------------------------------- #
# Helper Functions
# -------------------------------------------------------------------------------------------------------------------- #
def _get_n_highest_peaks(
    arr: np.ndarray,
    n: int,
    prominence: Optional[float] = None,
    min_distance: Optional[int] = None,
) -> np.ndarray:
    """
    Find the n highest peaks in an array.
    
    :param arr: Input array.
    :param n: Number of peaks to find.
    :param prominence: Minimum peak prominence (fraction of array max).
    :param min_distance: Minimum distance between peaks in samples.
    :returns: Array of peak indices (sorted by height, descending).
    """
    kwargs: Dict = {"height": (None, None)}
    if prominence is not None:
        kwargs["prominence"] = prominence
    if min_distance is not None:
        kwargs["distance"] = min_distance
    
    peaks, properties = sp_signal.find_peaks(arr, **kwargs)
    
    if len(peaks) == 0:
        return np.array([], dtype=int)
    
    # Sort by height (descending) and take top n
    heights = properties["peak_heights"]
    sorted_indices = np.argsort(heights)[::-1][:n]
    
    return peaks[sorted_indices]


def _calc_psd_area(freqs: np.ndarray, psd: np.ndarray) -> float:
    """
    Calculate area under the PSD curve using trapezoidal integration.
    
    :param freqs: Frequency array.
    :param psd: PSD values (normalized).
    :returns: Area under the curve.
    """
    if len(freqs) < 2:
        return 0.0
    return float(np.trapezoid(psd, freqs))


def _calc_peak_width(
    psd: np.ndarray,
    peak_idx: int,
    freq_res: float,
    rel_height: float = 0.1,
) -> float:
    """
    Calculate the width of a peak at a given relative height.
    
    :param psd: PSD array.
    :param peak_idx: Index of the peak.
    :param freq_res: Frequency resolution (Hz per sample).
    :param rel_height: Height fraction for width calculation (default: 90% of peak).
    :returns: Peak width in Hz.
    """
    try:
        widths = sp_signal.peak_widths(psd, [peak_idx], rel_height=1 - rel_height)
        return float(widths[0][0] * freq_res)
    except (IndexError, ValueError):
        return float("inf")  # Unable to calculate - assume wide peak


# -------------------------------------------------------------------------------------------------------------------- #
# Visualization Helpers for QA Assessment
# -------------------------------------------------------------------------------------------------------------------- #
def plot_psd_quality_assessment(
    emg_filtered: np.ndarray,
    fs: float = FS_MBAN,
    subject_id: str = "",
    side: str = "",
    session_label: str = "",
    save_path: Optional[str] = None,
    show: bool = False,
) -> Optional["matplotlib.figure.Figure"]:
    """
    Generate a diagnostic plot for PSD-based quality assessment.
    
    Creates a 2-panel figure showing:
    - Left: Time-domain signal (first 10 seconds)
    - Right: PSD with noise frequency markers and detection thresholds
    
    :param emg_filtered: Bandpass-filtered EMG signal.
    :param fs: Sampling frequency in Hz.
    :param subject_id: Subject identifier for title.
    :param side: Side (left/right) for title.
    :param session_label: Session label for title.
    :param save_path: If provided, save figure to this path (PNG format recommended).
    :param show: If True, display the figure interactively.
    :returns: matplotlib Figure object, or None if matplotlib unavailable.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    
    arr = np.asarray(emg_filtered).flatten()
    
    # Run detection to get results
    is_noisy, issues = detect_psd_noise(arr, fs)
    
    # Compute PSD
    freqs, psd = sp_signal.welch(arr, fs=fs, nperseg=min(4096, len(arr)))
    psd_norm = psd / psd.max() if psd.max() > 0 else psd
    
    # Get power at key frequencies
    idx_20 = np.argmin(np.abs(freqs - PEAK_20_HZ))
    idx_50 = np.argmin(np.abs(freqs - PEAK_50_HZ))
    idx_200 = np.argmin(np.abs(freqs - PEAK_200_HZ))
    idx_400 = np.argmin(np.abs(freqs - PEAK_400_HZ))
    
    power_20 = psd_norm[idx_20]
    power_50 = psd_norm[idx_50]
    power_200 = psd_norm[idx_200]
    power_400 = psd_norm[idx_400]
    
    # Calculate area (0-180 Hz)
    mask_low = freqs <= 180
    area = _calc_psd_area(freqs[mask_low], psd_norm[mask_low])
    
    # Create figure
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Determine status
    if is_noisy:
        status = "EXCLUDED"
        status_color = "red"
    elif issues:
        status = "WARNING"
        status_color = "orange"
    else:
        status = "CLEAN"
        status_color = "green"
    
    issue_text = issues[0]["message"] if issues else "No issues detected"
    
    # Title
    title = f"Subject {subject_id} - {side.upper()} - {session_label}"
    fig.suptitle(f"{title}  [{status}]", fontsize=14, fontweight="bold", color=status_color)
    
    # Left panel: Time domain
    ax1 = axes[0]
    display_samples = min(10 * int(fs), len(arr))  # Up to 10 seconds
    t = np.arange(display_samples) / fs
    ax1.plot(t, arr[:display_samples], "b-", linewidth=0.3, alpha=0.8)
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Amplitude (mV)")
    ax1.set_title("Time Domain (first 10s)")
    ax1.set_xlim(0, t[-1])
    
    # Add RMS annotation
    rms = np.sqrt(np.mean(arr**2))
    ax1.text(0.02, 0.98, f"RMS: {rms:.4f} mV", transform=ax1.transAxes,
             fontsize=10, verticalalignment="top", fontfamily="monospace",
             bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))
    
    # Right panel: PSD
    ax2 = axes[1]
    ax2.semilogy(freqs, psd_norm, "b-", linewidth=1, label="PSD")
    
    # Mark noise frequencies
    ax2.axvline(PEAK_20_HZ, color="purple", linestyle="--", alpha=0.6, label=f"20 Hz ({power_20:.3f})")
    ax2.axvline(PEAK_50_HZ, color="orange", linestyle="--", alpha=0.6, label=f"50 Hz ({power_50:.3f})")
    ax2.axvline(PEAK_200_HZ, color="red", linestyle="--", alpha=0.6, label=f"200 Hz ({power_200:.3f})")
    ax2.axvline(PEAK_400_HZ, color="darkred", linestyle="--", alpha=0.6, label=f"400 Hz ({power_400:.3f})")
    
    # Mark thresholds
    ax2.axhline(PEAK_PROMINENCE_LOW_FREQ, color="gray", linestyle=":", alpha=0.5, 
                label=f"Low-freq thresh ({PEAK_PROMINENCE_LOW_FREQ})")
    ax2.axhline(MIN_200HZ_POWER_FOR_NOISE, color="red", linestyle=":", alpha=0.5,
                label=f"200 Hz thresh ({MIN_200HZ_POWER_FOR_NOISE})")
    
    ax2.set_xlabel("Frequency (Hz)")
    ax2.set_ylabel("Normalized PSD")
    ax2.set_title(f"PSD Analysis | Area(0-180Hz): {area:.1f}")
    ax2.set_xlim(0, 500)
    ax2.set_ylim(1e-4, 1.5)
    ax2.legend(loc="upper right", fontsize=8)
    ax2.grid(True, alpha=0.3)
    
    # Add issue text box
    ax2.text(0.02, 0.02, issue_text, transform=ax2.transAxes,
             fontsize=9, verticalalignment="bottom", fontfamily="monospace",
             bbox=dict(boxstyle="round", facecolor="lightyellow" if not is_noisy else "lightcoral", alpha=0.8))
    
    plt.tight_layout()
    
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
    
    if show:
        plt.show()
    else:
        plt.close(fig)
    
    return fig


def save_quality_assessment_plot(
    emg_filtered: np.ndarray,
    output_dir: str,
    subject_id: str,
    side: str,
    session_label: str,
    acquisition_type: str = "session",
    fs: float = FS_MBAN,
) -> Optional[str]:
    """
    Convenience function to save a quality assessment plot with standardized naming.
    
    :param emg_filtered: Bandpass-filtered EMG signal.
    :param output_dir: Directory to save the plot.
    :param subject_id: Subject identifier.
    :param side: Side (left/right).
    :param session_label: Session label or time.
    :param acquisition_type: Type of acquisition ('mvc' or 'session').
    :param fs: Sampling frequency in Hz.
    :returns: Path to saved file, or None if failed.
    """
    from pathlib import Path
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Standardized filename
    safe_session = session_label.replace(":", "-").replace("/", "-")
    filename = f"qa_{subject_id}_{side}_{acquisition_type}_{safe_session}.png"
    save_path = output_path / filename
    
    try:
        plot_psd_quality_assessment(
            emg_filtered=emg_filtered,
            fs=fs,
            subject_id=subject_id,
            side=side,
            session_label=session_label,
            save_path=str(save_path),
            show=False,
        )
        return str(save_path)
    except Exception as e:
        print(f"[QA Plot] Failed to save {filename}: {e}")
        return None


# -------------------------------------------------------------------------------------------------------------------- #
# ADC Saturation Visualization
# -------------------------------------------------------------------------------------------------------------------- #
def plot_adc_saturation_assessment(
    raw_adc: np.ndarray,
    fs: float = FS_MBAN,
    subject_id: str = "unknown",
    side: str = "unknown",
    session_label: str = "unknown",
    save_path: Optional[str] = None,
    show: bool = True,
) -> Optional["matplotlib.figure.Figure"]:
    """
    Create diagnostic visualization for ADC saturation/clipping detection.
    
    Shows:
    - Time domain signal with clipped regions highlighted
    - Histogram of ADC values with limits marked
    - Summary statistics
    
    :param raw_adc: Raw ADC values (16-bit integers).
    :param fs: Sampling frequency in Hz.
    :param subject_id: Subject identifier for title.
    :param side: Side (left/right) for title.
    :param session_label: Session label for title.
    :param save_path: If provided, save plot to this path.
    :param show: If True, display the plot.
    :returns: Matplotlib Figure object.
    """
    import matplotlib.pyplot as plt
    
    arr = np.asarray(raw_adc).flatten()
    
    # Run detection to get results
    saturation_issue = detect_adc_saturation(arr)
    
    # Count samples at ADC limits (with margin)
    at_min = arr <= ADC_MIN + 10
    at_max = arr >= ADC_MAX - 10
    total_clipped = np.sum(at_min) + np.sum(at_max)
    clip_ratio = total_clipped / arr.size if arr.size > 0 else 0
    
    # Create figure with 2 panels
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Determine status
    if saturation_issue:
        status = "EXCLUDED"
        status_color = "red"
        issue_text = saturation_issue["message"]
    else:
        status = "CLEAN"
        status_color = "green"
        issue_text = f"Clipping: {clip_ratio:.2%} (below {ADC_SATURATION_THRESHOLD:.0%} threshold)"
    
    # Title
    title = f"Subject {subject_id} - {side.upper()} - {session_label}"
    fig.suptitle(f"{title}  [ADC Saturation: {status}]", fontsize=14, fontweight="bold", color=status_color)
    
    # Left panel: Time domain with clipped regions
    ax1 = axes[0]
    display_samples = min(10 * int(fs), len(arr))  # Up to 10 seconds
    t = np.arange(display_samples) / fs
    signal_display = arr[:display_samples]
    
    ax1.plot(t, signal_display, "b-", linewidth=0.3, alpha=0.8, label="Signal")
    
    # Highlight clipped regions
    at_min_display = signal_display <= ADC_MIN + 10
    at_max_display = signal_display >= ADC_MAX - 10
    
    if np.any(at_min_display):
        ax1.scatter(t[at_min_display], signal_display[at_min_display], 
                   c="red", s=5, alpha=0.8, label=f"Low clip ({np.sum(at_min_display)})", zorder=5)
    if np.any(at_max_display):
        ax1.scatter(t[at_max_display], signal_display[at_max_display],
                   c="orange", s=5, alpha=0.8, label=f"High clip ({np.sum(at_max_display)})", zorder=5)
    
    # Draw ADC limits
    ax1.axhline(ADC_MIN, color="red", linestyle="--", alpha=0.5, label=f"ADC Min ({ADC_MIN})")
    ax1.axhline(ADC_MAX, color="orange", linestyle="--", alpha=0.5, label=f"ADC Max ({ADC_MAX})")
    
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("ADC Value")
    ax1.set_title("Time Domain (first 10s)")
    ax1.set_xlim(0, t[-1] if len(t) > 0 else 1)
    ax1.legend(loc="upper right", fontsize=8)
    
    # Add statistics annotation
    stats_text = (
        f"Total samples: {len(arr):,}\n"
        f"Clipped: {total_clipped:,} ({clip_ratio:.2%})\n"
        f"Min: {arr.min():.0f}, Max: {arr.max():.0f}"
    )
    ax1.text(0.02, 0.98, stats_text, transform=ax1.transAxes,
             fontsize=10, verticalalignment="top", fontfamily="monospace",
             bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))
    
    # Right panel: Histogram of ADC values
    ax2 = axes[1]
    
    # Create histogram with focus on the distribution
    n_bins = min(100, len(np.unique(arr)))
    hist_counts, hist_bins, _ = ax2.hist(arr, bins=n_bins, color="steelblue", alpha=0.7, edgecolor="white")
    
    # Mark ADC limits
    ax2.axvline(ADC_MIN, color="red", linestyle="--", linewidth=2, label=f"ADC Min ({ADC_MIN})")
    ax2.axvline(ADC_MAX, color="orange", linestyle="--", linewidth=2, label=f"ADC Max ({ADC_MAX})")
    
    # Mark threshold region near limits
    ax2.axvline(ADC_MIN + 10, color="red", linestyle=":", alpha=0.5)
    ax2.axvline(ADC_MAX - 10, color="orange", linestyle=":", alpha=0.5)
    
    ax2.set_xlabel("ADC Value")
    ax2.set_ylabel("Count")
    ax2.set_title(f"ADC Distribution | Threshold: {ADC_SATURATION_THRESHOLD:.0%}")
    ax2.legend(loc="upper right", fontsize=8)
    ax2.grid(True, alpha=0.3)
    
    # Add issue text box
    ax2.text(0.02, 0.98, issue_text, transform=ax2.transAxes,
             fontsize=9, verticalalignment="top", fontfamily="monospace",
             bbox=dict(boxstyle="round", facecolor="lightcoral" if saturation_issue else "lightgreen", alpha=0.8))
    
    plt.tight_layout()
    
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
    
    if show:
        plt.show()
    else:
        plt.close(fig)
    
    return fig


def save_adc_saturation_plot(
    raw_adc: np.ndarray,
    output_dir: str,
    subject_id: str,
    side: str,
    session_label: str,
    acquisition_type: str = "session",
    fs: float = FS_MBAN,
) -> Optional[str]:
    """
    Convenience function to save an ADC saturation assessment plot with standardized naming.
    
    :param raw_adc: Raw ADC values (16-bit integers).
    :param output_dir: Directory to save the plot.
    :param subject_id: Subject identifier.
    :param side: Side (left/right).
    :param session_label: Session label or time.
    :param acquisition_type: Type of acquisition ('mvc' or 'session').
    :param fs: Sampling frequency in Hz.
    :returns: Path to saved file, or None if failed.
    """
    from pathlib import Path
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Standardized filename
    safe_session = session_label.replace(":", "-").replace("/", "-")
    filename = f"qa_adc_{subject_id}_{side}_{acquisition_type}_{safe_session}.png"
    save_path = output_path / filename
    
    try:
        plot_adc_saturation_assessment(
            raw_adc=raw_adc,
            fs=fs,
            subject_id=subject_id,
            side=side,
            session_label=session_label,
            save_path=str(save_path),
            show=False,
        )
        return str(save_path)
    except Exception as e:
        print(f"[QA ADC Plot] Failed to save {filename}: {e}")
        return None
