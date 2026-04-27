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
from datetime import datetime
from tqdm import tqdm


# internal imports
from sensors.visualize.plot_utils import handle_plot, get_weekday_name
from utils import extract_date_from_path, create_dir

# ------------------------------------------------------------------------------------------------------------------- #
# file specific constants
# ------------------------------------------------------------------------------------------------------------------- #
RESOURCES_PATH = r".\sensors\visualize\resources"

# view constants
TOP_VIEW = "top-view"
SIDE_VIEW = "side-view"
BACK_VIEW = "back-view"

VIEW_DIMENSIONS = {
        TOP_VIEW: (1.03, 1.03),   # width, height in meters
        SIDE_VIEW: (1.03, 1.03),
        BACK_VIEW: (1.23, 0.92)  # width = 1.50 m, height = 1.125 m
    }


# figure constants
AP_AXIS = 0
ML_AXIS = 1
VERT_AXIS = 2


# view language mapper
LOCALE_PT = 'pt'
LOCALE_ENG = 'eng'

VIEW_TITLES = {
    TOP_VIEW: {
        LOCALE_PT: "Vista Superior",
        LOCALE_ENG: "Top View",
    },
    SIDE_VIEW: {
        LOCALE_PT: "Vista Lateral",
        LOCALE_ENG: "Side View",
    },
    BACK_VIEW: {
        LOCALE_PT: "Vista das Costas",
        LOCALE_ENG: "Back View",
    }
}


# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #
def plot_postural_displacements_grid(displacement_store_path: str, subject_id: str, subject_sex: str, output_folder_path: str, locale: str='pt') -> None:
    """
    Creates a single figure with:
      - rows = acquisition days
      - columns = views (Vista Superior, Vista Lateral, Vista de Costas)
    :param displacement_store_path:
    :param subject_id:
    :param subject_sex:
    :param output_folder_path:
    :param locale:
    :return:
    """

    # generate path to subject folder containing the displacement data
    subject_folder_path = os.path.join(displacement_store_path, subject_id)

    # list files (filenames)
    displacement_filenames = os.listdir(subject_folder_path)

    # sort filenames by extracted date (chronologically)
    displacement_filenames = sorted(
        displacement_filenames,
        key=lambda f: datetime.strptime(extract_date_from_path(f, r'(\d{2}-\d{2}-\d{4})'), "%d-%m-%Y")
    )

    # build full paths in the SAME order
    displacement_files = [os.path.join(subject_folder_path, f) for f in displacement_filenames]

    # extract dates in the SAME order
    acquisition_dates = [extract_date_from_path(f, r'(\d{2}-\d{2}-\d{4})') for f in displacement_filenames]

    # load displacement arrays
    displacement_data = [np.load(f) for f in displacement_files]

    # get the images for each view based on the sex of the subject
    view_images = {
        TOP_VIEW: fr"{RESOURCES_PATH}\top-view_{subject_sex}.png",
        SIDE_VIEW: fr"{RESOURCES_PATH}\side-view_{subject_sex}.png",
        BACK_VIEW: fr"{RESOURCES_PATH}\back-view_{subject_sex}.png"
    }

    # Define view configuration: (view_key, view_name, x_idx, y_idx, image_path, (center_x, center_y))
    # Column indices: 0=AP, 1=ML, 2=Vertical
    views = [
        (TOP_VIEW, VIEW_TITLES[TOP_VIEW][locale], ML_AXIS, AP_AXIS, view_images[TOP_VIEW], (0.54, 0.34)),      # ML vs AP
        (SIDE_VIEW, VIEW_TITLES[SIDE_VIEW][locale],  AP_AXIS, VERT_AXIS, view_images[SIDE_VIEW], (0.39, 0.64)),     # AP vs Vertical
        (BACK_VIEW, VIEW_TITLES[BACK_VIEW][locale], ML_AXIS, VERT_AXIS, view_images[BACK_VIEW], (0.615, 0.5975)) # ML vs Vertical
    ]

    num_days = len(displacement_data)
    num_views = len(views)

    # create directory to store plots
    out_dir = create_dir(output_folder_path, os.path.join(subject_id, "posture_plots"))

    # figure size heuristic (tune if needed)
    fig_w = 4.2 * num_views
    fig_h = 3.2 * max(num_days, 1)
    fig, axs = plt.subplots(num_days, num_views, figsize=(fig_w, fig_h), constrained_layout=False)

    # make axs always 2D
    if num_days == 1 and num_views == 1:
        axs = np.array([[axs]])
    elif num_days == 1:
        axs = np.array([axs])
    elif num_views == 1:
        axs = np.array([[ax] for ax in axs])

    # column titles (views) on top row
    for col, (_, view_title, *_rest) in enumerate(views):
        axs[0, col].set_title(view_title, fontsize=16, pad=10)

    # plot each day (row) and each view (col)
    for row, day_array in enumerate(tqdm(displacement_data, desc="generating posture plot grid")):
        # row label (weekday + date) on the first column only (cleaner)
        weekday_str = get_weekday_name(acquisition_dates[row], locale_string=f"{locale}_{locale.upper()}.UTF-8")
        row_label = f"{weekday_str.title()}"

        for col, (_view_key, _view_title, x_idx, y_idx, bg_image, (center_x, center_y)) in enumerate(views):
            ax = axs[row, col]

            width, height = VIEW_DIMENSIONS[_view_key]

            # background image
            im = plt.imread(bg_image)
            ax.imshow(im, extent=(0, width, 0, height))

            # handle missing/empty day
            if day_array is None or getattr(day_array, "size", 0) == 0:
                ax.axis("off")
                if col == 0:
                    ax.text(0.02, 0.98, row_label, transform=ax.transAxes,
                            va="top", ha="left", fontsize=12)
                continue

            # subsample
            day_array_sub = day_array[::100]

            # center data
            x_centered = day_array_sub[:, x_idx] + center_x
            y_centered = day_array_sub[:, y_idx] + center_y

            # KDE
            sns.kdeplot(
                x=x_centered,
                y=y_centered,
                fill=True,
                bw_adjust=0.5,
                alpha=0.8,
                ax=ax
            )

            # lock view
            ax.set_xlim(0, width)
            ax.set_ylim(0, height)
            ax.set_aspect("auto")
            ax.margins(0)

            # remove ticks/spines
            ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
            for spine in ax.spines.values():
                spine.set_visible(False)

            # row label on first column
            if col == 0:
                ax.text(0.02, 0.98, row_label, transform=ax.transAxes,
                        va="top", ha="left", fontsize=12)

            # scale bar only once (top-left cell), to avoid repetition
            if row == 0 and col == 0:
                scalebar_length = 0.15  # meters
                x_start = width * 0.05
                y_start = height * 0.05
                ax.plot([x_start, x_start + scalebar_length], [y_start, y_start], color="black", lw=2)
                ax.text(x_start, y_start + 0.02, f"{scalebar_length} m", color="black", fontsize=9)

    # global spacing
    plt.subplots_adjust(left=0.02, right=0.995, top=0.92, bottom=0.02, wspace=0.02, hspace=0.06)

    # save single file
    file_name = f"{subject_id}_posture_views_grid.svg"
    handle_plot(save_dir=out_dir, filename=file_name, save=True)



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

    # build full paths
    displacement_files = [os.path.join(subject_folder_path, f) for f in os.listdir(subject_folder_path)]

    # generate full file paths
    # sort files by extracted date
    displacement_files = sorted(displacement_files, key=lambda f: datetime.strptime(
        extract_date_from_path(f, r'(\d{2}-\d{2}-\d{4})'),"%d-%m-%Y"))

    # get dates from the file names and sort the dates chronologically
    acquisition_dates = [extract_date_from_path(displacement_file, r'(\d{2}-\d{2}-\d{4})') for displacement_file in displacement_files]

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
        ("Vista_Superior", ML_AXIS, AP_AXIS, view_images["Vista_Superior"], (0.54, 0.34)),  # ML vs AP
        ("Vista_Lateral", AP_AXIS, VERT_AXIS, view_images["Vista_Lateral"], (0.39, 0.64)),  # AP vs Vertical
        ("Vista_de_Costas", ML_AXIS, VERT_AXIS, view_images["Vista_de_Costas"], (0.615, 0.5975))  # ML vs Vertical
    ]

    # create directory to store plots
    out_dir = create_dir(output_folder_path, os.path.join(subject_id, 'posture_plots'))

    for view_name, x_idx, y_idx, bg_image, (center_x, center_y) in views:
        width, height = VIEW_DIMENSIONS[view_name]

        num_days = len(displacement_data)
        fig, axs = plt.subplots(1, num_days, figsize=(5 * num_days, 4), constrained_layout=False)
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

            # Center data
            x_centered = day_array_sub[:, x_idx]  + center_x
            y_centered = day_array_sub[:, y_idx]  + center_y

            # KDE plot
            sns.kdeplot(
                x=x_centered,
                y=y_centered,
                fill=True,
                bw_adjust=0.5,
                alpha=0.8,
                ax=axs[i]
            )

            # IMPORTANT: lock the view so KDE doesn't change it
            axs[i].set_xlim(0, width)
            axs[i].set_ylim(0, height)
            axs[i].set_aspect('auto')
            axs[i].margins(0)

            # Remove ticks and spines
            axs[i].tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
            for spine in axs[i].spines.values():
                spine.set_visible(False)

            # Format date for title
            weekday_str = get_weekday_name(acquisition_dates[i], locale_string=f"pt_PT.UTF-8")

            axs[i].set_ylabel("")
            axs[i].set_xlabel(weekday_str, fontsize=18, labelpad=5)

            # Add scale bar in first subplot
            if i == 0:
                scalebar_length = 0.15  # meters
                x_start = width * 0.05
                y_start = height * 0.05
                axs[i].plot([x_start, x_start + scalebar_length], [y_start, y_start],
                            color='black', lw=2)
                axs[i].text(x_start, y_start + 0.02, f"{scalebar_length} m", color='black', fontsize=9)

        for ax in axs:
            pos = ax.get_position()
            ax.set_position([
                pos.x0,
                pos.y0,
                pos.width * 1.05,
                pos.height * 1.05
            ])

        fig.suptitle(f"{view_name.replace('_', ' ')}", fontsize=20, y=0.97)
        plt.subplots_adjust(left=0.01, right=0.99, top=0.90, bottom=0.08, wspace=0.0, hspace=0.03)
        # plt.tight_layout()

        # create file name
        file_name = f'{subject_id}_{view_name.replace("_", " ")}.png'

        # save the plot
        handle_plot(save_dir=out_dir, filename=file_name, save=True)





# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #