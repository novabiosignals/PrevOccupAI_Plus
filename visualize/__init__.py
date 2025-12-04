"""Visualization helpers exposed for legacy compatibility."""

from .processing import (  # noqa: F401
    plot_df_data,
    plot_emg_preprocess,
    plot_envelope,
    plot_psd,
    plot_psd_noise_detection,
    plot_walk_detector_output,
)
from .emg_visuals import (
    plot_apdf,
    plot_histogram,
    plot_metric_series,
    plot_session_effort_grid,
    plot_session_effort_stacks,
)

__all__ = [
    "plot_emg_preprocess",
    "plot_walk_detector_output",
    "plot_psd_noise_detection",
    "plot_psd",
    "plot_envelope",
    "plot_df_data",
    "plot_apdf",
    "plot_histogram",
    "plot_metric_series",
    "plot_session_effort_grid",
    "plot_session_effort_stacks",
]
