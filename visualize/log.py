"""
Functions for visualizing the data contained in the parsed logs.

Available Functions
-------------------
[Public]
plot_acquisition_maps(parsed_log_df, min_acq_length, logs_folder, num_groups=4, num_subjects_per_group=10, num_days=5, num_acq_per_day=4): Plots two acquisition maps (one for the left and one for the right muscleBAN) in which each acquisition is represented by a pixel (square).
plot_mutual_acquisition_map(success_acquisition_map, parsed_log_df, min_acq_length, logs_folder, num_days=5, num_groups=4): Plots an acquisition (acq_map) that shows where both the left and right had a successful acquisition (data has been fully processed).
plot_mutual_map_pattern_match(matched_map, parsed_log_df, session_match_pattern, min_acq_length, logs_folder, days_match_pattern=None, num_days=5, num_groups=4, fig_name=''):  Plots an acquisition map where the mutual acquisitions (fully processed for left and right side placement) are matched with a pattern (e.g., only the first and the last acquisition).
------------------
[Private]
rgb_to_hex(rgb_array): converts a numpy array containing RGB values into a hexadecimal color code
_format_acquisition_map(acq_map, ax, x_labels, y_labels, num_groups, num_subjects_per_group, num_days, num_acq_per_day): formats the acquisition map
_plot_single_activity_map(parsed_log_df, side, enum_dict, ax, num_groups=4, num_subjects_per_group=10, num_days=5, num_acq_per_day=4): Plots an acquisition acq_map in which each acquisition is represented by a pixel (square). The color of the pixel indicates the status of the acquisition.
"""

# ------------------------------------------------------------------------------------------------------------------- #
# imports
# ------------------------------------------------------------------------------------------------------------------- #
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl

# internal imports
import log.logger as logger

# ------------------------------------------------------------------------------------------------------------------- #
# constants
# ------------------------------------------------------------------------------------------------------------------- #
# color palette for generating the acquisition acq_map
PALETTE = np.array([[240, 82, 25],     # red = 'missing file'
                    [95, 173, 86],     # green = 'processed'
                    [112, 112, 112],   # dark grey = 'empty file'
                    [153, 153, 153],   # mid grey = '< 5 s'
                    [161, 88, 238],    # dark purple = 'mBAN broken'
                    [192, 144, 244],   # light purple = 'noisy signal'
                    [65, 103, 136],    # blue = 'saturated'
                    [245, 207, 41],    # yellow = '< min length'
                    [255, 146, 139]])  # pink = 'all walk'

FAIL_SUCCESS_PALETTE = np.array([[240, 82, 25],  # red
                                 [95, 173, 86]])  # green

RICH_BLACK = '#06171C'


LABELS = ['missing file', 'processed', 'empty file', '< 5 s',
          'mBAN broken', 'noisy signal', 'saturated', '< min length', 'all walk']


