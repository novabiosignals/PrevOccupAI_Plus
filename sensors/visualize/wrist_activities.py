"""
Functions to generate wrist activities visualizations
"""
# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.patches import Patch
import os
from typing import Dict

# internal imports
from .plot_utils import get_weekday_name
from .constants import ROMAN_NUMBERS
from OH_profile.constants import WRIST_SIGNIFICANT_ROT_PERC_KEY, WRIST_SIGNIFICANT_ACC_PERC_KEY
from utils import create_dir
from constants import PNG

# ------------------------------------------------------------------------------------------------------------------- #
# constants
# ------------------------------------------------------------------------------------------------------------------- #

DAY_ORDER_PT = ['segunda', 'terça', 'quarta', 'quinta', 'sexta']
FILE_FORMAT = PNG
# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #

def plot_wrist_movements_heatmaps(oh_profile, subject: str, output_folder_path: str) -> None:
    """
    Function to generate heatmaps and/or bar charts for wrist acceleration and rotation movements per individual.

    :param oh_profile: dictionary containing wrist movement metrics per session.
    :param subject: subject identifier
    :param output_folder_path: folder path to save the figures.
    :return: None
    """
    # organize wrist metrics for easier manipulation. The dictionary has the following structure:
    # {'acc': [{'weekday': 'segunda', 'acquisition': 'I', 'value': 50}, {'weekday': 'segunda', 'acquisition': 'II', 'value': 30}]
    wrist_metrics_dict = _organize_wrist_activities_from_oh_profile(oh_profile)

    # turn list of dictionaries into pandas DataFrame
    df_acc = pd.DataFrame(wrist_metrics_dict['acc'])
    df_rot = pd.DataFrame(wrist_metrics_dict['rot'])

    # Pivot table for plotting - pivot table organizes the dataframe- index are the days, columns are acquisition
    # numbers and values are the wrist percentages
    heatmap_acc = df_acc.pivot_table(index='weekday', columns='acquisition', values='value', aggfunc='sum')
    heatmap_rot = df_rot.pivot_table(index='weekday', columns='acquisition', values='value', aggfunc='sum')

    # order the days
    heatmap_acc = heatmap_acc.reindex(DAY_ORDER_PT)
    heatmap_rot = heatmap_rot.reindex(DAY_ORDER_PT)

    # generate output folder path
    output_path = create_dir(output_folder_path, os.path.join(str(subject), "wrist_movements"))

    # generate heatmap for the significant accelerations
    _plot_heatmap(heatmap_acc,f"Percentagem de movimentos significativos do pulso","YlOrBr","(%)",
                  output_path, f"wrist_acceleration_{subject}.{FILE_FORMAT}")

    # generate heatmap for the significant rotations
    _plot_heatmap(heatmap_rot,f"Percentagem de movimentos de rotação do pulso significativos","YlGnBu",
                  "(%)",output_path, f"wrist_rotation_{subject}.{FILE_FORMAT}")

# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #


def _organize_wrist_activities_from_oh_profile(oh_profile: dict) -> Dict:
    """
    Process raw metrics dictionary and group acceleration and rotation data per individual.

    :param oh_profile: dictionary with wrist movement metrics of one subject.
    :return: A organized dictionary with the wrist metrics for one subject.
    """
    # init dict for organizing the wrist metrics
    organized_wrist_metrics_dict = {'acc': [],'rot': []}

    # cycle over the different days
    for date_key, session_metrics_dict in oh_profile.items():

        # get week day from the date
        week_day = get_weekday_name(date_key, 'pt_PT.UTF-8')

        # day counter
        day_counter: int = 0

        # cycle over the different sessions
        for acquisition_time_key, wrist_metrics_dict in session_metrics_dict.items():

            # add number to the acquisition (I, II, III, IV), in case there are more than 4 it's IV+
            acq_num = ROMAN_NUMBERS[day_counter] if day_counter < len(ROMAN_NUMBERS) else f'IV+'

            # add dictionary to the list
            organized_wrist_metrics_dict['acc'].append({
                'weekday': week_day,
                'acquisition': acq_num,
                'value': wrist_metrics_dict.get(WRIST_SIGNIFICANT_ACC_PERC_KEY, 0)
            })
            organized_wrist_metrics_dict['rot'].append({
                'weekday': week_day,
                'acquisition': acq_num,
                'value': wrist_metrics_dict.get(WRIST_SIGNIFICANT_ROT_PERC_KEY, 0)
            })
            day_counter += 1

    return organized_wrist_metrics_dict


def _plot_heatmap(df: pd.DataFrame, title: str, color_map: str, value_label: str, output_path: str, filename: str) -> None:
    """
    Plot a heatmap from a pandas DataFrame, showing numbers and shading missing values in gray. Missing values (NaN) are
    shown in gray, with a small legend indicating "no data". The heatmap is annotated with the values, and the figure is
    saved to output_path.

    :param df: pandas DataFrame to plot.
    :param title: plot title.
    :param color_map: color map for heatmap.
    :param value_label: label for colorbar.
    :param output_path: folder to save figure.
    :param filename: filename to save figure.
    """
    # create ask that checks for nan values
    mask_na = df.isna()

    # use dummy valu to substitute the nan values - easier for seaborn to manipulate these
    df_safe = df.fillna(200)

    # define figure
    fig, ax = plt.subplots(figsize=(9, 6))

    sns.heatmap(df_safe,annot=True, fmt=".0f",cmap=color_map,linewidths=0.8,linecolor='white',vmin=0,
        vmax=max(df.max().max(), 1), cbar_kws={'label': value_label}, mask=mask_na, square=False,ax=ax)

    # Shade missing cells gray
    sns.heatmap(df_safe,mask=~mask_na,cmap=sns.light_palette("gray", as_cmap=True),cbar=False,linewidths=0.8,
        linecolor='white',ax=ax)

    # Legend for missing data
    legend_handles = [Patch(facecolor='lightgray', edgecolor='white', label='Sem dados')]
    ax_legend = fig.add_axes([0.85, 0.3, 0.05, 0.4])
    ax_legend.axis('off')
    ax_legend.legend(handles=legend_handles, loc="upper center", bbox_to_anchor=(1.1, 1.5), frameon=False,)

    fig.suptitle(title, fontsize=11, y=0.95)
    ax.set_xlabel("Aquisição")
    ax.set_ylabel("")
    # plt.tight_layout(rect=[0, 0, 0.84, 0.9])

    # save figure
    plt.savefig(os.path.join(output_path, filename), bbox_inches='tight')
    plt.close()
