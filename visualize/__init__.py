"""Visualization helpers exposed for legacy compatibility."""

from .processing import (  # noqa: F401
    plot_df_data,
    plot_emg_preprocess,
    plot_envelope,
    plot_psd,
    plot_psd_noise_detection,
    plot_walk_detector_output,
)

# EMG visualizations now in sensors.visualize
from sensors.visualize.emg_visuals import (
    plot_apdf,
    plot_histogram,
    plot_metric_series,
    plot_session_rest_active_grid,
    plot_session_rest_active_stacks,
    plot_mvc_segments,
    plot_mvc_hybrid_diagnostics,
)
from sensors.visualize.emg_timeline import (
    plot_session_timeline,
    generate_session_timeline_from_signal,
    process_session_for_timeline,
    create_baseline_from_oh_profile,
    create_weekly_baseline,
)
from sensors.visualize.oh_profile_plots import (
    generate_emg_plots_from_oh_profiles,
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
    "plot_session_rest_active_grid",
    "plot_session_rest_active_stacks",
    # MVC visualization
    "plot_mvc_segments",
    "plot_mvc_hybrid_diagnostics",
    # Timeline visualization
    "plot_session_timeline",
    "generate_session_timeline_from_signal",
    "process_session_for_timeline",
    "create_baseline_from_oh_profile",
    "create_weekly_baseline",
    # OH profile plots
    "generate_emg_plots_from_oh_profiles",
]