# ------------------------------------------------------------------------------------------------------------------- #
# public functions
# ------------------------------------------------------------------------------------------------------------------- #
def plot_acquisition_maps(parsed_log_df, min_acq_length, results_folder, num_groups=None, num_subjects_per_group=None,
                          num_days=None, num_acq_per_day=None):
    """
    Plots two acquisition maps (one for the left and one for the right muscleBAN) in which each acquisition is
    represented by a pixel (square). The color of the pixel indicates the status of the acquisition. A colorbar
    displayed at the bottom of the plot explains the mapping of the color to the respective status. The dimension of the
    map scales with the amount of data available (e.g., single-subject subsets) instead of assuming the full cohort.
    :param parsed_log_df: parsed logger file contained in a pd.DataFrame(). The parsed logger file can be obtained by
                          using the parse_log(...) function from log_parser.py
    :param min_acq_length: minimum acquisition length that was defined during EMG processing
    :param results_folder: path to folder for saving the processed results
    :param num_groups: optional manual override for the number of groups
    :param num_subjects_per_group: optional manual override for the number of subjects per group
    :param num_days: optional manual override for the number of acquisition days
    :param num_acq_per_day: optional manual override for the number of acquisitions per day
    :return: list containing maps for left and right with 1 where the data was completely processed and 0 else
    """

    # sort and derive layout metadata dynamically to support partial cohorts (e.g., single-subject runs)
    (sorted_log_df, subject_labels, group_boundaries,
     detected_num_days, detected_num_acq_per_day, entries_per_subject) = _prepare_layout_metadata(parsed_log_df)
    parsed_log_df = sorted_log_df

    # allow manual overrides for backwards compatibility while keeping detected defaults
    num_days = detected_num_days if num_days is None else num_days
    num_acq_per_day = detected_num_acq_per_day if num_acq_per_day is None else num_acq_per_day

    success_map_list = []

    # dict defining the mapping of acquisition comments to color
    enum_dict = {logger.COMMENT_NO_DATA: 0,
                 logger.COMMENT_PRE_PROCESSED: 1,
                 logger.COMMENT_EMPTY: 2,
                 logger.COMMENT_TOO_SHORT: 3,
                 logger.COMMENT_FAULTY_MBAN: 4,
                 logger.COMMENT_NOISE: 5,
                 logger.COMMENT_SATURATED: 6,
                 'shorter than minimum length ({} min)'.format(min_acq_length): 7,
                 logger.COMMENT_ALL_WALK: 8}

    # create the figure
    fig, axes = plt.subplots(1, 2, figsize=(10, 10), layout='constrained')

    # add title
    fig.suptitle('Acquisition evaluation (min length: {} min)'.format(min_acq_length), fontweight="bold", fontsize=14)

    for side, ax in zip(['L', 'R'], axes.flat):
        success_map = _plot_single_activity_map(parsed_log_df, side, enum_dict, ax,
                                                entries_per_subject=entries_per_subject,
                                                num_days=num_days,
                                                num_acq_per_day=num_acq_per_day,
                                                subject_labels=subject_labels,
                                                group_boundaries=group_boundaries)
        success_map_list.append(success_map)

    # create colorbar
    # (1) create color acq_map
    cmap = mpl.colors.ListedColormap([rgb_to_hex(rgb_array) for rgb_array in PALETTE])

    # (2) define the bounds
    bounds = list(range(0, len(set(enum_dict.values())) + 1, 1))

    # (3) create a norm for describing the interval boundaries
    norm = mpl.colors.BoundaryNorm(bounds, cmap.N)

    # (4) plot the colorbar
    cbar = fig.colorbar(mpl.cm.ScalarMappable(norm=norm, cmap=cmap), ax=axes, orientation='horizontal')
    cbar.set_ticks(ticks=[tick + 0.5 for tick in range(0, len(set(enum_dict.values())), 1)], labels=LABELS)
    cbar.minorticks_off()

    # save the plot
    fig.get_figure().savefig(os.path.join(results_folder, 'acquisition_map_{}.png'.format(min_acq_length)))
    plt.close(fig)

    return success_map_list


def plot_success_acquisition_map(success_acquisition_map, parsed_log_df, min_acq_length, map_type, results_folder):
    """
    Plots an acquisition map (acq_map) indicating where acquisitions where successfully processed (green) and where
    not (red).The acquisition map contains the data for all groups and shows the acquisition success over the entire
    acquisition period (Monday - Friday). Thus, the map consists of a image of the dimension 40 x 20 pixels (40 subjects
    and 4 acquisition per day over 5 consecutive days).


    :param success_acquisition_map: map containing the successful acquisitions. The map contains 1 where the data was
                                    completely processed and 0 else.
    :param parsed_log_df: pd.DataFrame containing the parsed log file
    :param min_acq_length: minimum acquisition length that was defined during EMG processing
    :param map_type: the type of the map either "left", "right", or "mutual"
    :param results_folder: path to folder for saving the processed results
    :return: map with 1 where the data was completely processed and 0 else containing the mutual
    (left and right combined) successful acquisitions.

    """

    (_, subject_labels, group_boundaries,
     num_days, num_acq_per_day, entries_per_subject) = _prepare_layout_metadata(parsed_log_df)

    expected_shape = (len(subject_labels), entries_per_subject)
    if success_acquisition_map.shape != expected_shape:
        raise ValueError("Acquisition map shape {} does not match expected layout {}".format(
            success_acquisition_map.shape, expected_shape))

    acq_map = FAIL_SUCCESS_PALETTE[success_acquisition_map]

    # generate plot and add title
    fig, ax = plt.subplots(1, 1, figsize=(10, 10), layout='constrained')
    plt.title("{} acquisition map (min length: {} min)".format(map_type, min_acq_length), fontweight="bold", fontsize=14)

    # plot the acq_map
    ax.imshow(acq_map)

    # format the acquisition map
    _format_acquisition_map(acq_map, ax, [], subject_labels, num_days, num_acq_per_day, group_boundaries)
    # save the plot
    fig.get_figure().savefig(os.path.join(results_folder, '{}_successful_acquisition_map_{}.png'.format(map_type, min_acq_length)))
    plt.close(fig)


