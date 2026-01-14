# EMG Pipeline Code Audit

**Date**: January 12, 2026  
**Purpose**: Map all EMG-related code, identify execution flow, find dead code, duplications, and cleanup opportunities.

---

## 1. Executive Summary

### Current State: ✅ Well Organized
The EMG pipeline is **properly structured** in the `sensors/` package with clear separation of concerns. The codebase has been recently refactored and follows a clean architecture.

### Key Findings
| Category | Status | Notes |
|----------|--------|-------|
| Code Organization | ✅ Good | Single authoritative location (`sensors/`) |
| Dead Code | ⚠️ Minor | 3 unused functions, 1 legacy wrapper package |
| Duplications | ⚠️ Minor | Archive folder has copies (intentional) |
| Backward Compatibility | ✅ Maintained | `signal_processing/` re-exports for legacy code |

---

## 2. Architecture Overview

### Entry Point
```
main_emg.py
└── sensors.emg_pipeline.run_emg_pipeline()
```

### Package Hierarchy
```
sensors/                          # Primary EMG package (AUTHORITATIVE)
├── emg_pipeline.py              # Main orchestration (1031 lines)
├── types.py                     # PreprocessConfig TypedDict
├── load/                        # Data loading & quality
│   ├── dataset_loader.py        # discover_daily_acquisitions, load_day_acquisitions
│   ├── emg_quality.py           # QA checks (ADC saturation, PSD noise, faulty sensor)
│   └── data_quality.py          # FileQualityReport types
├── process/                     # Signal processing
│   ├── emg_preprocessing.py     # Filtering, envelope, MVC peak computation
│   └── emg_mvc.py               # MVC segment detection (hybrid, TKEO, envelope)
├── metrics/                     # Metric computation
│   ├── emg_metrics.py           # APDF, rest metrics, session metrics
│   └── emg_metrics_export.py    # Table building, CSV export, aggregation
└── visualize/                   # EMG-specific plots
    ├── emg_visuals.py           # APDF, histogram, MVC segments
    ├── emg_timeline.py          # Session timeline with intensity zones
    └── oh_profile_plots.py      # Post-JSON visualizations (donut, stacks, trends)

OH_profile/                       # OH profile persistence
├── emg_oh_helper.py             # save_emg_to_oh_profiles, metric accessors
├── constants.py                 # Key names for JSON
├── load/                        # Profile loading utilities
└── write/                       # Profile writing utilities

signal_processing/                # BACKWARD COMPATIBILITY WRAPPER
├── __init__.py                  # Re-exports from sensors/ for legacy imports
├── archive/                     # Historical implementations (reference only)
│   ├── emg_mvc_original.py      # Original MVC detection (777 lines)
│   └── emg_mvc_hybrid_scoring.py # Scoring variant
└── filters.py                   # Possibly legacy (check usage)

visualize/                        # General visualization (not EMG-specific)
└── processing.py                # plot_envelope() - used by emg_pipeline
```

---

## 3. Execution Flow

### Call Graph: main_emg.py → Output Files

