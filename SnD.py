import numpy as np
import pandas as pd
from datetime import datetime as dt
import concurrent.futures
import requests

import GDrive as gd
import GLOBAL as GV

# Time Functions
if True:

    def add_time_columns(df, crop_year_start, cols_to_add=[]):
        """
        Example:
            time_cols = ['Time_CropYear_Int','Time_CropYear_Dt','Time_Quarter_Dt','Time_Quarter_Int','Time_Quarter_Pos']
            df=us.add_time_columns(df,crop_year_start,time_cols)
        """
        if len(cols_to_add)==0:
            cols_to_add=['Time_CropYear_Dt','Time_CropYear_Int','Time_CropYear_Str', 'Time_Quarter_Dt','Time_Quarter_Int','Time_Quarter_Pos']

        if 'Time_CropYear_Dt' in cols_to_add:df['Time_CropYear_Dt'] = [to_crop_year_dt(x, crop_year_start) for x in df.index]
        if 'Time_CropYear_Int' in cols_to_add: df['Time_CropYear_Int'] = [to_crop_year_int(x, crop_year_start) for x in df.index]
        if 'Time_CropYear_Str' in cols_to_add: df['Time_CropYear_Str'] = [to_crop_year_str(x, crop_year_start) for x in df.index]
        
        if 'Time_Quarter_Dt' in cols_to_add:df['Time_Quarter_Dt'] = [to_quarter_dt(x, crop_year_start) for x in df.index]
        if 'Time_Quarter_Int' in cols_to_add:df['Time_Quarter_Int'] = [to_quarter_int(x, crop_year_start) for x in df.index]
        if 'Time_Quarter_Pos' in cols_to_add:df['Time_Quarter_Pos'] = [to_position_in_quarter(x, crop_year_start) for x in df.index]
        return df

    def drop_time_columns(df):
        cols = [c for c in df.columns if 'Time_' in c]
        df = df.drop(columns=cols)
        return df

    def to_crop_year_int(input_date, crop_year_start):
        ym = input_date.year-1
        yp = input_date.year
        
        if input_date.month >= crop_year_start:
            return yp
        else:
            return ym 

    def to_crop_year_str(input_date, crop_year_start):
        year = to_crop_year_int(input_date, crop_year_start)
        return str(year) +'/'+str(year+1)

    def to_crop_year_dt(input_date, crop_year_start):
        return dt(to_crop_year_int(input_date, crop_year_start), crop_year_start, 1)
    
    def to_quarter_dt(input_date, crop_year_start):
        q = to_quarter_int(input_date, crop_year_start)
        date = dt(to_crop_year_int(input_date, crop_year_start), crop_year_start, 1)    
        return date + pd.DateOffset(months = (q-1)*3)

    def to_quarter_int(input_date, crop_year_start):
        date = input_date+pd.DateOffset(months=1-crop_year_start)
        return pd.Timestamp(date).quarter

    def to_position_in_quarter(input_date, crop_year_start):
        # 1 = first month of the quarter
        # 2 = second month of the quarter
        # 3 = third month of the quarter

        date = input_date+pd.DateOffset(months=-crop_year_start)
        return ((date.month) % 3)+1

# Other Functions
def quarters_dt_from_cropyears_dt(cropyears_dt=[]):
    quarters_starts=[]
    for y in cropyears_dt:
        quarters_starts = quarters_starts + [(y + pd.DateOffset(months=m)) for m in range(0,12,3)]
    return quarters_starts

def month_dt_from_quarters_dt(quarters_dt=[]):
    months=[]
    for q in quarters_dt:
        months = months + [(q + pd.DateOffset(months=m)) for m in range(0,3,1)]
    return months

