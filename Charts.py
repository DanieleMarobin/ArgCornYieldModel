# Colors
# https://plotly.com/python-api-reference/generated/plotly.express.colors.html

# color_scale = px.colors.sequential.RdBu # https://plotly.com/python/builtin-colorscales/
# color_scale = px.colors.qualitative.Light24 # https://plotly.com/python/discrete-color/

from datetime import datetime as dt
from datetime import timedelta
import re
import inspect
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

import pandas as pd
import warnings # supress warnings
warnings.filterwarnings('ignore')

import statsmodels.api as sm
import Weather as uw
import GLOBAL as GV

def seas_chart(df, seas_cols=None, seas_only=False):
    '''
    'seas_cols':
        - to calculate the seasonal, include 'mean' in 'seas_cols'.
        - the 'mean' will be calculated on all the years passes in 'seas_cols'
    '''
    if seas_cols is None:
        cols=list(df.columns)
    else:
        cols=seas_cols[:]

    cols_for_mean = [c for c in cols if ((c != dt.today().year) & (c != 'mean'))]

    # The below is to avoid having a 'jumping' seasonal because certain series have less data
    # it works, because 'seas df' has been calculated like this:
    # df=df.interpolate(method='polynomial', order=0, limit_area='inside')
    if ('mean' in cols):
        df_mean=df[cols_for_mean].dropna()
        df_mean['mean']=df_mean[cols_for_mean].mean(skipna=True, axis=1)
        df=pd.concat([df,df_mean['mean']], axis=1)
        # cols=['mean']+cols

    x=df.index
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    cols_show=[]
    if seas_only:
        if 'mean' in cols:
            cols_show=['mean']
        if 2023 in cols:
            cols_show= cols_show +[2023]        
    else:
        cols_show=cols[:]

    for s in cols_show:
        if s=='mean':
            sec_y=True
        else:
            sec_y=False

        year_str = '   <b>'+str(s)+'</b>'
        y_str = '   %{y:.2f}'
        x_str = '   %{x|%b %d}'
        hovertemplate="<br>".join([year_str, y_str, x_str, "<extra></extra>"])

        fig.add_trace(go.Scatter(x=x, y=df[s], name=s, hovertemplate=hovertemplate),secondary_y=sec_y)

    fig.update_traces(line=dict(width=1))

    traces=[t['name'] for t in fig.data]

    if str(dt.today().year) in traces:
        id=traces.index(str(dt.today().year))
        fig.data[id].update(line=dict(width=3, color='red'))

    if str('mean') in traces:
        id=traces.index('mean')
        fig.data[id].update(line=dict(width=3, color='black'))

    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)

    fig.update_layout(height=750, showlegend=False, xaxis=dict(title=None), yaxis=dict(title=None))
    fig.update_layout(margin=dict(l=50, r=0, t=0, b=20))
    return fig

def plotly_colors_to_hex(px_colors=px.colors.sequential.Jet):
    hex=[]
    for c in px_colors:
        if '#' in c:
            hex.append(c)
        elif 'rgb' in c:
            hex.append('#%02x%02x%02x' % tuple(int(s) for s in c.replace('rgb(','').replace(')','').split(',')))
    return hex

def find_on_x_axis(date, chart):
    id = 100*date.month+date.day
    for x in chart.data[0]['x']:
        if 100*x.month + x.day==id:
            return x

def seas_day(date, ref_year_start= dt(GV.CUR_YEAR,1,1)):
    """
    'seas_day' is the X-axis of the seasonal plot:
            - it makes sure to include 29 Feb
            - it is very useful in creating weather windows
    """

    start_idx = 100 * ref_year_start.month + ref_year_start.day
    date_idx = 100 * date.month + date.day

    if (start_idx<300):
        if (date_idx>=start_idx):
            return dt(GV.LLY, date.month, date.day)
        else:
            return dt(GV.LLY+1, date.month, date.day)
    else:
        if (date_idx>=start_idx):
            return dt(GV.LLY-1, date.month, date.day)
        else:
            return dt(GV.LLY, date.month, date.day)

def var_windows_from_model(model, ref_year_start= dt(GV.CUR_YEAR,1,1)):
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

    for c in (x for x  in model.params.index if '-' in x):
        split=re.split('_|-',c)
        var = split[0]+'_'+split[1]
        
        if len(split)>1:
            d_start = dt.strptime(split[2]+str(year),'%b%d%Y')
            d_end = dt.strptime(split[3]+str(year),'%b%d%Y')

            start = uw.seas_day(d_start, ref_year_start)
            end = uw.seas_day(d_end, ref_year_start)
        
        var_windows.append({'variables':[var], 'windows':[{'start': start,'end':end}]})
    
    # I return 'np.array' to be able to use masks with it
    return np.array(var_windows)

