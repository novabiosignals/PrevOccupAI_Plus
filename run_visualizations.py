import os

# internal imports
import sensors.visualize as sv
import sensors.load as sl
import sensors.metrics as sm
from OH_profile.constants import SENSOR_TIMELINE_KEY, SENSOR_METRICS_KEY
from utils import extract_group_from_path, extract_device_num_from_path
from OH_profile.load import get_OH_profile
from OH_profile.write import save_OH_profile, write_to_OH_profile
# ------------------------------------------------------------------------------------------------------------------- #
# flags
# ------------------------------------------------------------------------------------------------------------------- #
GENERATE_SENSOR_TIMELINE = True


# ------------------------------------------------------------------------------------------------------------------- #
# file constants
# ------------------------------------------------------------------------------------------------------------------- #
DRIVE = "E"
SUBJECT_FOLDER_PATH = f"{DRIVE}:\\Backup PrevOccupAI_PLUS Data\\data\\group1\\sensors\\LIBPhys #001"
OH_PROFILE_PATH = r"C:\Users\srale\Desktop\OH_profiles"
PLOTS_OUTPUT_PATH = r"C:\Users\srale\Desktop\sensor_timeline_plots"
FS = 100

# ------------------------------------------------------------------------------------------------------------------- #
# program starts here
# ------------------------------------------------------------------------------------------------------------------- #

# get group and device num from path
group = extract_group_from_path(SUBJECT_FOLDER_PATH)
device_num = extract_device_num_from_path(SUBJECT_FOLDER_PATH)

# get subject id
subject_id = sl.get_participant_id(sl.load_participants_info(), device_num, group)

if GENERATE_SENSOR_TIMELINE:


    for acquisition_date in os.listdir(SUBJECT_FOLDER_PATH):

        # generate path
        day_folder_path = os.path.join(SUBJECT_FOLDER_PATH, acquisition_date)

        # generate metrics dict
        daily_metrics_dict = sm.get_sensor_timeline_metrics(day_folder_path, fs=FS)

        # get oh profile
        oh_profile = get_OH_profile(OH_PROFILE_PATH, subject_id)

        # write to json file
        oh_profile = write_to_OH_profile(oh_profile, main_outer_key= SENSOR_METRICS_KEY,
                                         main_inner_key=SENSOR_TIMELINE_KEY, dict_to_write=daily_metrics_dict)

        # save to json
        save_OH_profile(OH_PROFILE_PATH, subject_id, oh_profile)

    # get oh profile
    oh_profile = get_OH_profile(OH_PROFILE_PATH, subject_id)

    # get output filename
    filename = f"subject_{subject_id}_sensor_timeline_plot.png"

    # generate plot
    sv.generate_sensor_timeline_plot(oh_profile[SENSOR_METRICS_KEY][SENSOR_TIMELINE_KEY], PLOTS_OUTPUT_PATH, filename)






