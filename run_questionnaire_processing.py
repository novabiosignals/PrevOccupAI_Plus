# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import os
import re

# internal imports
import questionnaires
import sensors.load as sl
from constants import WORKLOAD
from OH_profile.constants import *
from OH_profile.load import get_OH_profile
from OH_profile.write import save_OH_profile, write_to_OH_profile

# ------------------------------------------------------------------------------------------------------------------- #
# flags
# ------------------------------------------------------------------------------------------------------------------- #
GENERATE_SCORES = True
PROCESS_PSYCHOSOCIAL = True
PROCESS_PERSONAL = False
PROCESS_ENVIRONMENT = False
PROCESS_BIOMECHANICAL = False
PROCESS_WORKLOAD = False
GENERATE_QUESTIONNAIRES_DATASET = False
GENERATE_OH_PROFILE = False

# ------------------------------------------------------------------------------------------------------------------- #
# file constants
# ------------------------------------------------------------------------------------------------------------------- #

QUEST_DATASET_PATH = r"C:\Users\srale\Desktop\carga de trabalho\dataset"
SCORES_OUT_PATH = r"C:\Users\srale\Desktop\carga de trabalho\results"
RAW_LIMESURVEY_PATH = R"C:\Users\srale\Desktop\sara\limesurvey_questionarios"
DATASET_OUTPUT_PATH = "C:\\Users\\srale\\Desktop\\carga de trabalho\\dataset"
OH_PROFILE_PATH = r"C:\Users\srale\Desktop\OH_profiles"

# ------------------------------------------------------------------------------------------------------------------- #
# generate dataset from raw and unfiltered limesurvey files
# ------------------------------------------------------------------------------------------------------------------- #

if GENERATE_QUESTIONNAIRES_DATASET:
    questionnaires.generate_questionnaires_dataset(RAW_LIMESURVEY_PATH, DATASET_OUTPUT_PATH)


# ------------------------------------------------------------------------------------------------------------------- #
# calculate scores and generate csv files with the results
# ------------------------------------------------------------------------------------------------------------------- #

if GENERATE_SCORES:

    # cycle over the several group folders with the questionnaire data
    for group_folder in os.listdir(QUEST_DATASET_PATH):

        # inside there should be two folder: 'sensors' and 'questionnaires'
        for questionnaires_folder in os.listdir(os.path.join(QUEST_DATASET_PATH, group_folder)):

            # go into questionnaires
            if questionnaires_folder == 'questionnaires':

                # get questionnaire folder path
                domain_folder_path = os.path.join(QUEST_DATASET_PATH, group_folder, questionnaires_folder)

                if PROCESS_PSYCHOSOCIAL:

                    # generate individual results
                    questionnaires.calculate_linear_scores(domain_folder_path, domain='psychosocial',
                                                           output_folder_path=SCORES_OUT_PATH)

                if PROCESS_ENVIRONMENT:
                    questionnaires.calculate_linear_scores(QUEST_DATASET_PATH, domain='environment',
                                                           output_folder_path=SCORES_OUT_PATH)

                if PROCESS_PERSONAL:
                    questionnaires.calculate_personal_scores(domain_folder_path, output_folder_path=SCORES_OUT_PATH)

                if PROCESS_BIOMECHANICAL:
                    questionnaires.calculate_biomechanical_scores(domain_folder_path, pure_rosa=False,
                                                                  output_folder_path=SCORES_OUT_PATH)

                    questionnaires.calculate_rosa_scores(domain_folder_path, output_folder_path=SCORES_OUT_PATH)

                if PROCESS_WORKLOAD:
                    questionnaires.clean_daily_workload(domain_folder_path, output_folder_path=SCORES_OUT_PATH)

    # generate copsoq and mueq scores only if PROCESS PSYCHOSOCIAL = True since it needs the scores from all subjects
    if PROCESS_PSYCHOSOCIAL:

        # get copsoq and mueq scores # TODO ADD CHECK FOR AVERAGE METHOD
        questionnaires.get_psychosocial_scores(SCORES_OUT_PATH, average_method='population',
                                               output_folder_path=SCORES_OUT_PATH)
        questionnaires.get_psychosocial_scores(SCORES_OUT_PATH, average_method='work_type',
                                               output_folder_path=SCORES_OUT_PATH)


# ------------------------------------------------------------------------------------------------------------------- #
# write results to the OH profiles - all groups and all subjects
# ------------------------------------------------------------------------------------------------------------------- #

if GENERATE_OH_PROFILE:

    # (1) iterate through the folders inside the questionnaire scores directory
    for group_folder in os.listdir(SCORES_OUT_PATH):

        # get path
        path = os.path.join(SCORES_OUT_PATH, group_folder)

        # get list of ids for this group
        list_ids = sl.get_ids_per_group(sl.load_participants_info(), group=re.findall(r"\d+", group_folder)[0])

        # (2) cycle over the ids in the group
        for subject_id in list_ids:

            # open or generate OH dictionary for this subject
            oh_profile = get_OH_profile(OH_PROFILE_PATH, subject_id)

            # check if it's a file and not a folder
            if os.path.isfile(path):

                # if it's a file then it's the psychosocial scores
                metrics_dict = questionnaires.get_psychosocial_metrics(path)

                # write to OH profile
                oh_profile = write_to_OH_profile(oh_profile, main_outer_key=SINGLE_INSTANCE_QUESTIONNAIRE_KEY,
                                                 main_inner_key=PSYCHOSOCIAL_DOMAIN_KEY,
                                                 dict_to_write=metrics_dict)

            # subject specific scores
            else:

                # (3) iterate through the score files for that group
                for results_file in os.listdir(path):

                    # generate path to csv file
                    results_file_path = os.path.join(path, results_file)

                    # check if it is a single instance questionnaire - save metrics
                    if WORKLOAD in results_file_path:
                        print(f"Getting metrics for daily workload questionnaire of subject {subject_id}...")

                        # get metrics
                        metrics_dict = questionnaires.get_daily_workload_metrics(results_file_path, int(subject_id))

                        # write to OH profile
                        oh_profile = write_to_OH_profile(oh_profile, main_outer_key=DAILY_QUESTIONNAIRE_DOMAIN_KEY,
                                                         main_inner_key=WORKLOAD_DOMAIN_KEY,
                                                         dict_to_write=metrics_dict)

                    # it's single instance questionnaire - save metrics
                    else:

                        print(f"Getting metrics for {results_file} of subject {subject_id}...")
                        # get metrics
                        metrics_dict = questionnaires.get_single_instance_questionnaire_metrics(results_file_path, int(subject_id))

                        # get the main inner key depending on the questionnaire type
                        main_inner_key = questionnaires.get_domain_key_from_filename(results_file_path)

                        # write to OH profile
                        oh_profile = write_to_OH_profile(oh_profile, main_outer_key=SINGLE_INSTANCE_QUESTIONNAIRE_KEY,
                                                         main_inner_key=main_inner_key,
                                                         dict_to_write=metrics_dict)

                    # save OH profile to json
                    save_OH_profile(OH_PROFILE_PATH, subject_id, oh_profile)



