"""
Functions for plotting environmental sensor data.

Available Functions
-------------------
[Public]
plot_environment_data(...): Generate and save line plots containing the environmental sensor data for one subject.

-------------------
[Private]
_plot_environmental_lines(...): Creates horizontal line plots.
_parse_key(...): Extracts the physical quantity name and unit from a dictionary key.
_plot_reference(...): Draws reference information on a given matplotlib axis.
"""
# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
from typing import Tuple, Dict
from matplotlib.axes import Axes
import matplotlib.pyplot as plt
import os

# internal imports
from OH_profile.constants import *
from utils import create_dir
from constants import PNG
from .constants import LIGHT_PREVOCCUPAI_BLUE

# ------------------------------------------------------------------------------------------------------------------- #
# constants
# ------------------------------------------------------------------------------------------------------------------- #
# legend labels
REFERENCE_VALUE = 'Referência'
REFERENCE_MAX = 'Referência (max.)'
REFERENCE_MIN = 'Referência (min.)'
MEASURED_VALUE = 'Valor medido'

# reference values
CO2_REFERENCE_VALUE_PPM = 1200
CO_REFERENCE_VALUE_PPM = 9
COV_REFERENCE_VALUE_PPM = 12
ILLUMINANCE_REFERENCE_VALUE_LUX = 500
TEMPERATURE_REFERENCE_INTERVAL_CELSIUS = [20, 26]
REL_HUMIDITY_REFERENCE_INTERVAL_PERC = [30, 60]
PM10_REFERENCE_VALUE_UGM3 = 50
PM025_REFERENCE_VALUE_UGM3 = 30

# ppm plots filename
CO2_CO_COV_PLOT_FILENAME = f"CO2_CO_COV_plot{PNG}"
PARTICLES_PLOT_FILENAME = f"PM10_PM025_plot{PNG}"
TEMPERATURE_FILENAME =f"Temperature_plot{PNG}"
HUMIDITY_FILENAME = f"Humidity_plot{PNG}"
ILLUMINANCE_FILENAME = f"Illuminance_plot{PNG}"

# define reference values/intervals
REFERENCE_PPM = {
    ENV_CO2_KEY: CO2_REFERENCE_VALUE_PPM,
    ENV_CO_KEY: CO_REFERENCE_VALUE_PPM,
    ENV_COV_KEY: COV_REFERENCE_VALUE_PPM
}
REFERENCE_TEMPERATURE = {ENV_TEMPERATURE_KEY: TEMPERATURE_REFERENCE_INTERVAL_CELSIUS}

REFERENCE_PARTICLES = {ENV_PM10_KEY: PM10_REFERENCE_VALUE_UGM3, ENV_PM025_KEY: PM025_REFERENCE_VALUE_UGM3}

REFERENCE_ILLUMINANCE = {ENV_ILLUMINANCE_KEY: ILLUMINANCE_REFERENCE_VALUE_LUX}

REFERENCE_HUMIDITY = {ENV_REL_HUMIDITY_KEY: REL_HUMIDITY_REFERENCE_INTERVAL_PERC}

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #

def plot_environment_data(oh_profile: Dict[str, float], subject_id: str, output_folder_path: str) -> None:
    """
    Generate and save line plots containing the environmental sensor data for one subject.

    This function extracts environmental measurements from an
    OH profile (e.g. temperature, particles (PM10, PM2.5, CO2, CO, COV), illuminance and humidity) and creates one or
    more horizontal line plots per category. Each plot includes the measured value and corresponding reference values or
    ranges when available.
    The resulting figures are saved to the subject-specific subdirectory within the provided output folder.

    :param oh_profile: Dictionary containing environmental sensor measurements
    :param subject_id: Subject identifier
    :param output_folder_path: Path to the root directory where the plots should be saved.
    :return: None
    """

    # get dictionary with only CO2, CO and COV values
    ppm_keys = {ENV_CO2_KEY, ENV_CO_KEY, ENV_COV_KEY}
    ppm_dict = {ppm_key: sensor_value for ppm_key, sensor_value in oh_profile.items() if ppm_key in ppm_keys}

    # generate ppm plots
    _plot_environmental_lines(ppm_dict, output_folder_path, subject_id, filename=CO2_CO_COV_PLOT_FILENAME, reference_dict=REFERENCE_PPM)

    # temperature
    temp_dict = {ENV_TEMPERATURE_KEY: oh_profile[ENV_TEMPERATURE_KEY]}
    _plot_environmental_lines(temp_dict, output_folder_path, subject_id, filename=TEMPERATURE_FILENAME, reference_dict=REFERENCE_TEMPERATURE)

    # large particles
    particle_dict = {ENV_PM10_KEY: oh_profile[ENV_PM10_KEY], ENV_PM025_KEY: oh_profile[ENV_PM025_KEY]}
    _plot_environmental_lines(particle_dict, output_folder_path, subject_id, filename=PARTICLES_PLOT_FILENAME, reference_dict=REFERENCE_PARTICLES)

    # illuminance
    lux_dict = {ENV_ILLUMINANCE_KEY: oh_profile[ENV_ILLUMINANCE_KEY]}
    _plot_environmental_lines(lux_dict, output_folder_path, subject_id, filename=ILLUMINANCE_FILENAME, reference_dict=REFERENCE_ILLUMINANCE)

    # relative humidity
    hum_dict = {ENV_REL_HUMIDITY_KEY: oh_profile[ENV_REL_HUMIDITY_KEY]}
    _plot_environmental_lines(hum_dict, output_folder_path, subject_id, filename=HUMIDITY_FILENAME, reference_dict=REFERENCE_HUMIDITY)

# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #
def _plot_environmental_lines(data_dict: Dict[str, float], output_folder_path: str, subject_id: str, filename: str,
                              reference_dict: dict | None = None) -> None:
    """
    Creates horizontal line plots for each item in `data_dict`. This dictionary can either have only one item or multiple items,
    as this function generates a plot with the same number of subplots as items in the dictionary. Examples of the dictionary:
    {Temperature_Celsius: 26} or {CO2_ppm: 800, CO_ppm: 0.0, COV_ppm: 5.0}.
    Note: If multiple items are to be plotted, these should have the same unit for correctness

    Reference dict should have the reference values for the physical quantities that appear in data_dict. This reference
    can either be a single value (int/float) an interval ([float,float] or [int, int]) or None. For example:
    {Temperature_Celsius: [20,26]} or {CO2_ppm: 1200, CO_ppm: 10, COV_ppm: 12}

    Actual value is shown as a horizontal line with a center dot. References are dashed lines and remain on the y-axis.
    Y-axis only shows ticks for the reference values.

    :param data_dict: dict Dictionary of values to plot
    :param output_folder_path: Folder path to save figure
    :param subject_id: Identifier for subject
    :param filename: Output filename
    :param reference_dict: Dictionary of reference values or intervals
    :return: None
    """
    if not data_dict:
        raise ValueError("Data dictionary is empty.")

    # if no reference dict is passed, init empty dict
    reference_dict = reference_dict or {}

    # calculate the number of subplots needed based on the number of items in data_dict
    n = len(data_dict)

    # different figure sizes. If there's only one subplot it needs a slightly different shape
    if n == 1:
        fig, axes = plt.subplots(1, n, figsize=(4 * n, 3), squeeze=False)

    else:
        fig, axes = plt.subplots(1, n, figsize=(3 * n, 2), squeeze=False)
    axes = axes[0]

    # dict to collect legend handles
    legend_dict = {}

    # cycle over the data in the dictionary
    for idx, (ax, (key, value)) in enumerate(zip(axes, data_dict.items())):

        # get the physical quantity and unit from the key name
        label, unit = _parse_key(key)

        # get value
        y_val = value

        # Plot actual value line
        actual_line = ax.axhline(y=y_val,color=LIGHT_PREVOCCUPAI_BLUE,linewidth=2,zorder=2,label=MEASURED_VALUE)

        # add dot in the middle
        ax.scatter(0.5, y_val, color=LIGHT_PREVOCCUPAI_BLUE, s=50, zorder=3)

        # add arrows
        # ax.text(0.0, y_val, ">", fontsize=13, va="center", ha="left", fontweight="bold", color=LIGHT_PREVOCCUPAI_BLUE, zorder=3)
        #ax.text(1.0, y_val, "<", fontsize=13, va="center", ha="right", fontweight="bold", color=LIGHT_PREVOCCUPAI_BLUE, zorder=3)

        # Annotate actual value above the line - 6 points above the line
        ax.annotate(f"{value}", xy=(0.5, y_val), xytext=(0, 6), textcoords="offset points", ha="center", va="bottom",
            fontsize=12, fontweight="bold", zorder=4)

        # Add actual value to legend
        legend_dict[MEASURED_VALUE] = actual_line

        # get reference handles
        ref_handles = _plot_reference(ax, reference_dict.get(key))

        # add them to the dict to generate the legend
        for h in ref_handles:
            legend_dict[h.get_label()] = h

        # 'label' (physical quantity) in the x axis label and remove tick
        ax.set_xlabel(label, fontsize=12, labelpad=10)
        ax.set_xticks([])

        # add y-axis label only on the first plot (
        if idx == 0:
            ax.set_ylabel(unit)

        # remove spines around the plot
        for spine in ax.spines.values():
            spine.set_visible(False)

        # Remove y-ticks but keep **reference ticks**
        ax.tick_params(axis='y', which='both', length=0)

        # Get the reference associated with this key (may be None, a number, or a range)
        ref_val = reference_dict.get(key)

        # list for holding reference values
        ref_values = []

        # If reference is an interval (min, max), include both bounds in the list
        if isinstance(ref_val, (tuple, list)):
            ref_values = list(ref_val)

        # If reference is a single numeric value, include it as a one-element list
        elif isinstance(ref_val, (int, float)):
            ref_values = [ref_val]

        # Combine the actual value with all reference values so axis limits cover everything that is drawn
        all_values = ref_values + [value]

        # Determine the minimum and maximum y-values to display
        ymin, ymax = min(all_values), max(all_values)

        # Add vertical padding (10%) so lines and labels do not touch the top or bottom of the plot
        # If ymin == ymax, fall back to a fixed padding of 1
        padding = (ymax - ymin) * 0.1 if ymax != ymin else 1

        # Apply the final y-axis limits with padding
        ax.set_ylim(ymin - padding, ymax + padding)

        # Only show **y-ticks for references**
        ax.set_yticks(sorted(set(ref_values)))

    # leave some space at the top
    plt.tight_layout(rect=[0, 0, 1, 0.94])

    # plot legend
    if legend_dict:
        fig.legend(handles=list(legend_dict.values()), labels=list(legend_dict.keys()),loc='upper center',
            bbox_to_anchor=(0.5, 1.05), fontsize=10, frameon=False, ncol=len(legend_dict))

    # Save figure
    output_path = create_dir(output_folder_path, os.path.join(subject_id, 'environment'))
    fig.savefig(os.path.join(output_path, f"{subject_id}_{filename}"), dpi=300, bbox_inches="tight")
    plt.close(fig)


