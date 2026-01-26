# PrevOccupAI+ EMG Pipeline Overview

## Purpose

Analyze surface EMG from trapezius muscles to assess occupational workload and generate personalized Occupational Health (OH) profiles.

---

## High-Level Architecture

```
+---------------------------------------------------------------------------------+
|                              RAW DATA (External Drive)                          |
|    E:\data\group{X}\sensors\LIBPhys #{NNN}\{date}\{time}\*.txt                 |
+---------------------------------------------------------------------------------+
                                        |
                                        v
+---------------------------------------------------------------------------------+
|                           1. DATA DISCOVERY                                     |
|  +--------------+    +------------------+    +-----------------+                |
|  | participants |--->| discover_daily_  |--->|  Day Descriptors |               |
|  | _info.csv    |    | acquisitions()   |    |  (subject, date, |               |
|  +--------------+    +------------------+    |   MAC addresses) |               |
|                                              +-----------------+                |
+---------------------------------------------------------------------------------+
                                        |
                                        v
+---------------------------------------------------------------------------------+
|                           2. DATA LOADING                                       |
|                                                                                 |
|  +--------------+         +---------------+         +--------------+           |
|  |  OpenSignals |-------->|  Split by MAC |-------->|  DataFrames  |           |
|  |  .txt files  |         |  (Left/Right) |         |  per session |           |
|  +--------------+         +---------------+         +--------------+           |
|                                                                                 |
|  Output: {"mban_left": {"MVC": df, "09-30-00": df}, "mban_right": {...}}       |
+---------------------------------------------------------------------------------+
                                        |
                                        v
+---------------------------------------------------------------------------------+
|                        3. QUALITY CHECKS                                        |
|                                                                                 |
|  +-----------------+  +-----------------+  +-----------------+                  |
|  |  ADC Saturation |  |  Faulty Sensor  |  |   PSD Noise     |                  |
|  |   (clipping)    |  |  (all + or -)   |  |  (50/200/400Hz) |                  |
|  +--------+--------+  +--------+--------+  +--------+--------+                  |
|           |                    |                    |                           |
|           +--------------------+--------------------+                           |
|                                |                                                |
|                    +-----------+-----------+                                    |
|                    |   PASS    |   FAIL    |                                    |
|                    |  Continue |  Log to   |                                    |
|                    |  pipeline |  quality  |                                    |
|                    |           |  report   |                                    |
|                    +-----------+-----------+                                    |
+---------------------------------------------------------------------------------+
                                        |
                                        v
+---------------------------------------------------------------------------------+
|                        4. MVC CALIBRATION                                       |
|                                                                                 |
|  +--------------+    +------------------+    +-----------------+                |
|  |  MVC Signal  |--->|  Hybrid Segment  |--->|  Peak RMS       |                |
|  |  (raw mV)    |    |  Detection       |    |  (250ms window) |                |
|  +--------------+    +------------------+    +--------+--------+                |
|                                                       |                         |
|                                              +--------v--------+                |
|                                              |   MVC Reference |                |
|                                              |   (100% = max   |                |
|                                              |    voluntary    |                |
|                                              |   contraction)  |                |
|                                              +-----------------+                |
+---------------------------------------------------------------------------------+
                                        |
                                        v
+---------------------------------------------------------------------------------+
|                     5. SESSION PROCESSING (per work session)                    |
|                                                                                 |
|  +------------------------------------------------------------------------+    |
|  |                         PREPROCESSING                                  |    |
|  |  Raw ADC --> Transfer --> Bandpass --> Rectify --> Smooth --> %MVC    |    |
|  |            (to mV)     (10-450Hz)   (|signal|)  (Gaussian)  (/MVC)    |    |
|  +------------------------------------------------------------------------+    |
|                                        |                                       |
|                                        v                                       |
|  +------------------------------------------------------------------------+    |
|  |                    ACTIVE APDF + REST TIME FRAMEWORK                   |    |
|  |                                                                        |    |
|  |   +-----------------+              +-----------------+                 |    |
|  |   |  Active APDF    |              |   Rest Metrics  |                 |    |
|  |   |  (>=0.5% MVC)   |              |   (<0.5% MVC)   |                 |    |
|  |   |                 |              |                 |                 |    |
|  |   |  * P10 (low)    |              |  * Rest %       |                 |    |
|  |   |  * P50 (median) |              |  * Gap freq     |                 |    |
|  |   |  * P90 (high)   |              |  * Sustained    |                 |    |
|  |   +-----------------+              +-----------------+                 |    |
|  |                                                                        |    |
|  |   "How intense when working"    vs    "How much recovery time"        |    |
|  +------------------------------------------------------------------------+    |
+---------------------------------------------------------------------------------+
                                        |
                                        v
+---------------------------------------------------------------------------------+
|                     6. RELATIVE INTENSITY BINNING                               |
|                                                                                 |
|  +------------------------------------------------------------------------+    |
|  |                      WEEKLY BASELINE                                   |    |
|  |   Duration-weighted average of all sessions' Active APDF               |    |
|  |   -> P10 (10th percentile), P50 (median), P90 (90th percentile)       |    |
|  +------------------------------------------------------------------------+    |
|                                        |                                       |
|                                        v                                       |
|  +------------------------------------------------------------------------+    |
|  |                    CLASSIFY EACH 5-SECOND BIN                          |    |
|  |                                                                        |    |
|  |   [GREEN]  Below usual     < P10        "Light work for you"          |    |
|  |   [GREEN]  Typical-low     P10 - P50    "Normal low intensity"        |    |
|  |   [ORANGE] Typical-high    P50 - P90    "Normal high intensity"       |    |
|  |   [RED]    High for you    > P90        "Unusually intense"           |    |
|  |                                                                        |    |
|  +------------------------------------------------------------------------+    |
+---------------------------------------------------------------------------------+
                                        |
                                        v
+---------------------------------------------------------------------------------+
|                          7. OUTPUTS                                             |
|                                                                                 |
|  +------------------+  +------------------+  +------------------+               |
|  |   CSV Tables     |  |   OH Profiles    |  |  Visualizations  |               |
|  |                  |  |     (JSON)       |  |                  |               |
|  | * session_metrics|  |                  |  | * APDF curves    |               |
|  | * daily_metrics  |  | Per-subject file |  | * Histograms     |               |
|  | * weekly_metrics |  | with all EMG     |  | * Timeline plots |               |
|  | * quality_report |  | metrics stored   |  | * Donut charts   |               |
|  +------------------+  +------------------+  +------------------+               |
+---------------------------------------------------------------------------------+
```

