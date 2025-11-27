"""
Utility functions for Occupational Health (OH) Profiles

Available Functions
-------------------
[Public]
generate_OH_profile_json_skeleton(): generates the basic json skeleton for the OH profile
-------------------

[Private]

-------------------
"""

# -------------------------------------------------------------------------------------------------------------------- #
# imports
# -------------------------------------------------------------------------------------------------------------------- #

# -------------------------------------------------------------------------------------------------------------------- #
# constants
# -------------------------------------------------------------------------------------------------------------------- #
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
# public functions
# -------------------------------------------------------------------------------------------------------------------- #
def generate_OH_profile_json_skeleton():
    """
    generates the basic json skeleton for the OH profile. This skeleton is can be subsequently filled with the
    corresponding data using the respective keys
    :return:
    """

    # define json skeleton (as dictionary)
    oh_profile = {
        METADATA_KEY: {},

        SINGLE_INSTANCE_QUESTIONNAIRE_KEY: {
            PERSONAL_DOMAIN_KEY: {},
            BIOMECHANICAL_DOMAIN_KEY: {},
            PSYCHOSOCIAL_DOMAIN_KEY: {},
            ENVIRONMENTAL_DOMAIN_KEY: {}
        },

        DAILY_QUESTIONNAIRE_DOMAIN_KEY: {
            WORKLOAD_DOMAIN_KEY: {},
            PAIN_DOMAIN_KEY: {}
        },

        SENSOR_METRICS_KEY: {
            SENSOR_TIMELINE_KEY: {},
            HAR_KEY: {},
            HEART_RATE_KEY: {},
            POSTURE_KEY: {},
            NOISE_KEY: {},
            EMG_KEY: {},
            WRIST_KEY: {}
        }
    }

    return oh_profile

# -------------------------------------------------------------------------------------------------------------------- #
# private functions
# -------------------------------------------------------------------------------------------------------------------- #