# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import os

# internal imports
import sensors.visualize as sv
import sensors.load as sl
import sensors.metrics as sm
import questionnaires
from OH_profile.constants import SENSOR_METRICS_KEY, HEART_RATE_KEY, RELATIVE_HR_BASE_KEY, METADATA_KEY
from utils import extract_group_from_path, extract_device_num_from_path
from OH_profile.load import get_OH_profile
from OH_profile.write import save_OH_profile, write_to_OH_profile
from sensors.metrics.heart_rate import DAILY_PROPORTIONS, MIN_HR, MAX_HR


# ------------------------------------------------------------------------------------------------------------------- #
# flags
# ------------------------------------------------------------------------------------------------------------------- #
GENERATE_HEART_RATE_PLOTS = True
HEART_RATE_TIMELINE = False
HEART_RATE_WEEK = True

# ------------------------------------------------------------------------------------------------------------------- #
# file constants
# ------------------------------------------------------------------------------------------------------------------- #
DRIVE = "E"
DATASET_PATH = "Backup PrevOccupAI_PLUS Data\\data"
SUBJECT_FOLDER_PATH = f"{DRIVE}:\\{DATASET_PATH}\\group1\\sensors\\LIBPhys #001"
QUESTIONNAIRE_RESULTS_PATH = "C:\\Users\\srale\\Desktop\\carga de trabalho\\results"
OH_PROFILE_PATH = r"C:\Users\srale\Desktop\OH_profiles"
PLOTS_OUTPUT_PATH = r"C:\Users\srale\Desktop\timeline_plots"
FS = 100
W_SIZE = 5.0

# ------------------------------------------------------------------------------------------------------------------- #
# program starts here
# ------------------------------------------------------------------------------------------------------------------- #

# get group and device num from path
group = str(extract_group_from_path(SUBJECT_FOLDER_PATH))
device_num = str(extract_device_num_from_path(SUBJECT_FOLDER_PATH))

# get subject id
subject_id = sl.get_participant_id(sl.load_participants_info(), device_num, group)

if GENERATE_HEART_RATE_PLOTS:

    print(f"Extracting heart rate metrics for subject: {subject_id}")

    # get oh profile
    oh_profile = get_OH_profile(OH_PROFILE_PATH, subject_id)

    # check if the global metrics are not in the oh profile
    if RELATIVE_HR_BASE_KEY not in oh_profile[SENSOR_METRICS_KEY][HEART_RATE_KEY]:

        print(f"Extracting global heart rate metrics")

        # calculate the Min and MAX HR
        # get the age from the OH profile, if it exists
        try:
            age = oh_profile[METADATA_KEY]['idade']

        except KeyError:

            # generate path to the results of the group of this subject
            personal_quest_results_path = f"{QUESTIONNAIRE_RESULTS_PATH}\\group{str(group)}\\results_personal.csv"

            # check if the results exist
            if not os.path.exists(personal_quest_results_path):

                age = 50
                print("Couldn't find personal questionnaire results. Using age = 50 years old...")

            # get metadata (age) from data and add it to OH profile
            metadata_dict = questionnaires.get_metadata_metrics(personal_quest_results_path, int(subject_id))

            # write metadata results to the OH profile
            oh_profile = write_to_OH_profile(oh_profile, main_outer_key=METADATA_KEY,
                                             main_inner_key=None, dict_to_write=metadata_dict)
            # get age from metadata
            age = oh_profile[METADATA_KEY]['idade']

        # calculate relative metrics
        relative_HR_dict = sm.get_global_heart_rate_metrics(subject_data_folder=SUBJECT_FOLDER_PATH, subject_age=age)

        # write to oh profile
        oh_profile = write_to_OH_profile(oh_profile, main_outer_key=SENSOR_METRICS_KEY,
                                         main_inner_key=HEART_RATE_KEY, dict_to_write=relative_HR_dict)

    # get global metrics from OH profile
    global_metrics_dict = oh_profile[SENSOR_METRICS_KEY][HEART_RATE_KEY][RELATIVE_HR_BASE_KEY]

    # check if the metrics have already been extracted
    # if not then len = 1 since it has only the relative HR base metrics
    if len(oh_profile[SENSOR_METRICS_KEY][HEART_RATE_KEY]) < 2:

        # iterate through the folders of the several days
        for date_folder in os.listdir(SUBJECT_FOLDER_PATH):

            print(f"Extracting heart rate metrics: {date_folder}")

            # get path to the data of the day
            day_folder_path = os.path.join(SUBJECT_FOLDER_PATH, date_folder)

            # get heart rate metrics for the day
            metrics_dict = sm.get_heart_rate_metrics(day_folder_path, hr_min=global_metrics_dict[MIN_HR],
                                                     hr_max=global_metrics_dict[MAX_HR], fs=FS, w_size=W_SIZE)

            # write to oh profile
            oh_profile = write_to_OH_profile(oh_profile, main_outer_key=SENSOR_METRICS_KEY,
                                             main_inner_key=HEART_RATE_KEY, dict_to_write=metrics_dict)

            # save to json
            save_OH_profile(OH_PROFILE_PATH, subject_id, oh_profile)

    if HEART_RATE_TIMELINE:

        # cycle over the different days
        for key, features in oh_profile[SENSOR_METRICS_KEY][HEART_RATE_KEY].items():

            # get only the daily metrics - ignore key with the values of the daily proportions
            if key != DAILY_PROPORTIONS:

                # get inner dict for simplicity
                daily_hr_metrics_dict = oh_profile[SENSOR_METRICS_KEY][HEART_RATE_KEY][key]

                # plot hr timeline
                sv.plot_hr_timeline_per_acquisition(daily_hr_metrics_dict, day=key, group=f"group {group}", subject=subject_id,
                                                    output_folder_path=PLOTS_OUTPUT_PATH)

    if HEART_RATE_WEEK:

        hr_proportions_dict = oh_profile[SENSOR_METRICS_KEY][HEART_RATE_KEY]

        sv.plot_weekly_hr_data(hr_proportions_dict, group=f"group {group}", subject=subject_id, save_path=PLOTS_OUTPUT_PATH)