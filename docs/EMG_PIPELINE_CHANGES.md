# EMG Pipeline Changes Documentation

**Last Updated:** December 30, 2025  
**Purpose:** Document all significant changes made to the EMG processing pipeline for continuity across chat sessions.

---

## Table of Contents
1. [Overview](#overview)
2. [Active APDF + Rest Time Framework](#active-apdf--rest-time-framework)
3. [MVC Peak Computation (Hybrid Approach)](#mvc-peak-computation-hybrid-approach)
4. [Metrics Implementation](#metrics-implementation)
5. [OH Profile JSON Structure](#oh-profile-json-structure)
6. [Visualization System](#visualization-system)
7. [Recent Findings: 0.5% Rest Threshold Analysis](#recent-findings-05-rest-threshold-analysis)
8. [Key Files Modified](#key-files-modified)
9. [Pipeline Execution](#pipeline-execution)

---

## Overview

The EMG pipeline was significantly refactored to implement a physiologically meaningful analysis framework based on occupational EMG research literature (Veiersted et al., 2013; Marker et al., 2016). The key paradigm shift was separating **"intensity when working"** (Active APDF) from **"relaxation time"** (Rest metrics).

### Core Concepts

| Concept | Description |
|---------|-------------|
| **Active APDF** | APDF percentiles computed ONLY on samples ≥ rest threshold (0.5% MVC) |
| **Rest Time** | Percentage of time spent below 0.5% MVC (true muscular relaxation) |
| **Gap Analysis** | Micro-breaks detection (rest periods ≥ 0.25s) |
| **Relative Intensity Bins** | Session activity classified relative to subject's weekly baseline |

---

## Active APDF + Rest Time Framework

### Rationale
Traditional APDF mixes rest periods with active work, which:
- Artificially lowers percentile values
- Conflates "low intensity work" with "rest"
- Loses critical information about recovery patterns

### Implementation

**File:** `sensors/metrics/emg_metrics.py`

```python
def compute_active_apdf(
    signal_percent: np.ndarray,
    rest_threshold: float = 0.5,  # 0.5% MVC - literature standard
    percentiles: tuple = (10, 50, 90),
) -> dict:
    """
    Compute Active APDF: percentiles only on samples ABOVE the rest threshold.
    
    Returns:
        - active_samples: count of samples above threshold
        - total_samples: total sample count
        - active_fraction: ratio (0-1)
        - rest_threshold: threshold used
        - percentiles: {10: value, 50: value, 90: value}
    """
```

### Two-Pass Processing

The pipeline uses a two-pass approach for relative intensity binning:

1. **Pass 1:** Compute session-level Active APDF (P10, P50, P90) for all sessions
2. **Pass 2:** Compute weekly baseline (duration-weighted average of P10, P50, P90), then classify each session's active samples into bins:
   - **Below usual:** < weekly P10
   - **Typical-low:** P10 to P50
   - **Typical-high:** P50 to P90
   - **High for you:** > P90

**File:** `signal_processing/emg_pipeline.py` → `_add_relative_intensity_bins()`

---

## MVC Peak Computation (Hybrid Approach)

### Problem
Original approach used max of smoothed envelope, which:
- Was sensitive to noise spikes
- Could select non-physiological peaks
- Varied with envelope smoothing parameters

### Solution: Peak-Centered RMS

**File:** `signal_processing/emg_preprocessing.py`

```python
def compute_mvc_peak_rms(
    raw_emg_mv: np.ndarray,
    fs: float,
    bandpass_low: float = 20.0,
    bandpass_high: float = 450.0,
    rms_window_ms: float = 250.0,
) -> float:
    """
    Compute MVC peak using peak-centered RMS on bandpass-filtered rectified signal.
    
    Steps:
    1. Bandpass filter (20-450 Hz) - remove DC and high-frequency noise
    2. Full-wave rectification (absolute value)
    3. Find peak sample index
    4. Extract 250ms window centered on peak
    5. Compute RMS of that window
    
    This is more robust than max(envelope) because:
    - RMS averages over window, reducing spike sensitivity
    - Bandpass removes artifacts that might create false peaks
    - 250ms window captures sustained MVC effort, not transients
    """
```

### Hybrid MVC Segment Detection

**File:** `signal_processing/emg_preprocessing.py`

The `detect_mvc_segments_hybrid()` function uses TKEO (Teager-Kaiser Energy Operator) with evidence-driven threshold selection:

1. Compute TKEO envelope for burst detection
2. Log-transform to separate noise from signal
3. Use bimodal distribution analysis (Otsu's method) or percentile fallback
4. Validate segments (minimum 1 second, at least 2 segments required)

```python
def detect_mvc_segments_hybrid(
    raw_emg_mv: np.ndarray,
    fs: float,
    window_ms: float = 50.0,
    baseline_window_s: float = 0.5,
    k_mad: float = 6.0,
    min_length_samples: int = 1000,
) -> Tuple[List[Tuple[int, int]], dict]:
    """
    Hybrid MVC segment detection using TKEO + evidence-driven thresholding.
    
    Returns:
        - segments: List of (start, end) sample indices
        - debug_info: Dictionary with threshold method used, values, etc.
    """
```

---

## Metrics Implementation

### Session-Level Metrics

**File:** `sensors/metrics/emg_metrics.py` → `compute_session_metrics()`

| Metric | Key | Description |
|--------|-----|-------------|
| Duration | `duration_s` | Recording length in seconds |
| Mean %MVC | `mean_percent_mvc` | Average amplitude |
| Max %MVC | `max_percent_mvc` | Peak amplitude |
| Min %MVC | `min_percent_mvc` | Minimum amplitude |
| iEMG | `iemg_percent_seconds` | Integrated EMG (area under curve) |
| MVC Peak | `mvc_peak` | Reference MVC value used for normalization |
| Traditional APDF | `apdf_p10`, `apdf_p50`, `apdf_p90` | Percentiles on ALL samples |
| **Active APDF** | `active_apdf_p10`, `active_apdf_p50`, `active_apdf_p90` | Percentiles on ACTIVE samples only |
| Rest Percent | `rest_percent` | % time below 0.5% MVC |
| Gap Count | `gap_count` | Number of micro-breaks (≥0.25s below threshold) |
| **Gap Frequency/Min** | `gap_frequency_per_minute` | Gaps per minute (better for short sessions) |
| Max Sustained Activity | `max_sustained_activity_s` | Longest continuous active period |
| Active Duration | `active_duration_s` | Total time in active state |
| Relative Bins | `bin_below_usual_pct`, `bin_typical_low_pct`, `bin_typical_high_pct`, `bin_high_for_you_pct` | % of active time in each intensity bin |

### Gap Frequency Metric Change

**Important:** We removed `gap_frequency_per_hour` and replaced it with `gap_frequency_per_minute` because:
- Sessions are typically 20-60 minutes, not hours
- Per-minute frequency is more interpretable for short recordings
- Avoids extrapolation errors

**Files modified:**
- `sensors/metrics/emg_metrics.py`
- `OH_profile/constants.py`
- `signal_processing/emg_oh_helper.py`
- `signal_processing/emg_metrics_export.py`
- `visualize/oh_profile_plots.py`

---

## OH Profile JSON Structure

**File:** `signal_processing/emg_oh_helper.py`

The EMG data is saved to OH profiles with this nested structure:

```json
{
  "sensor_metrics": {
    "emg": {
      "2025-09-22": {
        "14-30-00": {
          "left": { /* session metrics */ },
          "right": { /* session metrics */ }
        },
        "16-00-00": { /* ... */ },
        "daily_aggregate": {
          "left": { /* daily aggregated metrics */ },
          "right": { /* daily aggregated metrics */ }
        }
      },
      "2025-09-23": { /* ... */ },
      "weekly_aggregate": {
        "left": {
          "day_count": 4,
          "duration_s": 16940.888,
          "active_apdf_p10": 2.87,
          "active_apdf_p50": 10.68,
          "active_apdf_p90": 30.29,
          "rest_percent": 0.0,
          "gap_frequency_per_minute": 0.0,
          /* ... other metrics ... */
        },
        "right": { /* ... */ }
      }
    }
  }
}
```

### Aggregation Method

- **Daily aggregates:** Duration-weighted average of session metrics
- **Weekly aggregates:** Duration-weighted average of daily metrics
- Central tendency = **weighted mean** (not simple mean or median)

---

## Visualization System

**File:** `visualize/oh_profile_plots.py`

### Plot Types Generated

| Plot | Description | Location |
|------|-------------|----------|
| Rest vs Active Distribution | Stacked bar chart per session | `{subject}/{date}/summary/rest_active_distribution.png` |
| Rest/Active Donut | Daily aggregate pie chart with Active APDF in center | `{subject}/{date}/summary/rest_active_donut_{side}.png` |
| Relative Intensity Bars | Session bins vs weekly baseline | `{subject}/{date}/summary/relative_intensity_bars.png` |
| Weekly Trends | Active APDF P10/P50/P90 over days | `{subject}/weekly/active_apdf_trend_{side}.png` |
| Weekly Rest Trend | Rest % over days | `{subject}/weekly/rest_percent_trend_{side}.png` |

### Plot Generation Function

```python
def generate_all_oh_profile_plots(
    oh_profile: Dict[str, Any],
    plots_root: Path,
    subject_id: str,
) -> int:
    """
    Generate all EMG visualization plots from OH profile data.
    
    Returns: Number of plots generated
    """
```

---

## Recent Findings: 0.5% Rest Threshold Analysis

### Dataset
- **37 subjects**, **175 days**, **1,257 sessions**

### Key Statistics

| Metric | Value |
|--------|-------|
| Sessions with rest > 0% | 125 (10%) |
| Sessions with rest > 1% | 71 (5.6%) |
| Sessions with rest > 5% | 40 (3.2%) |
| Subjects with meaningful rest (mean > 1%) | **7 / 37 (19%)** |
| Subjects with zero rest in ALL sessions | **22 / 37 (59%)** |

### Top Subjects with Rest Data

| Subject | Mean Rest % | Max Rest % |
|---------|-------------|------------|
| 89 | 7.0% | 34.1% |
| 105 | 6.0% | 55.2% |
| 127 | 3.8% | 55.1% |
| 107 | 3.5% | 31.3% |
| 125 | 3.1% | 24.6% |
| 97 | 2.2% | 24.9% |
| 118 | 1.3% | 27.6% |

### Interpretation

1. **The 0.5% threshold IS scientifically valid** (per Veiersted et al., 2013)
2. **~60% of subjects show continuous low-level activity** with no true rest
3. This could indicate:
   - Continuous postural stabilization (not necessarily bad)
   - MVC underestimation (if mean %MVC is >100%, investigate)
   - Task-specific demands (some jobs require constant engagement)
4. **Recommendation:** Keep the 0.5% threshold but acknowledge that "zero rest" subjects may need separate analysis or MVC recalibration

---

## Key Files Modified

### Core Processing
| File | Purpose |
|------|---------|
| `sensors/metrics/emg_metrics.py` | All metric computation functions |
| `signal_processing/emg_preprocessing.py` | Filtering, envelope, MVC peak computation |
| `signal_processing/emg_pipeline.py` | Main pipeline orchestration |
| `signal_processing/emg_oh_helper.py` | OH profile JSON construction |
| `signal_processing/emg_metrics_export.py` | CSV export functionality |

### Constants and Keys
| File | Purpose |
|------|---------|
| `OH_profile/constants.py` | JSON key definitions (EMG_ACTIVE_APDF_P10_KEY, etc.) |
| `constants.py` | Global constants (MBAN device labels, etc.) |

### Visualization
| File | Purpose |
|------|---------|
| `visualize/oh_profile_plots.py` | All plot generation from OH profiles |
| `visualize/emg_visuals.py` | Session-level plots (APDF curves, histograms, envelopes) |

### Data Loading
| File | Purpose |
|------|---------|
| `sensors/load/dataset_loader.py` | Subject/day discovery |
| `sensors/load/daily_data_loader.py` | Load mBAN data files |
| `sensors/load/data_quality.py` | Quality checks and guardrails |

---

## Pipeline Execution

### Entry Point
**File:** `main_emg.py`

```python
# Configuration
MAIN_ROOT = Path(r"E:\Backup PrevOccupAI_PLUS Data")
DATA_ROOT = MAIN_ROOT / "data"
RESULTS_ROOT = MAIN_ROOT / "results" / "emg_pipeline"
PLOTS_ROOT = RESULTS_ROOT / "plots"
OH_PROFILES_ROOT = MAIN_ROOT / "OH_profiles"

# Run pipeline
if __name__ == '__main__':
    # Run on all subjects
    main(run_all=True, subject_filter=None)
    
    # Or filter specific subjects
    # main(run_all=True, subject_filter=["80", "81", "85"])
```

### Output Files

| File | Description |
|------|-------------|
| `session_metrics.csv` | Per-session metrics (all columns) |
| `daily_metrics.csv` | Aggregated daily metrics |
| `weekly_metrics.csv` | Aggregated weekly metrics |
| `session_increments.csv` | Percentage changes between sessions |
| `daily_increments.csv` | Percentage changes between days |
| `data_quality_report.csv` | Skipped files and reasons |

### Virtual Environment

```powershell
# Activate environment
.\EMG_venv\Scripts\Activate.ps1

# Run pipeline
python main_emg.py
```

---

## Future Considerations

1. **Threshold Sensitivity Analysis:** Test 1%, 2%, 5% MVC thresholds for comparison
2. **MVC Validation:** Flag subjects with mean %MVC > 100% for recalibration
3. **Muscle-Specific Thresholds:** Different muscles may need different rest thresholds
4. **Fatigue Indices:** Add spectral fatigue metrics (median frequency shift)
5. **Cross-Session Normalization:** Consider using pooled MVC across days for stability

---

## Quick Reference: Key Function Locations

```
compute_active_apdf()          → sensors/metrics/emg_metrics.py:73
compute_rest_metrics()         → sensors/metrics/emg_metrics.py:117
compute_relative_intensity_bins() → sensors/metrics/emg_metrics.py:250
compute_mvc_peak_rms()         → signal_processing/emg_preprocessing.py
detect_mvc_segments_hybrid()   → signal_processing/emg_preprocessing.py
_add_relative_intensity_bins() → signal_processing/emg_pipeline.py:185
_build_emg_profile_structure() → signal_processing/emg_oh_helper.py:155
generate_all_oh_profile_plots() → visualize/oh_profile_plots.py
```

---

*This document should provide sufficient context for continuing development in a new chat session.*