def visualize_model_ww(model, ref_year_start, train_df=None, fuse_windows=True):
    '''
    fuse_windows = True:
        - it creates the aggregate of all the different windows of a certain variable:
        - if there are 3 variables:
            1) Precipitation in Jan-Feb
            2) Precipitation in Feb-Mar
            3) Precipitation in Mar-Apre
                -> it will create a single line called Precipitation that will sum all the coefficients in the overlapping parts
    '''

    if train_df is None:
        data=[1]*len(model.params)
        train_df_mean= pd.Series(data=data, index=model.params.index)
    else:
        train_df_mean=train_df.mean()
    fig = go.Figure()
    year = GV.LLY
    var_dict={}
    legend=[]

    for c in (x for x  in model.params.index if '-' in x):
        split=re.split('_|-',c)
        v = split[0]+'_'+split[1]
        coeff = model.params[c]           

        if len(split)>1:
            d_start = dt.strptime(split[2]+str(year),'%b%d%Y')
            d_end = dt.strptime(split[3]+str(year),'%b%d%Y')

            start = seas_day(d_start, ref_year_start)
            end = seas_day(d_end, ref_year_start)

            index = (np.arange(start, end + timedelta(days = 1), dtype='datetime64[D]'))
            data = np.full(len(index), coeff*train_df_mean[c])
            
            if v in var_dict:
                var_dict[v].append(pd.Series(data=data,index=index))
            else:
                var_dict[v]=[pd.Series(data=data,index=index)]
                
    for v, series_list in var_dict.items():
        if ('Temp' in v):
            color='orange'
        elif ('Sdd' in v):
            color='red'                        
        else:
            color='blue'

        name_str = '   <b>'+str(v)+'</b>'
        y_str = '   %{y:.2f}'
        x_str = '   %{x|%b %d}'
        hovertemplate="<br>".join([name_str, y_str, x_str, "<extra></extra>"])
    
        if fuse_windows:
            var_coeff=pd.concat(series_list,axis=1).sum(axis=1)
            var_coeff=var_coeff.resample('1D').asfreq()
            fig.add_trace(go.Scatter(x=var_coeff.index , y=var_coeff.values, name=v, mode='lines', line=dict(width=2,color=color, dash=None), marker=dict(size=8), showlegend=True, hovertemplate=hovertemplate))
        else:
            for sl in series_list:
                if v in legend:
                    showlegend=False
                else:
                    showlegend=True
                legend.append(v)

                if sl.values[0]<0.0:
                    dash='dash'
                else:
                    dash=None

                x=[sl.index[0],sl.index[-1]]
                y=[sl.values[0],sl.values[-1]]
                fig.add_trace(go.Scatter(x=x, y=y, name=v,mode='lines+markers', line=dict(width=2,color=color, dash=dash), marker=dict(size=8), showlegend=showlegend, hovertemplate=hovertemplate))

    # add today line
    fig.add_vline(x=seas_day(dt.today(), ref_year_start).timestamp() * 1000, line_dash="dash",line_width=1, annotation_text="Today", annotation_position="bottom")
    
    hovermode='x unified' # ['x', 'y', 'closest', 'x unified', 'y unified']
    fig.update_layout(height=750, legend=dict(orientation="h",yanchor="bottom",y=1.1,xanchor="left",x=0), hovermode=hovermode)
    fig.update_yaxes(zeroline=True, zerolinewidth=1, zerolinecolor='black')
    fig.update_xaxes(tickformat="%d %b")
    return fig


def add_ww_on_chart(chart, ww):
    """
    typically:
        ww = um.var_windows_from_cols(model.params.index, ref_year_start)
    """
    
    for w in ww:
        s= w['windows'][0]['start']
        e=w['windows'][0]['end']
        v=w['variables'][0] 
        

        if ('Temp' in v) or ('Sdd' in v):
            color='red'
        else:
            color='blue'

        position='top left'

        s=find_on_x_axis(s,chart)
        e=find_on_x_axis(e,chart)

        s_str=s.strftime("%Y-%m-%d")
        e_str=e.strftime("%Y-%m-%d")
        
        text= v+'   ('+s.strftime("%b%d")+' - '+e.strftime("%b%d")+')'

        chart.add_vrect(x0=s_str, x1=e_str,fillcolor=color, opacity=0.1,layer="below", line_width=0, annotation=dict(font_size=14,textangle=90,font_color=color), annotation_position=position, annotation_text=text)
    

