"""MVC (Maximum Voluntary Contraction) detection and validation utilities.

This module handles:
- Detection of MVC segments using evidence-driven hybrid approach
- Multiple threshold candidates evaluated by quality scoring
- Picking MVC acquisitions from session data

The hybrid approach uses TKEO energy + log transform + multi-threshold evaluation
to find the best segmentation. The scoring prioritizes segment quality (duration,
contrast) over strict segment count - as long as we get ≥2 segments.

Reference: Solnik et al. (2008) "Teager-Kaiser Operator improves the accuracy of EMG onset detection"
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from constants import MVC
from sensors.process.emg_preprocessing import bandpass_filter, tkeo, compute_tkeo_envelope


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
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    
    # Total statistics
    total = hist.sum()
    if total == 0:
        return float(np.median(data_flat))
    
    sum_total = np.dot(hist, bin_centers)
    
    # Iterate to find optimal threshold
    sum_bg = 0.0
    weight_bg = 0
    var_max = 0.0
    threshold = bin_centers[0]
    
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
# Robust Statistics
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
    sigma = 1.4826 * mad  # Scale MAD to match std for normal distribution
    
    # Compute adaptive minimum: 5% of signal dynamic range, with absolute floor
    if p10 is None:
        p10 = float(np.percentile(x, 10))
    if p90 is None:
        p90 = float(np.percentile(x, 90))
    
    # min_sigma = max(5% of dynamic range, 10% of baseline IQR, absolute floor)
    adaptive_min = 0.05 * (p90 - p10)
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


# -------------------------------------------------------------------------------------------------------------------- #
# Baseline Estimation
# -------------------------------------------------------------------------------------------------------------------- #

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

    window = max(1, int(window_s * fs))
    
    # Determine search range, excluding edges if specified
    start_search = exclude_edges
    if search_s is None:
        end_search = signal.size - exclude_edges
    else:
        end_search = min(signal.size - exclude_edges, int(search_s * fs))
    
    # Ensure valid search range
    if end_search - start_search <= window:
        return signal[start_search:start_search + window], start_search

    # Compute IQR floor for dropout detection (in linear space if available)
    if linear_energy is not None and linear_energy.size > 0:
        full_iqr = float(np.percentile(linear_energy, 75) - np.percentile(linear_energy, 25))
        iqr_floor = iqr_floor_ratio * full_iqr
        use_linear_check = True
    else:
        iqr_floor = 0.0
        use_linear_check = False
    
    # Collect all candidate windows with their scores and IQR metrics
    candidates: List[Tuple[float, float, int]] = []
    
    # Slide with 25% overlap for efficiency
    for start in range(start_search, end_search - window + 1, max(1, window // 4)):
        window_view = signal[start : start + window]
        score = float(np.median(window_view))
        
        # Compute IQR for dropout detection
        if use_linear_check and linear_energy is not None:
            lin_window = linear_energy[start : start + window]
            iqr_metric = float(np.percentile(lin_window, 75) - np.percentile(lin_window, 25))
        else:
            iqr_metric = float(np.var(window_view))
        
        candidates.append((score, iqr_metric, start))
    
    # Sort by score (lowest median = quietest)
    candidates.sort(key=lambda x: x[0])
    
    # Pick the quietest window that passes the dropout check
    for score, iqr_metric, start in candidates:
        if use_linear_check:
            if iqr_metric >= iqr_floor:
                return signal[start : start + window], start
        else:
            if iqr_metric >= 1e-6:
                return signal[start : start + window], start
    
    # All windows failed dropout check - use the one with highest IQR as fallback
    if candidates:
        candidates.sort(key=lambda x: x[1], reverse=True)
        _, _, best_start = candidates[0]
        return signal[best_start : best_start + window], best_start
    
    return signal[start_search:start_search + window], start_search


# -------------------------------------------------------------------------------------------------------------------- #
# Segment Building
# -------------------------------------------------------------------------------------------------------------------- #

def _segments_from_binary(
    binary: np.ndarray,
    min_length_samples: int,
    persist_on: int,
    persist_off: int,
    gap_merge: int,
) -> List[Tuple[int, int]]:
    """Convert a binary mask to merged segments with persistence and gap merge.
    
    :param binary: Binary mask (1 = active, 0 = rest).
    :param min_length_samples: Minimum segment length to keep.
    :param persist_on: Samples above threshold required to start a segment.
    :param persist_off: Samples below threshold required to end a segment.
    :param gap_merge: Maximum gap (samples) between segments to merge.
    :returns: List of (start, end) segment tuples.
    """
    segments: List[Tuple[int, int]] = []
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
    merged: List[Tuple[int, int]] = []
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


# -------------------------------------------------------------------------------------------------------------------- #
# Scoring System (Quality-Focused, Not Count-Penalizing)
# -------------------------------------------------------------------------------------------------------------------- #

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
    """Score a segmentation result based on segment quality.
    
    IMPORTANT: This scoring does NOT penalize having more than 2 segments.
    The goal is to detect true activity - if there are 3+ real contractions,
    that's fine. We only require at least 2 segments to pass the guardrail.
    
    Scoring focuses on:
    - Having at least 2 segments (required by guardrail)
    - Good segment duration (1-3s ideal for MVC)
    - High contrast between segments and baseline
    - Segments not overlapping with detected baseline
    - Well-separated segments
    
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
    
    # Base score: require at least 2 segments, but don't penalize having more
    if n_segs >= 2:
        score = 20.0  # Pass - we have enough segments
    elif n_segs == 1:
        score = -20.0  # Fail - missing one segment
    else:
        score = -50.0  # Fail - no segments at all
    
    if n_segs == 0:
        return score
    
    # =========================================================================
    # IDENTIFY TOP-2 SEGMENTS BY PEAK ENERGY (for duration/contrast scoring)
    # =========================================================================
    if log_energy is not None and n_segs >= 2:
        # Compute peak energy for each segment
        seg_peaks = []
        for start, end in segments:
            peak_energy = float(np.max(log_energy[start:end]))
            seg_peaks.append((peak_energy, start, end))
        
        # Sort by peak energy descending
        seg_peaks.sort(key=lambda x: x[0], reverse=True)
        
        # Top-2 segments (by energy) - these are most likely the real MVCs
        top_2 = [(s, e) for _, s, e in seg_peaks[:2]]
    else:
        top_2 = segments[:2] if n_segs >= 2 else segments
    
    # =========================================================================
    # DURATION SCORING (for top-2 segments)
    # =========================================================================
    # MVC contractions should be 1-3 seconds. Score based on duration quality.
    for start, end in top_2:
        duration_s = (end - start) / fs
        if 1.0 <= duration_s <= 3.0:
            score += 8.0  # Ideal duration
        elif 0.5 <= duration_s < 1.0:
            score += 4.0  # Short but acceptable
        elif 3.0 < duration_s <= 5.0:
            score += 4.0  # Long but acceptable
        elif 5.0 < duration_s <= 10.0:
            score -= 5.0  # Too long - might be merged
        elif duration_s > 10.0:
            # Very long segment - likely threshold too low
            score -= 15.0 - 1.0 * (duration_s - 10.0)
    
    # =========================================================================
    # CONTRAST SCORING
    # =========================================================================
    # Top-2 segments should have significantly higher energy than baseline
    if log_energy is not None and len(top_2) >= 2:
        top_2_peaks = [float(np.max(log_energy[s:e])) for s, e in top_2]
        avg_top_2_peak = np.mean(top_2_peaks)
        baseline_level = float(np.median(log_energy[baseline_start:baseline_end]))
        contrast = avg_top_2_peak - baseline_level
        
        # Good contrast means clear separation between activity and rest
        if contrast > 1.5:
            score += 8.0  # Excellent contrast (>30x energy difference)
        elif contrast > 1.0:
            score += 5.0  # Good contrast (>10x energy difference)
        elif contrast > 0.5:
            score += 2.0  # Moderate contrast
        elif contrast < 0.3:
            score -= 8.0  # Poor contrast - hard to distinguish from noise
    
    # =========================================================================
    # BASELINE OVERLAP PENALTY
    # =========================================================================
    # If segments overlap with the detected baseline, the threshold is too low
    for start, end in top_2:
        if start < baseline_end and end > baseline_start:
            score -= 15.0  # Baseline detected as active = bad threshold
    
    # =========================================================================
    # EDGE EFFECT PENALTY
    # =========================================================================
    # Segments in padded regions might be artifacts
    for start, end in top_2:
        if start < padded_start or end > padded_end:
            score -= 3.0
    
    # =========================================================================
    # SEPARATION BONUS
    # =========================================================================
    # Top-2 segments should be spread apart (not clustered together)
    if len(top_2) >= 2:
        seg_centers = [(s + e) / 2 for s, e in top_2]
        separation = abs(seg_centers[1] - seg_centers[0])
        if separation > signal_length * 0.25:  # Spread across >25% of recording
            score += 5.0
    
    return score


