from .sensor_timeline import generate_sensor_timeline_plot, get_daily_acquisitions_metadata
from .heart_rate import plot_hr_timeline_per_acquisition, plot_weekly_hr_data, plot_hr_ranges
from .noise import plot_noise_metrics_per_week
from .environmental_sensors import plot_environment_data
from .wrist_activities import plot_wrist_movements_heatmaps
from .plot_utils import get_weekday_name
from .human_activities import plot_activity_distributions_ospaq_vs_real, plot_activity_timeline_per_day, plot_steps_and_distance_per_day
from .posture import plot_postural_displacements, plot_postural_displacements_grid

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
    'generate_sensor_timeline_plot',
    'get_daily_acquisitions_metadata',
    'plot_hr_timeline_per_acquisition',
    'plot_weekly_hr_data',
    'plot_noise_metrics_per_week',
    'plot_hr_ranges',
    'plot_environment_data',
    'plot_wrist_movements_heatmaps',
    'get_weekday_name',
    'plot_activity_timeline_per_day',
    'plot_activity_distributions_ospaq_vs_real',
    'plot_steps_and_distance_per_day',
    'plot_postural_displacements',
    'plot_postural_displacements_grid'
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