import re
import numpy as np
import pandas as pd
import statsmodels.api as sm
from datetime import datetime as dt
from datetime import timedelta
from copy import deepcopy

import concurrent.futures
from itertools import combinations, combinations_with_replacement
from calendar import isleap

import GLOBAL as GV
import Charts as uc

def add_estimate(df, year_to_estimate, how='mean', last_n_years=5, normalize=False, overwrite=False):
    if (overwrite) or (year_to_estimate not in df.index):
        if how=='mean':
            mask=(df.index>=year_to_estimate-last_n_years)
            mean=df[mask].mean()

        if normalize:
            df.loc[year_to_estimate]=mean/mean.sum()
        else:
            df.loc[year_to_estimate]=mean    
    return df

def add_seas_timeline(df, years_offset, date_col=None):
    '''
    timeline:
        - original time line
    fo:
        - the 'common' seasonal timeline (the x-axis on the final 'seas' chart)
    '''
    fo = []
    if date_col==None:
        timeline=df.index
    else:
        timeline=df[date_col]

    for d in timeline:
        # print('timeline:', timeline)
        year = d.year + years_offset
        month = d.month
        day = d.day

        if (month == 2) and (day == 29) and (not isleap(year)):
            fo.append(dt(year, month, 28, 12,00,00))
        else:
            fo.append(dt(year, month, day))

    df['seas_day'] = fo
    return df

def add_seas_year(w_df, ref_year=GV.CUR_YEAR, ref_year_start= dt(GV.CUR_YEAR,1,1), offset = 2):
    # Add the 'year' of the seasonal (that is basically the value of the legend)
    # This is needed because if the crop year starts in Sep, then Sep, Oct, Nov, Dec, Jan, ..., Aug will be the same year

    # yo = year offset
    # offset = 2 means:
    #       - first year is going to be first year - 2
    #       - last year is going to be ref_year + 2 = CUR_YEAR + 2

    os = w_df.index[0].year - ref_year -offset # offset start
    oe = w_df.index[-1].year - ref_year +offset  # offset end

    for yo in range(os, oe):
        value = ref_year+yo
        ss = ref_year_start+ pd.DateOffset(years=yo) # start slice
        es = ref_year_start+ pd.DateOffset(years=yo+1)+pd.DateOffset(days=-1) # end slice

        mask = ((w_df.index>=ss) & (w_df.index<=es))
        w_df.loc[mask,'year']=int(value)

    w_df['year'] = w_df['year'].astype('int')

    return w_df

def add_seas_day(df, ref_year_start= dt.today(), date_col=None):
    if date_col==None:
        df['seas_day'] = [seas_day(d,ref_year_start) for d in df.index]
    else:
        df['seas_day'] = [seas_day(d,ref_year_start) for d in df[date_col]]
    return df        

def seas_day(date, ref_year_start= dt(GV.CUR_YEAR,1,1)):
    """
    'seas_day' is the X-axis of the seasonal plot:
            - it makes sure to include 29 Feb
            - it is very useful in creating weather windows
    """

    start_idx = 100 * ref_year_start.month + ref_year_start.day # Start of the seasonal x-axis
    date_idx = 100 * date.month + date.day

    # Seas start BEFORE 1 Mar
    if (start_idx<300):
        if (date_idx>=start_idx):
            return dt(GV.LLY, date.month, date.day)
        else:
            return dt(GV.LLY+1, date.month, date.day)
        
    # Seas start AFTER 1 Mar
    else:
        if (date_idx>=start_idx):
            return dt(GV.LLY-1, date.month, date.day)
        else:
            return dt(GV.LLY, date.month, date.day)