```
main(run_all=True)
├── build_day_index()
│   └── discover_daily_acquisitions()         [sensors/load/dataset_loader.py]
│
└── run_emg_pipeline()                         [sensors/emg_pipeline.py]
    │
    ├── FIRST PASS (per day/session)
    │   ├── load_day_acquisitions()           [sensors/load/dataset_loader.py]
    │   │   └── detect_adc_saturation()       [sensors/load/emg_quality.py]
    │   │
    │   └── _process_day()
    │       ├── pick_mvc()                    [sensors/process/emg_mvc.py]
    │       ├── _extract_emg_mv()             [sensors/process/emg_preprocessing.py]
    │       ├── _compute_envelope()           [sensors/process/emg_preprocessing.py]
    │       │
    │       ├── MVC Quality Checks:
    │       │   ├── detect_adc_saturation()   [sensors/load/emg_quality.py]
    │       │   ├── is_faulty_mban()          [sensors/load/emg_quality.py]
    │       │   ├── assess_mvc_signal_quality() [sensors/load/emg_quality.py]
    │       │   └── detect_psd_noise()        [sensors/load/emg_quality.py]
    │       │
    │       ├── detect_mvc_segments_hybrid()  [sensors/process/emg_mvc.py]
    │       │   └── _detect_mvc_segments()    (fallback)
    │       │
    │       ├── compute_mvc_peak_rms()        [sensors/process/emg_preprocessing.py]
    │       │
    │       └── Per Session:
    │           ├── Session Quality Checks (same as MVC)
    │           ├── compute_session_metrics() [sensors/metrics/emg_metrics.py]
    │           │   ├── compute_apdf()
    │           │   ├── compute_active_apdf()
    │           │   └── compute_rest_metrics()
    │           │
    │           └── _save_session_visuals()
    │               ├── plot_apdf()           [sensors/visualize/emg_visuals.py]
    │               ├── plot_histogram()
    │               └── plot_envelope()       [visualize/processing.py]
    │
    ├── SECOND PASS (relative intensity bins)
    │   └── _add_relative_intensity_bins()
    │       ├── compute_relative_intensity_bins() [sensors/metrics/emg_metrics.py]
    │       └── generate_session_timeline_from_signal() [sensors/visualize/emg_timeline.py]
    │
    ├── build_tables()                        [sensors/metrics/emg_metrics_export.py]
    │   ├── aggregate_daily_metrics()         [sensors/metrics/emg_metrics.py]
    │   ├── aggregate_weekly_metrics()
    │   └── compute_percentage_changes()
    │
    ├── write_tables()                        [sensors/metrics/emg_metrics_export.py]
    │   └── Outputs: session_metrics.csv, daily_metrics.csv, weekly_metrics.csv
    │
    ├── export_mvc_quality_summary()          [sensors/metrics/emg_metrics_export.py]
    │
    ├── save_emg_to_oh_profiles()             [OH_profile/emg_oh_helper.py]
    │   └── Outputs: {subject_id}_OH_profile.json
    │
    └── generate_emg_plots_from_oh_profiles() [sensors/visualize/oh_profile_plots.py]
        ├── plot_day_relative_bins_donut_from_json()
        ├── plot_day_relative_bins_stacks_from_json()
        ├── plot_week_relative_bins_stacks_from_json()
        └── plot_weekly_active_apdf_trend_from_json()
```

---

## 4. Function Inventory

### sensors/emg_pipeline.py (1031 lines)
| Function | Lines | Called By | Status |
|----------|-------|-----------|--------|
| `create_preprocess_config()` | 95-109 | main_emg.py | ✅ Used |
| `run_emg_pipeline()` | 111-234 | main_emg.py | ✅ Used |
| `_add_relative_intensity_bins()` | 240-388 | run_emg_pipeline | ✅ Used |
| `_process_day()` | 393-853 | run_emg_pipeline | ✅ Used |
| `_convert_date_to_dd_mm_yyyy()` | 856-868 | multiple | ✅ Used |
| `_generate_plots_for_loading_rejections()` | 871-930 | run_emg_pipeline | ✅ Used |
| `_build_metadata()` | 933-968 | _process_day | ✅ Used |
| `_save_session_visuals()` | 971-1023 | _process_day | ✅ Used |

### sensors/load/emg_quality.py (915 lines)
| Function | Lines | Called By | Status |
|----------|-------|-----------|--------|
| `detect_adc_saturation()` | 82-115 | emg_pipeline, data_quality | ✅ Used |
| `is_faulty_mban()` | 118-146 | emg_pipeline | ✅ Used |
| `detect_psd_noise()` | 149-200 | emg_pipeline | ✅ Used |
| `assess_mvc_signal_quality()` | 367-421 | emg_pipeline | ✅ Used |
| `run_emg_quality_checks()` | 424-479 | NONE | ⚠️ **UNUSED** |
| `plot_psd_quality_assessment()` | 554-683 | save_quality_assessment_plot | ✅ Used (internal) |
| `save_quality_assessment_plot()` | 686-733 | emg_pipeline | ✅ Used |
| `plot_adc_saturation_assessment()` | 736-867 | save_adc_saturation_plot | ✅ Used (internal) |
| `save_adc_saturation_plot()` | 870-915 | emg_pipeline | ✅ Used |

