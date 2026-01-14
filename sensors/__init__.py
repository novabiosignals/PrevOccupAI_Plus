"""Sensors package - load, process, and analyze sensor data.

Subpackages:
- load: Data loading and filesystem discovery
- process: Signal processing and preprocessing
- metrics: Metric computation and aggregation
- visualize: Sensor-specific visualization
- impute: Data imputation utilities
"""

from .types import PreprocessConfig
from .emg_pipeline import create_preprocess_config, run_emg_pipeline

__all__ = [
    'PreprocessConfig',
    'create_preprocess_config',
    'run_emg_pipeline',
]