def generate_weather_windows_df(input_w_df, date_start, date_end, ref_year = GV.CUR_YEAR, ref_year_start= dt(GV.CUR_YEAR,1,1), freq_start='1D', freq_end='1D'):
    wws=[]
    w_df = deepcopy(input_w_df)
    w_df = add_seas_year(w_df, ref_year, ref_year_start) # add the 'year' column
    w_df['seas_day'] = [seas_day(d, ref_year_start) for d in w_df.index]
    
    start_list = pd.date_range(start = date_start, end = date_end, freq=freq_start)

    for s in start_list:
        seas_s = seas_day(date=s, ref_year_start=ref_year_start)
        end_list = pd.date_range(start=min(s, date_end), end=date_end, freq=freq_end)

        for e in end_list:
            # the below condition, excludes the column from 29 Feb to 29 Feb (because there is going to be 1 data point every 4 years!)
            if not(s.month==2 and s.day==29 and e.month==2 and e.day==29):
                seas_e = seas_day(date=e, ref_year_start=ref_year_start)

                ww = w_df[(w_df['seas_day']>=seas_s) & (w_df['seas_day']<=seas_e)]
                ww=ww.drop(columns=['seas_day'])
                # Rename columns
                ww.columns=list(map(lambda x:'year'if x=='year'else x+'_'+s.strftime("%b%d")+'-'+e.strftime("%b%d"),list(ww.columns)))
                ww = ww.groupby('year').mean()
                ww.index=ww.index.astype(int)
                wws.append(ww)                                

    # Excluding everything: it exclude 2022 because some of the windows have not started yet
    fo = pd.concat(wws, sort=True, axis=1, join='inner')

    # Including everything: because only leap years 29 Feb
    # fo = pd.concat(wws, sort=True, axis=1, join='outer')
    return fo

def trend_yield(df_yield, start_year=None, n_years_min=20, rolling=False):
    """
    'start_year'
        - start calculating the trend yield from this year
        - if I put 1995 it will calculate the trend year for 1995 taking into account data up to 1994

    'n_years_min'
        - minimum years included for the trend year calculation
        - if I put 10, and I need to calculate 1995, it will take years from 1985 to 1994 (both included)
    
    simple way to get the input 'df_yield'

    import APIs.QuickStats as qs
    df_yield=qs.get_USA_yields(cols_subset=['Value','year'])
    """

    yield_str='yield'
    trend_str='trend_yield'
    devia_str='yield_deviation'

    if df_yield.index.name != 'year':
        df_yield=df_yield.set_index('year',drop=False)

    year_min=int(df_yield.index.min())
    year_max=int(df_yield.index.max())

    if start_year is None:
        start_year=year_min

    fo_dict={'year':[], trend_str:[] }
    for y in range(start_year,year_max+1):
        # this to avoid having nothing when we are considering the first year of the whole df
        year_to=max(y-1,year_min) 
        if rolling:
            mask=((df_yield.index>=y-n_years_min) & (df_yield.index<=year_to))
        else:
            mask=((df_yield.index>=start_year-n_years_min) & (df_yield.index<=year_to))

        df_model=df_yield[mask]

        model=Fit_Model(df_model,y_col='Value',x_cols=['year'])
        pred = predict_with_model(model,df_yield.loc[y:y])

        fo_dict['year'].append(y)
        fo_dict[trend_str].append(pred[y])

    df=pd.DataFrame(fo_dict)
    df=df.set_index('year')


    df=pd.concat([df_yield,df],axis=1,join='inner')
    df=df.rename(columns={'Value':yield_str})
    df[devia_str]=100.0*( df[yield_str]/df[trend_str]-1.0)
    df=df.set_index('year')
    return df


def var_windows_from_cols_old(cols=[]):
    """
    Typical Use:
        ww = um.var_windows_from_cols(m.params.index)
    
    Future development:
        - Use the other function 'def windows_from_cols(cols=[]):' to calculate the windows in this one
        - Note: 'def windows_from_cols(cols=[]):' just calculates the windows 
    """
    # Make sure that this sub is related to the function "def windows_from_cols(cols,year=2020):"
    var_windows=[]
    year = GV.LLY

    for c in (x for x  in cols if '-' in x):
        split=re.split('_|-',c)
        var = split[0]+'_'+split[1]
        
        if len(split)>1:
            start = dt.strptime(split[2]+str(year),'%b%d%Y')
            end = dt.strptime(split[3]+str(year),'%b%d%Y')
        
        var_windows.append({'variables':[var], 'windows':[{'start': start,'end':end}]})
    
    # I return 'np.array' to be able to use masks with it
    return np.array(var_windows)