def _parse_key(key: str) -> Tuple[str, str]:
    """
    Extracts the physical quantity name and unit from a dictionary key.

    Expected key format:
        <NAME>_<UNIT>
    Example:
        'CO2_ppm'  -> ('CO2', 'ppm')
        'Temperature_Celsius' -> ('Temperature', 'Celsius')
    :param key: Dictionary key representing a measured variable.
    :return: label : str
        The physical quantity or environmental variable name (x-axis label).
    unit : str
        The unit of measurement (y-axis label).
    """
    # Split the string using '_' as separator - Example: 'CO2_ppm' -> ['CO2', 'ppm']
    parts = key.split("_")

    # The variable name is assumed to be the first element
    label = parts[0]

    # The unit is assumed to be the last element
    unit = parts[-1]

    return label, unit


def _plot_reference(ax: Axes, ref) -> list:
    """
    Draws reference information on a given matplotlib axis.

    :param ax: matplotlib.axes.Axes - Axis object where the reference should be drawn.
    :param ref: int | float | tuple[float, float] | None
        Reference value(s) for the variable plotted.  Accepted formats:
        - Single numeric value (int or float) Example: 9
            → Draw a horizontal dashed line at this value.
        - Interval as a tuple of two floats Example: (400.0, 1000.0)
            → Draw two horizontal dashed lines at min and max values.
        - None
            → No reference is drawn.
    :return: list of handles for legend
    """
    handles = []

    if ref is None:
        return handles

    # Case 1: Interval (min, max)
    if isinstance(ref, (tuple, list)) and len(ref) == 2:
        ymin, ymax = ref

        # Draw two dashed lines for the interval
        line_min = ax.axhline(y=ymin, linestyle="--", color='blue', linewidth=2, label=REFERENCE_MIN)
        line_max = ax.axhline(y=ymax, linestyle="--", color='red', linewidth=2, label=REFERENCE_MAX)

        handles.extend([line_min, line_max])

    # Case 2: Single numeric value
    elif isinstance(ref, (int, float)):
        line = ax.axhline(ref, linestyle="--", color="red", linewidth=2, label=REFERENCE_VALUE)
        handles.append(line)

    return handles

#
# def _generate_yticks(ymin: float, ymax: float, n_ticks: int = 6) -> np.ndarray:
#     """
#     Compute exactly `n_ticks` nicely rounded y-ticks starting from ymin.
#     The top tick is the next "nice" multiple above the maximum of the value or reference.
#
#     :param ymin: Minimum y-value (usually 0)
#     :param ymax: Maximum y-value (highest bar or reference)
#     :param n_ticks: Desired number of ticks (including ymin and top)
#     :return: np.ndarray of tick positions
#     """
#
#     if ymax <= ymin:
#         # Default linear spacing if ymax <= ymin
#         return np.linspace(ymin, ymin + 1, n_ticks)
#
#     # Step size (raw)
#     raw_step = (ymax - ymin) / (n_ticks - 1)
#
#     # Order of magnitude
#     magnitude = 10 ** math.floor(math.log10(raw_step))
#
#     # Round step to a "nice" number: 1, 2, 5, 10 multiples of magnitude
#     nice_steps = np.array([1, 2, 5, 10])
#     possible_steps = nice_steps * magnitude
#     nice_step = min(possible_steps[possible_steps >= raw_step]) if any(possible_steps >= raw_step) else possible_steps[-1]
#
#     # Top tick: one step above ymax
#     top_tick = math.ceil(ymax / nice_step) * nice_step
#
#     # Generate exactly n_ticks from ymin to top_tick
#     ticks = np.linspace(ymin, top_tick, n_ticks)
#
#     # Round ticks to reasonable precision
#     if top_tick < 1:
#         ticks = np.round(ticks, 2)
#     elif top_tick < 10:
#         ticks = np.round(ticks, 1)
#     else:
#         ticks = np.round(ticks, 0)
#
#     return ticks