def add_interval_on_chart(chart, intervals=[], interval_index = GV.CUR_YEAR, text=[], position=['top left'],color=['red']):
    for i,d in enumerate(intervals):
        s=find_on_x_axis(d['start'][interval_index],chart)
        e=find_on_x_axis(d['end'][interval_index],chart)
                
        s_str=s.strftime("%Y-%m-%d")
        e_str=e.strftime("%Y-%m-%d")
        
        c= text[i] +'   ('+s.strftime("%b%d")+' - '+e.strftime("%b%d")+')'

        chart.add_vrect(x0=s_str, x1=e_str,fillcolor=color[i], opacity=0.1,layer="below", line_width=0, annotation=dict(font_size=14,textangle=90,font_color=color[i]), annotation_position=position[i], annotation_text=c)    

class Seas_Weather_Chart():
    """
    w_df_all: \n
        it MUST have only 1 weather variable, otherwise the sub doesn't know what to chart
    """
    def __init__(self, w_df_all, ext_mode=GV.EXT_DICT, cumulative = False, chart_df_ext = GV.WD_H_GFS, ref_year=GV.CUR_YEAR, ref_year_start = dt(GV.CUR_YEAR,1,1), hovermode='x unified'):
        self.all_figs = {}
        self.w_df_all=w_df_all
        self.ext_mode=ext_mode
        self.cumulative=cumulative
        self.chart_df_ext=chart_df_ext
        self.ref_year=ref_year
        self.ref_year_start=ref_year_start
        self.hovermode=hovermode

        self.chart_all()

    def chart(self, w_df_all):
        """
        the "seasonalize" function is called many times because it needs to put align everything for charting on the Last Leap Year time line
        """               
        cur_year_proj = str(GV.CUR_YEAR)+GV.PROJ
        w_var=w_df_all[GV.WD_HIST].columns[0].split('_')[1]

        has_fore = True
        if (w_var== GV.WV_HUMI) or (w_var== GV.WV_VVI) or (w_var==GV.WV_TEMP_SURF): has_fore=False
        # print(''); print(GV.WD_HIST);
        df = uw.seasonalize(w_df_all[GV.WD_HIST], mode=self.ext_mode, ref_year=self.ref_year,ref_year_start=self.ref_year_start)
        
        if has_fore:   
            # print(''); print(GV.WD_GFS);
            pivot_gfs = uw.seasonalize(w_df_all[GV.WD_GFS],mode=self.ext_mode,ref_year=self.ref_year,ref_year_start=self.ref_year_start)
            fvi_fore_gfs = pivot_gfs.first_valid_index()
            # print(''); print(GV.WD_ECMWF);
            pivot_ecmwf = uw.seasonalize(w_df_all[GV.WD_ECMWF],mode=self.ext_mode, ref_year=self.ref_year,ref_year_start=self.ref_year_start)
            fvi_fore_ecmwf = pivot_ecmwf.first_valid_index()


            # print(''); print(GV.WD_H_GFS);
            pivot_h_gfs = uw.seasonalize(w_df_all[GV.WD_H_GFS],mode=self.ext_mode,ref_year=self.ref_year,ref_year_start=self.ref_year_start)
            # print(''); print(GV.WD_H_ECMWF);
            pivot_h_ecmwf = uw.seasonalize(w_df_all[GV.WD_H_ECMWF],mode=self.ext_mode,ref_year=self.ref_year,ref_year_start=self.ref_year_start)
                            
        # Choose here what forecast to use to create the EXTENDED chart
        df_ext = uw.extend_with_seasonal_df(w_df_all[self.chart_df_ext], var_mode_dict=self.ext_mode, ref_year=self.ref_year, ref_year_start=self.ref_year_start)

        # The below calculates the analog with current year already extended
        # Using the analog from 1/1 to 31/12 is not right.
        # So, in the below section 'Analog Charting', to chart understand which analog to use there is an if statement to choose between:
        #       - pivot_h_gfs
        #       - pivot_h_ecmwf
        # Calculating 'df_ext_pivot' is done because it is what it is actually charted, but it cannot be used for picking the Analog

        df_ext_pivot = uw.seasonalize(df_ext, mode=self.ext_mode, ref_year=self.ref_year, ref_year_start=self.ref_year_start)

        if self.cumulative:  
            df = uw.cumulate_seas(df, excluded_cols= ['Max','Min','Mean', cur_year_proj])
            df_ext_pivot = uw.cumulate_seas(df_ext_pivot,excluded_cols=['Max','Min','Mean'])
            pivot_h_gfs = uw.cumulate_seas(pivot_h_gfs,excluded_cols=['Max','Min','Mean'])
            pivot_h_ecmwf = uw.cumulate_seas(pivot_h_ecmwf,excluded_cols=['Max','Min','Mean'])

        
        # Colors
        # https://plotly.com/python-api-reference/generated/plotly.express.colors.html
        # color_scale = px.colors.sequential.RdBu # https://plotly.com/python/builtin-colorscales/
        color_scale = px.colors.qualitative.Light24 # https://plotly.com/python/discrete-color/
        # print(px.colors.named_colorscales())
        
        i_color=1

        fig = go.Figure()
        # Max - Min - Mean
        fig.add_trace(go.Scatter(x=df.index, y=df['Min'],fill=None,mode=None,line_color='lightgrey',name='Min',showlegend=False))
        fig.add_trace(go.Scatter(x=df.index, y=df['Max'],fill='tonexty',mode=None,line_color='lightgrey',name='Max',showlegend=False))
        fig.add_trace(go.Scatter(x=df.index, y=df['Mean'],mode='lines',line=dict(color='blue',width=1.5), name='Mean',legendrank=GV.CUR_YEAR+2, showlegend=True))
        

        # Actuals
        for y in df.columns:       
            if ((y!='Max') and (y!='Min') and (y!='Mean') and (y!= cur_year_proj) and (GV.ANALOG not in str(y))):
                # Make the last 3 years visible
                if y>=GV.CUR_YEAR-0:
                    visible=True
                else: 
                    visible='legendonly'        

                # Use Black for the current year                

                if y==GV.CUR_YEAR:
                    fig.add_trace(go.Scatter(x=df.index, y=df[y],mode='lines', legendrank=y, name=str(y),line=dict(color = 'black', width=2.5),visible=visible))
                else:
                    fig.add_trace(go.Scatter(x=df.index, y=df[y],mode='lines',legendrank=y, name=str(y),line=dict(color = color_scale[i_color], width=1.5),visible=visible))

                i_color+=1
                if i_color==len(color_scale):i_color=0
                    
        # Forecasts
        if has_fore:
            # GFS
            df_dummy=pivot_h_gfs[pivot_h_gfs.index>=fvi_fore_gfs]            
            fig.add_trace(go.Scatter(x=df_dummy.index,y=df_dummy[GV.CUR_YEAR],mode='lines+markers',line=dict(color='black',width=2,dash='dash'), name='GFS',legendrank=GV.CUR_YEAR+5, showlegend=True))
            
            # ECMWF
            df_dummy=pivot_h_ecmwf[pivot_h_ecmwf.index>=fvi_fore_ecmwf]            
            fig.add_trace(go.Scatter(x=df_dummy.index,y=df_dummy[GV.CUR_YEAR],mode='lines',line=dict(color='black',width=2,dash='dot'), name='ECMWF',legendrank=GV.CUR_YEAR+4, showlegend=True))
        
        
        # Analog Charting        
        if (self.chart_df_ext == GV.WD_H_GFS):
            df_dummy=pivot_h_gfs
        elif (self.chart_df_ext == GV.WD_H_ECMWF):
            df_dummy=pivot_h_ecmwf

        analog_cols = [c for c in df_dummy.columns if GV.ANALOG in str(c)]

        for c in analog_cols:
            fig.add_trace(go.Scatter(x=df_dummy.index, y=df_dummy[c],mode='lines', name=c,legendrank=GV.CUR_YEAR+3,line=dict(color='green',width=1),visible=True))
        
        # Projection Charting
        lvi_hist=df[GV.CUR_YEAR].last_valid_index()
        df_dummy=df_ext_pivot[df_ext_pivot.index>=lvi_hist]
        fig.add_trace(go.Scatter(x=df_dummy.index, y=df_dummy[GV.CUR_YEAR],mode='lines',line=dict(color='red',width=2,dash='dash'), name=cur_year_proj,legendrank=GV.CUR_YEAR+1, showlegend=True))

        #formatting
        fig.update_xaxes(tickformat="%d %b")
        fig.update_layout(autosize=True,font=dict(size=12),hovermode=self.hovermode,margin=dict(l=20, r=20, t=50, b=20))
        fig.update_layout(width=1400,height=787)
        return fig

    def chart_all(self):        
        for col in self.w_df_all[GV.WD_HIST].columns:
            w_df_all={}

            for wd, w_df in self.w_df_all.items():                
                w_df_all[wd]=w_df[[col]]            

            self.all_figs[col]=self.chart(w_df_all)