def var_windows_from_cols(cols=[], ref_year_start= dt(GV.CUR_YEAR,1,1)):
    """
    Typical Use:
        ww = um.var_windows_from_cols(m.params.index)
    
    Future development:
        - Use the other function 'def windows_from_cols(cols=[]):' to calculate the windows in this one
        - Note: 'def windows_from_cols(cols=[]):' just calculates the windows 
    """
    # Make sure that this sub is related to the function "def windows_from_cols(cols,year=2020):"
    var_windows=[]
    year = GV.LLY

    for c in (x for x  in cols if '-' in x):
        split=re.split('_|-',c)
        var = split[0]+'_'+split[1]
        
        if len(split)>1:
            d_start = dt.strptime(split[2]+str(year),'%b%d%Y')
            d_end = dt.strptime(split[3]+str(year),'%b%d%Y')

            start = seas_day(d_start, ref_year_start)
            end = seas_day(d_end, ref_year_start)
        
        var_windows.append({'variables':[var], 'windows':[{'start': start,'end':end}]})
    
    # I return 'np.array' to be able to use masks with it
    return np.array(var_windows)

def var_windows_coverage(var_windows):
    fo = []
    w_days=[]
    for w in var_windows:
        s = w['windows'][0]['start']
        e = w['windows'][0]['end']
        fo.extend(np.arange(s, e + timedelta(days = 1), dtype='datetime64[D]'))
        w_days.append((e-s).days)
    
    actual = set(fo)    
    if (len(actual)>0):
        full = np.arange(min(actual), max(actual) + np.timedelta64(1,'D'), dtype='datetime64[D]')
    else:        
        full=[]
    
    if len(w_days)>0:
        min_days=min(w_days)
    else:
        min_days=0
    return full, actual, min_days

def prediction_interval(season_start, season_end, trend_case, full_analysis):
    if full_analysis:
        pred_date_start = season_start
        pred_date_end = season_end
    else:
        if trend_case:
            pred_date_start = season_start
            pred_date_end = season_start
        else:
            pred_date_start = season_end
            pred_date_end = season_end

    return pred_date_start, pred_date_end

def Build_DF_Instructions(WD_All='weighted', WD = GV.WD_HIST, prec_units = 'mm', temp_units='C', ext_mode = GV.EXT_DICT, ref_year = GV.CUR_YEAR, ref_year_start= dt(GV.CUR_YEAR,1,1)):
    fo={}

    if WD_All=='simple':
        fo['WD_All']='w_df_all'
    elif WD_All=='weighted':
        fo['WD_All']='w_w_df_all'

    fo['WD']=WD # which Dataset to use: 'hist', 'hist_gfs', 'hist_ecmwf', 'hist_gfsEn', 'hist_ecmwfEn'
        
    if prec_units=='mm':
        fo['prec_factor']=1.0
    elif prec_units=='in':
        fo['prec_factor']=1.0/25.4

    if temp_units=='C':
        fo['temp_factor']=1.0
    elif temp_units=='F':
        fo['temp_factor']=9.0/5.0

    fo['ext_mode']=ext_mode
    fo['ref_year']=ref_year
    fo['ref_year_start']=ref_year_start
    return fo

def predict_with_model(model, pred_df):
    if (('const' in model.params) & ('const' not in pred_df.columns)):
        pred_df = sm.add_constant(pred_df, has_constant='add')

    return model.predict(pred_df[model.params.index])


def Fit_Model(df, y_col: str, x_cols=[], exclude_from=None, extract_only=None):
    """
    'exclude_from' needs to be consistent with the df index
    """

    if not ('const' in df.columns):
        df = sm.add_constant(df, has_constant='add')

    if not ('const' in x_cols):        
        x_cols.append('const')

    if exclude_from!=None:
        df=df.loc[df.index<exclude_from]

    y_df = df[[y_col]]

    if (len(x_cols)>0):
        X_df=df[x_cols]
    else:
        X_df=df.drop(columns = y_col)

    model = sm.OLS(y_df, X_df).fit()

    if extract_only is None:
        fo = model
    elif extract_only == 'rsquared':
        fo = model.rsquared

    return fo

def max_correlation(X_df, threshold=1.0):
    """
    the 'threshold' is needed because when I want to analyze the 'max correlation'
    """
    try:
        max_corr = np.abs(np.corrcoef(X_df,rowvar=False))
        max_corr = np.max(max_corr[max_corr<threshold])
        return max_corr        
    except:
        # print('X_df', X_df)
        # print('max_corr',max_corr)
        return 1.0  



