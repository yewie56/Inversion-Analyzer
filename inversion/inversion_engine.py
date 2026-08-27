# -*- coding: utf-8 -*-
from __future__ import annotations
import numpy as np
import pandas as pd
from .config import PRESSURE_LEVELS, LOCATION_ELEVATION_M

PROFILE_DISPLAY_HEIGHTS_M = (100.0, 200.0, 500.0)


def _profile_levels_from_row(row):
    """Return sorted (height_agl_m, temperature_C, label) tuples.

    Important: pressure-level geopotential heights are MSL.  Since v0.15.11
    AGL is calculated with the configured elevation of the active location
    instead of the old hard-coded 100 m assumption.
    """
    levels=[(2.0,row.get('temperature_2m',np.nan),'2m')]
    for p in PRESSURE_LEVELS:
        z=row.get(f'geopotential_height_{p}hPa',np.nan)
        t=row.get(f'temperature_{p}hPa',np.nan)
        if pd.notna(z) and pd.notna(t):
            agl=float(z)-float(LOCATION_ELEVATION_M)
            if -100.0 <= agl <= 2000.0:
                levels.append((agl,float(t),f'{p}hPa'))
    return sorted(
        [(float(z),float(t),n) for z,t,n in levels if pd.notna(z) and pd.notna(t)],
        key=lambda x:x[0]
    )


def _interp_temperature(levels, target_height_m):
    """Linear interpolation within measured/modelled vertical support only.

    No extrapolation is performed beyond the available profile range.
    """
    clean=[]
    for z,t,_ in levels:
        if np.isfinite(z) and np.isfinite(t):
            clean.append((float(z),float(t)))
    if not clean:
        return np.nan
    clean=sorted(clean)
    # Collapse duplicate heights by keeping the last value.
    unique={}
    for z,t in clean:
        unique[z]=t
    zs=np.array(sorted(unique.keys()),dtype=float)
    ts=np.array([unique[z] for z in zs],dtype=float)
    h=float(target_height_m)
    if h < zs.min() or h > zs.max():
        return np.nan
    return float(np.interp(h,zs,ts))


def _local_stratification_metrics(row):
    """Local stratification index using the full available vertical profile.

    v0.15.14:
    - real measured surface temperature is the preferred lower anchor
    - otherwise model 2-m temperature is used
    - all available pressure-level temperatures up to 600 m AGL are evaluated
    - no reduction to fixed 100/200/500 m support points for the INDEX
    - fixed 100/200/500 m curves remain only for visualization

    Each adjacent layer contributes only when temperature increases with height.
    The score is deliberately separate from the main inversion index and KIT index.

    Index:
        5 * (
            0.45 * gradient_score
          + 0.35 * deltaT_score
          + 0.20 * depth_score
        )

    v0.15.14 normalizations:
        gradient_score = max positive gradient / 0.5 K per 100 m
        deltaT_score   = sum positive deltaT / 2.0 K
        depth_score    = total positive-gradient depth / 300 m

    Returns diagnostic fields that allow later validation and plotting.
    """
    measured_surface = row.get('surface_temperature_obs', np.nan)
    surface = row.get('surface_temperature_for_profile', np.nan)

    if pd.isna(surface):
        surface = row.get('temperature_2m', np.nan)

    if pd.isna(surface):
        return {
            'local_stratification_index': np.nan,
            'local_max_gradient_K_per_100m': np.nan,
            'local_positive_deltaT_K': np.nan,
            'local_inversion_depth_m': np.nan,
            'local_surface_measured': False,
            'local_inverted_layer_count': 0,
            'local_strongest_layer': '',
            'local_profile_top_m': np.nan,
            'local_profile_point_count': 0,
        }

    # Ground anchor + all actual model pressure levels up to 600 m AGL.
    # Model 2 m is not added separately if a measured surface value exists,
    # to avoid creating an artificial 2 m -> first model-level layer.
    points = [(2.0, float(surface), 'Boden')]

    for pressure in PRESSURE_LEVELS:
        z = row.get(f'geopotential_height_{pressure}hPa', np.nan)
        t = row.get(f'temperature_{pressure}hPa', np.nan)
        if pd.isna(z) or pd.isna(t):
            continue
        agl = float(z) - float(LOCATION_ELEVATION_M)
        if 20.0 < agl <= 600.0:
            points.append((agl, float(t), f'{pressure}hPa'))

    # Sort and collapse near-duplicate heights.
    points = sorted(points, key=lambda x: x[0])
    collapsed = []
    for z, t, name in points:
        if collapsed and abs(z - collapsed[-1][0]) < 1.0:
            collapsed[-1] = (z, t, name)
        else:
            collapsed.append((z, t, name))
    points = collapsed

    if len(points) < 2:
        return {
            'local_stratification_index': np.nan,
            'local_max_gradient_K_per_100m': np.nan,
            'local_positive_deltaT_K': np.nan,
            'local_inversion_depth_m': np.nan,
            'local_surface_measured': bool(pd.notna(measured_surface)),
            'local_inverted_layer_count': 0,
            'local_strongest_layer': '',
            'local_profile_top_m': points[-1][0] if points else np.nan,
            'local_profile_point_count': len(points),
        }

    positive_layers = []
    for (z1, t1, n1), (z2, t2, n2) in zip(points[:-1], points[1:]):
        dz = z2 - z1
        if dz <= 10.0:
            continue

        dt = t2 - t1
        grad100 = dt / dz * 100.0

        if dt > 0.0:
            positive_layers.append({
                'z1': z1,
                'z2': z2,
                'dt': dt,
                'grad100': grad100,
                'depth': dz,
                'name': f'{n1}-{n2}',
            })

    if not positive_layers:
        return {
            'local_stratification_index': 0.0,
            'local_max_gradient_K_per_100m': 0.0,
            'local_positive_deltaT_K': 0.0,
            'local_inversion_depth_m': 0.0,
            'local_surface_measured': bool(pd.notna(measured_surface)),
            'local_inverted_layer_count': 0,
            'local_strongest_layer': 'keine',
            'local_profile_top_m': float(points[-1][0]),
            'local_profile_point_count': len(points),
        }

    max_grad = max(x['grad100'] for x in positive_layers)
    positive_dt = sum(x['dt'] for x in positive_layers)
    inv_depth = sum(x['depth'] for x in positive_layers)

    strongest = max(
        positive_layers,
        key=lambda x: (x['grad100'], x['dt'])
    )

    grad_score = np.clip(max_grad / 0.5, 0.0, 1.0)
    dt_score = np.clip(positive_dt / 2.0, 0.0, 1.0)
    depth_score = np.clip(inv_depth / 300.0, 0.0, 1.0)

    index = 5.0 * (
        0.45 * grad_score
        + 0.35 * dt_score
        + 0.20 * depth_score
    )

    return {
        'local_stratification_index': float(np.clip(index, 0.0, 5.0)),
        'local_max_gradient_K_per_100m': float(max_grad),
        'local_positive_deltaT_K': float(positive_dt),
        'local_inversion_depth_m': float(inv_depth),
        'local_surface_measured': bool(pd.notna(measured_surface)),
        'local_inverted_layer_count': int(len(positive_layers)),
        'local_strongest_layer': str(strongest['name']),
        'local_profile_top_m': float(points[-1][0]),
        'local_profile_point_count': int(len(points)),
    }


def add_local_stratification_index(result):
    """Append the local fixed-height stratification index to a result DataFrame."""
    if result is None or result.empty:
        return result
    metrics=[_local_stratification_metrics(row) for _,row in result.iterrows()]
    for key in metrics[0].keys():
        result[key]=[m[key] for m in metrics]
    return result


def calculate_profile_metrics(df):
    if df is None or df.empty:
        return None

    max_gradients=[]
    depths=[]
    positive_dts=[]
    low_heights=[]
    fixed_temps={int(h):[] for h in PROFILE_DISPLAY_HEIGHTS_M}

    for _,row in df.iterrows():
        levels=_profile_levels_from_row(row)

        for h in PROFILE_DISPLAY_HEIGHTS_M:
            fixed_temps[int(h)].append(_interp_temperature(levels,h))

        grads=[]
        inv_depth=0.0
        pos_dt=0.0
        for (z1,t1,_),(z2,t2,_) in zip(levels[:-1],levels[1:]):
            dz=z2-z1
            if dz<=20:
                continue
            dt=t2-t1
            g100=dt/dz*100.0
            grads.append(g100)
            if dt>0:
                inv_depth+=dz
                pos_dt+=dt

        if not grads:
            max_gradients.append(np.nan)
            depths.append(np.nan)
            positive_dts.append(np.nan)
            low_heights.append(np.nan)
        else:
            max_gradients.append(max(0.0,max(grads)))
            depths.append(inv_depth)
            positive_dts.append(pos_dt)
            low_heights.append(levels[1][0] if len(levels)>1 else np.nan)

    out=df.copy()
    out['max_inv_gradient_K_per_100m']=max_gradients
    out['inversion_depth_m']=depths
    out['positive_deltaT_K']=positive_dts
    out['lowest_profile_height_agl_m']=low_heights

    for h in PROFILE_DISPLAY_HEIGHTS_M:
        col=f'temperature_{int(h)}m_agl'
        out[col]=fixed_temps[int(h)]
        out[f'deltaT_{int(h)}m_model_K']=out[col]-out['temperature_2m']

    gs=np.clip(out['max_inv_gradient_K_per_100m']/1.5,0,1)
    ds=np.clip(out['positive_deltaT_K']/4.0,0,1)
    zs=np.clip(out['inversion_depth_m']/500.0,0,1)
    out['inversion_index']=5.0*(0.55*gs+0.30*ds+0.15*zs)
    return out


def merge_surface_observation(model_df,obs_df):
    if model_df is None or model_df.empty:
        return None

    result=model_df.copy().set_index('time')

    if obs_df is None or obs_df.empty:
        result['surface_temperature_obs']=np.nan
        result['dwd_temperature_obs']=np.nan
        result['surface_temperature_for_profile']=result['temperature_2m']
        result['surface_temperature_source']='model_2m'
        result['surface_temp_bias_K']=np.nan
        result['inversion_index_corrected']=result['inversion_index']
        result['surface_correction_used']=False
        for h in PROFILE_DISPLAY_HEIGHTS_M:
            col=f'temperature_{int(h)}m_agl'
            if col in result.columns:
                result[f'deltaT_{int(h)}m_surface_K']=result[col]-result['temperature_2m']
        result=add_local_stratification_index(result)
        return result.reset_index()

    obs=obs_df.copy().set_index('time').sort_index()
    hourly_obs=obs['temperature_obs'].resample('1h').mean()
    result['surface_temperature_obs']=hourly_obs.reindex(result.index)
    result['dwd_temperature_obs']=result['surface_temperature_obs']
    result['surface_temperature_for_profile']=result['surface_temperature_obs'].where(
        result['surface_temperature_obs'].notna(),
        result['temperature_2m']
    )
    result['surface_temperature_source']=np.where(
        result['surface_temperature_obs'].notna(),
        'measured',
        'model_2m'
    )
    result['surface_temp_bias_K']=result['surface_temperature_obs']-result['temperature_2m']

    for h in PROFILE_DISPLAY_HEIGHTS_M:
        col=f'temperature_{int(h)}m_agl'
        if col in result.columns:
            result[f'deltaT_{int(h)}m_surface_K']=(
                result[col]-result['surface_temperature_for_profile']
            )

    corrected=[]
    used=[]
    for _,row in result.iterrows():
        base=float(row['inversion_index'])
        obs_t=row.get('surface_temperature_obs',np.nan)
        if pd.isna(obs_t):
            corrected.append(base)
            used.append(False)
            continue

        cand=[]
        for p in PRESSURE_LEVELS:
            z=row.get(f'geopotential_height_{p}hPa',np.nan)
            t=row.get(f'temperature_{p}hPa',np.nan)
            if pd.notna(z) and pd.notna(t):
                agl=float(z)-float(LOCATION_ELEVATION_M)
                if 20<agl<600:
                    cand.append((agl,float(t)))

        if not cand:
            corrected.append(base)
            used.append(False)
            continue

        z,t_upper=min(cand,key=lambda x:x[0])
        obs_grad=(t_upper-float(obs_t))/(z-2.0)*100.0
        corr=np.clip(obs_grad/1.5,-0.5,1.0)
        corrected.append(np.clip(0.75*base+1.25*max(0.0,corr),0,5))
        used.append(True)

    result['inversion_index_corrected']=corrected
    result['surface_correction_used']=used
    result=add_local_stratification_index(result)
    return result.reset_index()


def inversion_label(v):
    if v<0.5:return 'keine / sehr gering'
    if v<1.5:return 'schwach'
    if v<2.5:return 'maessig'
    if v<3.5:return 'deutlich'
    if v<4.5:return 'stark'
    return 'sehr stark'
