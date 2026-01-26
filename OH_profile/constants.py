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