### sensors/metrics/emg_metrics.py (540 lines)
| Function | Lines | Called By | Status |
|----------|-------|-----------|--------|
| `compute_apdf()` | 44-74 | compute_session_metrics | ✅ Used |
| `compute_active_apdf()` | 77-122 | compute_session_metrics | ✅ Used |
| `compute_rest_metrics()` | 125-183 | compute_session_metrics | ✅ Used |
| `compute_relative_intensity_bins()` | 238-314 | emg_pipeline | ✅ Used |
| `compute_session_metrics()` | 317-395 | emg_pipeline | ✅ Used |
| `aggregate_daily_metrics()` | 398-443 | emg_metrics_export | ✅ Used |
| `aggregate_weekly_metrics()` | 446-504 | emg_metrics_export | ✅ Used |
| `compute_percentage_changes()` | 507-540 | emg_metrics_export | ✅ Used |

### sensors/process/emg_preprocessing.py (~340 lines)
| Function | Lines | Called By | Status |
|----------|-------|-----------|--------|
| `load_opensignals_txt()` | 28-87 | compat exports | ⚠️ Not used in pipeline |
| `_compute_envelope()` | 90-118 | emg_pipeline | ✅ Used |
| `_extract_emg_mv()` | 121-146 | emg_pipeline | ✅ Used |
| `_to_millivolts()` | 149-169 | _extract_emg_mv | ✅ Used |
| `transfer_emg()` | 172-182 | compat exports | ⚠️ Not used in pipeline |
| `compute_mvc_peak_rms()` | 185-231 | emg_pipeline | ✅ Used |
| `bandpass_filter()` | 234-250 | multiple | ✅ Used |
| `preprocess_emg()` | 253-277 | compat exports | ⚠️ **UNUSED** (legacy) |
| `tkeo()` | 280-303 | compute_tkeo_envelope | ✅ Used |
| `compute_tkeo_envelope()` | 306-340 | emg_mvc | ✅ Used |

### sensors/process/emg_mvc.py (~800 lines)
| Function | Lines | Called By | Status |
|----------|-------|-----------|--------|
| `_otsu_threshold()` | 29-81 | detect_mvc_segments_hybrid | ✅ Used |
| `_robust_sigma()` | 84-128 | detect_mvc_segments_hybrid | ✅ Used |
| `_select_quiet_baseline()` | 131-221 | detect_mvc_segments_hybrid | ✅ Used |
| `_segments_from_binary()` | 224-284 | detect_mvc_segments_hybrid | ✅ Used |
| `_build_segments_for_threshold()` | 287-301 | detect_mvc_segments_hybrid | ✅ Used |
| `_score_segmentation()` | 304-436 | detect_mvc_segments_hybrid | ✅ Used |
| `_detect_mvc_segments()` | 439-483 | emg_pipeline, hybrid fallback | ✅ Used |
| `detect_mvc_segments_hybrid()` | 486-682 | emg_pipeline | ✅ Used |
| `detect_mvc_segments_tkeo()` | 685-758 | compat exports | ⚠️ **UNUSED** |
| `pick_mvc()` | 761-800 | emg_pipeline | ✅ Used |

### sensors/visualize/emg_visuals.py (~480 lines)
| Function | Lines | Called By | Status |
|----------|-------|-----------|--------|
| `plot_apdf()` | 55-84 | emg_pipeline | ✅ Used |
| `plot_histogram()` | 87-109 | emg_pipeline | ✅ Used |
| `plot_metric_series()` | 112-140 | compat exports | ⚠️ **UNUSED** |
| `plot_session_rest_active_grid()` | 143-206 | compat exports | ⚠️ **UNUSED** |
| `plot_session_rest_active_stacks()` | 209-319 | compat exports | ⚠️ **UNUSED** |
| `plot_mvc_segments()` | 366-413 | emg_pipeline | ✅ Used |
| `plot_mvc_hybrid_diagnostics()` | 416-480 | emg_pipeline | ✅ Used |

---

## 5. Dead Code Identified

### Definitely Unused
| Function | Location | Recommendation |
|----------|----------|----------------|
| `run_emg_quality_checks()` | sensors/load/emg_quality.py | **Remove** - orchestration function never integrated |
| `preprocess_emg()` | sensors/process/emg_preprocessing.py | **Keep** - useful for standalone preprocessing |
| `detect_mvc_segments_tkeo()` | sensors/process/emg_mvc.py | **Keep** - may be useful for experimentation |
| `plot_metric_series()` | sensors/visualize/emg_visuals.py | **Remove** - replaced by oh_profile_plots |
| `plot_session_rest_active_grid()` | sensors/visualize/emg_visuals.py | **Remove** - replaced by JSON-based plots |
| `plot_session_rest_active_stacks()` | sensors/visualize/emg_visuals.py | **Remove** - replaced by JSON-based plots |

