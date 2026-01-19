# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
# from HAR.classifier import ACTIVITY_COLUMN_NAME
# from constants import PHONE, TIME_COLUMN_NAME
# from sensors.load import load_daily_acquisitions
# from sensors.process import apply_pre_processing_pipeline
# from sensors.utils import generate_real_time_column
# from HAR import classify_human_activities

import os

# internal imports
import sensors.metrics as metrics_extractor
import sensors.load as sensor_loader
from OH_profile.constants import SENSOR_METRICS_KEY, HAR_KEY
from OH_profile.load import get_OH_profile
from OH_profile.write import write_to_OH_profile, save_OH_profile
from utils import extract_group_from_path, extract_device_num_from_path

# ------------------------------------------------------------------------------------------------------------------- #
# flags
# ------------------------------------------------------------------------------------------------------------------- #
GENERATE_HUMAN_ACTIVITY_OH_PROFILE = True
GENERATE_PLOTS = True
# ------------------------------------------------------------------------------------------------------------------- #
# file constants
# ------------------------------------------------------------------------------------------------------------------- #
# LOAD_DAILY_ACQUISITIONS = True
# SELECTED_SENSORS = {'phone': ['ACC', 'GYR', 'MAG', 'ROT']}

DRIVE = 'E'
DATASET_PATH = 'Backup PrevOccupAI_PLUS Data\\data'
SUBJECT_FOLDER_PATH = f"{DRIVE}:\\{DATASET_PATH}\\group2\\sensors\\LIBPhys #006\\"
OH_PROFILE_PATH = f"{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\OH_profiles"
OH_PLOTS_PATH = f"{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\OH_plots"
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

if GENERATE_HUMAN_ACTIVITY_OH_PROFILE:

    # inform user
    print(f"Extracting human activity metrics for subject: {subject_id}")

    # get the subject's OH profile
    oh_profile = get_OH_profile(OH_PROFILE_PATH, subject_id)

    # check if the metrics have already been extracted, otherwise extract
    if len(oh_profile[SENSOR_METRICS_KEY][HAR_KEY]) < 100:

        # iterate through the day folders
        for date_folder in os.listdir(SUBJECT_FOLDER_PATH):

            # inform user
            print(f"\n#---- Extracting human activity metrics for date: {date_folder} ----#")

            # get path to the date of the day
            day_folder = os.path.join(SUBJECT_FOLDER_PATH, date_folder)

            # extract human activity metrics
            daily_metrics_dict = metrics_extractor.get_human_activity_metrics(day_folder, fs=FS, w_size_HAR=W_SIZE)

            # write to OH profile
            oh_profile = write_to_OH_profile(oh_profile, main_outer_key=SENSOR_METRICS_KEY, main_inner_key=HAR_KEY, dict_to_write=daily_metrics_dict)

            # save the OH profile to json
            save_OH_profile(OH_PROFILE_PATH, subject_id, oh_profile)






