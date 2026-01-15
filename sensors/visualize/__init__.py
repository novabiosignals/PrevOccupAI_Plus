# Sensor timeline (non-EMG specific)
from .sensor_timeline import generate_sensor_timeline_plot, get_daily_acquisitions_metadata

# EMG Research: In-memory / signal-based visualizations
from .emg_research import (
    plot_apdf,
    plot_envelope,
    plot_histogram,
    plot_metric_series,
    plot_mvc_segments,
    plot_mvc_hybrid_diagnostics,
    plot_session_timeline,
    generate_session_timeline_from_signal,
    process_session_for_timeline,
    create_weekly_baseline,
    compute_rms_envelope,
    classify_into_bins,
)

# EMG OH: OH profile-based visualizations (reads from JSON)
from .emg_oh import (
    generate_emg_plots_from_oh_profiles,
    create_baseline_from_oh_profile,
    plot_day_relative_bins_donut_from_json,
    plot_day_relative_bins_stacks_from_json,
    plot_week_relative_bins_stacks_from_json,
    plot_weekly_active_apdf_trend_from_json,
)

__all__ = [
    # Sensor timeline
    'generate_sensor_timeline_plot',
    'get_daily_acquisitions_metadata',
    # EMG research (in-memory / signal-based)
    'plot_apdf',
    'plot_envelope',
    'plot_histogram',
    'plot_metric_series',
    'plot_mvc_segments',
    'plot_mvc_hybrid_diagnostics',
    'plot_session_timeline',
    'generate_session_timeline_from_signal',
    'process_session_for_timeline',
    'create_weekly_baseline',
    'compute_rms_envelope',
    'classify_into_bins',
    # EMG OH (reads from OH profile JSON)
    'generate_emg_plots_from_oh_profiles',
    'create_baseline_from_oh_profile',
    'plot_day_relative_bins_donut_from_json',
    'plot_day_relative_bins_stacks_from_json',
    'plot_week_relative_bins_stacks_from_json',
    'plot_weekly_active_apdf_trend_from_json',
]