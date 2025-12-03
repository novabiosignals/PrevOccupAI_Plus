# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
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
CLEAN_WORKLOAD = True
GENERATE_QUESTIONNAIRES_DATASET = False

quest_path = r"C:\Users\srale\Desktop\carga de trabalho\dataset\group1\questionnaires"
SCORES_OUT_PATH = r"C:\Users\srale\Desktop\carga de trabalho\results"
limesurvey_input_path = R"C:\Users\srale\Desktop\sara\limesurvey_questionarios"
dataset_output_path = "C:\\Users\\srale\\Desktop\\carga de trabalho\\dataset"
# ------------------------------------------------------------------------------------------------------------------- #
# program starts here
# ------------------------------------------------------------------------------------------------------------------- #

if __name__ == '__main__':


    if PROCESS_PSICOSSOCIAL:
        questionnaires.calculate_linear_scores(quest_path, domain='psicosocial', output_folder_path=SCORES_OUT_PATH)

    if CALCULATE_COPSOQ:


        print("Psicossocial questionnaire results not found. Generating psicossocial results...")
        questionnaires.calculate_linear_scores(quest_path, domain='psicosocial', output_folder_path=SCORES_OUT_PATH)

        print(f"Calculating COPSOQ scores...")
        questionnaires.calculate_copsoq_mean_scores(SCORES_OUT_PATH, average_method='all', output_folder_path=SCORES_OUT_PATH)

    if PROCESS_AMBIENTE:
        questionnaires.calculate_linear_scores(quest_path, domain='ambiente', output_folder_path=SCORES_OUT_PATH)

    if PROCESS_PESSOAIS:
        questionnaires.calculate_personal_scores(quest_path, output_folder_path=SCORES_OUT_PATH)

    if PROCESS_BIOMECANICO:
        questionnaires.calculate_biomechanical_scores(quest_path, pure_rosa=False, output_folder_path=SCORES_OUT_PATH)
        questionnaires.calculate_rosa_scores(quest_path, output_folder_path=SCORES_OUT_PATH)

    if CLEAN_WORKLOAD:
        questionnaires.clean_daily_workload(quest_path, output_folder_path=SCORES_OUT_PATH)

    if GENERATE_QUESTIONNAIRES_DATASET:
        questionnaires.generate_questionnaires_dataset(limesurvey_input_path, dataset_output_path)


