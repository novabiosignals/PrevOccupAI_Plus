# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #

# internal imports
import questionnaires.metrics as qm
import questionnaires.visualize as qv
import sensors.load as sl
from OH_profile.load import get_OH_profile
from OH_profile.write import save_OH_profile, write_to_OH_profile
from OH_profile.constants import DAILY_QUESTIONNAIRE_DOMAIN_KEY, PAIN_DOMAIN_KEY
# ------------------------------------------------------------------------------------------------------------------- #
# constants
# ------------------------------------------------------------------------------------------------------------------- #


DRIVE = 'E'
OH_PROFILE_PATH = f"{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\OH_profiles"
PLOTS_OUTPUT_PATH = f"{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\OH_plots"
PAIN_DATA_PATH = f"{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\data\\pain_data"
GENERATE_OH_PROFILE = True
GENERATE_PLOTS = True
RERUN_OH_PAIN = True
# ------------------------------------------------------------------------------------------------------------------- #
# program starts here
# ------------------------------------------------------------------------------------------------------------------- #

# get list with all subject ids
subject_id_list = sl.get_participant_ids_list(sl.load_participants_info())

if GENERATE_OH_PROFILE:

    # cycle over the subject id's
    for subject_id in subject_id_list:

        # open OH profile
        oh_profile = get_OH_profile(OH_PROFILE_PATH, subject_id)

        if RERUN_OH_PAIN:

            # extract metrics
            metrics_dict = qm.get_pain_metrics_per_day(folder_path=PAIN_DATA_PATH, subject_id=str(subject_id))

            # save oh profile
            oh_profile = write_to_OH_profile(oh_profile, main_outer_key=DAILY_QUESTIONNAIRE_DOMAIN_KEY,
                                             main_inner_key=PAIN_DOMAIN_KEY, dict_to_write=metrics_dict)

            # save to json
            save_OH_profile(OH_PROFILE_PATH, subject_id, oh_profile)

        if GENERATE_PLOTS:

            print(f"Generating pain plot for subject: {subject_id}")
            qv.generate_pain_plots(folder_path=PAIN_DATA_PATH, output_folder=PLOTS_OUTPUT_PATH, subject_id=str(subject_id))

