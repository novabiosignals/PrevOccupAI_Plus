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

# -------------------------------------------------------------------------------------------------------------------- #
# METADATA SUB-KEYS
# -------------------------------------------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------------------------------------------- #
# SINGLE-INSTANCE QUESTIONNAIRES SUB-KEYS
# -------------------------------------------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------------------------------------------- #
# DAILY QUESTIONNAIRES SUB-KEYS
# -------------------------------------------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------------------------------------------- #
# SENSOR TIMELINE SUB-KEYS
# -------------------------------------------------------------------------------------------------------------------- #
SENSOR_TIMELINE_TIMES_KEY = 'sensor_times'
SENSOR_TIMELINE_MISSING_TIMES_KEY = 'missing_sensor_times'

# -------------------------------------------------------------------------------------------------------------------- #
# HUMAN ACTIVITY SUB-KEYS
# -------------------------------------------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------------------------------------------- #
# HEART RATE SUB-KEYS
# -------------------------------------------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------------------------------------------- #
# POSTURE SUB-KEYS
# -------------------------------------------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------------------------------------------- #
# NOISE SUB-KEYS
# -------------------------------------------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------------------------------------------- #
# EMG SUB-KEYS
# -------------------------------------------------------------------------------------------------------------------- #
# Basic metrics
EMG_DURATION_S_KEY = 'duration_s' # duration of the EMG recording in seconds
EMG_MEAN_PERCENT_MVC_KEY = 'mean_percent_mvc' # mean of the daily EMG %MVC values
EMG_MAX_PERCENT_MVC_KEY = 'max_percent_mvc' # max of the daily EMG %MVC values
EMG_MIN_PERCENT_MVC_KEY = 'min_percent_mvc' # min of the daily EMG %MVC values
EMG_IEMG_PERCENT_SECONDS_KEY = 'iemg_percent_seconds' # integrated EMG in %MVC-seconds
EMG_MVC_PEAK_KEY = 'mvc_peak' # peak MVC value used for normalization

# Traditional APDF percentiles (all samples, for backward compatibility)
EMG_APDF_P10_KEY = 'apdf_p10' # 10th percentile of the APDF
EMG_APDF_P50_KEY = 'apdf_p50' # 50th percentile of the APDF
EMG_APDF_P90_KEY = 'apdf_p90' # 90th percentile of the APDF

# Active APDF percentiles (only samples above rest threshold - intensity when working)
EMG_ACTIVE_APDF_P10_KEY = 'active_apdf_p10' # 10th percentile of active samples only
EMG_ACTIVE_APDF_P50_KEY = 'active_apdf_p50' # 50th percentile of active samples only
EMG_ACTIVE_APDF_P90_KEY = 'active_apdf_p90' # 90th percentile of active samples only

# Rest metrics (relaxation patterns)
EMG_REST_PERCENT_KEY = 'rest_percent' # percentage of time below rest threshold (0.5% MVC)
EMG_GAP_FREQUENCY_PER_MINUTE_KEY = 'gap_frequency_per_minute' # micro-break frequency per minute (better for short sessions)
EMG_MAX_SUSTAINED_ACTIVITY_S_KEY = 'max_sustained_activity_s' # longest continuous active period
EMG_ACTIVE_DURATION_S_KEY = 'active_duration_s' # total time above rest threshold
EMG_GAP_COUNT_KEY = 'gap_count' # total number of rest gaps

# Relative intensity bins (compared to weekly baseline - only computed at weekly level)
EMG_BIN_BELOW_USUAL_PCT_KEY = 'bin_below_usual_pct' # active time below weekly P10
EMG_BIN_TYPICAL_LOW_PCT_KEY = 'bin_typical_low_pct' # active time between P10-P50
EMG_BIN_TYPICAL_HIGH_PCT_KEY = 'bin_typical_high_pct' # active time between P50-P90
EMG_BIN_HIGH_FOR_YOU_PCT_KEY = 'bin_high_for_you_pct' # active time above weekly P90

# Aggregation keys
EMG_DAILY_AGGREGATE_KEY = 'daily_aggregate'
EMG_WEEKLY_AGGREGATE_KEY = 'weekly_aggregate'
EMG_SESSION_COUNT_KEY = 'session_count'
EMG_DAY_COUNT_KEY = 'day_count'



# -------------------------------------------------------------------------------------------------------------------- #
# WRIST ACTIVITIES SUB-KEYS
# -------------------------------------------------------------------------------------------------------------------- #