def add_zeros_to_quarters(df, col):
    """
    This function is used when I need to add the zeros in the right places from Yearly to Quarterly (at the beginning of the Quarter month)

    So it is usually applied to a column like 'XXX_Y_Raw' or 'XXX_Y_Final'
    """

    # The assumption with the below line is that the first month that is populated is actually the 'crop_year_start' (that sadly might not be always true)
    fvi = df[col].first_valid_index()
    crop_year_start = fvi.month
    quarters_starts=[(dt(GV.CUR_YEAR,crop_year_start,1) + pd.DateOffset(months=m)).month for m in range(3,12,3)] # for crop years starting in September, this variable is going to be [12, 3, 6]

    mask=df.index.month.isin(quarters_starts)
    df.loc[mask,col]=0

    # The below mask selects all the months that are NOT quarter starts (so that I can set them to NaN)
    # and have numbers only on months [12, 3, 6] as I wanted for consistency with every other 'SnD' file
    # I also include in the mask all the cells that were before the 'fvi' (as I don't want to 'create' any data that wasn't there initially)
    quarters_starts.append(fvi.month)
    mask=(~df.index.month.isin(quarters_starts)) | (df.index<fvi)
    df.loc[mask,col]=np.NaN

    return df

def get_zeros_to_quarters_cols(df):
    """
    Basically trying to find the columns that have passed through the above function
    Gets all the columns that have a data structure like:

    value, 0, 0, 0,  value, 0, 0, 0,  value, 0, 0, 0,  value, 0, 0, 0,

    where 'value' is present at the start of the Crop Year
    """
    cols=[]

    for col in df.columns:
        mask_zeros = (df[col]==0)
        mask_value = (df[col]!=0) & (~df[col].isna())

        months_zero=np.unique(df.index[mask_zeros].month)
        months_value=np.unique(df.index[mask_value].month)

        if len(months_zero)==3 and len(months_value)==1:
            cols.append(col)

    return cols

def distribute_to_quarters(df, col):
    """
    The assumption in this function is that the first month that is populated is actually the 'crop_year_start' (that sadly might not be always true)
    So always check

    There are probably 2 ways in which this function is used:

    FIRST:
    distribute 'XXX_Y_Raw' to 'XXX_Q_Final'
        1) copy the 'XXX_Y_Raw' to 'XXX_Q_Final'
        2) run this function as:
                yearly_to_quarters(df, 'XXX_Q_Final')

    SECOND:
    distribute 'Prod_Q_Final'
        1) in this second case, there are zeros in every month that is not the start of the crop year: so it is necessary to remove them first
    """

    # Remove the 0s
    mask=(np.abs(df[col])<0.0000001)
    df.loc[mask,col]=np.NaN

    # The assumption with the below line is that the first month that is populated is actually the 'crop_year_start' (that sadly might not be always true)
    fvi = df[col].first_valid_index()
    crop_year_start = fvi.month
    quarters_starts=[(dt(GV.CUR_YEAR,crop_year_start,1) + pd.DateOffset(months=m)).month for m in range(0,12,3)] # for crop years starting in September, this variable is going to be [9, 12, 3, 6]
    df[col]=df[col].fillna(method='ffill')/4.0

    # The below mask selects all the months that are NOT quarter starts (so that I can set them to NaN)
    # and have numbers only on months [9, 12, 3, 6] as I wanted for consistency with every other 'SnD' file
    # I also include in the mask all the cells that were before the 'fvi' (as I don't want to 'create' any data that wasn't there initially)
    mask=(~df.index.month.isin(quarters_starts)) | (df.index<fvi)
    df.loc[mask,col]=np.NaN
    return df

