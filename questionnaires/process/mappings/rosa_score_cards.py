"""
Constants for the rosa score cards
The explanation for the score cards and other relevant information can be found in the original publication
https://www.sciencedirect.com/science/article/abs/pii/S0003687011000433

"""

# ---------------------- IMPORTS ----------------------
import numpy as np

# ---------------------- CONSTANTS ----------------------
# section A (arm rest and back support + seat pan height / depth) score card. The 0 and 1st row/column are made zero
# because in the rosa paper the matrix starts at the 2nd column/row
CARD_A_MATRIX = np.array([[0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                         [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                         [0, 0, 2, 2, 3, 4, 5, 6, 7, 8],
                         [0, 0, 2, 2, 3, 4, 5, 6, 7, 8],
                         [0, 0, 3, 3, 3, 4, 5, 6, 7, 8],
                         [0, 0, 4, 4, 4, 4, 5, 6, 7, 8],
                         [0, 0, 5, 5, 5, 5, 6, 7, 8, 9],
                         [0, 0, 6, 6, 6, 7, 7, 8, 8, 9],
                         [0, 0, 7, 7, 7, 8, 8, 9, 9, 9]])

# section B (monitor + phone) score card
CARD_B_MATRIX = np.array([[1, 1, 1, 2, 3, 4, 5, 6],
                         [1, 1, 2, 2, 3, 4, 5, 6],
                         [1, 2, 2, 3, 3, 4, 6, 7],
                         [2, 2, 3, 3, 4, 5, 6, 8],
                         [3, 3, 4, 4, 5, 6, 7, 8],
                         [4, 4, 5, 5, 6, 7, 8, 9],
                         [5, 5, 6, 7, 8, 8, 9, 9]])

# section C (keyboard + mouse) score card
CARD_C_MATRIX = np.array([[1, 1, 1, 2, 3, 4, 5, 6],
                         [1, 1, 2, 3, 4, 5, 6, 7],
                         [1, 2, 2, 3, 4, 5, 6, 7],
                         [2, 3, 3, 3, 5, 6, 7, 8],
                         [3, 4, 4, 5, 5, 6, 7, 8],
                         [4, 5, 5, 6, 6, 7, 8, 9],
                         [5, 6, 6, 7, 7, 8, 8, 9],
                         [6, 7, 7, 8, 8, 9, 9, 9]])


# monitor and peripherals score card. Combines the scores of CARD_B and CARD_C.
# The first row and column are made zero because in the ROSA paper starts with the 1st column/row
CARD_MAP_MATRIX = np.array([[0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                           [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
                           [0, 2, 2, 3, 4, 5, 6, 7, 8, 9],
                           [0, 3, 3, 3, 4, 5, 6, 7, 8, 9],
                           [0, 4, 4, 4, 4, 5, 6, 7, 8, 9],
                           [0, 5, 5, 5, 5, 5, 6, 7, 8, 9],
                           [0, 6, 6, 6, 6, 6, 6, 7, 8, 9],
                           [0, 8, 8, 8, 8, 8, 8, 8, 8, 9],
                           [0, 9, 9, 9, 9, 9, 9, 9, 9, 9]])


# final score card. Combines the scores of the monitor and peripherals score card with CARD_A
CARD_FINAL_MATRIX = np.array([[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                             [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                             [0, 2, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                             [0, 3, 3, 3, 4, 5, 6, 7, 8, 9, 10],
                             [0, 4, 4, 4, 4, 5, 6, 7, 8, 9, 10],
                             [0, 5, 5, 5, 5, 5, 6, 7, 8, 9, 10],
                             [0, 6, 6, 6, 6, 6, 6, 7, 8, 9, 10],
                             [0, 7, 7, 7, 7, 7, 7, 7, 8, 9, 10],
                             [0, 8, 8, 8, 8, 8, 8, 8, 8, 9, 10],
                             [0, 9, 9, 9, 9, 9, 9, 9, 9, 9, 10],
                             [0, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10]])

CARD_FINAL_MIN_SCORE = 1
CARD_FINAL_MAX_SCORE = 10

# ---------------------- SCORE CARDS DICTIONARIES ----------------------
# the values are taken from the ROSA paper the values with the suffix 'new' are based on the sum of ROSA points and the
# points from the added questions
card_a = {
    'matrix': CARD_A_MATRIX,
    'min': 2,
    'max_vertical': 8,
    'max_vertical_new': 13,
    'max_horizontal': 9,
    'max_horizontal_new': 9
}

card_b = {
    'matrix': CARD_B_MATRIX,
    'min': 0,
    'max_vertical': 6,
    'max_vertical_new': 7,
    'max_horizontal': 7,
    'max_horizontal_new': 9
}

card_c = {
    'matrix': CARD_C_MATRIX,
    'min': 0,
    'max_vertical': 7,
    'max_vertical_new': 9,
    'max_horizontal': 7,
    'max_horizontal_new': 9
}

card_map = {
    'matrix': CARD_MAP_MATRIX,
}

card_final = {
    'matrix': CARD_FINAL_MATRIX,
}