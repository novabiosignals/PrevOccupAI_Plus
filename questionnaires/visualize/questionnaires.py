"""
Functions to generate the questionnaire heat maps

Available Functions
-------------------
[Public]
generate_biomec_env_plots(...): Generates the heat maps for the biomechanical or environmental scores for one subject.
generate_copsoq_mueq_plots(...): Generates the heat maps for the COPSOQ and MUEQ scores for one subject.
-------------------

[Private]
_create_heat_map(...): Create a single-row heatmap from a DataFrame
-------------------
"""
# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.colors as clr
import os
import math
import copy

# internal imports
from OH_profile.constants import (PSYCHOSOCIAL_COPSOQ_WORK_TYPE_KEY, PSYCHOSOCIAL_COPSOQ_POPULATION_KEY,
                                  PSYCHOSOCIAL_MUEQ_WORK_TYPE_KEY, PSYCHOSOCIAL_MUEQ_POPULATION_KEY)
from sensors.visualize.constants import RED, GREEN, YELLOW
from utils import create_dir
from constants import PNG
import sensors.load as sl

# ------------------------------------------------------------------------------------------------------------------- #
# constants
# ------------------------------------------------------------------------------------------------------------------- #

# keys from the oh profile to keep for the rosa plot
ROSA_KEYS_KEEP = [
        "score_a_adapted",
        "monitor_adapted_norm",
        "phone_adapted_norm",
        "mouse_adapted_norm",
        "keyboard_adapted_norm",
        "final_normalized"
    ]

FILE_FORMAT = PNG

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #

def generate_biomec_env_plots(oh_profile: Dict[str, Any], subject: str, output_folder_path: str, filename_suffix: str,
                              is_rosa: bool, keys_to_keep: Optional[List[str]] = None) -> None:
    """
    Generates the heat maps for the biomechanical or environmental scores for one subject. From these scores, only the ones
    in keys_to_keep are used fo plotting.
    :param oh_profile: dictionary containing only the biomechanical/environmental questionnaire scores.
    :param subject: subject identifier
    :param output_folder_path: Path to the folder where the plots should be saved
    :param filename_suffix: Filename suffix appended to all plots.
    :param keys_to_keep: list of keys to keep. If none are provided, all are kept (default = None)
    :param is_rosa: if True, handle the ROSA_final_normalized column specially (default=False)
    :return: None
    """
    if is_rosa:
        oh_profile = oh_profile['ROSA']

    # create copy
    biomechanical_dict = copy.deepcopy(oh_profile)

    # remove columns that are not needed
    if keys_to_keep is not None:

        # keep only the relevant rosa questions
        biomechanical_dict = {k: oh_profile[k] for k in keys_to_keep}

    # convert the filtered dictionary into a single-row DataFrame
    df = pd.DataFrame([biomechanical_dict])

    # substitute the scores in the df with a discrete scale (0,1,2) depending on the interval. This is used for the colormap
    # Map score to 0/1/2 based on range: 0–1/3 → 0, 1/3–2/3 → 1, 2/3–1 → 2, NaN -> -1
    # cycle over the columns
    for i, col in enumerate(df.columns):

        # get the value
        score = df.iloc[0, i]

        # if NaN -> -1
        if score is None or (isinstance(score, float) and math.isnan(score)):
            df.iloc[0, i] = -1

        # if 0–1/3 → 0
        elif score <= 1 / 3:
            df.iloc[0, i] = 0

        # if 1/3–2/3 → 1
        elif score <= 2 / 3:
            df.iloc[0, i] = 1

        # it's 2/3–1 → 2
        else:
            df.iloc[0, i] = 2

    # generate output path
    output_path = create_dir(output_folder_path, os.path.join(f"{subject}", "questionnaire_plots"))

    # create colormap: gray for missing, then green, yellow, red
    cmap = clr.LinearSegmentedColormap.from_list('name', ['gray', GREEN, YELLOW, RED], N=4)

    # generate heat map
    _create_heat_map(df, output_path, f"{filename_suffix}_plot_{subject}{FILE_FORMAT}", color_map=cmap,vmin=-1,
                     vmax=2, is_rosa=is_rosa)