def distribute_corn_seed(df, col):
    """
    Special treatment for Quarterly Seed (as they behave very differently from everything else)
    to see what I am talking about:
        - snd_m[['Seed_Y_Corn_Fg','Seed_Q_Corn_Fg']]

    If there is a Yearly value for the current year, it is going to be at the beginning of the crop year (sep for corn: 2021-09-01)
    The corresponding quartely 90% is allocated to (2022-03-01) and 10% is allocated to (2022-06-01)

    As it can be seen from the below link, corn never starts planting in March and never finishes after June    
    https://www.nass.usda.gov/Charts_and_Maps/Crop_Progress_&_Condition/index.php
        
    So I move the march value to Apr and then interpolate (to have half the seeds in Apr, half in May and then Jun)
    """

    for i, row in df.iterrows():
        # I only want to change March (so the below condition, if i.month == 3) 
        if i.month == 3:
            value = row[col] / 2.0

            # Check if all the cells where I want to distribute are NaN (so I don't overwrite data)
            # if one of them has some data: just return the 'df_target' as-is
            for m in range(1,3):
                ii=i+pd.DateOffset(months=m)
                if not pd.isna(df.loc[ii,col]):
                    return df
                    
            df.loc[i+pd.DateOffset(months=0),col]=0     # Mar
            df.loc[i+pd.DateOffset(months=1),col]=value # Apr
            df.loc[i+pd.DateOffset(months=2),col]=value # May

    return df

def dates_from_progress(df, sel_percentage=50.0, time_col='week_ending', value_col='Value'):
    """
    Question answered:
    "What day the crop was 50% planted for each year?"
    """

    fo_dict={'year':[],'date':[]}
    df[time_col]=pd.to_datetime(df[time_col])

    # Remove current year information, if I have not enough data to interpolate the current year
    if True:
        mask=(df[time_col]>dt(GV.CUR_YEAR,1,1))
        cur_year_df=df.loc[mask]

        if (len(cur_year_df)>0):
            if (cur_year_df[value_col].max() < sel_percentage):
                mask=(df[time_col]<dt(GV.CUR_YEAR,1,1))
                df=df.loc[mask]

    df=df.set_index(time_col, drop=False)
    df=df.asfreq('1D')

    df[value_col]=df[value_col].interpolate(limit_area='inside')

    # To avoid interpolation from previous year end of planting (100%) to next year beginning of planting (0%)
    mask=(df[value_col]>df[value_col].shift(fill_value=0))
    df=df.loc[mask]

    df['diff']=abs(df[value_col]-sel_percentage)

    min_diff = df.groupby(df.index.year).min()
    
    for y in min_diff.index:
        sel_df=df.loc[(df['diff']==min_diff.loc[y]['diff']) & (df.index.year==y)]

        fo_dict['year'].append(y)
        fo_dict['date'].append(sel_df.index[0])

    fo=pd.DataFrame(fo_dict)
    fo=fo.set_index('year')
    return fo

def monthly_harvested_from_progress(df,time_col='week_ending', value_col='Value', crop_year_start=9):
    df[time_col]=pd.to_datetime(df[time_col])
    df=df.set_index(time_col, drop=False)
    df=df.asfreq('1D')
    df[value_col]=df[value_col].interpolate(limit_area='inside')

    # The below mask puts to NaN all the 'inter-crop year' interpolations (it doesn't make any sense to interpolate from 95% in 2020 to 5 )
    mask=(df[value_col]<=df[value_col].shift(fill_value=0)) & (df[time_col].isna())
    # mask=(df[value_col]<=df[value_col].shift(fill_value=0))
    df.loc[mask,value_col]=np.nan

    # Extend the Dataframe (to extend the extrapolation to 100 for the last year (probably stuck at 90 something)
    df=df.reindex(pd.date_range(df.index.min(), df.index.max()+pd.DateOffset(years=1)))

    # If it finds a day that is NaN (no more data for that year), it checks the previous value
    # if the previous value is less than 100, it keeps on adding with the previous daily pace (not great, but it's ok)
    for i, r in df.iterrows():
        if np.isnan(df.loc[i,value_col]):
            prev=df.loc[i+pd.DateOffset(days=-1),value_col] # 1 day ago

            if (prev<99.999):
                delta= prev-df.loc[i+pd.DateOffset(days=-2),value_col]
                df.loc[i,value_col]=min(prev+delta,100)
    
    # I have to put NaN where the harvest starts before the beginning of the crop_year:
    # so I put NaN every row that is "harvested" in the 2 months before the 'crop_year_start'
    mask=(df.index.month >= crop_year_start-2) & (df.index.month <= crop_year_start-1)
    df.loc[mask,value_col]=np.NaN

    df['month_dt']=[dt(d.year,d.month,1) for d in df.index]
    df=df.groupby('month_dt')[[value_col]].max()

    return df

