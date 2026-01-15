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
