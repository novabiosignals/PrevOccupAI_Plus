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
NOISE_DURATION_SECONDS_SUFFIX_KEY = '_duration_sec'
NOISE_TIMELINE_KEY = 'Noise_timeline'

# -------------------------------------------------------------------------------------------------------------------- #
# EMG SUB-KEYS
# -------------------------------------------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------------------------------------------- #
# WRIST ACTIVITIES SUB-KEYS
# -------------------------------------------------------------------------------------------------------------------- #


# -------------------------------------------------------------------------------------------------------------------- #
# ENVIRONMENT SUB-KEYS
# -------------------------------------------------------------------------------------------------------------------- #
# these constants should have the following format: f'{physical_quantity}_....._{unit}'
ENV_ILLUMINANCE_KEY = 'Illuminance_mean_lux'
ENV_CO2_KEY = 'CO2_ppm'
ENV_CO_KEY = 'CO_ppm'
ENV_COV_KEY = 'COV_ppm'
ENV_PM10_KEY = 'PM10_particles_ug/m3'
ENV_PM025_KEY = 'PM2.5_particles_ug/m3'
ENV_TEMPERATURE_KEY = 'Temperature_Celsius'
ENV_REL_HUMIDITY_KEY = 'Humidity_relative_percentage'