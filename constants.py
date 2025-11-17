# ------------------------------------------------------------------------------------------------------------------- #
# file constants
# ------------------------------------------------------------------------------------------------------------------- #
CSV = ".csv"

# ------------------------------------------------------------------------------------------------------------------- #
# input constants
# ------------------------------------------------------------------------------------------------------------------- #
PHONE = 'phone'
WATCH = 'watch'
MBAN = 'mban'

# ------------------------------------------------------------------------------------------------------------------- #
# device constants
# ------------------------------------------------------------------------------------------------------------------- #
ACQUISITION_PATTERN = r"\d{2}-\d{2}-\d{2}" # hh-mm-ss
MAC_ADDRESS_PATTERN = r'[A-F0-9]{12}'

# ------------------------------------------------------------------------------------------------------------------- #
# sensor constants
# ------------------------------------------------------------------------------------------------------------------- #
# definition of valid sensors
ACC = 'ACC'
GYR = 'GYR'
MAG = 'MAG'
ROT = 'ROT'
NOISE = 'NOISE'
HEART = 'HEART'
EMG = 'EMG'

# define valid sensors for the three devices
PHONE_SENSORS = [ACC, GYR, MAG, ROT, NOISE]
WATCH_SENSORS = [ACC, GYR, MAG, ROT, HEART]
MBAN_SENSORS = [ACC, EMG]

# mapping of valid sensors to sensor filename - for both watch and phone
SENSOR_MAP = {ACC: 'ACCELEROMETER',
              GYR: 'GYROSCOPE',
              MAG: 'MAGNET', # To find both 'MAGNETIC FIELD' and 'MAGNETOMETER'
              ROT: 'ROTATION_VECTOR',
              NOISE: 'NOISERECORDER',
              HEART: 'HEART_RATE'}

IMU_SENSORS = [ACC, GYR, MAG]

ACC_PREFIX = "ACCELEROMETER"
GYR_PREFIX = "GYROSCOPE"
MAG_PREFIX = "MAGNET"
HEART_PREFIX = "HEART_RATE"
ROT_PREFIX = "ROTATION_VECTOR"
NOISE_PREFIX = "NOISERECORDER"

# the order of the sensors in these two lists must be the same
AVAILABLE_ANDROID_PREFIXES = [ACC_PREFIX, GYR_PREFIX, MAG_PREFIX, HEART_PREFIX, ROT_PREFIX, NOISE_PREFIX]
AVAILABLE_ANDROID_SENSORS = [ACC, GYR, MAG, HEART, ROT, NOISE]


# definition of time column
TIME_COLUMN_NAME = 't'
# ------------------------------------------------------------------------------------------------------------------- #
# MuscleBan constants
# ------------------------------------------------------------------------------------------------------------------- #

FS_MBAN = 1000
EMG = 'EMG'
XACC = 'xACC'
YACC = 'yACC'
ZACC = 'zACC'
NSEQ = 'nSeq'

VALID_MBAN_DATA = [NSEQ, EMG, XACC, YACC, ZACC]

MBAN_LEFT = 'mBAN_left'
MBAN_RIGHT = 'mBAN_right'

# ------------------------------------------------------------------------------------------------------------------- #
# Questionnaire constants
# ------------------------------------------------------------------------------------------------------------------- #
CONFIG_FOLDER_NAME = 'config_files'
RESULTS_FOLDER_NAME = 'results'

PSICOSSOCIAL = 'psicosocial'
AMBIENTE = 'ambiente'
BIOMECANICO = 'biomecanico'
PESSOAIS = 'pessoais'

QUESTIONNAIRE_DOMAINS = [PSICOSSOCIAL, AMBIENTE, BIOMECANICO, PESSOAIS]

