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
from matplotlib.lines import Line2D
import os
import math
import copy
from babel.dates import format_datetime
from datetime import datetime

# internal imports
from OH_profile.constants import (PSYCHOSOCIAL_COPSOQ_WORK_TYPE_KEY, PSYCHOSOCIAL_COPSOQ_POPULATION_KEY,
                                  PSYCHOSOCIAL_MUEQ_WORK_TYPE_KEY, PSYCHOSOCIAL_MUEQ_POPULATION_KEY,
                                  DAILY_QUESTIONNAIRE_DOMAIN_KEY, WORKLOAD_DOMAIN_KEY)
from sensors.visualize import get_weekday_name
from sensors.visualize.constants import RED, GREEN, YELLOW
from sensors.visualize.plot_utils import handle_plot
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



# Likert scale (5-point)

LIKERT_SCALE = {
    1: "Strongly disagree",
    2: "Disagree",
    3: "Neutral",
    4: "Agree",
    5: "Strongly agree"
}

LIKERT_VALUES = list(LIKERT_SCALE.keys())


# Language mapping
LANG_MAPPING = {
    "eng": {
        "likert": LIKERT_SCALE,
        "locale": "en_US"
    },
    "pt": {
        "likert": {
            1: "Discordo totalmente",
            2: "Discordo",
            3: "Neutro",
            4: "Concordo",
            5: "Concordo totalmente"
        },
        "locale": "pt_PT"
    }
}

QUESTION_LABEL_MAPPING = {
    "pt": {
        "focus_and_mental_strain": "Concentração e esforço mental",
        "rushed_and_under_pressure": "Apressado e sobre pressão",
        "frequent_interruptions": "Interrupções frequentes",
        "more_effort_than_resources": "Mais esforço do que recursos",
        "heavy_workload": "Carga de trabalho elevada"
    },
    "eng": {
        # optional, if you want cleaner English labels
        "focus_and_mental_strain": "Focus and mental strain",
        "rushed_and_under_pressure": "Rushed and under pressure",
        "frequent_interruptions": "Frequent interruptions",
        "more_effort_than_resources": "More effort than resources",
        "heavy_workload": "Heavy workload"
    }
}

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




def generate_workload_plot(oh_profile: Dict[str, Any], subject_id: str, output_folder_path: str, language: str = "pt", color: str = "#577590") -> None:
    """

    :param oh_profile:
    :param subject_id:
    :param output_folder_path:
    :param language:
    :param color:
    :return:
    """

    lang_cfg = LANG_MAPPING.get(language, LANG_MAPPING["eng"])
    locale = lang_cfg["locale"]
    likert_labels = lang_cfg["likert"]

    # get the workload data from the oh_profile
    work_load_dict = oh_profile[DAILY_QUESTIONNAIRE_DOMAIN_KEY][WORKLOAD_DOMAIN_KEY]

    work_load_dict = {
        k: v for k, v in work_load_dict.items()
        if isinstance(v, dict) and len(v) > 0
    }


    fig, axes = plt.subplots(1, len(work_load_dict), figsize=(18, 4), sharey=True)

    axes = axes.flatten()
    x_labels = []

    # cycle over the days and sub_dicts
    for ax, (acquisition_date, sub_dict) in zip(axes, work_load_dict.items()):

        # Remove spines (keep only bottom)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)

        # transform the date to weekday
        try:
            weekday_str = format_datetime(datetime.strptime(acquisition_date, "%d-%m-%Y"), "EEEE",
                                          locale="pt_PT")
        except:
            weekday_str = acquisition_date

        x_positions = []
        x_labels = []

        # pop the last question
        sub_dict.pop('open_question')

        for pos, (q_item, value) in enumerate(sub_dict.items()):

            x_positions.append(pos)
            x_labels.append(q_item)

            # Thick horizontal line instead of bar
            ax.hlines(
                y=value,
                xmin=pos - 0.35,
                xmax=pos + 0.35,
                linewidth=3,
                color=color
            )

        ax.set_xticks(x_positions)
        ax.set_xticklabels([str(i + 1) for i in x_positions])
        ax.set_title(weekday_str)

        ax.set_ylim(0.5, 5.5)
        ax.set_yticks(LIKERT_VALUES)
        ax.set_yticklabels([likert_labels[v] for v in LIKERT_VALUES])

        ax.grid(
            axis="y",
            linestyle="--",
            linewidth=0.8,
            alpha=0.7
        )

    # transform legend labels
    if x_labels:

        x_labels =  [_format_question_key(label, language) for label in x_labels]


    legend_handles = [
        Line2D(
            [], [],
            linestyle=None,
            label=rf"$\bf{{{i + 1}}}$ – {key}"
        )
        for i, key in enumerate(x_labels)
    ]

    fig.legend(
        handles=legend_handles,
        loc="lower center",
        ncol=len(legend_handles),
        frameon=False,
        handlelength=0,
        handletextpad=0.4,
        fontsize=9
    )

    # add suptitle
    #fig.suptitle("Resultados dos Questionários da Carga de Trabalho")
    fig.subplots_adjust(top=0.82, bottom=0.25)

    # create output path
    output_path = create_dir(output_folder_path, os.path.join(f"{subject_id}", "questionnaire_plots"))

    # create file name
    file_name = f'{subject_id}_carga_de_trabalho.png'

    # save the plot
    handle_plot(save_dir=output_path, filename=file_name, save=True)



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


def _format_question_key(key: str, language: str) -> str:
    """
    Convert a question key to a human-readable label:
    - replace underscores with spaces
    - apply language translation if available

    :param key: Original dictionary key
    :param language: 'pt' or 'eng'
    :return: Formatted question label
    """
    if key in QUESTION_LABEL_MAPPING.get(language, {}):
        return QUESTION_LABEL_MAPPING[language][key]

    # fallback: replace underscores and capitalize first letter
    return key.replace("_", " ").capitalize()