def extend_date_progress(date_progress_df: pd.DataFrame, year=GV.CUR_YEAR, day=dt.today(), col='date', manual_entry=None):
    """
    Same as the weather extention wwith seasonals, but with dates of crop progress

    Args:
        date_progress_df (pd.DataFrame): index = year, columns = 'date' (for every year: when was the crop 80% planted? or 50% silked etc)

        year (int): the year that I need to have a value for

        day (datetime): the simulation day. It simulates not knowing anything before this day (included). Useful to avoid the "49" late planting


    Explanation:
        if we have data already all is good:
            -> 'if year in fo.index: return fo'
        
        Otherwise we have to pick the later between:
            - the average of previous years
            - simulation day
        
        case 1) there is no value yet for 80% planted in on 'June 15th':
            - the average is going to be 15th May
            - but being on June 15th and not having a value yet, it means that the value cannot be May 15th (otherwise we would have had a value)
            -> so return 'June 15th' that is Max('June 15th', 'May 15th')
        
        case 2) there is no value yet for 80% planted in on Feb 17th:
            - the average is going to be 15th May
            -> so return  'May 15th' that is Max('Feb 17th', 'May 15th')    
    """

    fo = date_progress_df
    if year in fo.index: return fo
    
    fo_excl_YEAR=fo.loc[fo.index<year]
    fo_excl_YEAR=pd.Series([dt(year,d.month,d.day) for d in fo_excl_YEAR[col]])

    avg_day = np.mean(fo_excl_YEAR)
    avg_day = dt(avg_day.year,avg_day.month,avg_day.day)

    # Old approach
    if ((avg_day > day) or (avg_day > dt.today())):
        fo.loc[year] = avg_day
    else:
        fo.loc[year] = avg_day
    
    return fo

def progress_from_date(df: pd.DataFrame, progress_date, time_col='week_ending', value_col='Value'):
    """
    Args:
        df (pd.DataFrame): _description_
        sel_date (_type_): _description_
        time_col (str, optional): _description_
        value_col (str, optional): _description_

    Returns:
        df (pd.DataFrame): index = year, columns = 'Value' (for every year: % progress on 'sel_date')
    """
    fo_dict={'year':[],value_col:[]}

    df[time_col]=pd.to_datetime(df[time_col])
    df=df.set_index(time_col)
    df=df.asfreq('1D')
    df[value_col]=df[value_col].interpolate(limit_area='inside')


    dates = [dt(y,progress_date.month,progress_date.day) for y in df.index.year.unique()]
    df = df.loc[dates]
    
    fo_dict['year']=df.index.year
    fo_dict['Value']=df[value_col]
    fo=pd.DataFrame(fo_dict)
    fo=fo.set_index('year')

    return fo

def extend_progress(progress_df: pd.DataFrame, progress_date, year=GV.CUR_YEAR, day=dt.today()):
    """_summary_

    Args:
        progress_df (pd.DataFrame): index = year, columns = 'Value' (for every year: % progress on 'progress_date')
        progress_date (datetime): '15th May' would indicate that the 'Value' is % progess on the '15th May'
        year (int): year to extend (create the row 2022)
        day (datetime): the simulation day. It simulates not knowing anything before this day (included). Useful to avoid the "49" late planting
        col (str):

    Returns:
        Same as the input but extended by 1 row
        progress_df (pd.DataFrame): index = year, columns = 'Value' (for every year: % progress on 'progress_date')
    """
    # Ex: May 15th % planted

    # if we are before May 15th -> take the average of the previous years (overwriting the previous value)
    # if there is no value -> take the average of the previous years    

    fo = progress_df
    if ((day<progress_date) or not(year in fo.index)):
        fo_excl_YEAR=fo.loc[fo.index<year]
        fo.loc[year] = fo_excl_YEAR.mean()     

    return fo