def plot_success_map_pattern_match(matched_map, parsed_log_df, session_match_pattern, min_acq_length, results_folder,
                                   days_match_pattern=None, fig_name=''):
    """
    Plots an acquisition map that where the mutual acquisitions (fully processed for left and right side placement)
    are matched with a pattern (e.g., only the first and the last acquisition).
    :param matched_map: map that is the result of the matching process. It contains ones where there was a match and
                        zeros otherwise.
    :param parsed_log_df: pd.DataFrame containing the parsed log file
    :param session_match_pattern: list containing a pattern indicating which sessions should be matched with the
                                  successful acquisition maps. As there are four sessions per day, the list should be of
                                  length 4. The pattern is a list of zeros and ones, where one indicates that this
                                  acquisition should be considered for the match.
                                  Example: if only the first and the last acquisition should be considered, the
                                  match pattern is [1, 0, 0, 1]
    :param min_acq_length: minimum acquisition length that was defined during EMG processing
    :param results_folder: path to folder for saving the processed results
    :param days_match_pattern: list containing a pattern indicating which days should be matched with the successful
                               acquisition maps. As acquisitions were carried out from Monday - Friday the list should
                               be of length 5. The pattern is a list of zeros and ones, where one indicates that this
                               day should be considered for the match.
                               Example: if only Monday and Friday should be considered, the match pattern is
                               [1, 0, 0, 0, 1]
    :param fig_name: the name of the figure for saving it. default: ''

    :return: None

    """

    (_, subject_labels, group_boundaries,
     num_days, num_acq_per_day, entries_per_subject) = _prepare_layout_metadata(parsed_log_df)

    expected_shape = (len(subject_labels), entries_per_subject)
    if matched_map.shape != expected_shape:
        raise ValueError("Matched map shape {} does not match expected layout {}".format(
            matched_map.shape, expected_shape))

    # broadcast the defined colors in FAIL_SUCCESS_PALETTE to the success_acquisition_map
    acq_map = FAIL_SUCCESS_PALETTE[matched_map]

    # generate plot and add title
    fig, ax = plt.subplots(1, 1, figsize=(10, 10), layout='constrained')

    if days_match_pattern is None or (days_match_pattern == np.array([1, 1, 1, 1, 1], dtype=bool)).all():
        plt.title("matched acquisition map (min length: {} min) \n pattern: {} | days_match_pattern: {}"
                  .format(min_acq_length, session_match_pattern, 'all'), fontweight="bold", fontsize=14)
    else:
        plt.title("matched acquisition map (min length: {} min) \n pattern: {} | days_match_pattern: {}"
                  .format(min_acq_length, session_match_pattern, days_match_pattern), fontweight="bold", fontsize=14)

    # plot the acq_map
    ax.imshow(acq_map)

    # format the acquisition map
    _format_acquisition_map(acq_map, ax, [], subject_labels, num_days, num_acq_per_day, group_boundaries)

    # save the plot
    fig.get_figure().savefig(os.path.join(results_folder, fig_name + '.png'))
    plt.close(fig)