def sorted_rsquared_var(model_df, y_col='y', n_var=1, with_replacement=False, cols_excluded=[], parallel=None, max_workers=None):
    """
    with_replacement = True
        - makes a difference only if 'n_var>1'
        - it means that if we have 'n_var==2', it will also try the model [v1, v1] so the same variable n times
        - 'n_var==3' => [v1, v1, v1]        
    """
    # Creating the results dictiony: 
    #       1) Adding Variables cols
    #       2) then the 'value'
    results_dict={}
    for v in range(n_var):
        results_dict['v'+str(v+1)]=[]
    results_dict['value']=[]

    x_cols_list=[]
    cols_excluded = cols_excluded+[y_col]
    cols_model = list(set(model_df.columns)-set(cols_excluded))

    if with_replacement:        
        comb = combinations(cols_model, n_var)
    else:
        comb = combinations_with_replacement(cols_model, n_var)

    x_cols_list = [list(c) for c in comb] # converting 'list of tuples' to 'list of lists' 

    models_results=run_multiple_models(df=model_df, y_col=y_col, x_cols_list=x_cols_list, extract_only=None, parallel=parallel, max_workers=max_workers)

    # Visualize with the heat map
    for key, model in models_results.items():
        # Add the variable names
        vars_split=key.split('|')        
        [results_dict['v'+str(i+1)].append(v) for i,v in enumerate(vars_split)]

        # Add the R-Squared
        if n_var>1:
            results_dict['value'].append(100.0*model.rsquared)
        else:
            # if there is only 1 variable, I also put the sign of the relationship
            results_dict['value'].append(np.sign(model.params[key])*100.0*model.rsquared)
            

    # Create and Sort the 'Ranking DataFrame'
    rank_df=pd.DataFrame(results_dict)

    rank_df['abs_value']=rank_df['value'].abs()
    rank_df=rank_df.sort_values(by='abs_value',ascending=False)

    # to extract the top N
    # sorted_vars = rank_df['variable']
    # x_cols_list=sorted_vars[0:top_n]

    return rank_df

def heat_map_2_variables(model_df, y_cols=['y'], top_n = 40, cols_excluded=[], parallel=None, max_workers=None, show=False):
    """
    1 'heat_map' for each item in 'y_cols'
    """
    fo={}    
    for y in y_cols:
        # Calculating the 'Top N Variables'
        rank_df=sorted_rsquared_var(model_df=model_df, y_col=y, n_var=1, cols_excluded=cols_excluded, parallel=parallel, max_workers=max_workers)
        sorted_vars = rank_df['v1']
        cols_model=list(sorted_vars[0:top_n])
        cols_model.append(y)
        print('Done Sorting')

        # Calcute the 2 Variables r-squares
        rank_df=sorted_rsquared_var(model_df=model_df[cols_model], y_col=y, n_var=2, cols_excluded=cols_excluded, parallel=parallel, max_workers=max_workers)

        # Adding rows to make the heat-map (2D matrix) symmetric
        mask=(rank_df['v1']!=rank_df['v2'])
        df = rank_df[mask]        
        df=df.rename(columns={'v1':'v2','v2':'v1'}) # swap 'v1' with 'v2'

        heat_map_df=pd.concat([rank_df,df])
        fo[y]=heat_map_df
        
        if show:
            fig=uc.chart_heat_map(heat_map_df,x_col='v1',y_col='v2', sort_by='mean', simmetric_sort=True, z_col='value',add_mean=True, transpose=True, color_continuous_scale='RdBu', format_labels = '%{z:.1f}', title=y, range_color=None, tickangle=-90)
            fig.show('browser')
            
        return fo

def extract_yearly_ww_variables(w_df, var_windows=[], ref_year = GV.CUR_YEAR, ref_year_start= dt(GV.CUR_YEAR,1,1), join='inner', drop_na=True, drop_how='any'):
    w_df = add_seas_year(w_df, ref_year, ref_year_start) # add the 'year' column
    w_df['seas_day'] = [seas_day(d, ref_year_start) for d in w_df.index]

    wws=[]
    
    for v_w in var_windows:    
        # Get only needed variables and 'year','seas_day'
        #    1) 'seas_day': to select the weather window
        #    2) 'year': to be able to group by crop year

        w_cols=['year','seas_day']
        w_cols.extend(v_w['variables'])
        w_df_sub = w_df[w_cols]
        
        for w in v_w['windows']:
            s = w['start']
            e = w['end']
            id_s = seas_day(date=s, ref_year_start=ref_year_start)
            id_e = seas_day(date=e, ref_year_start=ref_year_start)

            ww = w_df_sub[(w_df_sub['seas_day']>=id_s) & (w_df_sub['seas_day']<=id_e)]
            ww=ww.drop(columns=['seas_day'])
            ww.columns=list(map(lambda x:'year'if x=='year'else x+'_'+s.strftime("%b%d")+'-'+e.strftime("%b%d"),list(ww.columns)))
            ww = ww.groupby('year').mean()
            ww.index=ww.index.astype(int)
            wws.append(ww)  
                           
    w_df=w_df.drop(columns=['year','seas_day'])
    out_df = pd.concat(wws, sort=True, axis=1, join=join)        
    if drop_na: out_df.dropna(inplace=True, how=drop_how) # how : {'any', 'all'}
    return  out_df