# -------------------------------------------------------------------------------------------------------------------- #
# Envelope-Based Detection (Simple Fallback)
# -------------------------------------------------------------------------------------------------------------------- #

def _detect_mvc_segments(
    envelope: np.ndarray,
    fs: float,
    threshold_frac: float = 0.3,
    min_length_samples: Optional[int] = None,
    persist_on_ms: float = 25.0,
    gap_merge_ms: float = 150.0,
) -> List[Tuple[int, int]]:
    """Detect MVC peak segments using a relative threshold (fraction of peak).
    
    Simple fallback approach: threshold = threshold_frac × peak_amplitude
    
    :param envelope: EMG envelope signal.
    :param fs: Sampling frequency in Hz.
    :param threshold_frac: Fraction of peak to use as threshold (default 0.3 = 30%).
    :param min_length_samples: Minimum segment length; defaults to fs (1 second).
    :param persist_on_ms: Minimum consecutive ms above threshold to start a segment.
    :param gap_merge_ms: Merge gaps shorter than this duration between segments.
    :returns: List of (start_idx, end_idx) segments.
    """
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
    persist_off = persist_on
    gap_merge = max(0, int(gap_merge_ms * fs / 1000.0))

    return _segments_from_binary(binary, min_length_samples, persist_on, persist_off, gap_merge)


