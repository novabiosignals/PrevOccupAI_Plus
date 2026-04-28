# -------------------------------------------------------------------------------------------------------------------- #
# FILE CONSTANTS
# -------------------------------------------------------------------------------------------------------------------- #
# file suffix
JSON_FILE_SUFFIX = '_OH_profile.json'

# -------------------------------------------------------------------------------------------------------------------- #
# MAIN KEYS
# -------------------------------------------------------------------------------------------------------------------- #
# json dict keys
METADATA_KEY = 'meta_data'

SINGLE_INSTANCE_QUESTIONNAIRE_KEY = 'single_instance_questionnaires'
PERSONAL_DOMAIN_KEY = 'personal'
BIOMECHANICAL_DOMAIN_KEY = 'biomechanical'
PSYCHOSOCIAL_DOMAIN_KEY = 'psychosocial'
ENVIRONMENTAL_DOMAIN_KEY = 'environmental'

DAILY_QUESTIONNAIRE_DOMAIN_KEY = 'daily_questionnaires'
WORKLOAD_DOMAIN_KEY = 'workload'
PAIN_DOMAIN_KEY = 'pain'

SENSOR_METRICS_KEY = 'sensor_metrics'
SENSOR_TIMELINE_KEY = 'sensor_timeline'
HAR_KEY = 'human_activities'
HEART_RATE_KEY = 'heart_rate'
POSTURE_KEY = 'posture'
NOISE_KEY = 'noise'
EMG_KEY = 'emg'
WRIST_KEY = 'wrist_activities'
ENVIRONMENT_KEY = 'environment'

# -------------------------------------------------------------------------------------------------------------------- #
# METADATA SUB-KEYS
# -------------------------------------------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------------------------------------------- #
# SINGLE-INSTANCE QUESTIONNAIRES SUB-KEYS
# -------------------------------------------------------------------------------------------------------------------- #
PSYCHOSOCIAL_COPSOQ_WORK_TYPE_KEY = 'copsoq_work_type'
PSYCHOSOCIAL_COPSOQ_POPULATION_KEY = 'copsoq_population'

PSYCHOSOCIAL_MUEQ_WORK_TYPE_KEY = 'mueq_work_type'
PSYCHOSOCIAL_MUEQ_POPULATION_KEY = 'mueq_population'

# -------------------------------------------------------------------------------------------------------------------- #
# DAILY QUESTIONNAIRES SUB-KEYS
# -------------------------------------------------------------------------------------------------------------------- #
WORKLOAD_SCORING_KEY = 'scoring'

# -------------------------------------------------------------------------------------------------------------------- #
# SENSOR TIMELINE SUB-KEYS
# -------------------------------------------------------------------------------------------------------------------- #
SENSOR_TIMELINE_TIMES_KEY = 'sensor_times'
SENSOR_TIMELINE_MISSING_TIMES_KEY = 'missing_sensor_times'
SENSOR_TIMELINE_START_TIMES_KEY = 'start_times'
SENSOR_TIMELINE_END_TIMES_KEY = 'end_times'

# -------------------------------------------------------------------------------------------------------------------- #
# HUMAN ACTIVITY SUB-KEYS
# -------------------------------------------------------------------------------------------------------------------- #
HAR_TIMELINE_KEY = 'HAR_timeline'
HAR_DURATIONS_KEY = 'HAR_durations'
HAR_DISTRIBUTIONS_KEY = 'HAR_distributions'
HAR_STEPS_KEY = 'HAR_steps'

HAR_DISTANCE_KEY = 'distance_walked_m'
HAR_NUM_STEPS_KEY = 'num_steps'

# -------------------------------------------------------------------------------------------------------------------- #
# HEART RATE SUB-KEYS
# -------------------------------------------------------------------------------------------------------------------- #
HR_RELATIVE_BASE_KEY = 'HR_relative_base'
# HR classes
HR_NORMAL_KEY = 'Normal'
HR_POTENTIALLY_ELEVATED_KEY = 'Ligeiramente elevado'
HR_ELEVATED_KEY = 'Elevado'

