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
from OH_profile.write import save_OH_profile, write_to_OH_profile, clear_dict_entries
from OH_profile.constants import SENSOR_METRICS_KEY, WRIST_KEY
# ------------------------------------------------------------------------------------------------------------------- #
# flags
# ------------------------------------------------------------------------------------------------------------------- #
GENERATE_NOISE_OH_PROFILE = True
GENERATE_PLOTS = True

# ------------------------------------------------------------------------------------------------------------------- #
# file constants
# ------------------------------------------------------------------------------------------------------------------- #
DRIVE = "D"
DATA_FOLDER_PATH = f"{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\data"
OH_PROFILE_PATH = f"{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\OH_profiles"
PLOTS_OUTPUT_PATH = f"{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\OH_plots"
FS = 100
W_SIZE_SECONDS = 5.0

# ------------------------------------------------------------------------------------------------------------------- #
# program starts here
# ------------------------------------------------------------------------------------------------------------------- #

if GENERATE_NOISE_OH_PROFILE:

    # cycle over the group folders ('group1', group2...)
    for group_folder in os.listdir(DATA_FOLDER_PATH):

        # it t's not a folder ignore
        if os.path.isdir(os.path.join(DATA_FOLDER_PATH, group_folder)):

            # cycle over the folders 'questionnaires' and 'sensors'
            for folder in os.listdir(os.path.join(DATA_FOLDER_PATH, group_folder)):

                # ignore questionnaires
                if folder == 'sensors':

                    # cycle over the different subjects
                    for subject_folder in os.listdir(os.path.join(DATA_FOLDER_PATH, group_folder, folder)):

                        # get folder path
                        folder_path = os.path.join(DATA_FOLDER_PATH, group_folder, folder, subject_folder)

                        # get group and device num from path
                        group = str(extract_group_from_path(folder_path))
                        device_num = str(extract_device_num_from_path(folder_path))

                        # get subject id
                        subject_id = sl.get_participant_id(sl.load_participants_info(), device_num, group)

                        print(f"Extracting wrist metrics for subject: {subject_id}")

                        # get oh profile
                        oh_profile = get_OH_profile(OH_PROFILE_PATH, subject_id)

                        # check if the metrics have already been extracted, if not, extract noise metrics
                        if len(oh_profile[SENSOR_METRICS_KEY][WRIST_KEY]) < 1:

                            # iterate through the folders of the several days
                            for date_folder in os.listdir(folder_path):
                                print(f"Extracting wrist metrics: {date_folder}")

                                # get path to the data of the day
                                day_folder_path = os.path.join(folder_path, date_folder)

                                # extract noise features
                                daily_metrics_dict = sm.get_wrist_activity_metrics(day_folder_path, fs=FS, w_size=W_SIZE_SECONDS)

                                # if there are no metrics, continue
                                if len(daily_metrics_dict) == 0:
                                    continue

                                # write to oh profile
                                oh_profile = write_to_OH_profile(oh_profile, main_outer_key=SENSOR_METRICS_KEY,
                                                                 main_inner_key=WRIST_KEY, dict_to_write=daily_metrics_dict)

                                # save to json
                                save_OH_profile(OH_PROFILE_PATH, subject_id, oh_profile)

                        if GENERATE_PLOTS:

                            sv.plot_wrist_movements_heatmaps(oh_profile[SENSOR_METRICS_KEY][WRIST_KEY], str(subject_id), PLOTS_OUTPUT_PATH)