def chart_security_Ohlc(df):
    fig = go.Figure(data=[go.Ohlc(x=df.index, open=df['open_price'], high=df['high_price'], low=df['low_price'], close=df['close_price'])])
    fig.update_layout(xaxis_rangeslider_visible=False)
    return fig


# Line Chart
if True:
    def add_series(fig,x,y,name=None,mode='lines+markers',showlegend=True,line_width=1.0,color='black',marker_size=5,legendrank=0):
        fig.add_trace(go.Scatter(x=x, y=y,mode=mode, line=dict(width=line_width,color=color), marker=dict(size=marker_size), name=name, showlegend=showlegend, legendrank=legendrank))

    def line_chart(x,y,name=None,mode='lines+markers',showlegend=True,line_width=1.0,color='black',marker_size=5,legendrank=0,width=1400,height=600):
        fig = go.Figure()
        add_series(fig,x,y,name,mode=mode,showlegend=showlegend,line_width=line_width,color=color,marker_size=marker_size,legendrank=legendrank)
        update_layout(fig,marker_size,line_width,width,height)
        return fig  

# Bar Chart
if True:
    def add_bar(fig,x,y,name=None,color='black'):
        fig.add_trace(go.Bar(x=x,y=y,name=name,marker_color=color))

    def bar_chart(x,y,name=None,color='black',width=1400,height=600):
        fig = go.Figure()
        add_bar(fig,x,y,name=name,color=color)
        fig.update_layout(width=width,height=height)
        return fig  

