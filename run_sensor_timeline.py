# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import os

# internal imports
import sensors.visualize as sv
import sensors.load as sl
import sensors.metrics as sm
from OH_profile.constants import SENSOR_TIMELINE_KEY, SENSOR_METRICS_KEY
from utils import extract_group_from_path, extract_device_num_from_path
from OH_profile.load import get_OH_profile
from OH_profile.write import save_OH_profile, write_to_OH_profile

# ------------------------------------------------------------------------------------------------------------------- #
# flags
# ------------------------------------------------------------------------------------------------------------------- #
GENERATE_SENSOR_TIMELINE = True

# ------------------------------------------------------------------------------------------------------------------- #
# file constants
# ------------------------------------------------------------------------------------------------------------------- #
DRIVE = 'D'
DATASET_PATH = f'{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\data'
DATA_FOLDER_PATH = f"{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\data"
OH_PROFILE_PATH = f"{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\OH_profiles"
OH_PLOTS_PATH = f"{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\OH_plots"
FS = 100
W_SIZE = 5.0

# ------------------------------------------------------------------------------------------------------------------- #
# program starts here
# ------------------------------------------------------------------------------------------------------------------- #

if GENERATE_SENSOR_TIMELINE:

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

                        print(f"Extracting sensor timeline metrics for subject: {subject_id}")

                        # get oh profile
                        oh_profile = get_OH_profile(OH_PROFILE_PATH, subject_id)

                        # check if OH profile already exists
                        if len(oh_profile[SENSOR_METRICS_KEY][SENSOR_TIMELINE_KEY]) <1:

                            # inform user
                            print(f"OH profile not found for subject {subject_id}. Generating new OH profile...")

                            # generate OH profile
                            for acquisition_date in os.listdir(folder_path):

                                # generate path
                                day_folder_path = os.path.join(folder_path, acquisition_date)

                                # generate metrics dict
                                daily_metrics_dict = sm.get_sensor_timeline_metrics(day_folder_path, fs=FS)

                                # write to json file
                                oh_profile = write_to_OH_profile(oh_profile, main_outer_key= SENSOR_METRICS_KEY,
                                                                 main_inner_key=SENSOR_TIMELINE_KEY, dict_to_write=daily_metrics_dict)

                                # save to json
                                save_OH_profile(OH_PROFILE_PATH, subject_id, oh_profile)

                        # get oh profile
                        oh_profile = get_OH_profile(OH_PROFILE_PATH, subject_id)

                        # get output filename
                        filename = f"{subject_id}_sensor_timeline_plot.png"

                        # generate plot
                        sv.generate_sensor_timeline_plot(oh_profile[SENSOR_METRICS_KEY][SENSOR_TIMELINE_KEY], OH_PLOTS_PATH, filename, str(subject_id))