### Legacy Compatibility Exports (Keep)
| Function | Location | Reason to Keep |
|----------|----------|----------------|
| `load_opensignals_txt()` | emg_preprocessing.py | May be used by analysis notebooks |
| `transfer_emg()` | emg_preprocessing.py | May be used by analysis notebooks |

---

## 6. Duplication Analysis

### Intentional (Archive)
| File | Duplicates | Status |
|------|------------|--------|
| `signal_processing/archive/emg_mvc_original.py` | sensors/process/emg_mvc.py | ✅ Intentional archive |
| `signal_processing/archive/emg_mvc_hybrid_scoring.py` | sensors/process/emg_mvc.py | ✅ Intentional archive |

### Minor Duplication
| Pattern | Locations | Recommendation |
|---------|-----------|----------------|
| `ensure_parent()` | emg_visuals.py, oh_profile_plots.py | Consolidate to `sensors/visualize/utils.py` |
| `_annotate_missing()` | emg_visuals.py, oh_profile_plots.py | Consolidate to `sensors/visualize/utils.py` |

---

## 7. Package Dependencies

### Internal Import Graph
```
main_emg.py
├── constants.py
├── sensors/
│   ├── emg_pipeline.py
│   │   ├── sensors/load/data_quality.py
│   │   ├── sensors/load/dataset_loader.py
│   │   ├── sensors/load/emg_quality.py
│   │   ├── sensors/metrics/emg_metrics.py
│   │   ├── sensors/metrics/emg_metrics_export.py
│   │   ├── sensors/process/emg_mvc.py
│   │   ├── sensors/process/emg_preprocessing.py
│   │   ├── sensors/visualize/emg_timeline.py
│   │   ├── sensors/visualize/emg_visuals.py
│   │   ├── sensors/visualize/oh_profile_plots.py
│   │   ├── OH_profile/emg_oh_helper.py
│   │   └── visualize/processing.py  ← Cross-package import
│   └── types.py
└── OH_profile/
    ├── constants.py
    ├── load/
    └── write/
```

### Cross-Package Issue
- `sensors/emg_pipeline.py` imports from `visualize/processing.py`
- **Recommendation**: Move `plot_envelope()` to `sensors/visualize/` or create `sensors/visualize/utils.py`

---

## 8. Recommendations

### Immediate Actions (Low Risk)
1. **Remove dead visualization functions** from `emg_visuals.py`:
   - `plot_metric_series()`
   - `plot_session_rest_active_grid()`
   - `plot_session_rest_active_stacks()`

2. **Consolidate utility functions**:
   - Create `sensors/visualize/utils.py`
   - Move `ensure_parent()`, `_annotate_missing()`, `plot_envelope()` there

3. **Document `run_emg_quality_checks()`**:
   - Either remove or document as "available for custom pipelines"

### Medium-Term Improvements
1. **Type hints**: Add comprehensive type hints to all functions
2. **Unit tests**: Create tests for metric computation functions
3. **Config validation**: Add validation to `PreprocessConfig`

### Low Priority (Nice to Have)
1. Consider removing `signal_processing/` wrapper if no legacy code uses it
2. Add docstring examples to metric functions
3. Create Jupyter notebook demonstrating standalone function usage

---

## 9. Conclusion

The EMG pipeline is **well-structured and production-ready**. The main `sensors/` package is the single source of truth, with `signal_processing/` providing backward compatibility.

**Key Strengths**:
- Clear separation of concerns (load → process → metrics → visualize)
- Two-pass architecture well documented
- Quality checks comprehensive and systematic
- OH profile integration clean

**Minor Issues**:
- ~6 unused functions (mostly legacy plot functions)
- 1 cross-package import (`visualize/processing.py`)
- Some utility function duplication

**Overall Assessment**: The code is ready for presentation. The unused functions are not harmful and can be cleaned up at leisure.

---

*Generated by EMG Pipeline Code Audit*
