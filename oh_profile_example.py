from OH_profile.load import get_OH_profile
from OH_profile.write import save_OH_profile
from OH_profile.load.oh_profile_loader import METADATA_KEY
from sensors.load.subject_info import load_participants_info

# ------------------------------------------------------------------------------------------------------------------- #
# constants
# ------------------------------------------------------------------------------------------------------------------- #
# definition of sub-key. You can define new sub-keys as necessary. Always define them as constants so that others can
# use them in the future. NO HARD CODING of keys.
# as per "good programming practices" add your constants to OH_profile.constants in the corresponding section
# the naming convention for the sub-key constant should be "{MAIN-KEY-NAME}_{SUB-KEY-NAME}_KEY"
METADATA_SUBJECT_ID_KEY = 'subject_id'


# ------------------------------------------------------------------------------------------------------------------- #
# code starts here !!!
# ------------------------------------------------------------------------------------------------------------------- #
# example on how to use the OH profile work-flow. Please use the functions below to
# (1) load the profile (either from existing or from skeleton). This should be done at the beginning of your function
# (2) make updates to the profile (adding the metrics you extracted in your code as we defined in our meeting)
# (3) store/overwrite the profile. This should be done at the end of your function

# set the path. !IMPORTANT!: we should store all OH profiles (one for each subject) into a folder called "OH_profiles"
# the naming convention for the individual file is "{subjectID}_OH_profile.json". The functions will handle this for you
test_path = r"C:\Users\gonba\OneDrive\Treino\projects\OH_profiles"


# load the subject_info (in the wrapper function we will use this to cycle over the subjects)
subject_info = load_participants_info()


# example of subject ID. This is just an example, we should not hard code it. Whatever function you write should be able
# to receive the subject ID as parameter
subject_ID = str(subject_info.index[0])

# load the OH profile. If the profile does not exist, then the skeleton will be loaded
oh_profile = get_OH_profile(test_path, subject_ID)

# example of changing a field in the OH profile. Please use the main-keys as defined in "oh_profile_loader.py"
# Do NOT create new main-keys without discussing it first
oh_profile[METADATA_KEY] = {METADATA_SUBJECT_ID_KEY: subject_ID}

# save the updated OH profile
save_OH_profile(test_path, subject_ID, oh_profile)