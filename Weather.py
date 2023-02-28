import os
import numpy as np
import pandas as pd
from datetime import datetime as dt
from calendar import isleap

import Modeling as um
import GLOBAL as GV # Global Variables
import GDrive as gd

def from_cols_to_w_vars(cols):
    # ['MG_Prec', 'MG_TempMax', 'RS_Prec', 'RS_TempMax', 'MS_Prec', etc etc] --> ['Prec', 'TempMax', 'Sdd30']
    fo = [c.split('_')[1] for c in cols if len(c.split('_'))==2]
    fo = list(set(fo))
    return fo

def get_w_sel_df():    
    return gd.read_csv(GV.W_SEL_FILE,dtype=str)

def open_w_sel_file():
    program =r'"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE"'
    file = r'"\\ac-geneva-24\E\grains trading\Streamlit\Monitor\Data\Weather\weather_selection.csv"'
    # os.system("start " + program + " "+ GV.W_SEL_FILE_LOCAL)
    os.system("start " + program + " "+file)

def build_w_df_all(df_w_sel, w_vars=[GV.WV_PREC,GV.WV_TEMP_MAX], in_files=GV.WS_AMUIDS, out_cols=GV.WS_UNIT_NAME, sel_hist_fore=[GV.WD_HIST, GV.WD_GFS, GV.WD_ECMWF, GV.WD_GFS_EN, GV.WD_ECMWF_EN]):
    """
    in_files:
        - must match the way in which files were written (as different APIS have different conventions)
        - 'IA_TempAvg_hist.csv' vs '1015346_TempMax_hist.csv'
        -      unit_alpha       vs         amuIds
    
    sel_hist_fore = [GV.WD_HIST, GV.WD_GFS]
        - must contain HIST and at least one forecast to make sense
    """

    if GV.WV_SDD_30 in w_vars:
        w_vars.append(GV.WV_TEMP_MAX)

    # Initialization
    w_vars=list(set(w_vars))

    # fo = {GV.WD_HIST: [], GV.WD_GFS: [], GV.WD_ECMWF: [], GV.WD_GFS_EN: [], GV.WD_ECMWF_EN: []} # old
    fo = {hf:[] for hf in sel_hist_fore}

    # Prepare the parallel download list
    donwload_dict={'file_path':[], 'names':[], 'parse_dates':[], 'index_col':[],'names':[],'header':[],'dayfirst':[]}
    for key, value in fo.items():
        w_dfs = []
        dict_col_file = {}

        # creating the dictionary 'IL_Prec' from file 'E:/Weather/etc etc
        for index, row in df_w_sel.iterrows():
            for v in w_vars:
                if v != GV.WV_SDD_30: # becuase I don't save 'derivative variables files'
                    file = row[in_files]+'_'+v+'_'+key+'.csv'
                    col = row[out_cols]+'_'+v
                    dict_col_file[col] = file

        # reading the files
        for col, file in dict_col_file.items():
            donwload_dict['file_path'].append(GV.W_DIR+file)
            donwload_dict['parse_dates'].append(['time'])
            donwload_dict['index_col'].append('time')
            donwload_dict['names'].append(['time', col])
            donwload_dict['header'].append(0)
            donwload_dict['dayfirst'].append(True)

    # For some reasons, the parallel doesn't work with the same 'service' so I need to pass 'None' (so that it creates a new one all for each file)
    # service=gd.build_service()
    service=None
    parallel_dfs=gd.read_csv_parallel(donwload_dict=donwload_dict, service=service, max_workers=500)

    # Looping 'WD_HIST', 'WD_GFS', 'WD_ECMWF', 'WD_GFS_EN', 'WD_ECMWF_EN'
    for key, value in fo.items():
        w_dfs = []
        dict_col_file = {}

        # creating the dictionary 'IL_Prec' from file 'E:/Weather/etc etc
        for index, row in df_w_sel.iterrows():
            for v in w_vars:
                if v != GV.WV_SDD_30: # becuase I don't save 'derivative variables files'
                    file = row[in_files]+'_'+v+'_'+key+'.csv'
                    col = row[out_cols]+'_'+v
                    dict_col_file[col] = file

        # reading the files
        for col, file in dict_col_file.items():     
            # w_dfs.append(gd.read_csv(GV.W_DIR+file, parse_dates=['time'], index_col='time', names=['time', col], header=0, dayfirst=True))
            w_dfs.append(parallel_dfs[GV.W_DIR+file])
                
        # concatenating the files
        if len(w_dfs) > 0:
            w_df = pd.concat(w_dfs, axis=1, sort=True)
            w_df = w_df.dropna(how='all')
            fo[key] = w_df

    # Adding 'derivatives' columns
    if GV.WV_SDD_30 in w_vars:            
        add_Sdd_all(fo, source_WV=GV.WV_TEMP_MAX, threshold=30)
    

    # Create the DF = Hist + Forecasts
    # Operational
    if (len(fo[GV.WD_GFS])):
        fo[GV.WD_H_GFS] = pd.concat([fo[GV.WD_HIST], fo[GV.WD_GFS]], axis=0, sort=True)
    if (len(fo[GV.WD_ECMWF])):
        fo[GV.WD_H_ECMWF] = pd.concat([fo[GV.WD_HIST], fo[GV.WD_ECMWF]], axis=0, sort=True)

    # Ensemble
    if (len(fo[GV.WD_GFS_EN])):
        fo[GV.WD_H_GFS_EN] = pd.concat([fo[GV.WD_HIST], fo[GV.WD_GFS_EN]], axis=0, sort=True)
    if (len(fo[GV.WD_ECMWF_EN])):
        fo[GV.WD_H_ECMWF_EN] = pd.concat([fo[GV.WD_HIST], fo[GV.WD_ECMWF_EN]], axis=0, sort=True)
        
    return fo

