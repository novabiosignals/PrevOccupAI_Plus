# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
from typing import Dict
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.colors as clr
import os
import math

# internal imports
from OH_profile.constants import BIOMECHANICAL_DOMAIN_KEY
from sensors.visualize.constants import RED, GREEN, YELLOW
from utils import create_dir
from constants import PNG

# ------------------------------------------------------------------------------------------------------------------- #
# constants
# ------------------------------------------------------------------------------------------------------------------- #

# keys from the oh profile to keep for the rosa plot
ROSA_KEYS_KEEP = [
        "ROSA_score_a_adapted",
        "ROSA_monitor_adapted_norm",
        "ROSA_phone_adapted_norm",
        "ROSA_mouse_adapted_norm",
        "ROSA_keyboard_adapted_norm",
        "ROSA_final_normalized"
    ]

FILE_FORMAT = PNG

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #


def generate_rosa_plots(oh_profile: Dict, subject: str, output_folder_path: str):
    """

    :param oh_profile:
    :param subject:
    :param output_folder_path:
    :return:
    """

    # keep only the relevant rosa questions
    biomechanical_dict = {k: oh_profile[k] for k in ROSA_KEYS_KEEP}

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

    # generate heat map
    _create_heat_map(df, output_path, f"rosa_plot_{subject}{FILE_FORMAT}")



# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #

def _create_heat_map(df: pd.DataFrame, output_path: str, filename: str, is_rosa: bool = True) -> None:
    """
    Create a single-row heatmap from a DataFrame with discrete values (-1 for missing, 0/1/2 for risk).
    If is_rosa=True, moves 'ROSA_final_normalized' to the last column and adds a dashed vertical
    line before it that reaches the xtick numbers without overlapping the last block.

    :param df: single-row DataFrame with columns corresponding to questionnaire items
    :param output_path: folder where the figure will be saved
    :param filename: name of the file to save
    :param is_rosa: if True, handle the ROSA_final_normalized column specially
    """
    df_plot = df.copy()

    # Move ROSA_final_normalized to last column if needed
    if is_rosa and "ROSA_final_normalized" in df_plot.columns:
        cols = [c for c in df_plot.columns if c != "ROSA_final_normalized"] + ["ROSA_final_normalized"]
        df_plot = df_plot[cols]

    # Create colormap: gray for missing, then green, yellow, red
    cmap = clr.LinearSegmentedColormap.from_list('name', ['gray', GREEN, YELLOW, RED], N=4)

    # Plot heatmap
    plt.figure(figsize=(18, 9))  # wider for better spacing
    ax = sns.heatmap(df_plot, cmap=cmap, linecolor='white', linewidths=3,
                     vmin=-1, vmax=2, cbar=False,
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
    if is_rosa and "ROSA_final_normalized" in df_plot.columns:
        # Index of last regular column (before final score)
        last_regular_col_idx = df_plot.columns.get_loc("ROSA_final_normalized") - 1
        pos = ax.get_position()
        total_cols = df_plot.shape[1]
        # place line in the middle of the gap between last regular and final score
        x_fig = pos.x0 + (last_regular_col_idx + 1) / total_cols * (pos.x1 - pos.x0)

        fig = ax.get_figure()
        fig_line = plt.Line2D([x_fig, x_fig], [pos.y0, pos.y1 + 0.03], transform=fig.transFigure,
                              color='black', linewidth=1, linestyle='--')
        fig.add_artist(fig_line)

    # Save figure
    os.makedirs(output_path, exist_ok=True)
    plt.savefig(os.path.join(output_path, filename), bbox_inches='tight', dpi=300)
    plt.close()