def extract_yearly_ww_variables_old(w_df, var_windows=[], join='inner', drop_na=True, drop_how='any'):
    w_df['date']=w_df.index
    wws=[]
    
    for v_w in var_windows:    
        # Get only needed variables
        w_cols=['date']
        w_cols.extend(v_w['variables'])
        w_df_sub = w_df[w_cols]

        w_df_sub['month'] = pd.to_datetime(w_df_sub['date']).dt.month
        w_df_sub['day'] = pd.to_datetime(w_df_sub['date']).dt.day
        w_df_sub['year'] = pd.to_datetime(w_df_sub['date']).dt.year
        w_df_sub['time_id'] = 100*w_df_sub['month']+w_df_sub['day']

        # Adding:
        #    1) 'time_id': to select the weather window
        #    2) 'year': to be able to group by year

        w_cols.extend(['time_id','year'])
        w_df_sub = w_df_sub[w_cols]
        
        for w in v_w['windows']:
            s = w['start']; id_s = s.month * 100 + s.day
            e = w['end']; id_e = e.month * 100 + e.day

            ww = w_df_sub[(w_df_sub.time_id>=id_s) & (w_df_sub.time_id<=id_e)]                                
            ww.drop(columns=['time_id'], inplace=True)
            ww.columns = list(map(lambda x:'year'if x=='year'else x+'_'+s.strftime("%b%d")+'-'+e.strftime("%b%d"),list(ww.columns)))
            ww = ww.groupby('year').mean()
            ww.index=ww.index.astype(int)
            wws.append(ww)                                  

    out_df = pd.concat(wws, sort=True, axis=1, join=join)        
    if drop_na: out_df.dropna(inplace=True, how=drop_how) # how : {'any', 'all'}
    return  out_df



def print_folds(folds, years, X_df=None):
    '''
    Example (for the usual X_df with years as index):
        print_folds(folds, X_df, X_df.index.values)
    '''
    print('There are '+ str(len(folds)) +' folds:')
    if type(folds) == list:
        for f in folds:
            print(years[f[0]], "------>", years[f[1]])    
    else: 
        for train, test in folds.split(X_df): print(years[train], "------>", years[test])



def dm_scaler(df, col_to_rescale, new_min=-100.0, new_max=100.0):
    # I take the abs values because I want to have a summetric range (so that the signs will remain the same)
    old_max=abs(df[col_to_rescale].max())
    old_min=abs(df[col_to_rescale].min())

    old_max = max(old_max, old_min)
    old_min = -old_max

    to_rescale = df[col_to_rescale]
    rescaled = ((new_max - new_min) / (old_max - old_min)) * (to_rescale - old_min) + new_min
    return rescaled

def run_multiple_models(df, y_col: str, x_cols_list=[], extract_only='rsquared', parallel=None, max_workers=None):
    """
    'x_cols_list' (list of list):
        -   1 list for each model
        -   1 list of 'x_cols' (all the explanatory variables)


    the below [:] is needed because in python the lists are always passed by reference
    for a great explanation ask chatgpt the below:
            - how can I pass a list by value in python?        
    """
    fo={}

    if parallel is None:
        for x_cols in x_cols_list:            
            key = '|'.join(x_cols)
            fo[key] = Fit_Model(df, y_col, x_cols[:], None, extract_only)

    elif parallel=='thread':
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            results={}
            for x_cols in x_cols_list:
                key = '|'.join(x_cols)             
                results[key] = executor.submit(Fit_Model, df, y_col, x_cols[:], None, extract_only)
        
        for key, res in results.items():
            fo[key]=res.result()

    elif parallel=='process':
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            results={}
            for x_cols in x_cols_list:
                key = '|'.join(x_cols)             
                results[key] = executor.submit(Fit_Model, df, y_col, x_cols[:], None, extract_only)
        
        for key, res in results.items():
            fo[key]=res.result()

    return fo