def weighted_w_df_old(w_df, weights, w_vars=[], output_column='Weighted', ref_year=GV.CUR_YEAR, ref_year_start= dt(GV.CUR_YEAR,1,1)):
    # w_vars = [] needs to be a list
    w_df = um.add_seas_year(w_df, ref_year=ref_year, ref_year_start=ref_year_start)

    fo_list = []
    if len(w_vars)==0: 
        w_vars=from_cols_to_w_vars(w_df.columns)

    weights_years=weights.index.unique() # right

    # delete the below 3 lines
    w_df_years = w_df['year'].unique()    
    missing_weights = list(set(w_df_years) - set(weights_years))
    # print(missing_weights)

    w_df_years = w_df.index.year.unique() # right

    # Add missing years
    missing_weights = list(set(w_df_years) - set(weights_years))
    weight_mean=weights.mean()
    weight_mean=weight_mean/weight_mean.sum()

    # print(missing_weights)

    for m in missing_weights:
        weights.loc[m]=weight_mean

    # Remove useless years
    weights=weights.loc[w_df_years]
    weights=weights.sort_index()

    for v in w_vars:
        fo = w_df.copy()
        fo = fo.reset_index(drop=True).set_index(w_df.index.year)
        
        var_weights = weights.copy()
        var_weights.columns = [c+'_'+v for c in weights.columns]

        w_w_df = fo * var_weights

        w_w_df=w_w_df.set_index(w_df.index)

        w_w_df = w_w_df.dropna(how='all', axis=1)
        w_w_df = w_w_df.dropna(how='all', axis=0)        

        fo = w_w_df.sum(axis=1)
        fo = pd.DataFrame(fo)

        fo = fo.rename(columns={0: output_column+'_'+v})
        fo_list.append(fo)

    return pd.concat(fo_list, axis=1)

def weighted_w_df(w_df, weights, w_vars=[], output_column='Weighted', ref_year=GV.CUR_YEAR, ref_year_start= dt(GV.CUR_YEAR,1,1)):
    # w_vars = [] needs to be a list
    w_df = um.add_seas_year(w_df, ref_year=ref_year, ref_year_start=ref_year_start)

    fo_list = []
    if len(w_vars)==0: 
        w_vars=from_cols_to_w_vars(w_df.columns)
        
    # Add missing years
    weights_years=weights.index.unique()
    w_df_years = w_df['year'].unique()

    missing_weights = list(set(w_df_years) - set(weights_years))

    weight_mean=weights.mean()
    weight_mean=weight_mean/weight_mean.sum()

    for m in missing_weights:
        weights.loc[m]=weight_mean

    # Remove useless years
    weights=weights.loc[w_df_years]
    weights=weights.sort_index()

    for v in w_vars:
        fo = w_df.copy()
        fo = fo.reset_index(drop=True).set_index('year')
        
        var_weights = weights.copy()
        var_weights.columns = [c+'_'+v for c in weights.columns]

        w_w_df = fo * var_weights

        w_w_df=w_w_df.set_index(w_df.index)

        w_w_df = w_w_df.dropna(how='all', axis=1)
        w_w_df = w_w_df.dropna(how='all', axis=0)        

        fo = w_w_df.sum(axis=1)
        fo = pd.DataFrame(fo)

        fo = fo.rename(columns={0: output_column+'_'+v})
        fo_list.append(fo)

    return pd.concat(fo_list, axis=1)


