# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import os
import re

# internal imports
import questionnaires
import sensors.load as sl
from constants import WORKLOAD, PSYCHOSOCIAL, PERSONAL, WORK_TYPE, BIOMECHANICAL
from OH_profile.constants import *
from OH_profile.load import get_OH_profile
from OH_profile.write import save_OH_profile, write_to_OH_profile, clear_dict_entries
from questionnaires.visualize.questionnaires import ROSA_KEYS_KEEP
import questionnaires.visualize as qv
import questionnaires.metrics as qm
# ------------------------------------------------------------------------------------------------------------------- #
# flags
# ------------------------------------------------------------------------------------------------------------------- #
# flags to generate the scores
GENERATE_SCORES = False
PROCESS_PSYCHOSOCIAL = True
PROCESS_PERSONAL = True
PROCESS_ENVIRONMENT = True
PROCESS_BIOMECHANICAL = True
PROCESS_WORKLOAD = True

# generate the raw dataset
GENERATE_QUESTIONNAIRES_DATASET = False

# generate OH profile
GENERATE_OH_PROFILE = False
RERUN_OH_PROFILE = True

# generate visualizations
VISUALIZE = True

# ------------------------------------------------------------------------------------------------------------------- #
# file constants
# ------------------------------------------------------------------------------------------------------------------- #
DRIVE = 'E'
DATASET_PATH = f'{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\data'
QUEST_DATASET_PATH = f'{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\data'
SCORES_OUT_PATH = f"{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\questionnaire_scores"
OH_PROFILE_PATH = f"{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\OH_profiles"

RAW_LIMESURVEY_PATH = f"{DRIVE}:\\limesurvey_questionarios"
DATASET_OUTPUT_PATH = f"{DRIVE}:\\q_processed"

PLOTS_OUTPUT_PATH = f"{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\OH_plots"

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

        # if it's a folder (example: group1, group2, group3)
        if os.path.isdir(os.path.join(QUEST_DATASET_PATH, group_folder)):

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
                        questionnaires.calculate_linear_scores(domain_folder_path, domain='environment',
                                                               output_folder_path=SCORES_OUT_PATH)

                    if PROCESS_PERSONAL:
                        questionnaires.calculate_personal_scores(domain_folder_path, output_folder_path=SCORES_OUT_PATH)

                    if PROCESS_BIOMECHANICAL:
                        questionnaires.calculate_biomechanical_scores(domain_folder_path, output_folder_path=SCORES_OUT_PATH)

                    if PROCESS_WORKLOAD:
                        questionnaires.clean_daily_workload(domain_folder_path, output_folder_path=SCORES_OUT_PATH)

    # generate copsoq and mueq scores only if PROCESS PSYCHOSOCIAL = True since it needs the scores from all subjects
    if PROCESS_PSYCHOSOCIAL:

        # get copsoq and mueq scores
        questionnaires.get_psychosocial_scores(SCORES_OUT_PATH, average_method='population',
                                               output_folder_path=SCORES_OUT_PATH)
        questionnaires.get_psychosocial_scores(SCORES_OUT_PATH, average_method='work_type',
                                               output_folder_path=SCORES_OUT_PATH)


# ------------------------------------------------------------------------------------------------------------------- #
# write results to the OH profiles - all groups and all subjects
# ------------------------------------------------------------------------------------------------------------------- #

