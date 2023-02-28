# https://share.streamlit.io/

# https://share.streamlit.io/danielemarobin/monitor/main/Home.py

from datetime import datetime as dt

import numpy as np
import pandas as pd

import streamlit as st

import Corn_ARG_Yield_GA as ma

import GDrive as gd

import GLOBAL as GV

import Modeling as um
import SnD as us

import Charts as uc

st.set_page_config(page_title='ARG Corn Model',layout="wide",initial_sidebar_state="expanded")

# Delete all the items in Session state (to save memory)
for key in st.session_state.keys():
    del st.session_state[key]

# Analysis preferences
if True:    
    ref_year=2023
    file='Data/Models/ARG Corn Yield/GA_ARG_7'
    id=516

    # this should cover the 'yield development' window (so we can see the full evolution)
    ref_year_start=dt(ref_year-1,3,1)

    # this should cover the 'yield development' window (so we can see the full evolution)
    season_start=dt(2022,9,5)
    season_end=  dt(2023,1,30)

    sel_yields_calcs = ['trend', GV.WD_HIST, GV.WD_H_GFS, GV.WD_H_ECMWF, GV.WD_H_GFS_EN, GV.WD_H_ECMWF_EN]

# Preliminaries
if True:
    # Runs Info
    runs_df=gd.read_csv(GV.W_LAST_UPDATE_FILE)
    runs_df=runs_df.set_index('model_full')
    st.write('Runs used for the estimates')
    st.dataframe(runs_df[['Latest Available Run','Completed (%)','Completed','of']])
    st.markdown("---")

    yields={}
    pred_df={}
    progress_str_empty = st.empty()
    progress_empty = st.empty()    

# *************** Sidebar (Model User-Selected Settings) *******************
if True:
    st.sidebar.markdown("# Model Settings")
    full_analysis=st.sidebar.checkbox('Full Analysis', value=False)

# **************************** Calculation *********************************
if True:
    r = gd.deserialize(file)
    model = r['model'][id]

    # Get the data
    progress=0.0; progress_str_empty.write('Getting the data...'); progress_empty.progress(progress)

    scope = ma.Define_Scope()
    raw_data = ma.Get_Data_All_Parallel(scope)

    # Get the train_df (it is not used for the calculations. Only to show the previous years variables)
    train_df_instr=um.Build_DF_Instructions(WD_All='weighted', WD=GV.WD_HIST, ext_mode=GV.EXT_DICT, ref_year=ref_year, ref_year_start=ref_year_start)
    train_df = ma.Build_DF(raw_data=raw_data, instructions=train_df_instr,saved_m=model)
    train_df['year']=train_df.index

    # Yields
    progress_step=(1.0-progress)/len(sel_yields_calcs)
    for w in sel_yields_calcs:
        progress=progress+progress_step; progress_str_empty.write(w+' Yield...'); progress_empty.progress(progress)

        if w == 'trend':
            wd=GV.WD_HIST
            trend_yield_case = True       
        else:
            wd=w
            trend_yield_case = False

        pred_date_start, pred_date_end = um.prediction_interval(season_start, season_end, trend_yield_case, full_analysis)

        pred_instructions=um.Build_DF_Instructions(WD_All='weighted', WD=wd, ext_mode=GV.EXT_DICT, ref_year=ref_year, ref_year_start=ref_year_start)
        pred_df[w] = ma.Build_Pred_DF(raw_data=raw_data, instructions=pred_instructions, saved_m=model, date_start=pred_date_start, date_end=pred_date_end, trend_yield_case=trend_yield_case)

        yields[w] = model.predict(pred_df[w][model.params.index])

    progress_empty.empty(); progress_str_empty.empty()


# ****************************** Results ***********************************
# Metric
if True:
    metric_cols = st.columns(len(yields))

    for i, WD in enumerate(yields):
        metric_cols[i].metric(label='Yield - '+WD, value="{:.2f}".format(yields[WD][-1]))

# Chart
if full_analysis:    
    s='trend'; chart=uc.line_chart(x=yields[s].index, y=yields[s].values,name=s, color='black', mode='lines')

    s=GV.WD_H_GFS;uc.add_series(chart,x=yields[s].index, y=yields[s].values, name=s, color='blue')
    s=GV.WD_H_GFS_EN;uc.add_series(chart,x=yields[s].index, y=yields[s].values, name=s, color='yellow')
    s=GV.WD_H_ECMWF;uc.add_series(chart,x=yields[s].index, y=yields[s].values, name=s, color='red')
    s=GV.WD_H_ECMWF_EN;uc.add_series(chart,x=yields[s].index, y=yields[s].values, name=s, color='orange')
    s=GV.WD_HIST;uc.add_series(chart,x=yields[s].index, y=yields[s].values, name=s, color='green')

    st.plotly_chart(chart, use_container_width=True)

# Variables impact visualization & Coefficients
if True:    
    st.markdown('---')
    st.markdown('##### Selected Weather Windows')
    fig = uc.visualize_model_ww(model=model, ref_year_start=ref_year_start, train_df=train_df, fuse_windows=False)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown('---')
    st.markdown('##### Variables Impact')
    fig = uc.visualize_model_ww(model=model, ref_year_start=ref_year_start, train_df=train_df, fuse_windows=True)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown('---')
    st.markdown('##### Coefficients')
    st_model_coeff=pd.DataFrame(columns=model.params.index)
    st_model_coeff.loc[len(st_model_coeff)]=model.params.values
    st_model_coeff.index=['Model Coefficients']
    st.dataframe(st_model_coeff, use_container_width=True)    

# Prediction DataSets
if True:
    for i, WD in enumerate(pred_df):        
        first_cols=['Yield','year','const']
        sorted_cols= first_cols+list(set(pred_df[WD].columns)-set(first_cols))
        pred_df[WD]['Yield']=yields[WD] # Copying the yields in the df so that it is not an ugly NaN

        if WD != 'trend':
            st.markdown('---')

            st.markdown('##### Prediction DataSet - ' + WD)
            # st.dataframe(pred_df[WD][sorted_cols].drop(columns=['const']).sort_index(ascending=False), use_container_width=True)

            # simple Prediciton df. I take only the last row, because when calculating the full analysis it would have the whole season evolution
            yield_pred=pd.concat([pred_df[WD][-1:], pred_df['trend'][-1:]])

            # multiplying by coefficients to get the individual variables contribution
            yield_contribution=yield_pred.drop(columns=['Yield']) * model.params            
            yield_contribution['Yield']=yield_contribution.sum(axis=1)
            yield_contribution['const']=yield_contribution['const']+yield_contribution['year']
            
            yield_contribution.index=[WD + ' Yield - Components', 'trend Yield - Components']
            
            yield_contribution.loc['Difference']=yield_contribution.loc[WD + ' Yield - Components']- yield_contribution.loc['trend Yield - Components']

            yield_contribution=pd.concat([yield_pred, yield_contribution])
            yield_contribution=yield_contribution[sorted_cols].drop(columns=['year'])
            yield_contribution.index=[WD,'trend',WD + ' Yield - Components', 'trend Yield - Components','Difference']
            
            fig = uc.waterfall(yield_contribution)
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(yield_contribution,use_container_width=True)

# Actual vs Model Yield
if True:
    st.markdown('---')
    st.markdown('##### Actual vs Model')
    st.write(train_df)
    fig = uc.chart_actual_vs_model(model=model, train_df=train_df, y_col='Yield')
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("---")

# Training DataSet
if True:
    st.markdown('---')
    st.markdown('##### Training DataSet')
    st.dataframe(train_df.sort_index(ascending=False), use_container_width=True)
    st.markdown("---")

# Model Summary
if True:
    old_col, new_col = st.columns(2)
    with old_col:
        st.subheader('Model Summary:')
        st.write(model.summary())