def weighted_w_df_all(all_w_df, weights, w_vars=[], output_column='Weighted', ref_year=GV.CUR_YEAR, ref_year_start= dt(GV.CUR_YEAR,1,1)):
    fo={}
    for key, value in all_w_df.items():
        if len(value)>0:
            fo[key]=weighted_w_df(w_df=value, weights=weights, w_vars=w_vars, output_column=output_column, ref_year=ref_year, ref_year_start=ref_year_start)
    return fo


def add_Sdd_all(w_df_all, source_WV=GV.WV_TEMP_MAX, threshold=30):
    for key, w_df in w_df_all.items():
        add_Sdd(w_df_all[key], source_WV=source_WV, threshold=threshold)

def add_Sdd(w_df, source_WV=GV.WV_TEMP_MAX, threshold=30):
    for col in w_df.columns:
        geo, w_var= col.split('_')
        if w_var == source_WV:
            new_w_var = geo+'_Sdd'+str(threshold)
            w_df[new_w_var]=w_df[col]
            mask=w_df[new_w_var]>threshold
            w_df.loc[mask,new_w_var]=w_df.loc[mask,new_w_var]-threshold
            w_df.loc[~mask,new_w_var]=0
    return w_df
    
def analog_ranking(w_df, col=None, mode = GV.EXT_MEAN, ref_year=GV.CUR_YEAR, ref_year_start = dt(GV.CUR_YEAR,1,1), precalculated_pivot = []):
    if (len(precalculated_pivot)==0):
        if col==None: col = w_df.columns[0]
        w_df=w_df[[col]]
        
        um.add_seas_year(w_df,ref_year,ref_year_start)
        w_df['seas_day'] = [um.seas_day(d,ref_year_start) for d in w_df.index]

        pivot = w_df.pivot_table(index=['seas_day'], columns=['year'], values=[col], aggfunc='mean')
        pivot.columns = pivot.columns.droplevel(level=0)

        # Drop columns that don't start from the beginning of the crop year (ref_year_start)
        cols_to_drop = [c for c in pivot.columns if np.flatnonzero(~np.isnan(pivot[c]))[0] > 0]
        pivot=pivot.drop(columns=cols_to_drop)

        # the below interpolation is to fill 29 Feb every year
        pivot.interpolate(inplace=True, limit_area='inside')
                
        cur_year_v = pivot[ref_year].values
        lvi = np.flatnonzero(~np.isnan(cur_year_v))[-1] # Last Valid Index of the current year

        # Remove current year from the columns (to be able to exclude it from the calculations)
        cols_no_cur_year = list(pivot.columns)
        cols_no_cur_year.remove(ref_year)

        # analogue identification (on the cumulative values)
        analog_col=None
        analog_pivot = pivot.cumsum()
        df_sub=analog_pivot[cols_no_cur_year].subtract(analog_pivot[ref_year],axis=0).abs()


    if (len(df_sub.columns)>0):        
        dt_s=analog_pivot.index[0]
        dt_e=analog_pivot.index[lvi]

        abs_error= df_sub.loc[dt_s:dt_e].sum()        
        analog_col=abs_error.index[np.argmin(abs_error)]

    if analog_col!=None:
        abs_error=abs_error.sort_values()
        print('Analog: ', abs_error.index[0])

    return 0    


def extract_w_windows(w_df, windows_df: pd.DataFrame):
    """
    'windows_df' index is the 'year' and it will be the same as the output
    the 'windows_df' needs to have 'start' and 'end' columns
    """
    fo=pd.DataFrame(columns=w_df.columns)
    for i in windows_df.index:
        sd=windows_df.loc[i]['start']
        ed=windows_df.loc[i]['end']

        fo.loc[i]= np.sum(w_df.loc[sd:ed])
    return fo

