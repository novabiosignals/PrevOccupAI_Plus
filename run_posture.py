# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import os



# internal imports
import questionnaires.metrics as qm
from utils import extract_group_from_path, extract_device_num_from_path
import sensors.load as sensor_loader
import sensors.metrics as metrics_extractor
from OH_profile.constants import SENSOR_METRICS_KEY, POSTURE_KEY
from OH_profile.load import get_OH_profile
from OH_profile.write import write_to_OH_profile, save_OH_profile
from OH_profile.load.oh_profile_loader import METADATA_KEY
from sensors.visualize import plot_postural_displacements
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
DATA_FOLDER_PATH = f"{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\data"
OH_PROFILE_PATH = f"{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\OH_profiles"
OH_PLOTS_PATH = f"{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\OH_plots"
OH_DISPLACEMENT_DATA_PATH = f"{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\OH_postural_displacement"

# TODO: these paths need to be set somewhere generally or passed as parameters
QUESTIONNAIRE_RESULTS_PATH = f"{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\questionnaire_scores"
W_SIZE = 5.0
FS = 100

# ------------------------------------------------------------------------------------------------------------------- #
# program starts here
# ------------------------------------------------------------------------------------------------------------------- #
if GENERATE_POSTURE_OH_PROFILE:

    # cycle over the group folders ('group1', group2...)
    for group_folder in os.listdir(DATA_FOLDER_PATH):

        # it t's not a folder ignore
        if os.path.isdir(os.path.join(DATA_FOLDER_PATH, group_folder)):

            # cycle over the folders 'questionnaires' and 'sensors'
            for folder in os.listdir(os.path.join(DATA_FOLDER_PATH, group_folder)):

                # ignore questionnaires
                if folder == 'sensors':

                    # cycle over the different subjects
                    for subject_folder in sorted(os.listdir(os.path.join(DATA_FOLDER_PATH, group_folder, folder))):

                        # get folder path
                        folder_path = os.path.join(DATA_FOLDER_PATH, group_folder, folder, subject_folder)

                        # get group and device num from path
                        group = str(extract_group_from_path(folder_path))
                        device_num = str(extract_device_num_from_path(folder_path))

                        # get subject id
                        subject_id = sensor_loader.get_participant_id(sensor_loader.load_participants_info(), device_num, group)

                        print(f"\n\nExtracting posture metrics for subject: {subject_id}")

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
                            metadata_dict = qm.get_metadata_metrics(personal_quest_results_path, int(subject_id))

                            # write metadata results to the OH profile
                            oh_profile = write_to_OH_profile(oh_profile, main_outer_key=METADATA_KEY,
                                                             main_inner_key=None, dict_to_write=metadata_dict)

                            # get subject's height
                            subject_height = oh_profile[METADATA_KEY]['altura']


                        # put subject height in m
                        subject_height_m = subject_height / 100

                        # check if the metrics have already been extracted, otherwise extract
                        if len(oh_profile[SENSOR_METRICS_KEY][POSTURE_KEY]) < 1:

                            # iterate through the day folders
                            for date_folder in os.listdir(folder_path):

                                # inform user
                                print(f"\n#---- Extracting posture metrics for date: {date_folder} ----#")

                                # get path to the date of the day
                                day_folder = os.path.join(folder_path, date_folder)

                                # extract posture metrics
                                day_metrics_dict = metrics_extractor.get_posture_metrics(day_folder, fs=FS, w_size_HAR=W_SIZE,
                                                                                         subject_height_m=subject_height_m,
                                                                                         subject_id=subject_id, displacement_store_path=OH_DISPLACEMENT_DATA_PATH)

                                # write to OH profile
                                oh_profile = write_to_OH_profile(oh_profile, main_outer_key=SENSOR_METRICS_KEY, main_inner_key=POSTURE_KEY, dict_to_write=day_metrics_dict)

                                # save the OH profile to json
                                save_OH_profile(OH_PROFILE_PATH, subject_id, oh_profile)


                        if GENERATE_PLOTS:

                            print(f"\nGenerating plots for subject: {subject_id}")

                            # check whether there is metadata
                            if len(oh_profile[METADATA_KEY]) > 0:

                                # get the sex
                                sex = oh_profile[METADATA_KEY]['sexo']

                                # generate posture plot
                                plot_postural_displacements(OH_DISPLACEMENT_DATA_PATH, subject_id=subject_id, subject_sex=sex, output_folder_path=OH_PLOTS_PATH)