---

## Code Organization

```
PrevOccupAI_Plus/
|
+-- main_emg.py                       <-- ENTRY POINT
|
+-- sensors/                          <-- ALL EMG CODE
|   |
|   +-- emg_pipeline.py              <-- Main orchestrator (run_emg_pipeline)
|   |
|   +-- load/                        <-- Data Discovery & Loading
|   |   +-- dataset_loader.py        * discover_daily_acquisitions()
|   |   +-- daily_data_loader.py     * load_daily_acquisitions()
|   |   +-- path_handler.py          * File path resolution
|   |   +-- data_quality.py          * Quality report structures
|   |
|   +-- process/                     <-- Signal Processing
|   |   +-- emg_preprocessing.py     * Filtering, envelope, MVC RMS
|   |   +-- emg_mvc.py               * MVC segment detection
|   |   +-- emg_quality_analysis.py  * ADC saturation, PSD noise checks
|   |
|   +-- metrics/                     <-- Metric Computation
|   |   +-- emg_metrics.py           * APDF, rest metrics, aggregations
|   |   +-- emg_output.py            * CSV export, table building
|   |
|   +-- visualize/                   <-- Plotting
|       +-- emg_research.py          * Signal-based plots (APDF, timeline)
|       +-- emg_oh.py                * OH profile-based plots (donuts)
|
+-- OH_profile/                      <-- JSON Profile Management
    +-- emg_oh_helper.py             * Save EMG metrics to JSON
    +-- constants.py                 * Metric key definitions
```

---

## Key Scientific Framework

### Active APDF + Rest Time (Veiersted et al., 2013)

```
+---------------------------------------------------------------+
|                     EMG Signal (%MVC)                         |
|                                                               |
|  100% |                                                       |
|       |         /--\                      /-\                 |
|   50% |    /----    --\              /----   --\              |
|       | /--            --\    /------           --\           |
|  0.5% +-----------------  ----                    -------------
|       |  ^               ^    ^                   ^           |
|       |  |               |    |                   |           |
|       |  +-- ACTIVE -----+    +------ REST -------+           |
|       |     (>=0.5% MVC)           (<0.5% MVC)                |
|       |                                                       |
|       |  Compute APDF here         Count time here            |
|       |  (intensity when           (recovery/micro-breaks)    |
|       |   actually working)                                   |
+---------------------------------------------------------------+
```

**Key insight**: Traditional APDF mixes "intensity when working" with "rest time", making it hard to interpret. By separating them:

- **Active APDF** answers: "When this person is actually working, how hard?"
- **Rest metrics** answer: "How much recovery time are they getting?"

---

