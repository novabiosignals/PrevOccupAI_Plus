"""Signal Processing Package - BACKWARD COMPATIBILITY LAYER.

NOTE: The canonical EMG pipeline implementation is in the `sensors/` package.
This module re-exports the same symbols for backward compatibility with older
code that imports from `signal_processing`.

For new code, import directly from:
    - sensors.process.emg_preprocessing
    - sensors.process.emg_mvc
    - sensors.emg_pipeline

Subpackages:
    archive/    Archived implementations preserved for reference
"""
# Note: pre_process_android has broken import (needs pre_process_muscleban from sensors/process)
# from .pre_process_android import apply_pre_processing_pipeline
# Use sensors.process.apply_pre_processing_pipeline instead

# Import from new locations (sensors package) for backwards compatibility
from sensors.types import PreprocessConfig
from sensors.process.emg_preprocessing import (
    load_opensignals_txt,
    transfer_emg,
    bandpass_filter,
    preprocess_emg,
    tkeo,
    compute_tkeo_envelope,
)
from sensors.process.emg_mvc import (
    _detect_mvc_segments as detect_mvc_segments,
    detect_mvc_segments_hybrid,
    detect_mvc_segments_tkeo,
    pick_mvc,
)
from OH_profile.emg_oh_helper import save_emg_to_oh_profiles as _save_emg_to_oh_profiles

# Pipeline entry points (now in sensors package)
from sensors.emg_pipeline import create_preprocess_config, run_emg_pipeline

__all__ = [
    # EMG pipeline main entry points
    'PreprocessConfig',
    'create_preprocess_config',
    'run_emg_pipeline',
    # Signal preprocessing
    'load_opensignals_txt',
    'transfer_emg',
    'bandpass_filter',
    'preprocess_emg',
    # TKEO functions
    'tkeo',
    'compute_tkeo_envelope',
    # MVC detection
    'detect_mvc_segments',
    'detect_mvc_segments_hybrid',
    'detect_mvc_segments_tkeo',
    'pick_mvc',
    # OH profile helpers
    '_save_emg_to_oh_profiles',
]