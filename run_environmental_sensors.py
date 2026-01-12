# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #

# internal imports
import sensors.load as sl
import sensors.metrics as sm
import sensors.visualize as sv
from OH_profile.load import get_OH_profile
from OH_profile.write import save_OH_profile, write_to_OH_profile
from OH_profile.constants import SENSOR_METRICS_KEY, ENVIRONMENT_KEY
# ------------------------------------------------------------------------------------------------------------------- #
# flags
# ------------------------------------------------------------------------------------------------------------------- #
GENERATE_ENV_OH_PROFILE = True
GENERATE_PLOTS = True

# ------------------------------------------------------------------------------------------------------------------- #
# file constants
# ------------------------------------------------------------------------------------------------------------------- #
OH_PROFILE_PATH = r"C:\Users\srale\Desktop\OH_profiles"
PLOTS_OUTPUT_PATH = r"C:\Users\srale\Desktop\timeline_plots"

# ------------------------------------------------------------------------------------------------------------------- #
# program starts here
# ------------------------------------------------------------------------------------------------------------------- #

if GENERATE_ENV_OH_PROFILE:

    # get list with all subject ids
    subject_id_list = sl.get_participant_ids_list(sl.load_participants_info())

    # cycle over the subject id's
    for subject_id in subject_id_list:

        print(f"Extracting environment metrics for subject: {subject_id}")

        # get oh profile
        oh_profile = get_OH_profile(OH_PROFILE_PATH, subject_id)

        # check if the metrics have already been extracted, if not, extract metrics
        if len(oh_profile[SENSOR_METRICS_KEY][ENVIRONMENT_KEY]) < 1:

            # extract environment metrics
            env_metrics_dict = sm.get_environmental_sensors_metrics(subject_id=int(subject_id))

            # write to oh profile
            oh_profile = write_to_OH_profile(oh_profile, main_outer_key=SENSOR_METRICS_KEY,
                                             main_inner_key=ENVIRONMENT_KEY, dict_to_write=env_metrics_dict)

            # save to json
            save_OH_profile(OH_PROFILE_PATH, subject_id, oh_profile)