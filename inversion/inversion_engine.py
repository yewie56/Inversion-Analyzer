# -*- coding: utf-8 -*-
from __future__ import annotations
import numpy as np
import pandas as pd
from .config import PRESSURE_LEVELS

def calculate_profile_metrics(df):
    if df is None or df.empty: return None
    max_gradients=[]; depths=[]; positive_dts=[]; low_heights=[]
    for _,row in df.iterrows():
        levels=[(2.0,row.get('temperature_2m',np.nan),'2m')]
        for p in PRESSURE_LEVELS:
            z=row.get(f'geopotential_height_{p}hPa',np.nan); t=row.get(f'temperature_{p}hPa',np.nan)
            if pd.notna(z) and pd.notna(t):
                agl=float(z)-100.0
                if -100<=agl<=1600: levels.append((agl,float(t),f'{p}hPa'))
        levels=sorted([(z,t,n) for z,t,n in levels if pd.notna(z) and pd.notna(t)],key=lambda x:x[0])
        grads=[]; inv_depth=0.0; pos_dt=0.0
        for (z1,t1,_),(z2,t2,_) in zip(levels[:-1],levels[1:]):
            dz=z2-z1
            if dz<=20: continue
            dt=t2-t1; g100=dt/dz*100.0; grads.append(g100)
            if dt>0: inv_depth+=dz; pos_dt+=dt
        if not grads:
            # Keine vertikale Vergleichsschicht: NICHT als "keine Inversion = 0"
            # interpretieren. Fehlende Daten bleiben NaN.
            max_gradients.append(np.nan)
            depths.append(np.nan)
            positive_dts.append(np.nan)
            low_heights.append(np.nan)
        else:
            max_gradients.append(max(0.0, max(grads)))
            depths.append(inv_depth)
            positive_dts.append(pos_dt)
            low_heights.append(levels[1][0] if len(levels)>1 else np.nan)
    out=df.copy(); out['max_inv_gradient_K_per_100m']=max_gradients; out['inversion_depth_m']=depths; out['positive_deltaT_K']=positive_dts; out['lowest_profile_height_agl_m']=low_heights
    gs=np.clip(out['max_inv_gradient_K_per_100m']/1.5,0,1); ds=np.clip(out['positive_deltaT_K']/4.0,0,1); zs=np.clip(out['inversion_depth_m']/500.0,0,1)
    out['inversion_index']=5.0*(0.55*gs+0.30*ds+0.15*zs)
    return out

def merge_surface_observation(model_df,obs_df):
    if model_df is None or model_df.empty: return None
    result=model_df.copy().set_index('time')
    if obs_df is None or obs_df.empty:
        result['dwd_temperature_obs']=np.nan; result['surface_temp_bias_K']=np.nan; result['inversion_index_corrected']=result['inversion_index']; result['surface_correction_used']=False
        return result.reset_index()
    obs=obs_df.copy().set_index('time').sort_index(); hourly_obs=obs['temperature_obs'].resample('1h').mean()
    result['dwd_temperature_obs']=hourly_obs.reindex(result.index); result['surface_temp_bias_K']=result['dwd_temperature_obs']-result['temperature_2m']
    corrected=[]; used=[]
    for _,row in result.iterrows():
        base=float(row['inversion_index']); obs_t=row.get('dwd_temperature_obs',np.nan)
        if pd.isna(obs_t): corrected.append(base); used.append(False); continue
        cand=[]
        for p in PRESSURE_LEVELS:
            z=row.get(f'geopotential_height_{p}hPa',np.nan); t=row.get(f'temperature_{p}hPa',np.nan)
            if pd.notna(z) and pd.notna(t):
                agl=float(z)-100.0
                if 20<agl<600: cand.append((agl,float(t)))
        if not cand: corrected.append(base); used.append(False); continue
        z,t_upper=min(cand,key=lambda x:x[0]); obs_grad=(t_upper-float(obs_t))/(z-2.0)*100.0; corr=np.clip(obs_grad/1.5,-0.5,1.0)
        corrected.append(np.clip(0.75*base+1.25*max(0.0,corr),0,5)); used.append(True)
    result['inversion_index_corrected']=corrected; result['surface_correction_used']=used
    return result.reset_index()

def inversion_label(v):
    if v<0.5:return 'keine / sehr gering'
    if v<1.5:return 'schwach'
    if v<2.5:return 'maessig'
    if v<3.5:return 'deutlich'
    if v<4.5:return 'stark'
    return 'sehr stark'