def generate_copsoq_mueq_plots(oh_profile: Dict[str, Any], subject: str, output_folder_path: str) -> None:
    """
    Generates the heat maps for the COPSOQ and MUEQ scores for one subject.
    :param oh_profile: dictionary containing only the psychosocial questionnaire scores.
    :param subject: subject identifier
    :param output_folder_path: path to the folder where the plots should be saved
    :return: None
    """

    # get work type from subject id
    work_type = sl.get_participant_work_type(sl.load_participants_info(), subject_id=int(subject))

    # init list for holding the dataframes
    df_list: List[pd.DataFrame] = []

    # list for holding filename identifiers
    filename_str_list: List[str] = []

    # generate output path
    output_path = create_dir(output_folder_path, os.path.join(f"{subject}", "questionnaire_plots"))

    # from the OH profile, extract copsoq/ mueq scores
    df_copsoq_pop = pd.DataFrame([oh_profile[PSYCHOSOCIAL_COPSOQ_POPULATION_KEY]])
    df_copsoq_w_type = pd.DataFrame([oh_profile[f'{PSYCHOSOCIAL_COPSOQ_WORK_TYPE_KEY}_{work_type}']])
    df_mueq_pop = pd.DataFrame([oh_profile[PSYCHOSOCIAL_MUEQ_POPULATION_KEY]])
    df_mueq_w_type = pd.DataFrame([oh_profile[f'{PSYCHOSOCIAL_MUEQ_WORK_TYPE_KEY}_{work_type}']])

    # add to list
    df_list.extend([df_copsoq_pop, df_copsoq_w_type, df_mueq_pop, df_mueq_w_type])
    filename_str_list.extend(['copsoq_population', f'copsoq_{work_type}', 'mueq_population', f'mueq_{work_type}'])

    # create colormap: gray for missing, then green, yellow, red
    cmap = clr.LinearSegmentedColormap.from_list('name', [GREEN, YELLOW, RED], N=3)

    # cycle over the dataframes
    for df, filename_st in zip(df_list, filename_str_list):

        # generate plots
        _create_heat_map(df, output_path, f"{filename_st}{FILE_FORMAT}", color_map= cmap, vmin=0, vmax=1, is_rosa=False)


# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #

def _create_heat_map(df: pd.DataFrame, output_path: str, filename: str, color_map, vmin: int, vmax: int, is_rosa) -> None:
    """
    Create a single-row heatmap from a DataFrame with discrete values (-1 for missing, 0/1/2 for risk).
    If is_rosa=True, moves 'ROSA_final_normalized' to the last column and adds a dashed vertical
    line before it that reaches the xtick numbers without overlapping the last block.

    :param df: single-row DataFrame with columns corresponding to questionnaire items
    :param output_path: folder where the figure will be saved
    :param filename: name of the file to save
    :param is_rosa: if True, handle the ROSA_final_normalized column specially
    """
    # create copy of the original df
    df_plot = df.copy()

    # Move ROSA_final_normalized to last column if needed
    if is_rosa and "final_normalized" in df_plot.columns:
        cols = [c for c in df_plot.columns if c != "final_normalized"] + ["final_normalized"]
        df_plot = df_plot[cols]

    # Plot heatmap
    plt.figure(figsize=(15, 9))  # wider for better spacing
    ax = sns.heatmap(df_plot, cmap=color_map, linecolor='white', linewidths=3,
                     vmin=vmin, vmax=vmax, cbar=False,
                     xticklabels=np.arange(1, df_plot.shape[1] + 1))
    ax.xaxis.tick_top()
    ax.set_yticks([])

    # Adjust spacing
    plt.subplots_adjust(top=0.95,
                        bottom=0.90,
                        left=0.02,
                        right=0.014 + 0.03 * df_plot.shape[1],  # wider for thicker lines
                        hspace=0.958,
                        wspace=0.2)

    # Draw dashed vertical line before ROSA_final_normalized that reaches xtick numbers
    if is_rosa and "final_normalized" in df_plot.columns:

        # Index of last regular column (before final score)
        last_regular_col_idx = df_plot.columns.get_loc("final_normalized") - 1
        pos = ax.get_position()
        total_cols = df_plot.shape[1]

        # place line in the middle of the gap between last regular and final score
        x_fig = pos.x0 + (last_regular_col_idx + 1) / total_cols * (pos.x1 - pos.x0)

        fig = ax.get_figure()
        fig_line = plt.Line2D([x_fig, x_fig], [pos.y0, pos.y1 + 0.03], transform=fig.transFigure,
                              color='black', linewidth=1, linestyle='--')
        fig.add_artist(fig_line)

    # Save figure
    plt.savefig(os.path.join(output_path, filename), bbox_inches='tight', dpi=300)
    plt.close()