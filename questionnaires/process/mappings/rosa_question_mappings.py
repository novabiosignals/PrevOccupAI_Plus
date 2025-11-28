"""
File containing a dictionaries for multiple choice questions of the ROSA questionnaire.
The dictionary names are according to the question names defined in LimeSurvey
"""
rosa_a_score_columns = ['submitdate', 'id.1', 'opDuracaoCadeira', 'opAlturaCadeira', 'snEspacoCadeira', 'snAjustCadeira', 'opProfunAssento',
                        'snProfunAjustAssento', 'opAnguloEncosto', 'snAjustEncosto', 'opAltApoioBrasos', 'snSuperfiApoioBrasos',
                        'snAfastadApoioBracos', 'snAjustApoioBracos', 'opAlturaMesa']

rosa_b_c_score_columns = ['submitdate', 'id.1', 'opDuracaoComputador', 'opPosMonitor', 'snDistancMonitor', 'snPosPrincMonitor',
                          'snDocSupMonitor', 'opPosRato', 'snFormTamRato', 'snApoioErgonRato', 'snPosTecladoRato', 'opPosTeclado',
                          'snDesvioTeclado', 'snAltoTeclado', 'snAcimaTeclado', 'snAjustTeclado', 'snFonesTelefone', 'opSeguraTelefone',
                          'snDistanciaTelefone', 'opDuracaoTelefone'

]

# dictionary containing all the mappings for the rosa multiple choice questions of section a
rosa_mappings_section_a = {

    "opDuracaoCadeira": {
        "A1": -1,
        "A2": 0,
        "A3": 1
    },
    "opAlturaCadeira": {
        "A1": 1,
        **dict.fromkeys(["A2", "A3"], 2),
        "A4": 3
    },
    "opProfunAssento": {
        "A1": 1,
        **dict.fromkeys(["A2", "A3"], 2),
    },
    "opAnguloEncosto": {
        "A1": 1,
        **dict.fromkeys(["A2", "A3", "A4"], 2),
    },
    "opAltApoioBrasos": {
        "A1": 1,
        **dict.fromkeys(["A2", "A3"], 2),
    },
    "opAlturaMesa": {
        "A1": 0,
        **dict.fromkeys(["A2", "A3"], 1),
    }
}

# dictionary containing all the mappings of section b for the rosa multiple choice questions as well as some yes/no
# question that need a special mapping
rosa_mappings_section_b = {

    "opDuracaoComputador": {
        "A1": -3,
        "A2": 0,
        "A3": 3
    },
    "opPosMonitor": {
        "A1": 1,
        "A2": 2,
        "A3": 3
    },
    "snDistancMonitor": {
        "N": 0,
        "Y": 1
    },
    "opNumMonitor": {
        **dict.fromkeys(["A1", "A2", "A3"], 0)
    },
    "snTelefone": {
        **dict.fromkeys(["Y", "N"], 0)
    },
    "opDuracaoTelefone": {
        "A1": -1,
        "A2": 0,
        "A3": 1
    },
    "snFonesTelefone": {
        **dict.fromkeys(["Y", "N"], 1)
    },
    "opSeguraTelefone": {
        "A1": 1,
        "A2": 2
    },
    "snDistanciaTelefone": {
        "N": 0,
        "Y": 2
    }
}

rosa_mappings_section_c = {

    "snRato": {
        "N": 4,
        "Y": 0
    },
    "opPosRato": {
        "A1": 1,
        "A2": 2
    },
    "snPosTecladoRato": {
        "N": 0,
        "Y": 2
    },
    "opPosTeclado": {
        "A1": 2,
        "A2": 1
    },
    "snDesvioTeclado": {
        "N": 0,
        "Y": 1
    },
    "snAltoTeclado": {
        "N": 0,
        "Y": 1
    },
    "snAcimaTeclado": {
        "N": 0,
        "Y": 1
    },
    "opRatoUtil": {
        "A1": 1,
        "A2": 0,
        "A3": -1,
        "A4": -1,
    }

}

# dict for yes/no questions
sn = {
    "Y": 0,
    "N": 1
}