# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import os

# internal imports
import sensors.load as sl
import sensors.metrics as sm
import sensors.visualize as sv
from utils import extract_group_from_path, extract_device_num_from_path
from OH_profile.load import get_OH_profile
from OH_profile.write import save_OH_profile, write_to_OH_profile
from OH_profile.constants import SENSOR_METRICS_KEY, NOISE_KEY
# ------------------------------------------------------------------------------------------------------------------- #
# flags
# ------------------------------------------------------------------------------------------------------------------- #
GENERATE_NOISE_OH_PROFILE = True
GENERATE_PLOTS = True

# ------------------------------------------------------------------------------------------------------------------- #
# file constants
# ------------------------------------------------------------------------------------------------------------------- #
DRIVE = "E"
DATASET_PATH = "Backup PrevOccupAI_PLUS Data\\data"
SUBJECT_FOLDER_PATH = f"{DRIVE}:\\{DATASET_PATH}\\group1\\sensors\\LIBPhys #004"
OH_PROFILE_PATH = r"C:\Users\srale\Desktop\OH_profiles"
PLOTS_OUTPUT_PATH = r"C:\Users\srale\Desktop\timeline_plots"
FS = 100

# ------------------------------------------------------------------------------------------------------------------- #
# program starts here
# ------------------------------------------------------------------------------------------------------------------- #

# get group and device num from path
group = str(extract_group_from_path(SUBJECT_FOLDER_PATH))
device_num = str(extract_device_num_from_path(SUBJECT_FOLDER_PATH))

# get subject id
subject_id = sl.get_participant_id(sl.load_participants_info(), device_num, group)

if GENERATE_NOISE_OH_PROFILE:

    print(f"Extracting noise metrics for subject: {subject_id}")

    # get oh profile
    oh_profile = get_OH_profile(OH_PROFILE_PATH, subject_id)

    # check if the metrics have already been extracted, if not, extract noise metrics
    if len(oh_profile[SENSOR_METRICS_KEY][NOISE_KEY]) < 1:

        # iterate through the folders of the several days
        for date_folder in os.listdir(SUBJECT_FOLDER_PATH):
            print(f"Extracting heart rate metrics: {date_folder}")

            # get path to the data of the day
            day_folder_path = os.path.join(SUBJECT_FOLDER_PATH, date_folder)

            # extract noise features
            daily_metrics_dict = sm.get_noise_metrics(day_folder_path, fs=FS)

            # write to oh profile
            oh_profile = write_to_OH_profile(oh_profile, main_outer_key=SENSOR_METRICS_KEY,
                                             main_inner_key=NOISE_KEY, dict_to_write=daily_metrics_dict)

            # save to json
            save_OH_profile(OH_PROFILE_PATH, subject_id, oh_profile)

    if GENERATE_PLOTS:

        sv.plot_noise_metrics_per_week(oh_profile[SENSOR_METRICS_KEY][NOISE_KEY], str(subject_id), PLOTS_OUTPUT_PATH)
