# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import os

# internal imports
import sensors.visualize as sv
import sensors.load as sl
import sensors.metrics as sm
import questionnaires.metrics as qm
from OH_profile.constants import SENSOR_METRICS_KEY, HEART_RATE_KEY, HR_RELATIVE_BASE_KEY, METADATA_KEY
from utils import extract_group_from_path, extract_device_num_from_path
from OH_profile.load import get_OH_profile
from OH_profile.write import save_OH_profile, write_to_OH_profile
from sensors.metrics.heart_rate import HR_MIN_KEY, HR_MAX_KEY

# ------------------------------------------------------------------------------------------------------------------- #
# flags
# ------------------------------------------------------------------------------------------------------------------- #
GENERATE_HEART_RATE_OH_PROFILE = True
HEART_RATE_TIMELINE = False
HEART_RATE_WEEK = True

# ------------------------------------------------------------------------------------------------------------------- #
# file constants
# ------------------------------------------------------------------------------------------------------------------- #
DRIVE = "E"
DATA_FOLDER_PATH = f"{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\data"
QUESTIONNAIRE_RESULTS_PATH = f"{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\questionnaire_scores"
OH_PROFILE_PATH = f"{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\OH_profiles"
PLOTS_OUTPUT_PATH = f"{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\OH_plots"
FS = 100
W_SIZE = 5.0

# ------------------------------------------------------------------------------------------------------------------- #
# program starts here
# ------------------------------------------------------------------------------------------------------------------- #

if GENERATE_HEART_RATE_OH_PROFILE:

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

                        print(f"Extracting heart_rate metrics for subject: {subject_id}")

                        # get oh profile
                        oh_profile = get_OH_profile(OH_PROFILE_PATH, subject_id)

                        # check if the global metrics are not in the oh profile
                        if HR_RELATIVE_BASE_KEY not in oh_profile[SENSOR_METRICS_KEY][HEART_RATE_KEY]:

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

                                    raise ValueError (f"Couldn't find personal questionnaire results. \nPlease run the questionnaire processing "
                                                      f"to generate the results or place them in the correct folder: \n{personal_quest_results_path}")

                                # get metadata (age) from data and add it to OH profile
                                metadata_dict = qm.get_metadata_metrics(personal_quest_results_path, int(subject_id))

                                # write metadata results to the OH profile
                                oh_profile = write_to_OH_profile(oh_profile, main_outer_key=METADATA_KEY,
                                                                 main_inner_key=None, dict_to_write=metadata_dict)
                                # get age from metadata
                                age = oh_profile[METADATA_KEY]['idade']

                            # calculate relative metrics
                            relative_HR_dict = sm.get_global_heart_rate_metrics(subject_data_folder_path=folder_path, subject_age=age)

                            # if there are no metrics, continue
                            if len(relative_HR_dict) > 0:

                                # write to oh profile
                                oh_profile = write_to_OH_profile(oh_profile, main_outer_key=SENSOR_METRICS_KEY,
                                                                 main_inner_key=HEART_RATE_KEY, dict_to_write=relative_HR_dict)

                        # get global metrics from OH profile
                        global_metrics_dict = oh_profile[SENSOR_METRICS_KEY][HEART_RATE_KEY][HR_RELATIVE_BASE_KEY]

                        # check if the metrics have already been extracted
                        # if not then len = 1 since it has only the relative HR base metrics
                        if len(oh_profile[SENSOR_METRICS_KEY][HEART_RATE_KEY]) < 20000:

                            # iterate through the folders of the several days
                            for date_folder in os.listdir(folder_path):

                                print(f"Extracting heart rate metrics: {date_folder}")

                                # get path to the data of the day
                                day_folder_path = os.path.join(folder_path, date_folder)

                                # get heart rate metrics for the day
                                metrics_dict = sm.get_heart_rate_metrics(day_folder_path, hr_min=global_metrics_dict[HR_MIN_KEY],
                                                                         hr_max=global_metrics_dict[HR_MAX_KEY], fs=FS, w_size=W_SIZE)

                                # if there are no metrics, continue
                                if len(metrics_dict) == 0:
                                    continue

                                # write to oh profile
                                oh_profile = write_to_OH_profile(oh_profile, main_outer_key=SENSOR_METRICS_KEY,
                                                                 main_inner_key=HEART_RATE_KEY, dict_to_write=metrics_dict)

                                # save to json
                                save_OH_profile(OH_PROFILE_PATH, subject_id, oh_profile)

                        if HEART_RATE_TIMELINE:

                            # cycle over the different days
                            for key, features in oh_profile[SENSOR_METRICS_KEY][HEART_RATE_KEY].items():

                                # get only the daily metrics - ignore key with the values of the daily proportions
                                if key != HR_RELATIVE_BASE_KEY:

                                    # get inner dict for simplicity
                                    daily_hr_metrics_dict = oh_profile[SENSOR_METRICS_KEY][HEART_RATE_KEY][key]

                                    # plot hr timeline
                                    sv.plot_hr_timeline_per_acquisition(daily_hr_metrics_dict, day=key, subject=subject_id,
                                                                        output_folder_path=PLOTS_OUTPUT_PATH)

                        if HEART_RATE_WEEK:

                            hr_proportions_dict = oh_profile[SENSOR_METRICS_KEY][HEART_RATE_KEY]

                            # plot distributions
                            sv.plot_weekly_hr_data(hr_proportions_dict, subject=subject_id, save_path=PLOTS_OUTPUT_PATH)

                            # plot HR variability
                            sv.plot_hr_ranges(hr_proportions_dict, subject=subject_id, output_folder_path=PLOTS_OUTPUT_PATH)