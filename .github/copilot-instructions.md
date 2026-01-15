# PrevOccupAI+ Copilot Instructions

## Project Overview
Occupational health data analysis platform processing EMG (electromyography), IMU sensors, questionnaires, and human activity recognition data. Generates per-subject **OH (Occupational Health) profiles** as JSON files containing all metrics.

## Architecture

### Data Flow
```
Raw Data (E:\...\data\) → Pipeline Processing → OH Profiles (JSON) + CSV Exports
```

### Key Entry Points
- **`main_emg.py`** - EMG cohort processing (`run_all=True` runs full pipeline)
- **`main_sensors.py`** - IMU/HAR sensor processing
- **`main_questionnaires.py`** - Questionnaire data processing

### Core Modules (Authoritative)
| Module | Purpose |
|--------|---------|
| `sensors/` | **Primary EMG pipeline codebase** |
| `sensors/load/` | Dataset discovery, file loading, quality checks |
| `sensors/process/` | EMG preprocessing, MVC detection |
| `sensors/metrics/` | Metric computation (APDF, rest metrics, aggregations) |
| `sensors/visualize/` | EMG plots and OH profile visualizations |
| `OH_profile/` | OH profile JSON read/write and constants |
| `questionnaires/` | Questionnaire parsing and scoring |
| `signal_processing/` | **Legacy re-export wrapper (do not add new code here)** |

## EMG Pipeline Framework

### Active APDF + Rest Time Paradigm
The EMG pipeline separates **"intensity when working"** from **"relaxation time"**:
- **Active APDF**: Percentiles computed only on samples ≥ 0.5% MVC (excludes rest)
- **Rest metrics**: Time below 0.5% MVC threshold, gap frequency, sustained activity

### Key Constants (`sensors/metrics/emg_metrics.py`)
```python
DEFAULT_REST_THRESHOLD_MVC = 0.5  # Literature standard (Veiersted et al., 2013)
DEFAULT_GAP_MIN_DURATION_S = 0.25  # Minimum micro-break duration
MIN_ACTIVE_DURATION_FOR_BASELINE_S = 1800  # 30 min for weekly baseline
```

### MVC Normalization
Each session is normalized by **its side's MVC file**.
- MVC computed via peak-centered RMS on bandpass-filtered signal
- Mean %MVC of 5-25% is normal; >50% indicates MVC underestimation

## Development Patterns

### Virtual Environment (macOS)
```bash
source EMG_venv/bin/activate
```

### Running the EMG Pipeline
```python
# In main_emg.py - configure DATA_ROOT first
MAIN_ROOT = Path(r"E:\Backup PrevOccupAI_PLUS Data")
main(run_all=True, subject_filter=["81", "82"])  # Optional filtering
```

### Output Locations
- Session metrics: `{RESULTS_ROOT}/session_metrics.csv`
- Daily aggregates: `{RESULTS_ROOT}/daily_metrics.csv`
- Weekly aggregates: `{RESULTS_ROOT}/weekly_metrics.csv`
- OH profiles: `{OH_PROFILES_ROOT}/{subject_id}_OH_profile.json`
- Plots: `{RESULTS_ROOT}/plots/`

## Code Conventions

### Constants
- Device/sensor constants in `constants.py` (e.g., `FS_MBAN = 1000`, `MBAN_LEFT`, `MBAN_RIGHT`)
- OH profile keys in `OH_profile/constants.py` (use these, don't hardcode strings)

### Metric Keys Pattern
```python
# In OH_profile/constants.py
EMG_ACTIVE_APDF_P50_KEY = 'active_apdf_p50'  # Always use constant, not string
EMG_REST_PERCENT_KEY = 'rest_percent'
```

### Two-Pass Processing
Weekly relative intensity bins require:
1. **Pass 1**: Compute session-level Active APDF
2. **Pass 2**: Compute weekly baseline, then classify sessions into bins

See `sensors/emg_pipeline.py` → `_add_relative_intensity_bins()`

## Data Quality Checks
- Sessions with mean %MVC > 50% likely have MVC calibration issues
- Quality reports exported to `quality_report.csv`
- Known problematic subject-sides: 82-right, 109-right, 114-left (MVC underestimated)

## Documentation
Detailed pipeline documentation in `docs/EMG_PIPELINE_CHANGES.md` and `docs/EMG_CODE_AUDIT.md` - **read this first** when working on EMG code.

