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
EMG_DURATION_S_KEY = 'duration_s' # duration of the EMG recording in seconds
EMG_MEAN_PERCENT_MVC_KEY = 'mean_percent_mvc' # mean of the daily EMG %MVC values
EMG_MAX_PERCENT_MVC_KEY = 'max_percent_mvc' # max of the daily EMG %MVC values
EMG_MIN_PERCENT_MVC_KEY = 'min_percent_mvc' # min of the daily EMG %MVC values
EMG_IEMG_PERCENT_SECONDS_KEY = 'iemg_percent_seconds' # integrated EMG in %MVC-seconds
EMG_MVC_PEAK_KEY = 'mvc_peak' # peak MVC value used for normalization
EMG_APDF_P10_KEY = 'apdf_p10' # 10th percentile of the amplitude probability distribution function
EMG_APDF_P50_KEY = 'apdf_p50' # 50th percentile of the amplitude probability distribution function
EMG_APDF_P90_KEY = 'apdf_p90' # 90th percentile of the amplitude probability distribution function
EMG_EFFORT_LOW_PCT_KEY = 'effort_low_pct' # percentage of time in low effort band
EMG_EFFORT_MODERATE_PCT_KEY = 'effort_moderate_pct' # percentage of time in moderate effort band
EMG_EFFORT_HIGH_PCT_KEY = 'effort_high_pct' # percentage of time in high effort band
EMG_EFFORT_OVER100_PCT_KEY = 'effort_over100_pct' # percentage of time in over 100% effort band
EMG_EFFORT_LOW_MIN_KEY = 'effort_low_min' # minutes in low effort band
EMG_EFFORT_MODERATE_MIN_KEY = 'effort_moderate_min' # minutes in moderate effort band
EMG_EFFORT_HIGH_MIN_KEY = 'effort_high_min' # minutes in high effort band
EMG_EFFORT_OVER100_MIN_KEY = 'effort_over100_min' # minutes in over 100% effort band
EMG_DAILY_AGGREGATE_KEY = 'daily_aggregate'
EMG_WEEKLY_AGGREGATE_KEY = 'weekly_aggregate'
EMG_SESSION_COUNT_KEY = 'session_count'
EMG_DAY_COUNT_KEY = 'day_count'



# -------------------------------------------------------------------------------------------------------------------- #
# WRIST ACTIVITIES SUB-KEYS
# -------------------------------------------------------------------------------------------------------------------- #