# ------------------------------------------------------------------------------------------------------------------- #
# private functions
# ------------------------------------------------------------------------------------------------------------------- #
def rgb_to_hex(rgb_array):
    """
    converts a numpy array containing RGB values into a hexadecimal color code
    :param rgb_array: numpy.array containing the RGB values of a color
    :return: the hexadecimal color code for the provided RGB color
    """

    return "#{:02x}{:02x}{:02x}".format(rgb_array[0], rgb_array[1], rgb_array[2])


def _prepare_layout_metadata(parsed_log_df):
    """Sort the parsed log and derive plotting layout metadata."""

    if parsed_log_df.empty:
        raise ValueError("Parsed log DataFrame is empty; cannot create acquisition maps.")

    sort_cols = [col for col in ['GROUP', 'SUBJECT_NUM', 'DATE', 'TIME'] if col in parsed_log_df.columns]
    sorted_df = parsed_log_df.sort_values(by=sort_cols).reset_index(drop=True)

    subject_order_df = sorted_df[['GROUP', 'SUBJECT_NUM']].drop_duplicates().reset_index(drop=True)
    subject_labels = (subject_order_df['GROUP'].astype(str) + '_' + subject_order_df['SUBJECT_NUM']).tolist()

    group_boundaries = []
    prev_group = None
    for idx, group in enumerate(subject_order_df['GROUP']):
        if prev_group is not None and group != prev_group:
            group_boundaries.append(idx)
        prev_group = group

    entries_per_subject = int(sorted_df.groupby(['GROUP', 'SUBJECT_NUM']).size().max())
    num_days = int(sorted_df.groupby(['GROUP', 'SUBJECT_NUM'])['DATE'].nunique().max())
    num_days = max(1, num_days)
    num_acq_per_day = max(1, entries_per_subject // num_days)

    return sorted_df, subject_labels, group_boundaries, num_days, num_acq_per_day, entries_per_subject


def _plot_single_activity_map(parsed_log_df, side, enum_dict, ax, entries_per_subject,
                              num_days, num_acq_per_day, subject_labels, group_boundaries):
    """
    Plots an acquisition acq_map in which each acquisition is represented by a pixel (square). The color of the pixel
    indicates the status of the acquisition.
    :param parsed_log_df: parsed logger file contained in a pd.DataFrame(). The parsed logger file can be obtained by
                          using the parse_log(...) function from log_parser.py
    :param side: the placement side of the muslceBAN, either 'L' or 'R'
    :param enum_dict: dictionary defining an enumeration for the COMMENT column in parsed_log_df
    :param ax: the axis object into which the figure should be plotted
    :param num_groups: number of groups that participated in the study
    :param num_subjects_per_group: number of subjects per group (it is assumed that each group has the same amount of
                                   subjects).
    :param num_days: number of days on which data was acquired (it is assumed that for all subjects the same
                     amount of days was acquired).
    :param num_acq_per_day: number of acquisitions per day (it is assumed that all subjects had the same number
                            of acquisitions per day).
    :return: a binary np.array containing 1 where the acquisition was successfully processed and a 0 where not.
    """

    if entries_per_subject <= 0:
        raise ValueError("Entries per subject must be a positive integer.")

    num_subjects = len(subject_labels)
    if num_subjects == 0:
        raise ValueError("No subjects available to plot acquisition map.")

    subject_index = parsed_log_df[['GROUP', 'SUBJECT_NUM']].drop_duplicates().reset_index(drop=True)
    missing_code = enum_dict.get(logger.COMMENT_NO_DATA, 0)
    acq_rows = []

    for _, subject_row in subject_index.iterrows():
        subject_mask = ((parsed_log_df['GROUP'] == subject_row['GROUP']) &
                        (parsed_log_df['SUBJECT_NUM'] == subject_row['SUBJECT_NUM']))
        subject_comments = (parsed_log_df.loc[subject_mask, f'{side}_COMMENT']
                            .map(enum_dict)
                            .fillna(missing_code)
                            .astype(int)
                            .to_numpy())

        if subject_comments.size > entries_per_subject:
            raise ValueError("Subject {}_{} has {} entries which exceeds detected layout capacity {}".format(
                subject_row['GROUP'], subject_row['SUBJECT_NUM'], subject_comments.size, entries_per_subject))

        padded_row = np.full(entries_per_subject, missing_code)
        padded_row[:subject_comments.size] = subject_comments
        acq_rows.append(padded_row)

    acq_status = np.vstack(acq_rows)

    # get a map that only contains the acquisitions that were successfully processed
    success_map = acq_status.copy()
    success_map[success_map != enum_dict[logger.COMMENT_PRE_PROCESSED]] = 0

    # create the acquisition acq_map (with the corresponding colouring)
    # here python broadcasting is used to broadcast the acq_status to the color PALETTE
    # the resulting array is 3D array (RGB image) with the specified colors assigned to the mapped acquisition statuses
    # defined in enum_dict and then later the LABELS are assigned to the colors
    # e.g., [95, 173, 86] (green) is assigned to 1 ('processed')
    #       [240, 82, 25] (red) is assigned to 0 ('no data in DB'), etc.
    # inspired by: https://stackoverflow.com/questions/37719304/python-imshow-set-certain-value-to-defined-color
    acq_map = PALETTE[acq_status]

    # plot the acq_map
    ax.imshow(acq_map)

    # format the acquisition map
    _format_acquisition_map(acq_map, ax, [], subject_labels, num_days, num_acq_per_day, group_boundaries)

    # (7) add title
    if side == 'L':
        ax.set_title('left mBAN')
    else:
        ax.set_title('right mBAN')

    return success_map


def _format_acquisition_map(acq_map, ax, x_labels, y_labels, num_days, num_acq_per_day, group_boundaries):
    """
    formats the acquisition map by performing the following steps
    (1) override the x- and y-ticks and add labels
    (2) drawing a grid that allows for easier identification each acquisition
    (3) removing the minor ticks (left and bottom) and if x_labels is an empty list the major ticks (bottom)
    (4) drawing separator lines that separate the days (horizontally) and the groups (vertically)
    :param acq_map: 3D numpy.Array containing the acquisition map.
                The dimensions of the map should be the following
                [num_subjects_per_group * num_groups, num_acq_per_day * num_days, 3], where three indicates the RGB
                color of each pixel in the map.
    :param ax: plot axis
    :param x_labels: list of labels displayed at the bottom of the map. Pass empty list [] if no labels should be shown
    :param y_labels: list of labels displayed at the left of the map.
    :param num_groups: number of groups that participated in the study
    :param num_subjects_per_group: number of subjects per group (it is assumed that each group has the same amount of
                                   subjects).
    :param num_days: number of days on which data was acquired (it is assumed that for all subjects the same
                     amount of days was acquired).
    :param num_acq_per_day: number of acquisitions per day (it is assumed that all subjects had the same number
                            of acquisitions per day).
    :return:
    """

    # figure formatting
    # (1) override the x- and y-tick labels
    ax.set_xticks(np.arange(acq_map.shape[1]), labels=x_labels)
    ax.set_yticks(np.arange(acq_map.shape[0]), labels=y_labels)

    # (2) draw white grid
    ax.set_xticks(np.arange(acq_map.shape[1]) - .5, minor=True)
    ax.set_yticks(np.arange(acq_map.shape[0]) - .5, minor=True)
    ax.grid(which="minor", color="w", linestyle='-', linewidth=2)

    # (3) remove minor ticks and major ticks at the bottom of the plot
    ax.tick_params(which="minor", bottom=False, left=False)
    if not x_labels:
        ax.tick_params(which="major", bottom=False)

    # (4) draw separators that separate the groups
    for day_boundary in range(1, num_days):
        ax.vlines(day_boundary * num_acq_per_day - 0.5, -0.5, acq_map.shape[0] - 0.5, colors=RICH_BLACK, linewidth=2)

    for boundary in group_boundaries:
        ax.hlines(boundary - 0.5, -0.5, acq_map.shape[1] - 0.5, colors=RICH_BLACK, linewidth=2)

    # (6) remove the spines
    ax.spines[:].set_visible(False)