# -------------------------------------------------------------------------------------------------------------------- #
# Main Entry Point: Hybrid Detection
# -------------------------------------------------------------------------------------------------------------------- #

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
    3. Compute percentile-based thresholds (P75, P85)
    4. Run segmentation with all candidate thresholds
    5. Score each result based on segment QUALITY (not count)
    6. Select the threshold that produces the best segmentation
    
    IMPORTANT: The scoring does NOT penalize having >2 segments. It focuses
    on segment quality (duration, contrast, separation). As long as we get
    ≥2 segments, the guardrail passes.
    
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
        min_length_samples = int(fs)
    
    # =========================================================================
    # STEP 1: PREPROCESSING
    # =========================================================================
    emg_dc = emg_mv - np.mean(emg_mv)
    emg_filt = bandpass_filter(emg_dc, fs, lowcut=lowcut, highcut=highcut)
    
    # =========================================================================
    # STEP 2: ENERGY EXTRACTION (TKEO + windowing)
    # =========================================================================
    energy_tkeo = tkeo(emg_filt, rectify=True)
    
    win_samples = max(1, int(window_ms * fs / 1000.0))
    if len(energy_tkeo) >= win_samples:
        windows = np.lib.stride_tricks.sliding_window_view(energy_tkeo, win_samples)
        energy_windowed = np.sum(windows, axis=1)
        pad_left = win_samples // 2 
        pad_right = len(energy_tkeo) - len(energy_windowed) - pad_left
        energy = np.pad(energy_windowed, (pad_left, pad_right), mode='edge')
    else:
        energy = energy_tkeo
        pad_left = 0
        pad_right = 0
    
    padded_end = len(energy) - pad_right if pad_right > 0 else len(energy)
    
    # =========================================================================
    # STEP 3: LOG TRANSFORM
    # =========================================================================
    eps = 1e-12
    log_energy = np.log10(energy + eps)
    
    # =========================================================================
    # STEP 4: BASELINE ESTIMATION
    # =========================================================================
    baseline, baseline_start = _select_quiet_baseline(
        log_energy, fs, baseline_window_s, 
        search_s=None,  # Search entire signal
        exclude_edges=pad_left,
        linear_energy=energy,
    )
    baseline_end = baseline_start + len(baseline)
    
    p10 = float(np.percentile(log_energy, 10))
    p90 = float(np.percentile(log_energy, 90))
    baseline_iqr = float(np.percentile(baseline, 75) - np.percentile(baseline, 25))
    
    robust_sigma = _robust_sigma(baseline, p10=p10, p90=p90, baseline_iqr=baseline_iqr)
    baseline_median = float(np.median(baseline))
    
    # =========================================================================
    # STEP 5: COMPUTE CANDIDATE THRESHOLDS
    # =========================================================================
    threshold_baseline = baseline_median + k_mad * robust_sigma
    threshold_otsu = _otsu_threshold(log_energy)
    floor_baseline = baseline_median + 2.0 * robust_sigma
    
    # =========================================================================
    # STEP 6: EVIDENCE-DRIVEN THRESHOLD SELECTION
    # =========================================================================
    persist_on = max(1, int(persist_on_ms * fs / 1000.0))
    persist_off = persist_on
    gap_merge = max(0, int(gap_merge_ms * fs / 1000.0))
    
    candidates = []
    candidates.append(("baseline", threshold_baseline))
    
    if threshold_otsu > threshold_baseline and p10 < threshold_otsu < p90:
        candidates.append(("otsu", threshold_otsu))
    
    threshold_high = baseline_median + (k_mad + 2) * robust_sigma
    if threshold_high < p90:
        candidates.append(("baseline_high", threshold_high))
    
    threshold_higher = baseline_median + (k_mad + 4) * robust_sigma
    if threshold_higher < p90:
        candidates.append(("baseline_higher", threshold_higher))
    
    threshold_p75 = float(np.percentile(log_energy, 75))
    if threshold_p75 > floor_baseline:
        candidates.append(("p75", threshold_p75))
    
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
        thresh_clamped = max(thresh, floor_baseline)
        
        segs = _build_segments_for_threshold(
            log_energy, thresh_clamped,
            min_length_samples, persist_on, persist_off, gap_merge
        )
        
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
    binary = (log_energy > best_threshold).astype(int)
    
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


