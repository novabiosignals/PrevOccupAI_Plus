# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import os
import re

# internal imports
import questionnaires
import sensors.load as sl
from constants import PSYCHOSOCIAL, ENVIRONMENT, PERSONAL, BIOMECHANICAL, QUESTIONNAIRE_DOMAINS
from OH_profile.constants import *

# ------------------------------------------------------------------------------------------------------------------- #
# flags
# ------------------------------------------------------------------------------------------------------------------- #
GENERATE_SCORES = True
PROCESS_PSYCHOSOCIAL = True
PROCESS_PERSONAL = True
PROCESS_ENVIRONMENT = True
PROCESS_BIOMECHANICAL = True
CALCULATE_COPSOQ = True
PROCESS_WORKLOAD = True
GENERATE_QUESTIONNAIRES_DATASET = False
GENERATE_OH_PROFILE = False

# ------------------------------------------------------------------------------------------------------------------- #
# file constants
# ------------------------------------------------------------------------------------------------------------------- #
KEY_DOMAIN_MAPPING = {PSYCHOSOCIAL: PSYCHOSOCIAL_DOMAIN_KEY, PERSONAL: PERSONAL_DOMAIN_KEY,
                      BIOMECHANICAL: BIOMECHANICAL_DOMAIN_KEY, ENVIRONMENT: ENVIRONMENTAL_DOMAIN_KEY}

quest_path = r"C:\Users\srale\Desktop\carga de trabalho\dataset\group7\questionnaires"
SCORES_OUT_PATH = r"C:\Users\srale\Desktop\carga de trabalho\results"
limesurvey_input_path = R"C:\Users\srale\Desktop\sara\limesurvey_questionarios"
dataset_output_path = "C:\\Users\\srale\\Desktop\\carga de trabalho\\dataset"

# ------------------------------------------------------------------------------------------------------------------- #
# program starts here
# ------------------------------------------------------------------------------------------------------------------- #

# generate dataset from raw and unfiltered limesurvey files
if GENERATE_QUESTIONNAIRES_DATASET:
    questionnaires.generate_questionnaires_dataset(limesurvey_input_path, dataset_output_path)

# calculate scores and generate csv files with te results
if GENERATE_SCORES:

    if PROCESS_PSYCHOSOCIAL:
        questionnaires.calculate_linear_scores(quest_path, domain='psychosocial', output_folder_path=SCORES_OUT_PATH)

    if CALCULATE_COPSOQ:

        print("Generating psicossocial results...")
        questionnaires.calculate_linear_scores(quest_path, domain='psychosocial', output_folder_path=SCORES_OUT_PATH)

        print(f"Calculating COPSOQ scores...")
        questionnaires.calculate_copsoq_mean_scores(SCORES_OUT_PATH, average_method='all', output_folder_path=SCORES_OUT_PATH)

    if PROCESS_ENVIRONMENT:
        questionnaires.calculate_linear_scores(quest_path, domain='environment', output_folder_path=SCORES_OUT_PATH)

    if PROCESS_PERSONAL:
        questionnaires.calculate_personal_scores(quest_path, output_folder_path=SCORES_OUT_PATH)

    if PROCESS_BIOMECHANICAL:
        questionnaires.calculate_biomechanical_scores(quest_path, pure_rosa=False, output_folder_path=SCORES_OUT_PATH)
        questionnaires.calculate_rosa_scores(quest_path, output_folder_path=SCORES_OUT_PATH)

    if PROCESS_WORKLOAD:
        questionnaires.clean_daily_workload(quest_path, output_folder_path=SCORES_OUT_PATH)

# write results to the OH profiles
if GENERATE_OH_PROFILE:

    # iterate through the folders inside the input directory
    for group_folder in os.listdir(SCORES_OUT_PATH):

        # get list of ids for this group
        list_ids = sl.get_ids_per_group(sl.load_participants_info(), group=re.findall(r"\d+", group_folder)[0])

        # cycle over the ids in the group
        for subject_id in list_ids:

            # iterate through the score files for that group
            for cvs_file in os.listdir(os.path.join(SCORES_OUT_PATH, group_folder)):

                # generate path to
                if WORKLOAD not in csv_file:

                    pass









        # # iterate through the domains
        # for domain in QUESTIONNAIRE_DOMAINS:
        #
        #     # check if the domain is in the csv file
        #     if domain in scores_csv:
        #
        #         # get correspondent domain key

        pass