# SnD general checks
def SnD_general_checks(df):
    """
    Inside the individual SnD files there are the checks specific to each SnD    
    Instead, this function is meant to check general features of all the SnDs:
            - like Yearly, Monthly, Quarterly structure
    """
     
    for col in df.columns:
        split = col.split('_')
        if len(split)>1:
            freq = split[-2]          
            mask=~df[col].isna()
            un=np.unique(df.index[mask].month)

            if (freq=='M') and (len(un)!=12):
                print('Issue with', col)
                return False
            elif (freq=='Q') and (len(un)!=4):
                print('Issue with', col)
                return False
            elif (freq=='Y') and (len(un)!=1):
                print('Issue with', col)
                return False
        
    return True

# Filling forwad missing info
def extrapolate_forward(df, from_col, to_col, threshold=1):
    """
    This is typically used when the 'current' or 'next' crop year Yearly data is available
    while the quarterly not yet.

    So the function checks the 'average distribution' over the missing quarters and distibutes the yearly data accordingly
    """
    conversion=from_col.split('_')[-2]+'->'+ to_col.split('_')[-2]

    if conversion=='Y->Q':
        group_col='Time_CropYear_Dt' # column to group and check the differences
        pc_col = 'Time_Quarter_Int' # column to calculate the % allocation
        last_full_offset = pd.DateOffset(years=1)
        periods_to_fill_function = quarters_dt_from_cropyears_dt

    elif conversion=='Q->M':
        group_col='Time_Quarter_Dt' # column to group and check the differences
        pc_col = 'Time_Quarter_Pos' # column to calculate the % allocation
        last_full_offset = pd.DateOffset(months=3)
        periods_to_fill_function = month_dt_from_quarters_dt

    cols=[group_col,from_col,to_col]

    # Group by year to check the yearly differences
    group_df=df[cols].groupby(by=group_col).sum()

    # Get the years with differences from 3 years ago till now
    diff = group_df[from_col]-group_df[to_col]
    mask = abs(diff)>threshold
    mask = (group_df.index.year > GV.CUR_YEAR-3) & mask

    # If there are no differences and everything is matching, there is nothing to extrapolate and I should just return the DataFrame
    if (mask.sum()==0):
        return df

    periods_dt_to_fill= group_df.index[mask]

    last_full_period=periods_dt_to_fill[0] - last_full_offset

    # Create the % (pc) allocation table based on the 5 year period from 'last_full_y-4' to 'last_full_y'
    mask=(df['Time_CropYear_Dt']>=last_full_period- pd.DateOffset(years=4)) & (df['Time_CropYear_Dt']<=last_full_period)
    group=df.loc[mask].groupby(pc_col)[[to_col]].sum()
    pc=group/group.sum()

    # Filling one by one the years that need filling
    for p in periods_dt_to_fill:
        period_starts=periods_to_fill_function([p])
        pc.index = period_starts
        period_df=df.loc[period_starts]

        # Of the above quarters, I need to find only the quarters that are empty
        mask=(period_df[to_col].isna())
        periods_to_fill = period_df[mask].index
        
        # I redistibute the % only between the quarters that need filling
        pc_to_fill=pc.loc[periods_to_fill]/pc.loc[periods_to_fill].sum()
        filled_df=pc_to_fill*diff[p]

        # Finally, I assign the 'filled_df' to the 'column to fill' of the DataFrame
        df.loc[periods_to_fill,to_col]=filled_df

    return df

def distribute_differences(df, from_col, to_col):
    """
    This is used when we have both Quarterly AND Monthly
    Generally the quarterly is correct (from_col) and I want to make sure that the 2 match
    So I basically calculate the % split of the monthly (to_col) data and use it to distribute the Quarterly
    """

    distribution=from_col.split('_')[-2]+'->'+ to_col.split('_')[-2]

    if distribution=='Y->Q':
        group_col='Time_CropYear_Dt' # column to group and check the differences

    elif distribution=='Q->M':
        group_col='Time_Quarter_Dt' # column to group and check the differences

    # Creating the monthly % splits within each quarter (long list of quarters)
    pc_split=df[to_col] / df.groupby(group_col)[to_col].transform('sum')

    # Distributing the Quarterly Imports to the different months within that Quarter        
    df[to_col]=pc_split * df.groupby(group_col)[from_col].transform('sum')

    return df

def fill_NaN_Monthly_columns(df):
    """
    The Monthly columns are not supposed to have NaN (differently from Quarterly and Yearly)
    I use this one when the provided Raw data have some holes (like for Sorghum, Oats or other minor crops)
    """
    for col in df.columns:
        split = col.split('_')
        if len(split)>1:
            freq = split[-2]
            if (freq=='M'):
                df[col]=df[col].fillna(method='ffill')
        
    return df

# Grouping
def dm_sum(arr):
    # This is needed because when using "groupby('quarter_dt').sum()"
    # the sum ignores the NaN, filling with zero every row from 1866
    # the issue is described here: https://stackoverflow.com/questions/18429491/pandas-groupby-columns-with-nan-missing-values
    #     
    if np.isnan(arr).all():
        return np.NaN
    else:
        return np.sum(arr)   

def snd_group_by(df, group_by_col = 'Time_Quarter_Dt', custom_sum=False, crop_year_start=9):
    """
        group_by_col =  'Time_Quarter_Dt'
        group_by_col = 'Time_CropYear_Str'
    """    
    # Adding the 'group_by_col' columns (in case it is not already present)
    if ~(group_by_col in df.columns):
        df=add_time_columns(df,crop_year_start,[group_by_col])

    # as it is necessary to use different functions for different columns:
    # I need to build a 'Function Map' with the dictionary func_map ={}
    func_map ={}
    # Time: 'first'
    for col in [c for c in df.columns if 'Time' in c]:
        func_map[col]='first'

    # Carry-In: 'first'
    for col in [c for c in df.columns if 'CarryIn' in c]:
        func_map[col]='first'

    # Carry-Out: 'last'
    for col in [c for c in df.columns if 'CarryOut' in c]:
        func_map[col]='last'

    # Prices: 'mean'
    for col in [c for c in df.columns if 'Price' in c]:
        func_map[col]=np.mean

    # Everything else:
    cols = list(set(df.columns)-set(func_map.keys()))
    if custom_sum:
        # This one doesn't 'Extrapolate' zeros
        for col in cols:
            func_map[col]=dm_sum
    else:
        # This one puts zeros everywhere
        for col in cols:
            func_map[col]=np.sum

    # Group Everything
    df = df.groupby(group_by_col).agg(func_map)

    # Recalculating the Total Supply (as it is the only one that needs recalculating)
    tot_supply_cols = [c for c in df.columns if 'TotSupply' in c]

    for col in tot_supply_cols:
        # Looking for the other components (Carry-In, Production, Import) to be able to recalculate it.
        # If I don't find it, then I will delete the column
        prod_col=col.replace('TotSupply','Prod')
        carry_in_col=col.replace('TotSupply','CarryIn')
        import_col=col.replace('TotSupply','Import')

        if (prod_col not in df.columns) or (carry_in_col not in df.columns) or (import_col not in df.columns):
            print('Dropped:',col)
            df=df.drop(columns=[col])
        else:
            df[col]=df[carry_in_col]+df[prod_col]+df[import_col]


    return df

def extract_Yearly_SnD(df, crop_year_start=9, group_by_col = 'Time_CropYear_Str', custom_sum=True):
    df=add_time_columns(df,crop_year_start,[group_by_col])
    df=snd_group_by(df,group_by_col=group_by_col, custom_sum=custom_sum)    
    return df


# SnD Items

# BRA
if True:
    def download_yearly_municipios_safrina_production(year):
        sidra_url = 'https://apisidra.ibge.gov.br/values/t/839/n6/all/v/214/p/'+str(year)+'/c81/114254'
        print('Downloading',year,'...')
        
        sidra_response = requests.get(sidra_url,verify=False)
        print(sidra_response)

        fo = sidra_response.json()
        del fo[0]
        print('Downloaded:',year)
        
        return fo
        
    def download_municipios_safrina_production(years_list):
        dfs=[]
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=40) as executor:
            year_prod={}
            for y in years_list:
                year_prod[y] = executor.submit(download_yearly_municipios_safrina_production, y)    
            
        for key,value in year_prod.items():
            dfs.append(pd.DataFrame(value.result()))

        fo = pd.concat(dfs)
        fo['D3C'] = fo['D3C'].astype(int)
        
        return fo
        
    def build_municipios_production_weights(prod_df, output_years_list=[], estimate_y_start=-1, estimate_y_end=-1):    
        # 'prod_df':
        #       - is the output of function: 'download_municipios_safrina_production'
        #       - will have data up to a certain year (let's say 2020)
        # 
        # Therefore 'output_years_list':
        #       - is needed because it is possible to provide estimates for data we don't have
        #
        # estimate_y_start=-1, estimate_y_end=-1 are needed to provide the above estimate:
        #       - is needed because it is possible to provide estimates for data we don't have    

        # The output Table has the following struc
        # rows:       years
        # columns:    region


        yearly_prod_list=[]

        if len(output_years_list)==0:
            output_years_list=list(set(prod_df['D3C']))
            output_years_list.sort()

        if estimate_y_start==-1:
            estimate_y_start=prod_df['D3C'].min()
        if estimate_y_end==-1:
            estimate_y_end=prod_df['D3C'].max()

        for y in output_years_list:       
            avg_prod_df=prod_df[((prod_df.D3C>=estimate_y_start) & (prod_df.D3C<=estimate_y_end))]

            avg_prod_df=avg_prod_df[['D1C','V']]
            mask=avg_prod_df.V.str.isnumeric()
            avg_prod_df.loc[~mask,'V']='0'
            avg_prod_df['V'] = avg_prod_df['V'].astype(float)
            avg_prod_df=avg_prod_df.groupby('D1C').mean()
            avg_prod_df['V']=avg_prod_df['V']/avg_prod_df['V'].sum()
            avg_prod_df=avg_prod_df.rename(columns={'V':y})
            yearly_prod_list.append(avg_prod_df)

        yearly_prod_percentages=pd.concat(yearly_prod_list,axis=1)
        yearly_prod_percentages=yearly_prod_percentages.T

        yearly_prod_percentages=yearly_prod_percentages.sort_index()
        return yearly_prod_percentages


        return fo.T

    def get_BRA_prod_weights(states=['MT','PR','GO'], product='MILHO', crop='1ª SAFRA', years=list(range(1800,2050)), conab_df=None):
        # rows:       years
        # columns:    region

        fo=get_BRA_conab_data(states=states, product=product, crop=crop, years=years, conab_df=conab_df)

        fo = pd.pivot_table(fo,values='Production',index='State',columns='year')

        fo=fo/fo.sum()

        return fo.T    

    def get_CONAB_df():
        url = 'https://portaldeinformacoes.conab.gov.br/downloads/arquivos/SerieHistoricaGraos.txt'

        rename_conab_cols= {
            'produtividade_mil_ha_mil_t'    : 'Yield',
            'producao_mil_t'                : 'Production',
            'area_plantada_mil_ha'          : 'Area',
            'uf'                            : 'State',
            'produto'                       : 'Product',
            'id_produto'                    : 'Product_id',
            'ano_agricola'                  : 'CropYear',
            'dsc_safra_previsao'            : 'Crop',
            }

        url = url.replace(" ", "%20")
        df = pd.read_csv( url,low_memory=False,sep=';')

        df=df.rename(columns=rename_conab_cols)

        df['Crop']=df['Crop'].str.strip()
        df['Product']=df['Product'].str.strip()
        df['year']=(df['CropYear'].str[:4]).astype('int')+1 # Incresing by 1 to match the Modeling Nomenclature
        df = df.set_index('year', drop=False)
        df.index.name=''
        return df

    def get_BRA_conab_data(states=['NATIONAL'], product='MILHO', crop='1ª SAFRA', years=list(range(1800,2050)), cols_subset=[], conab_df=None):
        if conab_df is None:
            df = get_CONAB_df()
        else:
            df = conab_df

        # Crop selection
        mask = (df['Product']==product) & (df['Crop']==crop)
        df=df[mask]

        # States selection
        if len(states)==0:
            df=df
        elif states[0]=='NATIONAL':        
            df=df.groupby(by='year').sum()
            df['Yield']=df['Production']/df['Area']
            df.index.name=''
            df['year']=df.index
        else:
            mask = np.isin(df['State'],states)
            df=df[mask]

        # Years selection
        mask = np.isin(df['year'],years)
        df=df[mask]

        # Column selection
        if len(cols_subset)>0: df = df[cols_subset]
        df=df.sort_values(by='year',ascending=True)
        
        return df

# ARG
if True:
    def get_MINAGRI_df(commodity='corn'):
        '''
        Download from here:  
        https://datosestimaciones.magyp.gob.ar/  
        https://datosestimaciones.magyp.gob.ar/reportes.php?reporte=Estimaciones  

        And save here (file name: ARG_Corn_Yield_data.csv):  
        Corn: E:\grains trading\Streamlit\Monitor\Data\Models\ARG Corn Yield\ARG_Corn_Yield_data.csv
        '''

        if commodity=='corn':
            file='Data/Models/ARG Corn Yield/ARG_Corn_Yield_data.csv'
        rename_minagri_cols= {
            'Rendimiento'                   : 'Yield',
            'Producción'                    : 'Production',
            'Sup. Sembrada'                 : 'PlantedArea',
            'Sup. Cosechada'                : 'HarvestedArea',
            'Provincia'                     : 'State',
            'Cultivo'                       : 'Product',
            'Campaña'                       : 'CropYear',
            }

        df = gd.read_csv(file,encoding='ISO 8859-1',sep=';')

        df=df.rename(columns=rename_minagri_cols)

        mask=(df['Yield']!='SD')
        df=df[mask]
        for c in ['Yield','Production','PlantedArea','HarvestedArea']:
            df[c]=df[c].astype(float)

        # df['Crop']=df['Crop'].str.strip()
        # df['Product']=df['Product'].str.strip()
        # df['year']=(df['CropYear'].str[:4]).astype('int')+1 # Incresing by 1 to match the Modeling Nomenclature
        # df = df.set_index('year', drop=False)
        # df.index.name=''
        return df
        
    def get_ARG_yields(commodity='corn', years=[]):
        '''
        at the moment it ouputs only the 'National' yearly values
        '''
        df=get_MINAGRI_df(commodity=commodity)
        df=df[['CropYear','Production','HarvestedArea']].groupby(by='CropYear').sum()
        df['Yield']=df['Production']/df['HarvestedArea']

        df.index=[int(y[0:4])+1 for y in df.index]

        if len(years)>0:
            mask = np.isin(df.index,years)
            df=df[mask]

        df=df.drop(columns=['Production','HarvestedArea'])

        return df
    
    def get_ARG_prod_weights(commodity='corn', years=[]):
        # rows:       years
        # columns:    region

        fo=get_MINAGRI_df(commodity=commodity)

        fo = pd.pivot_table(fo,values='Production',index='State',columns='CropYear')

        fo=fo/fo.sum()
        fo=fo.T

        fo.index=[int(y[0:4])+1 for y in fo.index]

        if len(years)>0:
            mask = np.isin(fo.index,years)
            fo=fo[mask]

        return fo