## EMG Metrics (Detailed)

All EMG metrics are computed on **%MVC** signals (per session, per side). The pipeline uses a **rest threshold of 0.5% MVC** to separate active vs rest time. “Active” refers to samples $\ge 0.5\%$ MVC; “rest” refers to samples $< 0.5\%$ MVC.

### 1) Session Metadata (`EMG_session`)

- **`duration_s`**: Total recording duration in seconds.
- **`mvc_peak`**: MVC reference value used for normalization (peak RMS from MVC calibration).
- **`active_duration_s`**: Total time (seconds) with %MVC $\ge 0.5\%$.

### 2) Intensity Metrics (`EMG_intensity`)

- **`mean_percent_mvc`**: Mean %MVC across the whole session.
- **`max_percent_mvc`**: Maximum %MVC observed in the session.
- **`min_percent_mvc`**: Minimum %MVC observed in the session.
- **`iemg_percent_seconds`**: Integrated EMG in %MVC-seconds. Computed as:

$$
\mathrm{iEMG}_{\%MVC\cdot s} = \sum_{t=1}^{N} \left(\%MVC_t\right)\cdot \Delta t
$$

### 3) APDF Percentiles (`EMG_apdf`)

APDF (Amplitude Probability Distribution Function) is computed for:

- **`full`**: includes all samples.
- **`active`**: includes only samples $\ge 0.5\%$ MVC.

For both `full` and `active`, the following percentiles are stored:

- **`p10`**: 10th percentile
- **`p50`**: 50th percentile (median)
- **`p90`**: 90th percentile

### 4) Rest & Recovery (`EMG_rest_recovery`)

- **`rest_percent`**: Percent of time below 0.5% MVC.
- **`gap_frequency_per_minute`**: Number of rest gaps per minute.
- **`gap_count`**: Total number of rest gaps.
- **`max_sustained_activity_s`**: Longest continuous active period (seconds).

**Gap definition**: contiguous rest segments with a minimum duration of 0.25 s.

### 5) Relative Intensity Bins (`EMG_relative_bins`)

Each 5-second bin is classified relative to the **weekly Active APDF baseline** (P10, P50, P90). Percentages are expressed over **active time only**:

- **`below_usual_pct`**: Active time $< P10$ ("light work for you")
- **`typical_low_pct`**: Active time between $P10$ and $P50$
- **`typical_high_pct`**: Active time between $P50$ and $P90$
- **`high_for_you_pct`**: Active time $> P90$ ("unusually intense")

### 6) Aggregates

- **Daily aggregates** (`EMG_daily_metrics`): Same metric groups as above, summarized per day.
- **Weekly aggregates** (`EMG_weekly_metrics`): Same metric groups as above, summarized per week.
- **`session_count`**: number of sessions aggregated.
- **`day_count`**: number of days aggregated.

---

## Example Output: Session Timeline

```
Subject 81 - Left Trapezius - 2024-09-30 09:30

EMG (%MVC)
    |
 50 |     ####                    ########
    |   ##########              ############
 25 |  ############            ##################
    | ##############  ####    ####################
 10 |################################################
    |::::::::::::::::::::::::::::::::::::::::::::::::
    +------------------------------------------------> Time
     09:30        10:00        10:30        11:00

Legend:
    ## High for you (>P90)     :: Rest (<0.5% MVC)
    ## Typical-high (P50-P90)  -- P50 baseline
    ## Typical-low (P10-P50)   -- P10 baseline  
    ## Below usual (<P10)
```

---

## Clinical Relevance

| Metric | What it tells us | Risk indicator |
|--------|------------------|----------------|
| **Active APDF P50** | Typical muscle load when working | High = sustained strain |
| **Rest %** | Recovery time during work | Low = insufficient breaks |
| **Gap frequency** | Number of micro-pauses/min | Low = continuous tension |
| **High-for-you %** | Time above personal P90 | High = overexertion risk |

---

## Running the Pipeline

```python
# In main_emg.py
from main_emg import main

# Process all subjects
main(run_all=True)

# Process specific subjects
main(run_all=True, subject_filter=["81", "82", "83"])

# Quick test with limited data
main(run_all=True, max_subjects=2, max_days_per_subject=1)
```

---

## References

- Veiersted, K. B., et al. (2013). "Assessment of occupational muscle activity." *Applied Ergonomics*.
- Hansson, G. A., et al. (2010). "Validity and reliability of triaxial accelerometers for inclinometry in posture analysis." *Medical and Biological Engineering and Computing*.

---

*Document generated: January 2026*

*PrevOccupAI+ Project - LIBPhys/NOVA School of Science and Technology*