if GENERATE_OH_PROFILE:

    # init list fo holding the id's of all participants
    all_ids = []

    # (1) iterate through the folders inside the questionnaire scores directory
    for group_folder in os.listdir(SCORES_OUT_PATH):

        # get path
        path = os.path.join(SCORES_OUT_PATH, group_folder)

        # subject specific scores
        if os.path.isdir(path):

            # get list of ids for this group
            list_ids = sl.get_ids_per_group(sl.load_participants_info(), group=re.findall(r"\d+", group_folder)[0])

            # (2) cycle over the ids in the group
            for subject_id in list_ids:

                # add to list of all ids
                all_ids.append(subject_id)

                # open or generate OH dictionary for this subject
                oh_profile = get_OH_profile(OH_PROFILE_PATH, subject_id)

                # (3) iterate through the score files for that group (example: results_biomechanical.csv, results_personal.csv...)
                for results_file in os.listdir(path):

                    # generate path to csv file
                    results_file_path = os.path.join(path, results_file)

                    # check if it is a single instance questionnaire
                    if WORKLOAD in results_file_path:
                        print(f"Getting metrics for daily workload questionnaire of subject {subject_id}...")

                        # get metrics
                        metrics_dict = qm.get_daily_workload_metrics(results_file_path, int(subject_id))

                        # write to OH profile
                        oh_profile = write_to_OH_profile(oh_profile, main_outer_key=DAILY_QUESTIONNAIRE_DOMAIN_KEY,
                                                         main_inner_key=WORKLOAD_DOMAIN_KEY,
                                                         dict_to_write=metrics_dict)

                    # it's single instance questionnaire except psychosocial
                    elif PSYCHOSOCIAL not in results_file_path:

                        # use personal questionnaire results to add the metadata
                        if PERSONAL in results_file_path:

                            # add metadata to OH profile
                            metadata_dict = qm.get_metadata_metrics(results_file_path, int(subject_id))

                            # add personal scores to the oh profile
                            personal_metrics_dict = qm.get_single_instance_questionnaire_metrics(results_file_path,int(subject_id),domain=PERSONAL)

                            # write to oh profile
                            oh_profile = write_to_OH_profile(oh_profile, main_outer_key=METADATA_KEY,main_inner_key=None, dict_to_write=metadata_dict)
                            oh_profile = write_to_OH_profile(oh_profile,main_outer_key=SINGLE_INSTANCE_QUESTIONNAIRE_KEY,
                                                             main_inner_key=PERSONAL_DOMAIN_KEY, dict_to_write=personal_metrics_dict)

                        elif BIOMECHANICAL in results_file_path:

                            # get metrics
                            metrics_dict = qm.get_single_instance_questionnaire_metrics(results_file_path, int(subject_id), domain=BIOMECHANICAL)

                            # write to OH profile
                            oh_profile = write_to_OH_profile(oh_profile, main_outer_key=SINGLE_INSTANCE_QUESTIONNAIRE_KEY,
                                                             main_inner_key=BIOMECHANICAL_DOMAIN_KEY, dict_to_write=metrics_dict)

                        else: # its environmental
                            # get metrics
                            metrics_dict = qm.get_single_instance_questionnaire_metrics(results_file_path,int(subject_id),domain=None)

                            # write to OH profile
                            oh_profile = write_to_OH_profile(oh_profile, main_outer_key=SINGLE_INSTANCE_QUESTIONNAIRE_KEY,
                                                             main_inner_key=ENVIRONMENTAL_DOMAIN_KEY,dict_to_write=metrics_dict)

                    # save OH profile to json
                    save_OH_profile(OH_PROFILE_PATH, subject_id, oh_profile)

        # if it's not a dir then it's a csv file with copsoq or mueq
        else:

            # the results are the same for all subjects
            for participant_id in all_ids:

                # check if the file corresponds to COPSOQ/MUEQ scores with work_type mean
                if WORK_TYPE in path:

                    # check the work_type of the subject
                    work_type = sl.get_participant_work_type(sl.load_participants_info(), int(participant_id))


                # open or generate OH dictionary for this subject
                oh_profile = get_OH_profile(OH_PROFILE_PATH, participant_id)

                # if it's a file then it's the psychosocial scores
                metrics_dict = qm.get_psychosocial_metrics(path, int(participant_id))

                # write to OH profile
                oh_profile = write_to_OH_profile(oh_profile, main_outer_key=SINGLE_INSTANCE_QUESTIONNAIRE_KEY,
                                                 main_inner_key=PSYCHOSOCIAL_DOMAIN_KEY,
                                                 dict_to_write=metrics_dict)

                # save OH profile to json
                save_OH_profile(OH_PROFILE_PATH, participant_id, oh_profile)


# ------------------------------------------------------------------------------------------------------------------- #
# visualize
# ------------------------------------------------------------------------------------------------------------------- #

if VISUALIZE:

    # get list with all subject ids
    subject_id_list = sl.get_participant_ids_list(sl.load_participants_info())

    # cycle over the subject id's
    for subject_id in subject_id_list:

        # get oh profile
        oh_profile = get_OH_profile(OH_PROFILE_PATH, subject_id)

        # check if there are biomechanical metrics to plot
        if len(oh_profile[SINGLE_INSTANCE_QUESTIONNAIRE_KEY][BIOMECHANICAL_DOMAIN_KEY]) > 0:

            # plot rosa
            qv.generate_biomec_env_plots(oh_profile[SINGLE_INSTANCE_QUESTIONNAIRE_KEY][BIOMECHANICAL_DOMAIN_KEY],
                                                     subject_id, PLOTS_OUTPUT_PATH, filename_suffix='Rosa',keys_to_keep=ROSA_KEYS_KEEP, is_rosa=True)

            # plot environmental results
            qv.generate_biomec_env_plots(oh_profile= oh_profile[SINGLE_INSTANCE_QUESTIONNAIRE_KEY][ENVIRONMENTAL_DOMAIN_KEY],
                                                     subject=subject_id, output_folder_path=PLOTS_OUTPUT_PATH, filename_suffix='environment')

            # plot copsoq and mueq
            qv.generate_copsoq_mueq_plots(oh_profile[SINGLE_INSTANCE_QUESTIONNAIRE_KEY][PSYCHOSOCIAL_DOMAIN_KEY],
                                                      subject_id, PLOTS_OUTPUT_PATH)

        else:
            print(f"No biomechanical metrics to plot for subject {subject_id}. \nPlease generate the oh profile first by setting {GENERATE_OH_PROFILE} to True.")
