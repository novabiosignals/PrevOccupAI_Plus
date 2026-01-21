# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import os

# internal imports
import sensors.metrics as metrics_extractor
import sensors.load as sensor_loader
import sensors.visualize as sensor_visualizer
from OH_profile.constants import SENSOR_METRICS_KEY, HAR_KEY, PERSONAL_DOMAIN_KEY, SINGLE_INSTANCE_QUESTIONNAIRE_KEY, METADATA_KEY
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

DRIVE = 'E'
DATASET_PATH = 'Backup PrevOccupAI_PLUS Data\\data'
SUBJECT_FOLDER_PATH = f"{DRIVE}:\\{DATASET_PATH}\\group1\\sensors\\LIBPhys #001\\"
OH_PROFILE_PATH = r"C:\Users\srale\Desktop\OH_profiles"
OH_PLOTS_PATH = r"C:\Users\srale\Desktop\timeline_plots"
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
    if len(oh_profile[SENSOR_METRICS_KEY][HAR_KEY]) < 1:

        # iterate through the day folders
        for date_folder in os.listdir(SUBJECT_FOLDER_PATH):

            # inform user
            print(f"\n#---- Extracting human activity metrics for date: {date_folder} ----#")

            # get path to the date of the day
            day_folder = os.path.join(SUBJECT_FOLDER_PATH, date_folder)

            # extract human activity metrics
            daily_metrics_dict = metrics_extractor.get_human_activity_metrics(day_folder, fs=FS, w_size_HAR=W_SIZE)

            if len(daily_metrics_dict) == 0:
                continue

            # write to OH profile
            oh_profile = write_to_OH_profile(oh_profile, main_outer_key=SENSOR_METRICS_KEY, main_inner_key=HAR_KEY, dict_to_write=daily_metrics_dict)

            # save the OH profile to json
            save_OH_profile(OH_PROFILE_PATH, subject_id, oh_profile)

    if GENERATE_PLOTS:

        print(f"Generating plots for subject: {subject_id}")

        # generate timeline
        sensor_visualizer.plot_activity_timeline_per_day(oh_profile[SENSOR_METRICS_KEY][HAR_KEY], subject_id,OH_PLOTS_PATH)

        # plot distributions OSPAQ vs Real
        if len(oh_profile[SINGLE_INSTANCE_QUESTIONNAIRE_KEY][PERSONAL_DOMAIN_KEY]) > 0:

            sensor_visualizer.plot_activity_distributions_ospaq_vs_real(oh_profile[SINGLE_INSTANCE_QUESTIONNAIRE_KEY][PERSONAL_DOMAIN_KEY],
                                                                        oh_profile[SENSOR_METRICS_KEY][HAR_KEY], subject_id, OH_PLOTS_PATH)

        # plot steps
        if len(oh_profile[METADATA_KEY]) > 0:

            # get age from metadata dict
            age = oh_profile[METADATA_KEY]['idade']
            sensor_visualizer.plot_steps_and_distance_per_day(oh_profile[SENSOR_METRICS_KEY][HAR_KEY], subject_id, OH_PLOTS_PATH, age=age)







