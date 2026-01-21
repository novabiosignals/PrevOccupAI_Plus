# ------------------------------------------------------------------------------------------------------------------- #
# PAIN
# ------------------------------------------------------------------------------------------------------------------- #

# Define the color-intensity mapping used in the legend
PAIN_COLORS = {
    "1": "#04ba02",
    "2": "#4ec101",
    "3": "#8bc901",
    "4": "#cad203",
    "5": "#ffd108",
    "6": "#f7a216",
    "7": "#e77529",
    "8": "#db463e",
    "9": "#d8194e",
    "10": "#800000"
}

BODY_PART_MAPPING = {
    "Head (front)": [(140, 0), (270, 140)],
    "Head (back)": [(550, 15), (690, 150)],
    "Neck/Traps (front)": [(120, 140), (300, 180)],
    "Neck/Traps (back)": [(500, 150), (750, 230)],
    "Chest": [(120, 190), (290, 350)],
    "Upper Back": [(540, 230), (700, 360)],
    "Abdomen": [(130, 350), (290, 460)],
    "Lower Back and Buttocks": [(540, 360), (710, 530)],
    "Left Arm (front)": [(285, 185), (375, 500)],
    "Left Arm (back)": [(465, 230), (540, 500)],
    "Right Arm (front)": [(40, 190), (120, 500)],
    "Right Arm (back)": [(700, 230), (790, 500)],
    "Left Hand (front)": [(330, 500), (410, 600)],
    "Left Hand (back)": [(420, 500), (510, 610)],
    "Right Hand (front)": [(0, 500), (80, 600)],
    "Right Hand (back)": [(740, 510), (834, 613)],
    "Left Thigh (front)": [(110, 460), (210, 700)],
    "Left Thigh (back)": [(525, 540), (620, 750)],
    "Right Thigh (front)": [(215, 460), (310, 700)],
    "Right Thigh (back)": [(625, 540), (725, 750)],
    "Left Shin (front)": [(130, 700), (210, 920)],
    "Left Shin (back)": [(550, 750), (625, 900)],
    "Right Shin (front)": [(215, 700), (290, 920)],
    "Right Shin (back)": [(625, 750), (700, 900)],
    "Left Foot (front)": [(140, 920), (210, 1010)],
    "Left Foot (back)": [(560, 900), (625, 1020)],
    "Right Foot (front)": [(215, 920), (290, 1020)],
    "Right Foot (back)": [(625, 900), (700, 1020)]
}

# ------------------------------------------------------------------------------------------------------------------- #
# QUESTIONNAIRES
# ------------------------------------------------------------------------------------------------------------------- #

BIOMECHANICAL_METRIC_LABELS = {
    "pt": {
        "localizacaoDor": "dor_localização",
        "tempoDor": "dor_tempo",
        "incapacidade": "dor_incapacidade",
        "sofrimento": "dor_sofrimento",
        "Intensidade": "dor_intensidade",
        "percecao_dor": "dor_perceção",
        "rosa": "ROSA",
    },
    "en": {
        "localizacaoDor": "pain_location",
        "tempoDor": "pain_duration",
        "incapacidade": "pain_disability",
        "sofrimento": "pain_distress",
        "Intensidade": "pain_intensity",
        "percecao_dor": "pain_perception",
        "rosa": "ROSA",
    },
}

#
OSPAQ_KEYS = {
    "horas_trabalho_semana",
    "dias_trabalho_semana",
    "percentagem_sentado",
    "percentagem_pe",
    "percentagem_caminhar",
    "percentagem_trab_pesado",
}

IPAQ_KEYS = {
    "ipaq",
    "total_met",
}