"""18 Nov (A, subtropics): 40 ascent + 20 subsidence ERA5 137-level columns in 20-40N 50-110E (low ground); based on 17 Nov (convection column test): ERA5 columns on all 137 model levels where ERA5's own convective rain is strong, plus ERA5 cp, tp,
surface fluxes and surface state at the same hour - to feed our IFS convection code with ERA5's own state and compare rain.
Times: 2020-11-01T00 and 2020-11-11T00 (hour 1 accumulations). Points: 0.25-deg cells 20S-25N, 40-180E with cp(hour 1) >= 1 mm/h,
40 strongest per time (min spacing 3 deg), plus 20 random cells with 0.1-1 mm/h and 20 with cp = 0 (control)."""
import os, numpy as np, xarray as xr
FULL = 'gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3'
ML = 'gs://gcp-public-data-arco-era5/ar/model-level-1h-0p25deg.zarr-v1'
A = xr.open_zarr(FULL, storage_options={'token': 'anon'}, chunks=None)
B = xr.open_zarr(ML, storage_options={'token': 'anon'}, chunks=None)
print('ML vars', list(B.data_vars)[:60], 'dims', dict(B.sizes), flush=True)
la = A.latitude.values; lo = A.longitude.values; rng = np.random.default_rng(0); out = {}
SURF = ['convective_precipitation', 'total_precipitation', 'surface_sensible_heat_flux', 'surface_latent_heat_flux', 'surface_pressure',
        '2m_temperature', '2m_dewpoint_temperature', 'sea_surface_temperature', 'land_sea_mask', 'geopotential_at_surface',
        'boundary_layer_height', 'convective_available_potential_energy', 'skin_temperature', '10m_u_component_of_wind', '10m_v_component_of_wind']
MLV = [v for v in ('temperature', 'specific_humidity', 'u_component_of_wind', 'v_component_of_wind', 'vertical_velocity',
                   'specific_cloud_liquid_water_content', 'specific_cloud_ice_water_content', 'logarithm_of_surface_pressure') if v in B.data_vars]
print('using ML', MLV, flush=True)
for t0 in ('2020-11-01T00', '2020-11-11T00'):
    t1 = np.datetime64(t0) + np.timedelta64(1, 'h')
    w = A['vertical_velocity'].sel(time=np.datetime64(t0), level=850).values; spx = A['surface_pressure'].sel(time=np.datetime64(t0)).values
    cp = A['convective_precipitation'].sel(time=t1).values * 1000.0
    box = (la[:, None] >= 20) & (la[:, None] <= 40) & (lo[None] >= 50) & (lo[None] <= 110) & (spx > 90000.0)
    c = np.argwhere(box & (w <= 0)); pick = [tuple(c[j]) for j in rng.choice(len(c), size=min(40, len(c)), replace=False)]
    c = np.argwhere(box & (w > 0)); pick += [tuple(c[j]) for j in rng.choice(len(c), size=min(20, len(c)), replace=False)]
    Y = np.array([p[0] for p in pick]); X = np.array([p[1] for p in pick]); tag = t0[:10]
    out[f'{tag}_lat'], out[f'{tag}_lon'], out[f'{tag}_cp1'] = la[Y], lo[X], cp[Y, X]
    for v in SURF:
        if v in A.data_vars:
            f = A[v].sel(time=t1 if v in ('convective_precipitation', 'total_precipitation', 'surface_sensible_heat_flux', 'surface_latent_heat_flux') else np.datetime64(t0))
            out[f'{tag}_{v}'] = f.values[Y, X]
    for v in MLV:
        f = B[v].sel(time=np.datetime64(t0)).values                               # [level, lat, lon]
        out[f'{tag}_ml_{v}'] = f[..., Y, X] if f.ndim == 3 else f[Y, X]
    print(t0, 'columns', len(pick), 'cp1 strongest', np.round(cp[Y, X][:5], 2), flush=True)
if 'hybrid' in B.coords: out['hybrid'] = B['hybrid'].values
# L137 half-level coefficients (p = a + b ps): ECMWF table as distributed in EC-Earth's TM5 (const_ec_v__ml137.F90)
import re, urllib.request
try:
    src = urllib.request.urlopen('https://gogs.elic.ucl.ac.be/pbarriat/ecearth3/raw/3.3.1/sources/tm5mp/levels/ml137/const_ec_v__ml137.F90', timeout=60).read().decode()
    def arr(name):
        m = re.search(name + r'[^=\n]*=\s*\(/(.*?)/\)', src, re.S); print(name, 'match', bool(m), '' if m else repr(src[src.find(name):src.find(name) + 400]), flush=True)
        return np.array([float(x.replace('d', 'e').replace('D', 'e')) for x in re.findall(r'[-+]?\d+\.\d*(?:[eEdD][-+]?\d+)?', re.sub(r'!.*', '', m.group(1)))])
    a, b = arr('a_ec'), arr('b_ec'); print('L137 a/b', len(a), len(b), a[:3], a[-3:], b[-3:], flush=True)
    if len(a) == 138 and len(b) == 138: out['a_half'], out['b_half'] = a, b
except Exception as e: print('L137 table failed', e, flush=True)
# cross-check: the same columns on the 37 pressure levels
for t0 in ('2020-11-01T00', '2020-11-11T00'):
    tag = t0[:10]; la_, lo_ = out[f'{tag}_lat'], out[f'{tag}_lon']
    Y = np.abs(la[:, None] - la_[None]).argmin(0); X = np.abs(lo[:, None] - lo_[None]).argmin(0)
    for v in ('temperature', 'specific_humidity', 'geopotential', 'u_component_of_wind', 'v_component_of_wind', 'vertical_velocity'):
        out[f'{tag}_pl_{v}'] = A[v].sel(time=np.datetime64(t0)).values[:, Y, X]
out['pl_levels'] = A['level'].values
os.makedirs('/tmp/cyc_out', exist_ok=True); np.savez_compressed('/tmp/cyc_out/ml_columns_sub.npz', **out); print('saved', len(out))
