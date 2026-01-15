# EMG Pipeline Changes Documentation

**Last Updated:** January 12, 2026  
**Purpose:** Document all significant changes made to the EMG processing pipeline for continuity across chat sessions.

---

## Table of Contents
1. [Overview](#overview)
2. [Package Architecture](#package-architecture)
3. [Active APDF + Rest Time Framework](#active-apdf--rest-time-framework)
4. [MVC Peak Computation (Hybrid Approach)](#mvc-peak-computation-hybrid-approach)
5. [Quality Assessment System](#quality-assessment-system)
6. [Metrics Implementation](#metrics-implementation)
7. [OH Profile JSON Structure](#oh-profile-json-structure)
8. [Visualization System](#visualization-system)
9. [Recent Findings: 0.5% Rest Threshold Analysis](#recent-findings-05-rest-threshold-analysis)
10. [Key Files Reference](#key-files-reference)
11. [Pipeline Execution](#pipeline-execution)

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

## Package Architecture

The EMG pipeline was refactored into a clean package structure under `sensors/`. The `signal_processing/` module now serves as a **backward compatibility layer** that re-exports from `sensors/`.

### Package Structure

```
sensors/                           # Canonical EMG implementation
├── __init__.py                    # Exports: PreprocessConfig, create_preprocess_config, run_emg_pipeline
├── emg_pipeline.py                # Main pipeline orchestration (1031 lines)
├── types.py                       # Shared type definitions (PreprocessConfig)
├── load/                          # Data loading and quality assessment
│   ├── dataset_loader.py          # Subject/day discovery
│   ├── daily_data_loader.py       # Load mBAN session files
│   ├── emg_filesystem.py          # File path utilities
│   ├── emg_quality.py             # PSD noise detection, ADC saturation, faulty sensor checks (915 lines)
│   ├── data_quality.py            # Quality report data structures
│   └── ...
├── process/                       # Signal processing
│   ├── emg_preprocessing.py       # Filtering, envelope, transfer function
│   ├── emg_mvc.py                 # MVC segment detection, peak computation
│   ├── filters.py                 # Bandpass, notch filters
│   └── ...
├── metrics/                       # Metric computation
│   ├── emg_metrics.py             # Active APDF, rest metrics, session metrics
│   ├── emg_metrics_export.py      # CSV export, aggregation
│   ├── emg_session.py             # Session-level metric helpers
│   └── ...
└── visualize/                     # Plotting
    ├── emg_visuals.py             # APDF, histogram, envelope plots
    ├── emg_timeline.py            # Session timeline visualization
    ├── oh_profile_plots.py        # OH profile visualizations
    └── ...

signal_processing/                 # BACKWARD COMPATIBILITY LAYER
├── __init__.py                    # Re-exports from sensors/ package
├── filters.py                     # Legacy filter implementations
└── archive/                       # Archived older implementations
    ├── emg_mvc_original.py
    └── emg_mvc_hybrid_scoring.py

OH_profile/                        # OH profile persistence
├── constants.py                   # JSON key definitions
├── emg_oh_helper.py               # EMG-specific OH profile functions
├── load/                          # Profile loading utilities
└── write/                         # Profile writing utilities
```

### Import Patterns

```python
# Preferred: Import from sensors package
from sensors.emg_pipeline import run_emg_pipeline, create_preprocess_config
from sensors.load.emg_quality import detect_psd_noise, detect_adc_saturation
from sensors.metrics.emg_metrics import compute_session_metrics

# Backward compatible: Still works via re-exports
from signal_processing import run_emg_pipeline  # Re-exported from sensors
```

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

**File:** `sensors/emg_pipeline.py` → `_add_relative_intensity_bins()`

---

## MVC Peak Computation (Hybrid Approach)

### Problem
Original approach used max of smoothed envelope, which:
- Was sensitive to noise spikes
- Could select non-physiological peaks
- Varied with envelope smoothing parameters

### Solution: Peak-Centered RMS

**File:** `sensors/process/emg_preprocessing.py`

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

**File:** `sensors/process/emg_mvc.py`

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

## Quality Assessment System

The pipeline includes comprehensive quality checks at multiple processing stages, implemented in `sensors/load/emg_quality.py` (915 lines).

### Quality Check Hierarchy

| Stage | Check | Fatal? | Description |
|-------|-------|--------|-------------|
| Loading | ADC Saturation | Yes | >1% samples at ADC limits (0 or 65520) |
| Loading | Recording too short | Yes | <8s for MVC, <60s for sessions |
| MVC | Faulty sensor | Yes | All values same sign (hardware failure) |
| MVC | PSD noise | Yes | 50 Hz powerline or 200/400 Hz hardware harmonics |
| MVC | Low amplitude | Yes | Peak <0.05 mV |
| Session | Faulty sensor | Yes | All values same sign |
| Session | PSD noise | Yes | Significant noise peaks detected |

### PSD Noise Detection

**File:** `sensors/load/emg_quality.py` → `detect_psd_noise()`

Uses Welch's method PSD analysis to detect:
- **20 Hz noise**: Unknown artifact (rare)
- **50 Hz powerline**: European mains interference
- **200/400 Hz harmonics**: MuscleBAN hardware artifacts

#### PSD Constants (Empirically Tuned)

```python
# Target frequencies
PEAK_20_HZ = 20
PEAK_50_HZ = 50
PEAK_200_HZ = 200
PEAK_400_HZ = 400

# Peak detection
PEAK_PROMINENCE_LOW_FREQ = 0.1    # 10% for 20/50 Hz
PEAK_PROMINENCE_HIGH_FREQ = 0.05  # 5% for 200/400 Hz
FREQ_TOLERANCE_LOW = 4.0          # ±4 Hz for 20/50 Hz
FREQ_TOLERANCE_HIGH = 10.0        # ±10 Hz for 200/400 Hz

# 200 Hz power threshold (empirical: 0.30 gives ~50 exclusions)
MIN_200HZ_POWER_FOR_NOISE = 0.30

# Area thresholds (0-180 Hz normalized PSD)
AREA_MIN = 45.0          # Below = poor signal quality
AREA_MAX = 115.0         # Above = unusual power concentration
AREA_CRITICAL = 20.0     # Below with 50 Hz peak = definite discard

# Peak width factor (narrow = interference, not muscle)
PEAK_WIDTH_FACTOR = 4.0  # Width < 4 * freq_resolution = too narrow
```

#### PSD Analysis Logic

```python
def detect_psd_noise(emg_filtered: np.ndarray, fs: float = 1000.0) -> Tuple[bool, Optional[QualityIssue]]:
    """
    Detect noise peaks in filtered EMG signal via PSD analysis.
    
    Algorithm:
    1. Compute Welch PSD (nperseg=1024 → ~1 Hz resolution at 1000 Hz)
    2. Normalize PSD to 0-180 Hz band (excludes high-freq where EMG is weak)
    3. Check for prominent peaks at 20, 50, 200, 400 Hz
    4. Validate peaks: narrow width + high prominence = interference
    5. Return (should_discard, QualityIssue or None)
    """
```

### Quality Diagnostic Plots

When a session fails quality checks, diagnostic plots are saved to `{plots_root}/qa_flagged/`:
- ADC saturation histograms (MVC and session files)
- PSD plots with marked noise peaks (MVC and session files)
- MVC segment detection visualizations

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
- `OH_profile/emg_oh_helper.py`
- `sensors/metrics/emg_metrics_export.py`
- `sensors/visualize/oh_profile_plots.py`

---

## OH Profile JSON Structure

**File:** `OH_profile/emg_oh_helper.py`

The EMG data is saved to OH profiles with a **nested grouped structure**:

```json
{
  "sensor_metrics": {
    "emg": {
      "2025-09-22": {
        "14-30-00": {
          "left": {
            "EMG_session": {
              "duration_s": 1800.0,
              "mvc_peak": 0.45,
              "active_duration_s": 1750.0
            },
            "EMG_intensity": {
              "mean_percent_mvc": 15.2,
              "max_percent_mvc": 85.0,
              "min_percent_mvc": 0.1,
              "iemg_percent_seconds": 27360.0
            },
            "EMG_apdf": {
              "full": {"p10": 2.1, "p50": 12.5, "p90": 35.0},
              "active": {"p10": 3.2, "p50": 14.8, "p90": 38.5}
            },
            "EMG_rest_recovery": {
              "rest_percent": 2.8,
              "gap_frequency_per_minute": 1.5,
              "max_sustained_activity_s": 180.0,
              "gap_count": 45
            },
            "EMG_relative_bins": {
              "below_usual_pct": 15.0,
              "typical_low_pct": 35.0,
              "typical_high_pct": 35.0,
              "high_for_you_pct": 15.0
            }
          },
          "right": { /* same structure */ }
        },
        "EMG_daily_metrics": {
          "left": { /* aggregated daily metrics */ },
          "right": { /* aggregated daily metrics */ }
        }
      },
      "EMG_weekly_metrics": {
        "left": {
          "day_count": 4,
          "duration_s": 16940.888,
          "active_apdf_p10": 2.87,
          "active_apdf_p50": 10.68,
          "active_apdf_p90": 30.29,
          /* ... */
        },
        "right": { /* ... */ }
      }
    }
  }
}
```

### OH Profile Constant Keys

**File:** `OH_profile/constants.py`

```python
# Group keys
EMG_SESSION_GROUP_KEY = 'EMG_session'
EMG_INTENSITY_GROUP_KEY = 'EMG_intensity'
EMG_APDF_GROUP_KEY = 'EMG_apdf'
EMG_REST_GROUP_KEY = 'EMG_rest_recovery'
EMG_RELATIVE_BINS_GROUP_KEY = 'EMG_relative_bins'

# APDF nested keys
EMG_APDF_FULL_KEY = 'full'
EMG_APDF_ACTIVE_KEY = 'active'
EMG_APDF_P10_KEY = 'p10'
EMG_APDF_P50_KEY = 'p50'
EMG_APDF_P90_KEY = 'p90'

# Aggregation keys
EMG_DAILY_AGGREGATE_KEY = 'EMG_daily_metrics'
EMG_WEEKLY_AGGREGATE_KEY = 'EMG_weekly_metrics'
```

### Aggregation Method

- **Daily aggregates:** Duration-weighted average of session metrics
- **Weekly aggregates:** Duration-weighted average of daily metrics
- Central tendency = **weighted mean** (not simple mean or median)

---

## Visualization System

**File:** `sensors/visualize/oh_profile_plots.py`

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

## Key Files Reference

### Core Pipeline (sensors/)
| File | Purpose | Lines |
|------|---------|-------|
| `sensors/emg_pipeline.py` | Main pipeline orchestration, two-pass processing | ~1031 |
| `sensors/types.py` | Shared type definitions (PreprocessConfig) | ~12 |
| `sensors/__init__.py` | Package exports | ~20 |

### Data Loading (sensors/load/)
| File | Purpose | Lines |
|------|---------|-------|
| `sensors/load/dataset_loader.py` | Subject/day discovery | ~200 |
| `sensors/load/daily_data_loader.py` | Load mBAN session files | ~150 |
| `sensors/load/emg_quality.py` | **PSD noise, ADC saturation, faulty sensor detection** | ~915 |
| `sensors/load/data_quality.py` | Quality report data structures | ~100 |
| `sensors/load/emg_filesystem.py` | File path utilities | ~80 |

### Signal Processing (sensors/process/)
| File | Purpose |
|------|---------|
| `sensors/process/emg_preprocessing.py` | Filtering, envelope, transfer function |
| `sensors/process/emg_mvc.py` | MVC segment detection (hybrid TKEO), peak computation |
| `sensors/process/filters.py` | Bandpass, notch filter implementations |

### Metrics (sensors/metrics/)
| File | Purpose |
|------|---------|
| `sensors/metrics/emg_metrics.py` | Active APDF, rest metrics, session metrics |
| `sensors/metrics/emg_metrics_export.py` | CSV export, daily/weekly aggregation |
| `sensors/metrics/emg_session.py` | Session-level metric helpers |

### Visualization (sensors/visualize/)
| File | Purpose |
|------|---------|
| `sensors/visualize/emg_visuals.py` | APDF curves, histograms, envelope plots |
| `sensors/visualize/emg_timeline.py` | Session timeline visualization |
| `sensors/visualize/oh_profile_plots.py` | OH profile summary charts |

### OH Profile Persistence (OH_profile/)
| File | Purpose |
|------|---------|
| `OH_profile/constants.py` | JSON key definitions (grouped structure) |
| `OH_profile/emg_oh_helper.py` | EMG-specific OH profile construction |

### Backward Compatibility (signal_processing/)
| File | Purpose |
|------|---------|
| `signal_processing/__init__.py` | Re-exports from sensors/ package |
| `signal_processing/archive/` | Archived older MVC implementations |

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
| `mvc_quality_summary.csv` | Sessions with mean %MVC > threshold (MVC calibration issues) |

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
# Pipeline entry points
run_emg_pipeline()                 → sensors/emg_pipeline.py
create_preprocess_config()         → sensors/emg_pipeline.py

# Quality checks
detect_psd_noise()                 → sensors/load/emg_quality.py
detect_adc_saturation()            → sensors/load/emg_quality.py
is_faulty_mban()                   → sensors/load/emg_quality.py
assess_mvc_signal_quality()        → sensors/load/emg_quality.py

# Metric computation
compute_active_apdf()              → sensors/metrics/emg_metrics.py
compute_rest_metrics()             → sensors/metrics/emg_metrics.py
compute_session_metrics()          → sensors/metrics/emg_metrics.py
compute_relative_intensity_bins()  → sensors/metrics/emg_metrics.py

# MVC processing
detect_mvc_segments_hybrid()       → sensors/process/emg_mvc.py
compute_mvc_peak_rms()             → sensors/process/emg_preprocessing.py
pick_mvc()                         → sensors/process/emg_mvc.py

# Signal processing
preprocess_emg()                   → sensors/process/emg_preprocessing.py
bandpass_filter()                  → sensors/process/emg_preprocessing.py
compute_tkeo_envelope()            → sensors/process/emg_preprocessing.py

# OH profile persistence
save_emg_to_oh_profiles()          → OH_profile/emg_oh_helper.py
_build_session_metrics_dict()      → OH_profile/emg_oh_helper.py

# Visualization
generate_emg_plots_from_oh_profiles() → sensors/visualize/oh_profile_plots.py
plot_apdf()                        → sensors/visualize/emg_visuals.py
```

---

*This document should provide sufficient context for continuing development in a new chat session.*