def seasonalize(w_df, col=None, mode = GV.EXT_MEAN, ref_year=GV.CUR_YEAR, ref_year_start = dt(GV.CUR_YEAR,1,1)):
    """
    This function MUST do only 1 column at a time

    Takes a very long daily DataSet (from 1985 and "squares it" by pivoting it with rows='day of the year' and colums =year)
    From the code:
                    "pivot = w_df.pivot_table(index=['seas_day'], columns=['year'], values=[col], aggfunc='mean')"
    
    Args:
        w_df: Long Daily Dataset
        col:
        mode:
        ref_year: reference year
        ref_year_start: reference seasonal start

    Returns:
        The Pivot with "columns=['year']" and a few added columns ['Max','Min','Mean', 'Analog'] etc

        Most important output is probably the: "2022_proj" column (as it is the projected weather according to the seasonal and the specified "mode")

                pivot[str(ref_year)+GV.PROJ] = proj
    """
        
    if col==None: col = w_df.columns[0]
    w_df=w_df[[col]]

    w_df=um.add_seas_year(w_df, ref_year, ref_year_start)
    w_df['seas_day'] = [um.seas_day(d,ref_year_start) for d in w_df.index]

    pivot = w_df.pivot_table(index=['seas_day'], columns=['year'], values=[col], aggfunc='mean')
    pivot.columns = pivot.columns.droplevel(level=0)

    # Drop columns that don't start from the beginning of the crop year (ref_year_start)
    cols_to_drop = [c for c in pivot.columns if np.flatnonzero(~np.isnan(pivot[c]))[0] > 0]
    pivot=pivot.drop(columns=cols_to_drop)

    # the below interpolation is to fill 29 Feb every year
    pivot.interpolate(inplace=True, limit_area='inside')
            
    cur_year_v = pivot[ref_year].values
    lvi = np.flatnonzero(~np.isnan(cur_year_v))[-1] # Last Valid Index of the current year

    cols_no_cur_year = list(pivot.columns); cols_no_cur_year.remove(ref_year)
    max_no_cur_year_v = pivot[cols_no_cur_year].max(axis=1).values
    min_no_cur_year_v = pivot[cols_no_cur_year].min(axis=1).values
    avg_no_cur_year_v = pivot[cols_no_cur_year].mean(axis=1).values            

    # analogue identification
    analog_col=None
    analog_pivot = pivot.cumsum()
    df_sub=analog_pivot.drop(columns=[ref_year]).subtract(analog_pivot[ref_year],axis=0).abs()

    if (len(df_sub.columns)>0):        
        dt_s=analog_pivot.index[0]
        dt_e=analog_pivot.index[lvi]

        abs_error= df_sub.loc[dt_s:dt_e].sum()        
        analog_col=abs_error.index[np.argmin(abs_error)]

    if analog_col!=None:
        # print('Variable {0} - Ext Mode {1} - Analog {2}'.format(col,mode,analog_col)); print('')
        pivot[str(analog_col)+GV.ANALOG] = pivot[analog_col]

    # analog_ranking(w_df, col, mode, ref_year, ref_year_start, [])

    pivot['Max']=max_no_cur_year_v
    pivot['Min']=min_no_cur_year_v
    pivot['Mean']=avg_no_cur_year_v

    # initialize the projection as the current year values (all 366 values still including the NaN at the end)
    proj = np.array(cur_year_v)

    # the below condition kicks in only if we actually need a projection:
    # basically saying for 'hist' len(cur_year_v) == 366 so just calculate if 'lvi' is less
    # for GFS and ECMWF the 2 are the same, so it will not do anything
    
    if len(cur_year_v)>lvi+1:       
        # Attaching the "projection" part to the "proj" column
        if GV.EXT_MEAN in mode:            
            proj[lvi+1:] = avg_no_cur_year_v[lvi+1:]  # Avg weather (for variables like Precipitation)
        elif GV.EXT_ANALOG in mode:
            split = mode.split('_')
            if (len(split)==1):
                proj[lvi+1:] = pivot[analog_col][lvi+1:]
            else:
                proj[lvi+1:] = pivot[int(split[1])][lvi+1:]
            
    # Writing the projection column on the pivot
    pivot[str(ref_year)+GV.PROJ] = proj    

    return pivot

def cumulate_seas(df, excluded_cols = [], ref_year=GV.CUR_YEAR):
    df=df.drop(columns=excluded_cols)

    cols_no_cur_year = list(df.columns); 
    cols_no_cur_year.remove(ref_year)

    df = df.cumsum()
    df['Max']=df[cols_no_cur_year].max(axis=1)
    df['Min']=df[cols_no_cur_year].min(axis=1)
    df['Mean']=df[cols_no_cur_year].mean(axis=1)
    return df

