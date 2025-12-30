"""MVC (Maximum Voluntary Contraction) detection and validation utilities.

This module handles:
- Detection of MVC segments based on amplitude thresholding
- TKEO-enhanced segment detection with baseline statistics
- Picking MVC acquisitions from session data

These functions are re-exported for use by emg_pipeline.py and can be
imported directly for standalone MVC processing tasks.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from signal_processing.emg_preprocessing import bandpass_filter, compute_tkeo_envelope, tkeo

import numpy as np
import pandas as pd


# -------------------------------------------------------------------------------------------------------------------- #
# Threshold Helpers
# -------------------------------------------------------------------------------------------------------------------- #

def _otsu_threshold(data: np.ndarray) -> float:
    """Compute Otsu's threshold for bimodal separation.
    
    Finds the threshold that minimizes intra-class variance (equivalently,
    maximizes inter-class variance) assuming two classes (rest vs. active).
    
    :param data: 1D array of values (typically log-energy).
    :returns: Optimal threshold value.
    """
    data_flat = data.flatten()
    
    # Build histogram
    hist, bin_edges = np.histogram(data_flat, bins=256)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2 # output array of shape (256,) with bin centers
    
    # Total statistics
    total = hist.sum()
    if total == 0:
        return float(np.median(data_flat))
    
    sum_total = np.dot(hist, bin_centers) # weighted sum of all bins
    
    # Iterate to find optimal threshold
    sum_bg = 0.0
    weight_bg = 0
    var_max = 0.0
    threshold = bin_centers[0] # default to lowest bin center
    
    for i in range(256):
        weight_bg += hist[i]
        if weight_bg == 0:
            continue
        
        weight_fg = total - weight_bg
        if weight_fg == 0:
            break
        
        sum_bg += bin_centers[i] * hist[i]
        mean_bg = sum_bg / weight_bg
        mean_fg = (sum_total - sum_bg) / weight_fg
        
        # Inter-class variance
        var_between = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
        
        if var_between > var_max:
            var_max = var_between
            threshold = bin_centers[i]
    
    return float(threshold)

# -------------------------------------------------------------------------------------------------------------------- #
# MVC Segment Detection Helpers
# -------------------------------------------------------------------------------------------------------------------- #

def _robust_sigma(
    x: np.ndarray, 
    p10: Optional[float] = None, 
    p90: Optional[float] = None,
    baseline_iqr: Optional[float] = None,
) -> float:
    """Compute a robust scale estimate using MAD (scaled to match std for Gaussian).
    
    Uses adaptive minimum sigma based on signal dynamic range and baseline IQR
    to handle zero-inflated baselines (common after TKEO rectification).
    
    :param x: Input array (typically baseline window of log-energy).
    :param p10: 10th percentile of full signal (for adaptive min). If None, computed from x.
    :param p90: 90th percentile of full signal (for adaptive min). If None, computed from x.
    :param baseline_iqr: IQR of baseline window. If provided, used in min_sigma calculation.
    :returns: Robust sigma estimate with adaptive minimum guard.
    """
    med = float(np.median(x))
    mad = float(np.median(np.abs(x - med)))
    sigma = 1.4826 * mad # Scale MAD to match std for normal distribution
    
    # Compute adaptive minimum: 5% of signal dynamic range, with absolute floor
    if p10 is None:
        p10 = float(np.percentile(x, 10))
    if p90 is None:
        p90 = float(np.percentile(x, 90))
    
    # min_sigma = max(5% of dynamic range, 10% of baseline IQR, absolute floor)
    adaptive_min = 0.05 * (p90 - p10)  # 5% of dynamic range
    iqr_term = 0.1 * baseline_iqr if baseline_iqr is not None else 0.0
    min_sigma = max(adaptive_min, iqr_term, 0.02)  # Absolute floor of 0.02 in log-space
    
    # Guard against sigma ≈ 0 (can happen with zero-inflated TKEO baselines)
    if sigma < min_sigma:
        # Fall back to IQR-based estimate
        q75 = float(np.percentile(x, 75))
        q25 = float(np.percentile(x, 25))
        iqr_sigma = (q75 - q25) / 1.349  # IQR scaled to sigma for normal
        sigma = max(iqr_sigma, min_sigma)
    
    return sigma


def _select_quiet_baseline(
    signal: np.ndarray,
    fs: float,
    window_s: float = 0.5,
    search_s: Optional[float] = None,
    exclude_edges: int = 0,
    linear_energy: Optional[np.ndarray] = None,
    iqr_floor_ratio: float = 0.01,
) -> Tuple[np.ndarray, int]:
    """Pick the quietest window (by lowest median value) within the signal.
    
    For log-energy signals, lower values = less energy = rest.
    Finds the window with the lowest median to identify rest periods.
    
    Includes dropout detection: if linear_energy is provided, checks IQR in
    linear space (more sensitive to dropouts than log-space variance).
    
    :param signal: 1D signal array (typically log-energy where lower = quieter).
    :param fs: Sampling frequency in Hz.
    :param window_s: Window size in seconds for baseline estimation.
    :param search_s: Search horizon in seconds. If None, searches entire signal.
    :param exclude_edges: Number of samples to exclude from start/end (for padded signals).
    :param linear_energy: Optional linear energy array (before log transform) for dropout detection.
    :param iqr_floor_ratio: IQR floor as fraction of full-signal IQR; windows below are dropouts.
    :returns: Tuple of (quietest window array, start index of that window).
    """

    if signal.size == 0:
        return signal, 0

    window = max(1, int(window_s * fs))  # window size in samples
    
    # Determine search range, excluding edges if specified
    start_search = exclude_edges
    if search_s is None:
        end_search = signal.size - exclude_edges
    else:
        end_search = min(signal.size - exclude_edges, int(search_s * fs))
    
    # Ensure valid search range
    if end_search - start_search <= window:
        # Not enough data, return what we can
        return signal[start_search:start_search + window], start_search

    # Compute IQR floor for dropout detection (in linear space if available)
    if linear_energy is not None and linear_energy.size > 0:
        full_iqr = float(np.percentile(linear_energy, 75) - np.percentile(linear_energy, 25))
        iqr_floor = iqr_floor_ratio * full_iqr # 1% of full IQR
        use_linear_check = True
    else:
        iqr_floor = 0.0
        use_linear_check = False
    
    # Collect all candidate windows with their scores and IQR metrics
    candidates: List[Tuple[float, float, int]] = []  # (median_score, iqr_metric, start_idx)
    
    # Slide with 25% overlap for efficiency
    for start in range(start_search, end_search - window + 1, max(1, window // 4)):
        window_view = signal[start : start + window]
        score = float(np.median(window_view))
        
        # Compute IQR for dropout detection
        if use_linear_check and linear_energy is not None:
            lin_window = linear_energy[start : start + window]
            iqr_metric = float(np.percentile(lin_window, 75) - np.percentile(lin_window, 25))
        else:
            # Fallback to log-space variance if linear not provided
            iqr_metric = float(np.var(window_view))
        
        candidates.append((score, iqr_metric, start))
    
    # Sort by score (lowest median = quietest)
    candidates.sort(key=lambda x: x[0])
    
    # Pick the quietest window that passes the dropout check
    for score, iqr_metric, start in candidates:
        if use_linear_check:
            # IQR-based dropout check in linear space
            if iqr_metric >= iqr_floor:
                return signal[start : start + window], start
        else:
            # Fallback variance check
            if iqr_metric >= 1e-6:
                return signal[start : start + window], start
    
    # All windows failed dropout check - use the one with highest IQR as fallback
    # (least likely to be a true dropout)
    if candidates:
        candidates.sort(key=lambda x: x[1], reverse=True)  # Sort by IQR descending
        _, _, best_start = candidates[0]
        return signal[best_start : best_start + window], best_start
    
    # Shouldn't reach here, but fallback
    return signal[start_search:start_search + window], start_search


def _segments_from_binary(
    binary: np.ndarray,
    min_length_samples: int,
    persist_on: int,
    persist_off: int,
    gap_merge: int,
) -> List[tuple[int, int]]:
    """Convert a binary mask to merged segments with persistence and gap merge."""

    segments: List[tuple[int, int]] = []
    in_seg = False
    start = 0
    on_streak = 0
    off_streak = 0

    for idx, val in enumerate(binary):
        if not in_seg:
            if val:
                on_streak += 1
                if on_streak >= persist_on:
                    start = idx - persist_on + 1
                    in_seg = True
                    off_streak = 0
            else:
                on_streak = 0
        else:
            if val:
                off_streak = 0
            else:
                off_streak += 1
                if off_streak >= persist_off:
                    end = idx - persist_off + 1
                    segments.append((start, end))
                    in_seg = False
                    on_streak = 0

    if in_seg:
        segments.append((start, len(binary)))

    # Merge short gaps
    merged: List[tuple[int, int]] = []
    for seg in segments:
        if not merged:
            merged.append(seg)
            continue
        prev_start, prev_end = merged[-1]
        gap = seg[0] - prev_end
        if gap <= gap_merge:
            merged[-1] = (prev_start, seg[1])
        else:
            merged.append(seg)

    # Enforce minimum length
    return [(s, e) for (s, e) in merged if (e - s) >= min_length_samples]


def _score_segmentation(
    segments: List[Tuple[int, int]],
    fs: float,
    baseline_start: int,
    baseline_end: int,
    padded_start: int,
    padded_end: int,
    signal_length: int,
    log_energy: Optional[np.ndarray] = None,
) -> float:
    """Score a segmentation result based on how well it matches MVC expectations.
    
    We want exactly 2 segments. If more are detected, we identify the top-2 by
    peak energy and score those specifically, penalizing extra segments.
    
    :param segments: List of (start, end) segment tuples.
    :param fs: Sampling frequency.
    :param baseline_start: Start index of the detected baseline window.
    :param baseline_end: End index of the detected baseline window.
    :param padded_start: Number of padded samples at start.
    :param padded_end: Index where padding starts at end.
    :param signal_length: Total signal length.
    :param log_energy: Optional log-energy array for ranking segments by peak energy.
    :returns: Score (higher is better).
    """
    n_segs = len(segments)
    
    # Base score based on segment count
    # Guardrail requires n_segs >= 2, so passing cases must always beat failing cases
    if n_segs >= 2:
        # PASSING cases (aligned with guardrail)
        if n_segs == 2:
            score = 25.0  # Ideal - exactly what protocol expects
        elif n_segs == 3:
            score = 15.0  # Good - extra contraction but still valid
        else:  # 4+
            score = 10.0 - 2.0 * (n_segs - 4)  # Penalize fragmentation
    else:
        # FAILING cases (will be rejected by guardrail anyway)
        # These scores are only for diagnostics - picking "least bad" failure
        if n_segs == 1:
            score = -20.0  # Bad - missing one contraction
        else:  # 0
            score = -50.0  # Very bad - no detection at all
    
    if n_segs == 0:
        return score
    
    # =========================================================================
    # IDENTIFY TOP-2 SEGMENTS BY PEAK ENERGY
    # =========================================================================
    # If we have more than 2 segments, find the top-2 by peak energy
    # Score those specifically and penalize the extras
    if log_energy is not None and n_segs > 2:
        # Compute peak energy for each segment
        seg_peaks = []
        for start, end in segments:
            peak_energy = float(np.max(log_energy[start:end]))
            seg_peaks.append((peak_energy, start, end))
        
        # Sort by peak energy descending
        seg_peaks.sort(key=lambda x: x[0], reverse=True)
        
        # Top-2 segments (by energy)
        top_2 = [(s, e) for _, s, e in seg_peaks[:2]]
        extra_segs = [(s, e) for _, s, e in seg_peaks[2:]]
        
        # Penalty for extra segments (beyond top-2)
        score -= 3.0 * len(extra_segs)
    else:
        # Use all segments if 2 or fewer, or no energy array
        top_2 = segments[:2] if n_segs >= 2 else segments
        extra_segs = segments[2:] if n_segs > 2 else []
    
    # =========================================================================
    # SCORE TOP-2 SEGMENTS
    # =========================================================================
    # Duration scoring: MVC should be 1-3s. Penalize too long or too short.
    for start, end in top_2:
        duration_s = (end - start) / fs
        if 1.0 <= duration_s <= 3.0:
            score += 5.0  # Ideal duration
        elif 0.5 <= duration_s < 1.0:
            score += 2.0  # Acceptable (short)
        elif 3.0 < duration_s <= 5.0:
            score += 2.0  # Acceptable (long)
        elif 5.0 < duration_s <= 10.0:
            score -= 10.0  # Too long - likely merged segments
        elif duration_s > 10.0:
            # Severely penalize extremely long segments - proportional to duration
            # A 30s segment should be catastrophically penalized
            score -= 20.0 - 2.0 * (duration_s - 10.0)  # Gets worse with length
        # Very short segments (<0.5s) already filtered by min_length
    
    # Bonus if top-2 have significantly higher energy than baseline
    if log_energy is not None and len(top_2) >= 2:
        # Get peak energies for top-2
        top_2_peaks = [float(np.max(log_energy[s:e])) for s, e in top_2]
        avg_top_2_peak = np.mean(top_2_peaks)
        
        # Compare to baseline region
        baseline_level = float(np.median(log_energy[baseline_start:baseline_end]))
        contrast = avg_top_2_peak - baseline_level
        
        # Good contrast (>1 log unit = 10x energy) gets bonus
        if contrast > 1.5:
            score += 5.0  # Excellent contrast
        elif contrast > 1.0:
            score += 3.0  # Good contrast
        elif contrast < 0.5:
            score -= 5.0  # Poor contrast - suspicious
    
    # Penalty if top-2 segments overlap with baseline window (threshold too low)
    for start, end in top_2:
        if start < baseline_end and end > baseline_start:
            score -= 15.0  # Baseline detected as active = bad
    
    # Penalty if top-2 segments are in padded edge regions
    for start, end in top_2:
        if start < padded_start or end > padded_end:
            score -= 5.0
    
    # Bonus for top-2 segments being well-separated (not clustered together)
    if len(top_2) >= 2:
        seg_centers = [(s + e) / 2 for s, e in top_2]
        separation = abs(seg_centers[1] - seg_centers[0])
        if separation > signal_length * 0.3:  # Spread across >30% of recording
            score += 5.0
    
    return score


def _build_segments_for_threshold(
    log_energy: np.ndarray,
    threshold: float,
    min_length_samples: int,
    persist_on: int,
    persist_off: int,
    gap_merge: int,
) -> List[Tuple[int, int]]:
    """Build segments for a given threshold (helper for threshold comparison)."""
    binary = (log_energy > threshold).astype(int)
    return _segments_from_binary(binary, min_length_samples, persist_on, persist_off, gap_merge)


def _detect_mvc_segments(
    envelope: np.ndarray,
    fs: float,
    threshold_frac: float = 0.3,
    min_length_samples: Optional[int] = None,
    persist_on_ms: float = 25.0,
    gap_merge_ms: float = 150.0,
) -> List[tuple[int, int]]:
    """Detect MVC peak segments using a relative threshold plus persistence/gap merge."""

    if envelope.size == 0:
        return []
    if not 0.0 <= threshold_frac <= 1.0:
        raise ValueError("threshold_frac must be between 0 and 1")

    if min_length_samples is None:
        min_length_samples = int(fs)

    env_abs = np.abs(envelope)
    peak = float(np.max(env_abs))
    if peak <= 0.0:
        return []

    thresh = threshold_frac * peak
    binary = (env_abs >= thresh).astype(int)

    persist_on = max(1, int(persist_on_ms * fs / 1000.0))
    persist_off = persist_on  # symmetric persistence
    gap_merge = max(0, int(gap_merge_ms * fs / 1000.0))

    return _segments_from_binary(binary, min_length_samples, persist_on, persist_off, gap_merge)

def detect_mvc_segments_tkeo(
    emg_mv: np.ndarray,  # Raw EMG in millivolts (will be filtered internally)
    fs: float,
    baseline_window_s: float = 0.5,
    baseline_search_s: float = 2.0,
    k_mad: float = 6.0,
    min_length_samples: Optional[int] = None,
    persist_on_ms: float = 25.0,
    gap_merge_ms: float = 150.0,
    lowcut: float = 20.0,  # Bandpass low cutoff (paper uses 20 Hz)
    highcut: float = 500.0,  # Bandpass high cutoff
) -> List[Tuple[int, int]]:
    """Detect MVC segments using TKEO-enhanced onset detection.

    Based on Solnik et al. (2008) "Teager-Kaiser Operator improves
    the accuracy of EMG onset detection". 
    
    Pipeline: raw EMG -> bandpass filter -> TKEO -> low-pass smooth -> threshold
    
    TKEO enhances muscle activation onsets by computing instantaneous energy,
    making threshold-based detection more robust to noise.

    :param emg_mv: Raw EMG signal in millivolts (bandpass filtering done internally).
    :param fs: Sampling frequency in Hz.
    :param baseline_window_s: Window size (seconds) for baseline estimation.
    :param baseline_search_s: Search horizon (seconds) to pick the quietest baseline window.
    :param k_mad: Multiplier applied to robust sigma (MAD-based) to set the threshold.
    :param min_length_samples: Minimum segment length in samples; defaults to fs (1 second).
    :param persist_on_ms: Minimum consecutive ms above threshold to start a segment.
    :param gap_merge_ms: Merge gaps shorter than this duration between segments.
    :param lowcut: Bandpass filter low cutoff in Hz (default 20 Hz as per paper).
    :param highcut: Bandpass filter high cutoff in Hz (default 500 Hz).
    :returns: List of (start_idx, end_idx) segments above threshold after length filtering.
    """

    if min_length_samples is None:
        min_length_samples = int(fs)  # 1 second default
    
    # Step 1: Bandpass filter (as per Solnik et al. Step 2)
    emg_dc = emg_mv - np.mean(emg_mv)  # Remove DC offset
    emg_filt = bandpass_filter(emg_dc, fs, lowcut=lowcut, highcut=highcut)
    
    # Step 2 & 3: TKEO + low-pass smoothing
    energy_smooth = compute_tkeo_envelope(emg_filt, fs, smooth_cutoff_hz=10.0) # 10 Hz smoothing not as per paper

    # Compute percentiles for adaptive sigma
    p10_energy = float(np.percentile(energy_smooth, 10))
    p90_energy = float(np.percentile(energy_smooth, 90))

    # Baseline and robust threshold
    baseline, _ = _select_quiet_baseline(
        energy_smooth, fs, window_s=baseline_window_s, search_s=baseline_search_s
    )
    robust_sigma = _robust_sigma(baseline, p10=p10_energy, p90=p90_energy)
    threshold = float(np.median(baseline)) + k_mad * robust_sigma

    # Clamp threshold to avoid over-lenient or over-strict cases
    if energy_smooth.size:
        p50 = float(np.percentile(energy_smooth, 50))
        p90 = float(np.percentile(energy_smooth, 90))
        floor = 0.05 * p90  # floor at 5% of P90
        ceil = 0.7 * p90    # cap at 70% of P90
        if p90 > 0:
            threshold = max(threshold, floor)
            threshold = min(threshold, ceil)
        else:
            threshold = max(threshold, 0.0)
    else:
        threshold = 0.0

    if threshold <= 0:
        threshold = 0.0

    binary = (energy_smooth > threshold).astype(int)

    persist_on = max(1, int(persist_on_ms * fs / 1000.0))
    persist_off = persist_on
    gap_merge = max(0, int(gap_merge_ms * fs / 1000.0))

    return _segments_from_binary(binary, min_length_samples, persist_on, persist_off, gap_merge)


def detect_mvc_segments_hybrid(
    emg_mv: np.ndarray,
    fs: float,
    window_ms: float = 50.0,
    baseline_window_s: float = 0.5,
    k_mad: float = 6.0,
    min_length_samples: Optional[int] = None,
    persist_on_ms: float = 25.0,
    gap_merge_ms: float = 150.0,
    lowcut: float = 20.0,
    highcut: float = 500.0,
) -> Tuple[List[Tuple[int, int]], dict]:
    """Detect MVC segments using evidence-driven hybrid approach.
    
    This function uses an evidence-driven threshold selection strategy:
    1. Compute baseline-MAD threshold (primary/default)
    2. Compute Otsu threshold (candidate)
    3. Run segmentation with both thresholds
    4. Score each result based on MVC expectations (2 segments, ~1-3s each)
    5. Select the threshold that produces the best segmentation
    
    Key improvements over naive approaches:
    - Baseline-first logic (robust to class imbalance)
    - Evidence-driven selection (aligned with actual goal)
    - Guards against zero-inflated baselines (min sigma)
    - Excludes padded edges from baseline search
    - Floor derived from baseline window (not global percentiles)
    
    :param emg_mv: Raw EMG signal in millivolts.
    :param fs: Sampling frequency in Hz.
    :param window_ms: Window size in ms for energy computation (default 50ms).
    :param baseline_window_s: Window size for baseline estimation.
    :param k_mad: MAD multiplier for baseline threshold.
    :param min_length_samples: Minimum segment length; defaults to 1 second.
    :param persist_on_ms: Persistence duration to confirm onset/offset.
    :param gap_merge_ms: Maximum gap to merge between segments.
    :param lowcut: Bandpass low cutoff in Hz.
    :param highcut: Bandpass high cutoff in Hz.
    :returns: Tuple of (segments, debug_info) where segments is list of (start, end) 
              and debug_info contains intermediate values for visualization.
    """
    if min_length_samples is None:
        min_length_samples = int(fs)  # 1 second default (aligned with guardrail)
    
    # =========================================================================
    # STEP 1: PREPROCESSING
    # =========================================================================
    emg_dc = emg_mv - np.mean(emg_mv)
    emg_filt = bandpass_filter(emg_dc, fs, lowcut=lowcut, highcut=highcut)
    
    # =========================================================================
    # STEP 2: ENERGY EXTRACTION
    # =========================================================================
    # TKEO with rectification
    energy_tkeo = tkeo(emg_filt, rectify=True)
    
    # Windowed energy: sum TKEO values over sliding windows
    win_samples = max(1, int(window_ms * fs / 1000.0))
    if len(energy_tkeo) >= win_samples:
        windows = np.lib.stride_tricks.sliding_window_view(energy_tkeo, win_samples)
        energy_windowed = np.sum(windows, axis=1)
        # Pad to original length (assign window energy to window center)
        pad_left = win_samples // 2 
        pad_right = len(energy_tkeo) - len(energy_windowed) - pad_left
        energy = np.pad(energy_windowed, (pad_left, pad_right), mode='edge')
    else:
        energy = energy_tkeo
        pad_left = 0
        pad_right = 0
    
    # Track padded regions for later exclusion
    padded_end = len(energy) - pad_right if pad_right > 0 else len(energy)
    
    # =========================================================================
    # STEP 3: LOG TRANSFORM
    # =========================================================================
    eps = 1e-12
    log_energy = np.log10(energy + eps)
    
    # =========================================================================
    # STEP 4: BASELINE ESTIMATION (excluding padded edges)
    # =========================================================================
    # Pass linear energy for dropout detection (IQR check before log transform)
    baseline, baseline_start = _select_quiet_baseline(
        log_energy, fs, baseline_window_s, 
        search_s=None,  # Search entire signal
        exclude_edges=pad_left,  # Exclude padded regions
        linear_energy=energy,  # For dropout detection in linear space
    )
    baseline_end = baseline_start + len(baseline)
    
    # Compute percentiles for reference (needed for adaptive sigma)
    p10 = float(np.percentile(log_energy, 10))
    p90 = float(np.percentile(log_energy, 90))
    
    # Compute baseline IQR for min_sigma calculation
    baseline_iqr = float(np.percentile(baseline, 75) - np.percentile(baseline, 25))
    
    # Compute robust sigma with adaptive minimum guard
    robust_sigma = _robust_sigma(baseline, p10=p10, p90=p90, baseline_iqr=baseline_iqr)
    baseline_median = float(np.median(baseline))
    
    # =========================================================================
    # STEP 5: COMPUTE CANDIDATE THRESHOLDS
    # =========================================================================
    # Primary: Baseline-MAD threshold
    threshold_baseline = baseline_median + k_mad * robust_sigma
    
    # Secondary: Otsu threshold (only if distribution suggests bimodality)
    threshold_otsu = _otsu_threshold(log_energy)
    
    # Floor based on baseline window (not global percentiles)
    # Threshold should be at least baseline_median + 2*sigma
    floor_baseline = baseline_median + 2.0 * robust_sigma
    
    # =========================================================================
    # STEP 6: EVIDENCE-DRIVEN THRESHOLD SELECTION
    # =========================================================================
    persist_on = max(1, int(persist_on_ms * fs / 1000.0))
    persist_off = persist_on
    gap_merge = max(0, int(gap_merge_ms * fs / 1000.0))
    
    # Build candidate thresholds list
    candidates = []
    
    # Always include baseline threshold (primary)
    candidates.append(("baseline", threshold_baseline))
    
    # Include Otsu only if it's plausibly valid
    # Otsu should be above baseline (otherwise it detects noise as active)
    # and within reasonable range
    if threshold_otsu > threshold_baseline and p10 < threshold_otsu < p90:
        candidates.append(("otsu", threshold_otsu))
    
    # Add higher threshold candidates to try if baseline is too low
    # These help when baseline threshold catches too much noise
    threshold_high = baseline_median + (k_mad + 2) * robust_sigma  # k+2 sigma
    if threshold_high < p90:
        candidates.append(("baseline_high", threshold_high))
    
    # Add even higher threshold: k+4 sigma
    threshold_higher = baseline_median + (k_mad + 4) * robust_sigma
    if threshold_higher < p90:
        candidates.append(("baseline_higher", threshold_higher))
    
    # Add a percentile-based threshold (P75)
    threshold_p75 = float(np.percentile(log_energy, 75))
    if threshold_p75 > floor_baseline:
        candidates.append(("p75", threshold_p75))
    
    # Add P85 threshold - more aggressive for noisy signals
    threshold_p85 = float(np.percentile(log_energy, 85))
    if threshold_p85 > floor_baseline and threshold_p85 < p90:
        candidates.append(("p85", threshold_p85))
    
    # Evaluate each candidate
    best_score = float("-inf")
    best_threshold = threshold_baseline
    best_method = "baseline"
    best_segments: List[Tuple[int, int]] = []
    
    candidate_scores = {}
    for method, thresh in candidates:
        # Apply floor constraint
        thresh_clamped = max(thresh, floor_baseline)
        
        # Build segments
        segs = _build_segments_for_threshold(
            log_energy, thresh_clamped,
            min_length_samples, persist_on, persist_off, gap_merge
        )
        
        # Score the segmentation (pass log_energy for top-2 ranking)
        score = _score_segmentation(
            segs, fs,
            baseline_start, baseline_end,
            pad_left, padded_end,
            len(log_energy),
            log_energy=log_energy,
        )
        
        candidate_scores[method] = {
            "threshold": thresh,
            "threshold_clamped": thresh_clamped,
            "segments": segs,
            "n_segments": len(segs),
            "score": score,
        }
        
        if score > best_score:
            best_score = score
            best_threshold = thresh_clamped
            best_method = method
            best_segments = segs
    
    # =========================================================================
    # STEP 7: FINALIZE
    # =========================================================================
    # Build binary mask with selected threshold
    binary = (log_energy > best_threshold).astype(int)
    
    # Debug info for visualization
    debug_info = {
        "emg_filt": emg_filt,
        "energy_tkeo": energy_tkeo,
        "energy_windowed": energy,
        "log_energy": log_energy,
        "threshold": best_threshold,
        "threshold_otsu": threshold_otsu,
        "threshold_baseline": threshold_baseline,
        "threshold_method": best_method,
        "baseline_median": baseline_median,
        "baseline_start": baseline_start,
        "baseline_end": baseline_end,
        "robust_sigma": robust_sigma,
        "floor": floor_baseline,
        "p10": p10,
        "p90": p90,
        "pad_left": pad_left,
        "pad_right": pad_right,
        "binary": binary,
        "candidate_scores": candidate_scores,
        "best_score": best_score,
    }
    
    return best_segments, debug_info


def pick_mvc(
    acquisitions: Dict[str, pd.DataFrame]
) -> Tuple[Optional[str], Optional[pd.DataFrame]]:
    """Return the acquisition labeled as MVC along with its dataframe.

    Searches for any acquisition key containing 'mvc' (case-insensitive).

    :param acquisitions: Mapping of session_label -> dataframe for a device/day.
    :returns: Tuple of (label, dataframe) or (None, None) if no MVC found.
    """
    for key, df in acquisitions.items():
        if "mvc" in key.lower():
            return key, df
    return None, None
