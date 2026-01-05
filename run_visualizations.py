# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import os

# internal imports
import sensors.visualize as sv
import sensors.load as sl
import sensors.metrics as sm
from OH_profile.constants import SENSOR_TIMELINE_KEY, SENSOR_METRICS_KEY, HEART_RATE_KEY, RELATIVE_HR_BASE_KEY, METADATA_KEY
from utils import extract_group_from_path, has_matching_json, extract_device_num_from_path
from OH_profile.load import get_OH_profile
from OH_profile.write import save_OH_profile, write_to_OH_profile
from sensors.metrics.heart_rate import DAILY_PROPORTIONS, MIN_HR, MAX_HR

# ------------------------------------------------------------------------------------------------------------------- #
# flags
# ------------------------------------------------------------------------------------------------------------------- #
GENERATE_SENSOR_TIMELINE = False
GENERATE_HEART_RATE_PLOTS = True

# ------------------------------------------------------------------------------------------------------------------- #
# file constants
# ------------------------------------------------------------------------------------------------------------------- #
DRIVE = "E"
SUBJECT_FOLDER_PATH = f"{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\data\\group1\\sensors\\LIBPhys #001"
OH_PROFILE_PATH = r"C:\Users\srale\Desktop\OH_profiles"
PLOTS_OUTPUT_PATH = r"C:\Users\srale\Desktop\timeline_plots"
FS = 100
W_SIZE = 5.0

# ------------------------------------------------------------------------------------------------------------------- #
# program starts here
# ------------------------------------------------------------------------------------------------------------------- #

# get group and device num from path
group = extract_group_from_path(SUBJECT_FOLDER_PATH)
device_num = extract_device_num_from_path(SUBJECT_FOLDER_PATH)

# get subject id
subject_id = sl.get_participant_id(sl.load_participants_info(), device_num, group)

if GENERATE_SENSOR_TIMELINE:

    # check if OH profile already exists
    if not has_matching_json(OH_PROFILE_PATH, subject_id):

        # inform user
        print(f"OH profile not found for subject {subject_id}. Generating new OH profile...")

        # generate OH profile
        for acquisition_date in os.listdir(SUBJECT_FOLDER_PATH):

            # generate path
            day_folder_path = os.path.join(SUBJECT_FOLDER_PATH, acquisition_date)

            # generate metrics dict
            daily_metrics_dict = sm.get_sensor_timeline_metrics(day_folder_path, fs=FS)

            # get oh profile
            oh_profile = get_OH_profile(OH_PROFILE_PATH, subject_id)

            # write to json file
            oh_profile = write_to_OH_profile(oh_profile, main_outer_key= SENSOR_METRICS_KEY,
                                             main_inner_key=SENSOR_TIMELINE_KEY, dict_to_write=daily_metrics_dict)

            # save to json
            save_OH_profile(OH_PROFILE_PATH, subject_id, oh_profile)

    # get oh profile
    oh_profile = get_OH_profile(OH_PROFILE_PATH, subject_id)

    # get output filename
    filename = f"subject_{subject_id}_sensor_timeline_plot.png"

    # generate plot
    sv.generate_sensor_timeline_plot(oh_profile[SENSOR_METRICS_KEY][SENSOR_TIMELINE_KEY], PLOTS_OUTPUT_PATH, filename)


if GENERATE_HEART_RATE_PLOTS:

    print(f"Extracting heart rate metrics for subject: {subject_id}")

    # get oh profile
    oh_profile = get_OH_profile(OH_PROFILE_PATH, subject_id)

    # check if the global metrics are not in the oh profile
    if RELATIVE_HR_BASE_KEY not in oh_profile[SENSOR_METRICS_KEY][HEART_RATE_KEY]:

        print(f"Extracting global heart rate metrics")

        # TODO -   DO THIS AFTER MERGING THE QUESTIONNAIRES BRANCH
        # # calculate the Min and MAX HR
        # # get the age from the OH profile, if it exists
        # try:
        #     age = oh_profile[METADATA_KEY]['idade']
        #
        # except KeyError:
        #
        #     # get metadata (age) from data and add it to OH profile

        # calculate relative metrics
        age = 50
        relative_HR_dict = sm.get_global_heart_rate_metrics(subject_data_folder=SUBJECT_FOLDER_PATH, subject_age=age)

        # write to oh profile
        oh_profile = write_to_OH_profile(oh_profile, main_outer_key=SENSOR_METRICS_KEY,
                                         main_inner_key=HEART_RATE_KEY, dict_to_write=relative_HR_dict)

    # get global metrics from OH profile
    global_metrics_dict = oh_profile[SENSOR_METRICS_KEY][HEART_RATE_KEY][RELATIVE_HR_BASE_KEY]

    # check if the metrics have already been extracted
    # if not then len = 1 since it has only the relative HR base metrics
    if len(oh_profile[SENSOR_METRICS_KEY][HEART_RATE_KEY] < 2):

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

    # cycle over the different days
    for key, features in oh_profile[SENSOR_METRICS_KEY][HEART_RATE_KEY].items():

        # get only the daily metrics - ignore key with the values of the daily proportions
        if key != DAILY_PROPORTIONS:

            # get inner dict for simplicity
            daily_hr_metrics_dict = oh_profile[SENSOR_METRICS_KEY][HEART_RATE_KEY][key]

            # plot hr timeline
            sv.plot_hr_timeline_per_acquisition(daily_hr_metrics_dict, day=key, group=f"group {group}", subject=subject_id,
                                                output_folder_path=PLOTS_OUTPUT_PATH)