def extend_with_seasonal_df(w_df_to_ext, cols_to_extend=[], seas_cols_to_use=[], var_mode_dict=GV.EXT_DICT, ref_year=GV.CUR_YEAR, ref_year_start= dt(GV.CUR_YEAR,1,1), input_dict_col_seas ={}, return_dict_col_seas = False, keep_duplicates='first'):
    """
    - Extends the full DataFrame column by column ('IL_Prec', 'IA_TempMax', 'USA_Sdd30')
    - Extend 'w_df_to_ext' (long daily dataframe from 1950 till today) to the end of the seasonals period (calculated from the input 'ref_year_start')
    - duplicates_keep=
            - 'first': keeps the data and drops the seasonal
            - 'last': keeps the seasonal and drops the actual data (only time I found it useful is when calculating the "trend yield" because I need a big average of everything
        
    - 'dict_col_seas':
            - used to speed up the calculation
            - if provided it by-passes the whole seasonalization calculation
            - it is a dictionary of {'col' column to extend : corresponding 'seasonal'} to be applied to extend 'col'
    """
            
    w_df_ext_s=[]
    fo_dict_col_seas={}
    calc_seas = len(input_dict_col_seas)==0 # true if 'input_dict_col_seas' is not provided. So basically: calculate the seasonal if not provided already
    
    if len(cols_to_extend)==0:
        cols_to_extend = [c for c in w_df_to_ext.columns if ((len(c.split('_'))==2) & (c!='seas_day'))]

    # Extending column by column ('IL_Prec', 'IA_TempMax', 'USA_Sdd30')
    for idx, col in enumerate(cols_to_extend):
        if (calc_seas):
            w_var=col.split('_')[1]
            # choosing the column to extract from the "Seasonalize" function
            if len(seas_cols_to_use)==0:
                seas_col_to_use = str(ref_year)+GV.PROJ # 2022_Proj
            else:
                i = min(idx,len(seas_cols_to_use)-1)
                seas_cols_to_use[i]

            # Picking the 'mode'
            # print(var_mode_dict)
            if w_var in var_mode_dict:
                # print('Found Key:', w_var)
                ext_mode=var_mode_dict[w_var]
            else:
                # print('No Key:', w_var)
                ext_mode=GV.EXT_MEAN
            
            # Calculate the seasonal
            seas = seasonalize(w_df_to_ext, col, mode=ext_mode, ref_year=ref_year, ref_year_start=ref_year_start)            
                        
            # ext_year = pd.to_datetime(w_df_to_ext.last_valid_index()).year # old
            ext_year = ref_year

            if not isleap(ext_year):
                seas=seas.drop(str(GV.LLY)+'-02-29') # Remove 29 Feb if not leap year

            # Trasfer the "timeline" to the CUR_YEAR
            # that is probably different from the seasonals pivot, because it uses the LLY (Last Leap Year)

            year_offset = ref_year - seas.index[-1].year            
            seas['time'] = [dt(year=x.year+year_offset, month=x.month, day=x.day) for x in seas.index]
            seas=seas.set_index('time')

            # From: '2022_Proj' to 'IL_Prec'
            seas=seas.rename(columns={seas_col_to_use:col})

            fo_dict_col_seas[col]=seas[[col]].copy()
        else:
            fo_dict_col_seas[col] = input_dict_col_seas[col]

        # Append the Seasonal Rows at the end of the of the long "w_df_to_ext"
        w_df_ext = pd.concat([w_df_to_ext[[col]], fo_dict_col_seas[col]])

        # Efficient method for "drop_duplicates", dropping rows with duplicated index
        # Keep the first meaning: keep the actual Data and Drop the seasonal (that is exactly right)
        w_df_ext = w_df_ext[~w_df_ext.index.duplicated(keep=keep_duplicates)]

        # putting all the columns in a list (to be able to concat them all together at the end)
        w_df_ext_s.append(w_df_ext.copy())

    # put all the columns side by side 
    fo=pd.concat(w_df_ext_s,axis=1)
    fo=fo.sort_index(ascending=True)

    if return_dict_col_seas:
        return fo , fo_dict_col_seas
    else:
        return fo