# -------------------------------------------------------------------------------------------------------------------- #
# Legacy TKEO-only detection (simplified, no scoring)
# -------------------------------------------------------------------------------------------------------------------- #

def detect_mvc_segments_tkeo(
    emg_mv: np.ndarray,
    fs: float,
    baseline_window_s: float = 0.5,
    baseline_search_s: Optional[float] = None,
    k_mad: float = 6.0,
    min_length_samples: Optional[int] = None,
    persist_on_ms: float = 25.0,
    gap_merge_ms: float = 150.0,
    lowcut: float = 20.0,
    highcut: float = 500.0,
) -> List[Tuple[int, int]]:
    """Detect MVC segments using TKEO with single baseline+kσ threshold.
    
    This is a simplified version without multi-threshold scoring.
    For better results, use detect_mvc_segments_hybrid() instead.
    
    :param emg_mv: Raw EMG signal in millivolts.
    :param fs: Sampling frequency in Hz.
    :param baseline_window_s: Window size (seconds) for baseline estimation.
    :param baseline_search_s: Search horizon (seconds). If None, searches entire signal.
    :param k_mad: Multiplier applied to robust sigma for threshold.
    :param min_length_samples: Minimum segment length in samples; defaults to fs (1 second).
    :param persist_on_ms: Minimum consecutive ms above threshold to start a segment.
    :param gap_merge_ms: Merge gaps shorter than this duration between segments.
    :param lowcut: Bandpass filter low cutoff in Hz.
    :param highcut: Bandpass filter high cutoff in Hz.
    :returns: List of (start_idx, end_idx) segments above threshold.
    """
    if min_length_samples is None:
        min_length_samples = int(fs)
    
    # Bandpass filter
    emg_dc = emg_mv - np.mean(emg_mv)
    emg_filt = bandpass_filter(emg_dc, fs, lowcut=lowcut, highcut=highcut)
    
    # TKEO + smoothing
    energy_smooth = compute_tkeo_envelope(emg_filt, fs, smooth_cutoff_hz=10.0)

    # Simple baseline estimation (search whole file by default)
    baseline, _ = _select_quiet_baseline(
        energy_smooth, fs, window_s=baseline_window_s, search_s=baseline_search_s
    )
    
    # Simple robust sigma
    med = float(np.median(baseline))
    mad = float(np.median(np.abs(baseline - med)))
    sigma = max(1.4826 * mad, 0.01)
    
    threshold = med + k_mad * sigma

    # Clamp threshold
    if energy_smooth.size:
        p90 = float(np.percentile(energy_smooth, 90))
        floor = 0.05 * p90
        ceil = 0.7 * p90
        if p90 > 0:
            threshold = max(threshold, floor)
            threshold = min(threshold, ceil)

    if threshold <= 0:
        threshold = 0.0

    binary = (energy_smooth > threshold).astype(int)

    persist_on = max(1, int(persist_on_ms * fs / 1000.0))
    persist_off = persist_on
    gap_merge = max(0, int(gap_merge_ms * fs / 1000.0))

    return _segments_from_binary(binary, min_length_samples, persist_on, persist_off, gap_merge)


# -------------------------------------------------------------------------------------------------------------------- #
# MVC Acquisition Picker
# -------------------------------------------------------------------------------------------------------------------- #

def pick_mvc(
    acquisitions: Dict[str, pd.DataFrame]
) -> Tuple[Optional[str], Optional[pd.DataFrame]]:
    """Return the acquisition labeled as MVC along with its dataframe.

    Searches for any acquisition key containing 'mvc' (case-insensitive).

    :param acquisitions: Mapping of session_label -> dataframe for a device/day.
    :returns: Tuple of (label, dataframe) or (None, None) if no MVC found.
    """
    for key, df in acquisitions.items():
        if MVC in key:
            return key, df
    return None, None
