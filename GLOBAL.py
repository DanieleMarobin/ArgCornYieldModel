from datetime import datetime as dt
from calendar import isleap

def last_leap_year():    
    start=dt.today().year
    while(True):
        if isleap(start): return start
        start-=1

CUR_YEAR = dt.today().year
LLY = last_leap_year()

LOCAL_DIR = r'\\ac-geneva-24\E\grains trading\Streamlit\Monitor\\'

# Securities
SEC_DIR = 'Data/Securities/'
SEC_DIR_LOCAL = LOCAL_DIR+SEC_DIR

# Feed Grain Files
FG_DIR = 'Data/FeedGrains/'
FG_DB_FILE_ZIP = FG_DIR + 'FeedGrains.zip'
FG_DB_FILE = FG_DIR + 'FeedGrains.csv'
FG_TC_FILE = FG_DIR + 'fg_db_time_conversion.csv' # TC stads for Time Convertion

FG_DB_FILE_ZIP_LOCAL =LOCAL_DIR + FG_DB_FILE_ZIP
FG_DB_FILE_LOCAL = LOCAL_DIR + FG_DB_FILE
FG_TC_FILE_LOCAL = LOCAL_DIR + FG_TC_FILE

# QuickStats Files
QS_DIR = 'Data/QuickStats/'
QS_DB_FILE = QS_DIR + 'qs_db.csv'

# Weather Files
W_DIR = 'Data/Weather/'
W_DIR_LOCAL = LOCAL_DIR+W_DIR
W_SEL_FILE = W_DIR + 'weather_selection.csv'
W_SEL_FILE_LOCAL = LOCAL_DIR + W_SEL_FILE
W_LAST_UPDATE_FILE = W_DIR + 'last_update.csv'
W_LAST_UPDATE_FILE_LOCAL = LOCAL_DIR + W_LAST_UPDATE_FILE


# Weather Data types
WD_HIST='hist'

WD_GFS='gfs'
WD_ECMWF='ecmwf'
WD_GFS_EN='gfsEn'
WD_ECMWF_EN='ecmwfEn'

WD_H_GFS='hist_gfs'
WD_H_ECMWF='hist_ecmwf'
WD_H_GFS_EN='hist_gfsEn'
WD_H_ECMWF_EN='hist_ecmwfEn'

# WV = Weather variable
WV_PREC='Prec'

WV_TEMP_MAX='TempMax'
WV_TEMP_MIN='TempMin'
WV_TEMP_AVG='TempAvg'
WV_TEMP_SURF='TempSurf'
WV_SDD_30='Sdd30'

WV_SOIL='Soil'
WV_HUMI='Humi'
WV_VVI='VVI'

# Extention Modes
EXT_MEAN='Mean'
EXT_ANALOG='Analog'

# 
EXT_DICT = {
    WV_PREC : EXT_MEAN,

    WV_TEMP_MAX: EXT_MEAN,
    WV_TEMP_MIN: EXT_MEAN,
    WV_TEMP_AVG: EXT_MEAN,
    WV_TEMP_SURF: EXT_MEAN,
    WV_SDD_30: EXT_MEAN,

    WV_SOIL: EXT_MEAN,
    WV_HUMI: EXT_MEAN,
    WV_VVI: EXT_MEAN,
}

# Projection
PROJ='_Proj'
ANALOG='_Analog'

# w_sel file columns
WS_AMUIDS='amuIds'
WS_COUNTRY_NAME='country_name'
WS_COUNTRY_ALPHA='country_alpha'
WS_COUNTRY_CODE='country_code'
WS_UNIT_NAME='unit_name'
WS_UNIT_ALPHA='unit_alpha'
WS_UNIT_CODE='unit_code'
WS_STATE_NAME='state_name'
WS_STATE_ALPHA='state_alpha'
WS_STATE_CODE='state_code'

# Bloomberg (the number is the rows of a completely finished run)
BB_RUNS_DICT={
    'GFS_DETERMINISTIC_0':129,
    'GFS_DETERMINISTIC_6':129,
    'GFS_DETERMINISTIC_12':129,
    'GFS_DETERMINISTIC_18':129,

    'GFS_ENSEMBLE_MEAN_0':65,
    'GFS_ENSEMBLE_MEAN_6':65,
    'GFS_ENSEMBLE_MEAN_12':65,
    'GFS_ENSEMBLE_MEAN_18':65,

    'ECMWF_DETERMINISTIC_0':65,
    'ECMWF_DETERMINISTIC_6':31,
    'ECMWF_DETERMINISTIC_12':65,
    'ECMWF_DETERMINISTIC_18':31,

    'ECMWF_ENSEMBLE_MEAN_0':61,
    'ECMWF_ENSEMBLE_MEAN_6':25,
    'ECMWF_ENSEMBLE_MEAN_12':61,
    'ECMWF_ENSEMBLE_MEAN_18':25,        
}

# Earth Engine

# Sentinel 2 Bands and Combinations
# https://gisgeography.com/sentinel-2-bands-combinations/
SENTINEL_2_VISUALIZATIONS={
    'Natural Color': {'min': 0.0,'max': 0.3,'bands': ['B4', 'B3', 'B2']},
    'Color Infrared': {'min': 0.0,'max': 0.3,'bands': ['B8', 'B4', 'B3']},
    'Short-Wave Infrared': {'min': 0.0,'max': 0.3,'bands': ['B12', 'B8A', 'B4']},
    'Agriculture': {'min': 0.0,'max': 0.3,'bands': ['B11', 'B8', 'B2']},
    'Geology': {'min': 0.0,'max': 0.3,'bands': ['B12', 'B11', 'B2']},
}