# keys for the inner dictionaries with the HR features
HR_DISTRIBUTIONS_KEY = 'HR_distributions'
HR_TIMELINE_KEY = 'HR_timeline'
HR_RATIO_STATS_KEY = 'HR_ratio_stats'
HR_BPM_STATS_KEY = 'HR_BPM_stats'
HR_MIN_KEY = 'HR_min'
HR_MAX_KEY = 'HR_max'

# -------------------------------------------------------------------------------------------------------------------- #
# POSTURE SUB-KEYS
# -------------------------------------------------------------------------------------------------------------------- #
POSTURE_DATA_PATH_KEY = 'posture_data_path'
POSTURE_AP_RANGE_KEY = 'posture_ap_range'
POSTURE_ML_RANGE_KEY = 'posture_ml_range'
POSTURE_RANGE_RATIO_KEY = 'posture_ratio_range'
POSTURE_SWAY_LENGTH_KEY = 'posture_total_sway_length'
POSTURE_SWAY_VELOCITY_KEY = 'posture_average_sway_velocity'
POSTURE_SWAY_AREA_KEY = 'posture_sway_area_per_second'
POSTURE_ELLIPSE_KEY = 'posture_95_confidence_ellipse_area'

# -------------------------------------------------------------------------------------------------------------------- #
# NOISE SUB-KEYS
# -------------------------------------------------------------------------------------------------------------------- #
NOISE_NEAR_SILENCE_KEY = 'Silencioso'
NOISE_LOW_KEY = 'Ruído baixo'
NOISE_DISTURBING_KEY = 'Ruído incomodativo'
NOISE_HIGH_KEY = 'Ruído elevado'

NOISE_STATISTICS_KEY = 'Noise_statistics'
NOISE_DURATIONS_KEY = 'Noise_durations'
NOISE_DISTRIBUTIONS_NOISE = 'Noise_distributions'

NOISE_TIMELINE_KEY = 'Noise_timeline'

# -------------------------------------------------------------------------------------------------------------------- #
# EMG SUB-KEYS
# -------------------------------------------------------------------------------------------------------------------- #
# Top-level category keys (for nested structure)
EMG_SESSION_GROUP_KEY = 'EMG_session'           # Session metadata (duration, mvc_peak, active_duration)
EMG_INTENSITY_GROUP_KEY = 'EMG_intensity'       # Intensity metrics (mean/max/min %MVC, iEMG)
EMG_APDF_GROUP_KEY = 'EMG_apdf'                 # APDF percentiles (full and active)
EMG_REST_GROUP_KEY = 'EMG_rest_recovery'        # Rest/recovery metrics (rest%, gaps, sustained activity)
EMG_RELATIVE_BINS_GROUP_KEY = 'EMG_relative_bins'  # Relative intensity bins (vs weekly baseline)

# Within EMG_session
EMG_DURATION_S_KEY = 'duration_s'               # duration of the EMG recording in seconds
EMG_MVC_PEAK_KEY = 'mvc_peak'                   # peak MVC value used for normalization
EMG_ACTIVE_DURATION_S_KEY = 'active_duration_s' # total time above rest threshold

# Within EMG_intensity
EMG_MEAN_PERCENT_MVC_KEY = 'mean_percent_mvc'   # mean of the daily EMG %MVC values
EMG_MAX_PERCENT_MVC_KEY = 'max_percent_mvc'     # max of the daily EMG %MVC values
EMG_MIN_PERCENT_MVC_KEY = 'min_percent_mvc'     # min of the daily EMG %MVC values
EMG_IEMG_PERCENT_SECONDS_KEY = 'iemg_percent_seconds'  # integrated EMG in %MVC-seconds

# Within EMG_apdf (nested: full/active)
EMG_APDF_FULL_KEY = 'full'                      # Traditional APDF (all samples)
EMG_APDF_ACTIVE_KEY = 'active'                  # Active APDF (only samples above rest threshold)
EMG_APDF_P10_KEY = 'p10'                        # 10th percentile
EMG_APDF_P50_KEY = 'p50'                        # 50th percentile (median)
EMG_APDF_P90_KEY = 'p90'                        # 90th percentile

