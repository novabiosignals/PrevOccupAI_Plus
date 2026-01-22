# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import os



# internal imports
import questionnaires
from utils import extract_group_from_path, extract_device_num_from_path
import sensors.load as sensor_loader
import sensors.metrics as metrics_extractor
from OH_profile.constants import SENSOR_METRICS_KEY, POSTURE_KEY
from OH_profile.load import get_OH_profile
from OH_profile.write import write_to_OH_profile, save_OH_profile
from OH_profile.load.oh_profile_loader import METADATA_KEY
# ------------------------------------------------------------------------------------------------------------------- #
# flags
# ------------------------------------------------------------------------------------------------------------------- #
GENERATE_POSTURE_OH_PROFILE = True
GENERATE_PLOTS = True

# ------------------------------------------------------------------------------------------------------------------- #
# file constants
# ------------------------------------------------------------------------------------------------------------------- #
DRIVE = 'E'
DATASET_PATH = 'Backup PrevOccupAI_PLUS Data\\data'
SUBJECT_FOLDER_PATH = f"{DRIVE}:\\{DATASET_PATH}\\group2\\sensors\\LIBPhys #006\\"
OH_PROFILE_PATH = f"{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\OH_profiles"
OH_PLOTS_PATH = f"{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\OH_plots"

# TODO: these paths need to be set somewhere generally or passed as parameters
QUESTIONNAIRE_RESULTS_PATH = f"{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\questionnaire_scores"
W_SIZE = 5.0
FS = 100

# ------------------------------------------------------------------------------------------------------------------- #
# program starts here
# ------------------------------------------------------------------------------------------------------------------- #
# get group and device from path
group = str(extract_group_from_path(SUBJECT_FOLDER_PATH))
device_num = str(extract_device_num_from_path(SUBJECT_FOLDER_PATH))

# get subject id
subject_id = sensor_loader.get_participant_id(sensor_loader.load_participants_info(), device_num, group)

if GENERATE_POSTURE_OH_PROFILE:

    # inform user
    print(f"Extracting posture metrics for subject: {subject_id}")

    # get the subject's OH profile
    oh_profile = get_OH_profile(OH_PROFILE_PATH, subject_id)

    try:

        # get subject's height
        subject_height = oh_profile[METADATA_KEY]['altura']

    except KeyError:

        # generate path to the results of the group of this subject
        personal_quest_results_path = f"{QUESTIONNAIRE_RESULTS_PATH}\\group{str(group)}\\results_personal.csv"

        # check if the results exist
        if not os.path.exists(personal_quest_results_path):
            raise ValueError(f"Couldn't find personal questionnaire results. \nPlease run the questionnaire processing "
                             f"to generate the results or place them in the correct folder: \n{personal_quest_results_path}")

        # get metadata (age) from data and add it to OH profile
        metadata_dict = questionnaires.get_metadata_metrics(personal_quest_results_path, int(subject_id))

        # write metadata results to the OH profile
        oh_profile = write_to_OH_profile(oh_profile, main_outer_key=METADATA_KEY,
                                         main_inner_key=None, dict_to_write=metadata_dict)

        # get subject's height
        subject_height = oh_profile[METADATA_KEY]['altura']


    # put subject height in m
    subject_height_m = subject_height / 100

    # check if the metrics have already been extracted, otherwise extract
    if len(oh_profile[SENSOR_METRICS_KEY][POSTURE_KEY]) < 100:

        # iterate through the day folders
        for date_folder in os.listdir(SUBJECT_FOLDER_PATH):

            # inform user
            print(f"\n#---- Extracting posture metrics for date: {date_folder} ----#")

            # get path to the date of the day
            day_folder = os.path.join(SUBJECT_FOLDER_PATH, date_folder)

            # extract posture metrics
            day_metrics_dict = metrics_extractor.get_posture_metrics(day_folder, fs=FS, w_size_HAR=W_SIZE, subject_height_m=subject_height_m)

            # write to OH profile
            oh_profile = write_to_OH_profile(oh_profile, main_outer_key=SENSOR_METRICS_KEY, main_inner_key=POSTURE_KEY, dict_to_write=day_metrics_dict)

            # save the OH profile to json
            save_OH_profile(OH_PROFILE_PATH, subject_id, oh_profile)