# Histogram Chart
if True:
    def histogram_chart(df, col,bin_size=1,width=None,height=None):
        # width=1400
        # height=600

        histogram=px.histogram(df, x=col).update_xaxes(categoryorder='total descending',tickformat=",.0f")
        histogram.update_traces(xbins_size=bin_size)
        histogram.update_layout(width=width,height=height,showlegend=False,yaxis_title=None,xaxis_title=None)
        print('Sample size:',len(df[col]))
        return histogram


def chart_corr_matrix(X_df, threshold=1.0):
    corrMatrix = np.abs(X_df.corr())*100.0
    fig = px.imshow(corrMatrix,color_continuous_scale='RdBu_r')
    fig.update_traces(texttemplate="%{z:.1f}%")
    fig.update_layout(width=1400,height=787)
    return(fig)

def chart_heat_map(heat_map_df, x_col,y_col,z_col,range_color=None, add_mean=False, sort_by=None, abs=False, subtract=None, simmetric_sort=False, transpose=False, drop_cols=[], color_continuous_scale='RdBu', format_labels=None, title=None,tickangle=None, sorted_cols=[]):
    """
        heat_map_df: it must have 3 columns, to be able to have x,y, and values to put into the heat matrix

        'format_labels' example: '%{z:.1f}%'
    """
    # heat_map = heat_map_df.pivot_table(index=[y_col], columns=[x_col], values=[z_col], aggfunc=aggfunc)
    heat_map = heat_map_df.pivot(index=[y_col], columns=[x_col], values=[z_col])    
    heat_map.columns = heat_map.columns.droplevel(level=0)

    if add_mean:
        heat_map['mean']=heat_map.mean(axis=1)

    if sort_by is not None:
        if (('_abs' in sort_by) & (sort_by not in heat_map.columns)):
            sort_var=sort_by.split('_')[0]
            heat_map[sort_by]=heat_map[sort_var].abs()
            heat_map=heat_map.sort_values(by=sort_by, ascending=False)
            heat_map=heat_map.drop(columns=[sort_by])
        else:
            heat_map=heat_map.sort_values(by=sort_by, ascending=False)

    if simmetric_sort:
        sorted_cols = list(heat_map.index)
        
        if add_mean:
            sorted_cols.extend(['mean'])
        
        heat_map=heat_map[sorted_cols]

    if abs:
        heat_map=heat_map.abs()

    if subtract is not None:
        heat_map=heat_map.subtract(heat_map[subtract],axis=0)

    heat_map=heat_map.drop(columns=drop_cols)

    if transpose:
        heat_map=heat_map.T

    if len(sorted_cols)>0:
        heat_map=heat_map[sorted_cols]
    fig = px.imshow(heat_map, color_continuous_scale=color_continuous_scale, range_color=range_color,title=title, aspect='auto')

    if format_labels is not None:
        fig.update_traces(texttemplate=format_labels)

    fig.update_yaxes(dtick=1,tickangle=tickangle,automargin=True,title=None)
    fig.update_xaxes(dtick=1,tickangle=tickangle,automargin=True,title=None)

    return fig

