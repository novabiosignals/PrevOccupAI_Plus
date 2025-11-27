# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
from pathlib import Path
import os

# internal imports
import questionnaires
from utils import find_project_root

# ------------------------------------------------------------------------------------------------------------------- #
# constants
# ------------------------------------------------------------------------------------------------------------------- #
PROCESS_PSICOSSOCIAL = True
PROCESS_PESSOAIS = True
PROCESS_AMBIENTE = True
PROCESS_BIOMECANICO = True
CALCULATE_COPSOQ = True
GENERATE_QUESTIONNAIRES_DATASET = False

quest_path = r"E:\Backup PrevOccupAI_PLUS Data\data\group1\questionnaires"
limesurvey_input_path = "C:\\Users\\srale\\Desktop\\limesurvey_questionarios"
dataset_output_path = "C:\\Users\\srale\\Desktop\\TESTE"
# ------------------------------------------------------------------------------------------------------------------- #
# program starts here
# ------------------------------------------------------------------------------------------------------------------- #

if __name__ == '__main__':


    if PROCESS_PSICOSSOCIAL:
        questionnaires.calculate_linear_scores(quest_path, domain='psicosocial')

    if CALCULATE_COPSOQ:

        # get path to the questionnaire results
        results_path = find_project_root() / "results_questionnaires"

        # calculate copsoq scores
        if results_path.exists():
            questionnaires.calculate_copsoq_mean_scores(results_path, average_method='all')

        else:
            print("Psicossocial questionnaire results not found. Generating psicossocial results...")
            questionnaires.calculate_linear_scores(quest_path, domain='psicosocial')

            print(f"Calculating COPSOQ scores...")
            questionnaires.calculate_copsoq_mean_scores(results_path, average_method='all')

    if PROCESS_AMBIENTE:
        questionnaires.calculate_linear_scores(quest_path, domain='ambiente')

    if PROCESS_PESSOAIS:
        questionnaires.calculate_personal_scores(quest_path)

    if PROCESS_BIOMECANICO:
        questionnaires.calculate_biomechanical_scores(quest_path, pure_rosa=False)
        questionnaires.calculate_rosa_scores(quest_path)

    if GENERATE_QUESTIONNAIRES_DATASET:
        questionnaires.generate_questionnaires_dataset(limesurvey_input_path, dataset_output_path)
