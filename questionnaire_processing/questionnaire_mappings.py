"""
File containing a dictionaries and lists to map the column names from limesurvey with more readable ones. And also to map
the code responses to readable text
"""


# ------------------------------------------------------------------------------------------------------------------- #
# Estilo de Vida mappings
# ------------------------------------------------------------------------------------------------------------------- #

EV_COLUMN_NAMES_MAP = {
        'q1': 'fuma',
        'q1a': 'cigarros_dia',
        'q1b[SQ001]': 'tempo_fuma_meses',
        'q1b[SQ002]': 'tempo_fuma_anos',
        'q1c': 'cigarros_passado_unit',
        'q1d[SQ001]': 'tempo_passado_meses',
        'q1d[SQ002]': 'tempo_passado_anos',
        'q2': 'alcool',
        'q2a': 'bebidas',
    }

EV_ANSWERS_MAP = {
        'fuma': {
            'A1': 'Sim, diariamente',
            'A2': 'Ocasionalmente',
            'A3': 'Não, mas fumou no passado',
            'A4': 'Não, nunca fumou',
            'A5': 'Não sabe/Não responde',
        },
        'alcool': {
            'A1': 'Diariamente',
            'A2': 'Ocasionalmente',
            'A3': 'Nunca',
            'A4': 'Não sabe/Não responde',
        },
        'bebidas': {
            'A1': '< 3 semana',
            'A2': '> 3 semana',
            'A3': '> 3 dia',
        },
    }


# ------------------------------------------------------------------------------------------------------------------- #
# Atividade Fisica mappings
# ------------------------------------------------------------------------------------------------------------------- #

AF_OLD_COLUMNS = [
    'q1a', 'q1b[SQ001]', 'q1b[SQ002]',
    'q2a', 'q2b[SQ001]', 'q2b[SQ002]',
    'q3a', 'q3b[SQ001]', 'q3b[SQ002]', 'q3c',
    'q4a[SQ001]', 'q4a[SQ002]', 'q4b[SQ001]', 'q4b[SQ002]', 'horasTrabalho', 'diasTrabalho', 'ospaqDist[sentado]',
    'ospaqDist[pe]', 'ospaqDist[caminhando]', 'ospaqDist[trabPesado]'
]

AF_NEW_COLUMNS = [
    'vigorosa_dias', 'vigorosa_horas', 'vigorosa_minutos',
    'moderada_dias', 'moderada_horas', 'moderada_minutos',
    'caminhada_dias', 'caminhada_horas', 'caminhada_minutos', 'caminhada_ritmo',
    'sentada_semana_horas', 'sentada_semana_minutos',
    'sentada_fds_horas', 'sentada_fds_minutos',
    'horas_trabalho_semana', 'dias_trabalho_semana',
    'percentagem_sentado', 'percentagem_pe',
    'percentagem_caminhar', 'percentagem_trab_pesado'
]

AF_TIME_PAIRS = [
        ('vigorosa_horas', 'vigorosa_minutos'),
        ('moderada_horas', 'moderada_minutos'),
        ('caminhada_horas', 'caminhada_minutos'),
        ('sentada_semana_horas', 'sentada_semana_minutos'),
        ('sentada_fds_horas', 'sentada_fds_minutos'),
    ]

# ------------------------------------------------------------------------------------------------------------------- #
# Dados Demográficos mappings
# ------------------------------------------------------------------------------------------------------------------- #
DD_COLUMN_NAMES_MAP = {
        'profissao[other]': 'profissao_outro',
        'anosProf[SQ001]': 'anos_profissao',
        'anosProf[SQ002]': 'meses_profissao'
    }


DD_ANSWERS_MAP = {
    'sexo': {
        'A1': 'F',
        'A2': 'M',
        'A3': 'O',
    },
    'mao': {
        'A1': 'D',
        'A2': 'E',
        'A3': 'O',
    },
    'estadoCivil': {
        'A1': 'Solteiro',
        'A2': 'Casado',
        'A3': 'Divorciado',
        'A4': 'Viúvo',
        'A5': 'União de Facto',
    },
    'habilitacoes': {
        'A1': 'Ensino Obrigatório (9º ano)',
        'A2': 'Ensino Secundário (10º a 12º ano)',
        'A3': 'Ensino Técnico-profissional',
        'A4': 'Ensino Superior (bacharelato ou licenciatura)',
        'A5': 'Ensino Superior Pós-graduado (mestrado ou doutoramento)',
    },
    'profissao':{
        'A1': 'Atendimento ao publico presencial',
        'A2': 'Atendimento ao publico por telefone',
        'A3': 'Atendimento ao publico online/chat',
        'A4': 'Back Office',
        'A5': 'Atendimento ao publico e Back Office',
        'A6': 'Outro'
    }
}

# ------------------------------------------------------------------------------------------------------------------- #
# Incapacidade e Sofrimento associados a Dor mappings
# ------------------------------------------------------------------------------------------------------------------- #

ID_OLD_COLUMNS = ['SQ001', 'SQ002', 'SQ003', 'SQ004', 'SQ005', 'SQ006', 'SQ007', 'SQ008', 'SQ009']

ID_NEW_COLUMNS = ['Cervical / pescoço', 'Ombros', 'Região dorsal superior / Torácica',
                       'Braços(cotovelo / antebraço)', 'Punhos / mãos / dedos', 'Região dorsal inferior / Lombar',
                       'Ancas / coxas', 'Joelhos', 'Pés / tornozelos']

ID_ANSWERS_MAP = {
    "incapacidade_sofrimento": {
        "A1": "A2",
        "A2": "leve",
        "A3": "leve",
        "A4": "leve",
        "A5": "moderada",
        "A6": "moderada",
        "A7": "moderada",
        "A8": "severa",
        "A9": "severa",
        "A10": "severa"
    },
    "tempo": {
        "A1": "aguda",
        "A2": "crónica",
        "A3": "crónica",
        "A4": "crónica",
        "A5": "crónica",
        "A6": "crónica"
    }
}