def update_layout(fig,marker_size,line_width,width,height):
    fig.update_traces(marker=dict(size=marker_size),line=dict(width=line_width))
    fig.update_xaxes(tickformat="%d %b")
    fig.update_layout(autosize=True,font=dict(size=12),hovermode="x unified",margin=dict(l=20, r=20, t=50, b=20))
    fig.update_layout(width=width,height=height)

def get_plotly_colorscales():
    """
    color_scales = uc.get_plotly_colorscales()
    fig=px.scatter(df,x='x',y='y', color_continuous_scale=color_scales[chart_color_key], color_discrete_sequence=color_scales[chart_color_key])
    """    
    colorscale_dict={}
    colors_modules = ['carto', 'cmocean', 'cyclical','diverging', 'plotlyjs', 'qualitative', 'sequential']
    for color_module in colors_modules:
        colorscale_dict.update({name+'-'+color_module:body for name, body in inspect.getmembers(getattr(px.colors, color_module)) if (isinstance(body, list) & ('__all__' not in name))})
        
    return colorscale_dict

def print_plotly_colorscales_name():
    fo=list(get_plotly_colorscales().keys())
    fo.sort()
    for c in fo:
        print(c)

def plot_plotly_colorscales(step=0.1, colors_modules = ['carto', 'cmocean', 'cyclical','diverging', 'plotlyjs', 'qualitative', 'sequential']):   
    x=np.arange(1,-1.001,-step)
    y=np.arange(-1,1.001,step)

    matrix=(y.reshape(1, -1) + x.reshape(-1 ,1))

    color_scales=get_plotly_colorscales()
    for k, v in color_scales.items():
        if np.isin( k.split('-')[-1], colors_modules):
            try:
                fig=px.imshow(matrix,title=k,color_continuous_scale=v)
                fig.update_xaxes(visible=False)
                fig.update_yaxes(visible=False)
                # fig.update_coloraxes(showscale=False)
                fig.show('browser')
            except:
                print('Cannot use: '+ k)

    print('Done')


def scatter_matrix_chart(df, marker_color='blue', add_trendline=True, add_title=True, vertical_spacing=0.03, horizontal_spacing=0.01, marker_size=2, today_index=None, today_size=5, prediction_index=None, prediction_size=5, x_tickangle=90, y_tickangle=0):
    cols=list(df.columns)

    if add_title:
        titles=['title ' + str(i) for i in range(len(cols)*len(cols))]
    else:
        titles=[]

    fig = make_subplots(rows=len(cols), cols=len(cols), shared_xaxes=True, shared_yaxes=True, subplot_titles=titles, vertical_spacing=vertical_spacing, horizontal_spacing=horizontal_spacing)
    mode='markers'
    
    anno_count=0
    for ri, yc in enumerate(cols):
        for ci, xc in enumerate(cols):
            rr=ri+1
            cc=ci+1

            x=df[xc]
            y=df[yc]

            date_format = "%d %B %Y"
            y_str = 'Y: '+ yc +' %{y:.2f}'
            x_str = 'X: '+ xc +' %{x:.2f}'
            text=[]
            if xc=='date':
                text = [d.strftime(date_format) for d in [dt.fromordinal(i) for i in x]]
                x_str='X: %{text}'

            if yc=='date':
                text = [d.strftime(date_format) for d in [dt.fromordinal(i) for i in y]]
                y_str='Y: %{text}'

            hovertemplate="<br>".join([y_str, x_str, "<extra></extra>"])

            fig.add_trace(go.Scatter(x=x, y=y, mode=mode,marker=dict(size=marker_size,color=marker_color),hovertemplate=hovertemplate,text=text), row=rr, col=cc)
            if today_index is not None:
                add_today(fig,df,xc,yc,today_index,today_size, row=rr, col=cc)
                        
            fig.update_xaxes(row=rr, col=cc, showgrid=False,zeroline=False)
            if rr==len(cols):
                tick_pos=(x.max()+x.min())/2.0
                fig.update_xaxes(row=rr, col=cc, tickangle=x_tickangle,automargin=True,tickvals=[tick_pos],ticktext=[xc], showgrid=False,zeroline=False)

            fig.update_yaxes(row=rr, col=cc, showgrid=False,zeroline=False)
            if cc==1:
                tick_pos=(y.max()+y.min())/2.0
                fig.update_yaxes(row=rr, col=cc, tickangle=y_tickangle,automargin=True,tickvals=[tick_pos],ticktext=[yc],showgrid=False,zeroline=False)

            if ((add_trendline) | (add_title)):
                model = sm.OLS(y.values, sm.add_constant(x.values, has_constant='add'), missing="drop").fit()
                r_sq_str="Rsq "+str(round(100*model.rsquared,1))
                hovertemplate="<br>".join([r_sq_str, "<extra></extra>"])

                if add_trendline:
                    fig.add_trace(go.Scatter(x=x, y=model.predict(), mode='lines',hovertemplate=hovertemplate, line=dict(color='black', width=0.5)), row=rr, col=cc)
                    pred_str=''
                    print('prediction_index',prediction_index)
                    
                    if prediction_index is not None:
                        pred_str= 'Pred '+str(round(add_today(fig,df,xc,yc,prediction_index, size=prediction_size, color='black', symbol='x', name='Prediction', row=rr, col=cc,model=model),1))
                    
                if add_title:
                    fig.layout.annotations[anno_count].update(text=r_sq_str+ ' '+pred_str)
                    anno_count+=1
    
    fig.update_layout(showlegend=False)
    return fig

