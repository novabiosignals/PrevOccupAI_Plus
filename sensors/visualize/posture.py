"""
Functions for visualizing posture data.

Available Functions
-------------------
[Public]

-------------------
"""

# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import os
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from babel.dates import format_datetime
from datetime import datetime

from sensors.visualize.plot_utils import handle_plot
# internal imports
from utils import extract_date_from_path, create_dir

# ------------------------------------------------------------------------------------------------------------------- #
# file specific constants
# ------------------------------------------------------------------------------------------------------------------- #
RESOURCES_PATH = r".\sensors\visualize\resources"

VIEW_DIMENSIONS = {
        "Vista_Superior": (1.25, 1.25),   # width, height in meters
        "Vista_Lateral": (1.25, 1.25),
        "Vista_de_Costas": (1.50, 1.125)  # width = 1.50 m, height = 1.125 m
    }

AP_AXIS = 0
ML_AXIS = 1
VERT_AXIS = 2

# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #
def plot_postural_displacements(displacement_store_path: str, subject_id: str, subject_sex: str, output_folder_path: str) -> None:
    """

    :param displacement_store_path:
    :param subject_id:
    :param subject_sex:
    :param output_folder_path:
    :return:
    """

    # generate path to subject folder containing the displacement data
    subject_folder_path = os.path.join(displacement_store_path, subject_id)

    # list files in the path
    displacement_files = os.listdir(subject_folder_path)

    # generate full file paths
    displacement_files = sorted([os.path.join(subject_folder_path, displacement_file) for displacement_file in displacement_files])

    # get dates from the file names and sort the dates chronologically
    acquisition_dates = sorted([extract_date_from_path(displacement_file, r'(\d{2}-\d{2}-\d{4})') for displacement_file in displacement_files], key=lambda d: datetime.strptime(d, "%d-%m-%Y"))

    # Load all displacement arrays
    displacement_data = [np.load(f) for f in displacement_files]

    # get the images for each view based on the sex of the subject
    view_images = {
        "Vista_Superior": fr"{RESOURCES_PATH}\top-view_{subject_sex}.png",
        "Vista_Lateral": fr"{RESOURCES_PATH}\side-view_{subject_sex}.png",
        "Vista_de_Costas": fr"{RESOURCES_PATH}\back-view_{subject_sex}.png"
    }

    # define view configuration
    # Define view configuration: (view_name, x_idx, y_idx, image_path, (center_x, center_y))
    # Column indices: 0=AP, 1=ML, 2=Vertical
    views = [
        ("Vista_Superior", ML_AXIS, AP_AXIS, view_images["Vista_Superior"], (0.65, 0.45)),  # ML vs AP
        ("Vista_Lateral", AP_AXIS, VERT_AXIS, view_images["Vista_Lateral"], (0.5, 0.75)),  # AP vs Vertical
        ("Vista_de_Costas", ML_AXIS, VERT_AXIS, view_images["Vista_de_Costas"], (0.75, 0.7))  # ML vs Vertical
    ]

    # create directory to store plots
    out_dir = create_dir(output_folder_path, os.path.join(subject_id, 'posture_plots'))

    for view_name, x_idx, y_idx, bg_image, (center_x, center_y) in views:
        width, height = VIEW_DIMENSIONS[view_name]

        num_days = len(displacement_data)
        fig, axs = plt.subplots(1, num_days, figsize=(5 * num_days, 4))
        if num_days == 1:
            axs = [axs]

        for i, day_array in enumerate(displacement_data):
            im = plt.imread(bg_image)
            axs[i].imshow(im, extent=(0, width, 0, height))

            if day_array.size == 0:
                axs[i].axis('off')
                axs[i].set_title(acquisition_dates[i])
                continue

            # Subsample data to every 100th sample
            day_array_sub = day_array[::100]

            # Center data using median displacement
            x_centered = day_array_sub[:, x_idx] - np.median(day_array_sub[:, x_idx]) + center_x
            y_centered = day_array_sub[:, y_idx] - np.median(day_array_sub[:, y_idx]) + center_y

            # KDE plot
            sns.kdeplot(
                x=x_centered,
                y=y_centered,
                fill=True,
                bw_adjust=0.5,
                alpha=0.8,
                ax=axs[i]
            )

            # Remove ticks and spines
            axs[i].tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
            for spine in axs[i].spines.values():
                spine.set_visible(False)

            # Format date for title
            try:
                weekday_str = format_datetime(datetime.strptime(acquisition_dates[i], "%d-%m-%Y"), "EEEE",
                                              locale="pt_PT")
            except:
                weekday_str = acquisition_dates[i]

            axs[i].set_ylabel("")
            axs[i].set_xlabel(weekday_str, fontsize=10, labelpad=5)

            # Add scale bar in first subplot
            if i == 0:
                scalebar_length = 0.15  # meters
                x_start = width * 0.05
                y_start = height * 0.05
                axs[i].plot([x_start, x_start + scalebar_length], [y_start, y_start],
                            color='black', lw=2)
                axs[i].text(x_start, y_start + 0.02, f"{scalebar_length} m", color='black', fontsize=9)

        fig.suptitle(f"{view_name.replace('_', ' ')}", fontsize=12)
        plt.subplots_adjust(left=0.03, right=0.97, top=0.92, bottom=0.08, wspace=0.03, hspace=0.03)
        plt.tight_layout()

        # create file name
        file_name = f'{subject_id}_{view_name.replace("_", " ")}.png'

        # save the plot
        handle_plot(save_dir=out_dir, filename=file_name, save=True)


    print('test')




# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #