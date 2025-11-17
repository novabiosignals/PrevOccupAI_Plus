# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import questionnaire_processing as qp

# ------------------------------------------------------------------------------------------------------------------- #
# constants
# ------------------------------------------------------------------------------------------------------------------- #
PROCESS_PSICOSSOCIAL = True
PROCESS_PESSOAIS = True
PROCESS_AMBIENTE = True
PROCESS_BIOMECANICO = False
GENERATE_QUESTIONNAIRES_DATASET = False

quest_path = "C:\\Users\\srale\\Desktop\\TESTE\\group7\\questionnaires"
ls_input_path = "C:\\Users\\srale\\Desktop\\limesurvey_questionarios"
ls_output_path = "C:\\Users\\srale\\Desktop\\TESTE"

# ------------------------------------------------------------------------------------------------------------------- #
# program starts here
# ------------------------------------------------------------------------------------------------------------------- #

if __name__ == '__main__':


    if PROCESS_PSICOSSOCIAL:
        qp.calculate_linear_scores(quest_path, domain='psicosocial')

    if PROCESS_AMBIENTE:
        qp.calculate_linear_scores(quest_path, domain='ambiente')

    if PROCESS_PESSOAIS:
        qp.calculate_personal_scores(quest_path)

    if PROCESS_BIOMECANICO:
        qp.calculate_biomechanical_scores(quest_path)

    if GENERATE_QUESTIONNAIRES_DATASET:
        qp.generate_questionnaires_dataset(ls_input_path, ls_output_path)