def sorted_scatter_chart(df, y_col, N_col_subplots=5, marker_color='blue', add_trendline=True, add_title=True, vertical_spacing=0.03, horizontal_spacing=0.01, marker_size=2, today_index=None, today_size=5, prediction_index=None, prediction_size=5, x_tickangle=90, y_tickangle=0):
    """
    N_col_subplots = 5
        - it means: 5 chart in each row
    """
    
    cols=list(df.columns)

    if add_title:
        titles=['title ' + str(i) for i in range(len(cols))]
    else:
        titles=[]

    cols=list(df.columns)
    cols_subsets=[]
    for i in range(0, len(cols), N_col_subplots):
        cols_subsets=cols_subsets+[cols[i:i+N_col_subplots]]

    fig = make_subplots(rows=len(cols_subsets), cols=len(cols_subsets[0]), shared_xaxes=False, shared_yaxes=True, subplot_titles=titles, vertical_spacing=vertical_spacing, horizontal_spacing=horizontal_spacing)

    mode='markers'
    
    anno_count=0
    for ri, cols in enumerate(cols_subsets):
        for ci, xc in enumerate(cols):
            rr=ri+1
            cc=ci+1

            x=df[xc]
            y=df[y_col]

            date_format = "%d %B %Y"
            y_str = 'Y: '+ y_col +' %{y:.2f}'
            x_str = 'X: '+ xc +' %{x:.2f}'
            text=[]
            if xc=='date':
                text = [d.strftime(date_format) for d in [dt.fromordinal(i) for i in x]]
                x_str='X: %{text}'

            if y_col=='date':
                text = [d.strftime(date_format) for d in [dt.fromordinal(i) for i in y]]
                y_str='Y: %{text}'

            hovertemplate="<br>".join([y_str, x_str, "<extra></extra>"])

            fig.add_trace(go.Scatter(x=x, y=y, mode=mode,marker=dict(size=marker_size,color=marker_color),hovertemplate=hovertemplate,text=text), row=rr, col=cc)
            if today_index is not None:
                add_today(fig,df,xc,y_col,today_index,today_size, row=rr, col=cc)
            
            # X-axis
            tick_pos=(x.max()+x.min())/2.0
            fig.update_xaxes(row=rr, col=cc, tickangle=x_tickangle,automargin=True,tickvals=[tick_pos],ticktext=[xc], showgrid=False,zeroline=False)

            # Y-axis
            tick_pos=(y.max()+y.min())/2.0
            fig.update_yaxes(row=rr, col=cc, tickangle=y_tickangle,automargin=True,tickvals=[tick_pos],ticktext=[y_col],showgrid=False,zeroline=False)

            if ((add_trendline) | (add_title)):
                model = sm.OLS(y.values, sm.add_constant(x.values, has_constant='add'), missing="drop").fit()
                r_sq_str="Rsq "+str(round(100*model.rsquared,1))
                hovertemplate="<br>".join([r_sq_str, "<extra></extra>"])

                if add_trendline:
                    fig.add_trace(go.Scatter(x=x, y=model.predict(), mode='lines',hovertemplate=hovertemplate, line=dict(color='black', width=0.5)), row=rr, col=cc)
                    pred_str=''
                    print('prediction_index',prediction_index)
                    
                    if prediction_index is not None:
                        pred_str= 'Pred '+str(round(add_today(fig,df,xc,y_col,prediction_index, size=prediction_size, color='black', symbol='x', name='Prediction', row=rr, col=cc,model=model),1))
                    
                if add_title:
                    fig.layout.annotations[anno_count].update(text=r_sq_str+ ' '+pred_str)
                    anno_count+=1
    
    fig.update_layout(showlegend=False)
    return fig