# Within EMG_rest_recovery
EMG_REST_PERCENT_KEY = 'rest_percent'           # percentage of time below rest threshold (0.5% MVC)
EMG_GAP_FREQUENCY_PER_MINUTE_KEY = 'gap_frequency_per_minute'  # micro-break frequency per minute
EMG_MAX_SUSTAINED_ACTIVITY_S_KEY = 'max_sustained_activity_s'  # longest continuous active period
EMG_GAP_COUNT_KEY = 'gap_count'                 # total number of rest gaps

# Within EMG_relative_bins
EMG_BIN_BELOW_USUAL_PCT_KEY = 'below_usual_pct'    # active time below weekly P10
EMG_BIN_TYPICAL_LOW_PCT_KEY = 'typical_low_pct'    # active time between P10-P50
EMG_BIN_TYPICAL_HIGH_PCT_KEY = 'typical_high_pct'  # active time between P50-P90
EMG_BIN_HIGH_FOR_YOU_PCT_KEY = 'high_for_you_pct'  # active time above weekly P90

# Aggregation keys
EMG_DAILY_AGGREGATE_KEY = 'EMG_daily_metrics'
EMG_WEEKLY_AGGREGATE_KEY = 'EMG_weekly_metrics'
EMG_SESSION_COUNT_KEY = 'session_count'
EMG_DAY_COUNT_KEY = 'day_count'

# Legacy flat keys (for backward compatibility with existing code reading DataFrames)
# These are still used in pandas DataFrames, only the OH profile JSON uses nested structure
EMG_LEGACY_APDF_P10_KEY = 'apdf_p10'
EMG_LEGACY_APDF_P50_KEY = 'apdf_p50'
EMG_LEGACY_APDF_P90_KEY = 'apdf_p90'
EMG_LEGACY_ACTIVE_APDF_P10_KEY = 'active_apdf_p10'
EMG_LEGACY_ACTIVE_APDF_P50_KEY = 'active_apdf_p50'
EMG_LEGACY_ACTIVE_APDF_P90_KEY = 'active_apdf_p90'
EMG_LEGACY_BIN_BELOW_USUAL_PCT_KEY = 'bin_below_usual_pct'
EMG_LEGACY_BIN_TYPICAL_LOW_PCT_KEY = 'bin_typical_low_pct'
EMG_LEGACY_BIN_TYPICAL_HIGH_PCT_KEY = 'bin_typical_high_pct'
EMG_LEGACY_BIN_HIGH_FOR_YOU_PCT_KEY = 'bin_high_for_you_pct'



# -------------------------------------------------------------------------------------------------------------------- #
# WRIST ACTIVITIES SUB-KEYS
# -------------------------------------------------------------------------------------------------------------------- #
WRIST_SIGNIFICANT_ACC_PERC_KEY = 'WRIST_significant_acceleration_percentage'
WRIST_SIGNIFICANT_ROT_PERC_KEY = 'WRIST_significant_rotation_percentage'

# -------------------------------------------------------------------------------------------------------------------- #
# ENVIRONMENT SUB-KEYS
# -------------------------------------------------------------------------------------------------------------------- #
# these constants should have the following format: f'{physical_quantity}_....._{unit}'
ENV_ILLUMINANCE_KEY = 'Iluminância_mean_lux'
ENV_CO2_KEY = 'CO2_ppm'
ENV_CO_KEY = 'CO_ppm'
ENV_COV_KEY = 'COV_ppm'
ENV_PM10_KEY = 'PM10_particles_ug/m3'
ENV_PM025_KEY = 'PM2.5_particles_ug/m3'
ENV_TEMPERATURE_KEY = 'Temperatura_Celsius'
ENV_REL_HUMIDITY_KEY = 'Humidade_relativa_percentagem'


# -------------------------------------------------------------------------------------------------------------------- #
# GENERAL
# -------------------------------------------------------------------------------------------------------------------- #
DURATION_SECONDS_SUFFIX_KEY = '_duration_sec'
SESSION_KEY = 'Session'