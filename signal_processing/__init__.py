# Note: pre_process_android has broken import (needs pre_process_muscleban from sensors/process)
# from .pre_process_android import apply_pre_processing_pipeline
# Use sensors.process.apply_pre_processing_pipeline instead

from .emg_types import PreprocessConfig
from .emg_pipeline import create_preprocess_config, run_emg_pipeline
from .emg_preprocessing import (
    load_opensignals_txt,
    transfer_emg,
    bandpass_filter,
    preprocess_emg,
    tkeo,
    compute_tkeo_envelope,
)
from .emg_mvc import (
    _detect_mvc_segments as detect_mvc_segments,
    detect_mvc_segments_tkeo,
    detect_mvc_segments_hybrid,
    pick_mvc,
)
from .emg_oh_helper import _save_emg_to_oh_profiles

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
    'detect_mvc_segments_tkeo',
    'detect_mvc_segments_hybrid',
    'pick_mvc',
    # OH profile helpers
    '_save_emg_to_oh_profiles',
]