def add_today(fig, df, x_col, y_col, today_idx, size=10, color='red', symbol='star', name='Today', model=None, row=1, col=1):
    """
    if 'model' is not None, it will calculate the prediction
    markers:
        https://plotly.com/python/marker-style/
    """

    x = df.loc[today_idx][x_col]

    if model is None:    
        y = df.loc[today_idx][y_col]
    else:
        pred_df=sm.add_constant(df, has_constant='add').loc[today_idx][['const',x_col]]
        y=model.predict(pred_df)[0]
    
    y_str = 'Y: '+ y_col +' %{y:.2f}'
    x_str = 'X: '+ x_col +' %{x:.2f}'
    hovertemplate="<br>".join([name, y_str, x_str, "<extra></extra>"])
    fig.add_trace(go.Scatter(name=name,x=[x], y=[y], mode = 'markers', marker_symbol = symbol,marker_size = size, marker_color=color, hovertemplate=hovertemplate), row=row, col=col)
    return y

        
def waterfall(yield_contribution):
    df= yield_contribution.loc['Difference':'Difference']
    df=df.T

    # Remove the 0s (because they give no contrinution to the yield change)
    mask = abs(df['Difference'])>0
    df=df[mask]
    df=df.T

    sorted_cols=[c for c in df.columns if c!='Yield']
    sorted_cols.append('Yield')
    df=df[sorted_cols]

    measure=['relative']*(len(sorted_cols)-1)
    measure.append('total')

    y=list(df.values[0])
    text = ['+'+ str(round(v,3)) if v > 0 else '-'+ str(abs(round(v,3))) for v in y]
    text[-1]= 'Yield Difference vs Trend: <br>'+text[-1]

    if y[-1]<0:
        totals = {"marker":{"color":"darkred", "line":{"color":"red", "width":3}}}
    else:
        totals = {"marker":{"color":"darkgreen", "line":{"color":"green", "width":3}}}


    fig = go.Figure(go.Waterfall(
        orientation = 'v',
        measure = measure,
        x = sorted_cols,
        textposition = 'auto',
        text = text,
        y = y,
        totals=totals,
        # connector = {"line":{"color":"rgb(63, 63, 63)"}},
        ))
                
    return fig

def chart_actual_vs_model(model, df, y_col, x_col=None, plot_last_actual=False):
    '''
    plot_last_actual=False
        - sometimes the last row is the the prediction (so it is better not to show it as 'actual')
    '''
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[1,0.4])

    if x_col is None:
        x=df.index
    else:
        x=df[x_col]

    y_actu=df[y_col]
    y_pred= model.predict(df[model.params.index])
    y_diff=100*(y_pred-y_actu)/y_actu    

    if plot_last_actual:
        x_actu=x[:]
    else:
        mask= y_actu.index <(y_actu.index.max())
        x_actu=x[mask]
        y_actu=y_actu[mask]    
        
    fig.add_trace(go.Scatter(x=x_actu, y=y_actu,mode='lines+markers', line=dict(width=1,color='black'), marker=dict(size=5), name='Actual'), row=1, col=1)

    fig.add_trace(go.Scatter(x=x, y=y_pred,mode='lines+markers', line=dict(width=1,color='blue'), marker=dict(size=5), name='Model'), row=1, col=1)
    fig.add_trace(go.Bar(x=x, y=y_diff, name='Error (%)'), row=2, col=1)

    hovermode='x unified' # ['x', 'y', 'closest', 'x unified', 'y unified']

    fig.update_layout(height=750, hovermode=hovermode)

    return fig