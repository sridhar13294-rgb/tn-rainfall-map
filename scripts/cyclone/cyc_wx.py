"""General-weather exam data (runs on GitHub Actions). For starts every 5 days through 2020 at 00 UTC:
1. ERA5 truth at 00 UTC on every valid day (start + 1..10 days): 500 hPa height, 850 hPa temperature, sea-level pressure,
   2 m temperature, 24 h rain, 850/200 hPa wind -> /tmp/cyc_out/wx_truth_2020.npz (with the ERA5 1990-2019 climate of each day).
2. ECMWF's main run (IFS HRES, WeatherBench2 archive) for the same starts and days, scored with the same code
   (scripts/cyclone/mm/wxscore.py) -> data/cyclone/wx/hres_2020_scores.json.
Start fields for our model come from cyc_libm.py (LIBM_TIMES)."""
import os, sys, json, datetime as dt, numpy as np, xarray as xr
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, 'mm'))
import wxscore as WS
os.makedirs('data/cyclone/wx', exist_ok=True); LOG = open('data/cyclone/wx/wx_log.txt', 'w')
def log(*a): print(*a, flush=True); print(*a, file=LOG, flush=True)
G = 9.80665
STARTS = [dt.datetime(2020, 1, 1) + dt.timedelta(days=5 * i) for i in range(73)]
DAYS = sorted({s + dt.timedelta(days=d) for s in STARTS for d in range(1, 11)})
ERA = 'gs://weatherbench2/datasets/era5/1959-2023_01_10-6h-240x121_equiangular_with_poles_conservative.zarr'
CLIM = ['gs://weatherbench2/datasets/era5-hourly-climatology/1990-2019_6h_240x121_equiangular_with_poles_conservative.zarr',
        'gs://weatherbench2/datasets/era5-hourly-climatology/1990-2019_6h_1440x721.zarr']
HRES = ['gs://weatherbench2/datasets/hres/2016-2022-0012-240x121_equiangular_with_poles_conservative.zarr',
        'gs://weatherbench2/datasets/hres/2016-2022-0012-64x32_equiangular_conservative.zarr']
VARS = {'z500': ('geopotential', 500, 1 / G), 't850': ('temperature', 850, 1.0), 'mslp': ('mean_sea_level_pressure', None, 1.0),
        't2': ('2m_temperature', None, 1.0), 'rain24': ('total_precipitation_24hr', None, 1000.0),
        'u850': ('u_component_of_wind', 850, 1.0), 'v850': ('v_component_of_wind', 850, 1.0), 'u200': ('u_component_of_wind', 200, 1.0), 'v200': ('v_component_of_wind', 200, 1.0)}
def opn(paths):
    for p in paths:
        try: d = xr.open_zarr(p, storage_options={'token': 'anon'}, chunks=None); log('opened', p, list(d.data_vars)[:40]); return d
        except Exception as e: log('cannot open', p, repr(e)[:200])
    return None
def grab(ds, key, **sel):
    var, lev, sc = VARS[key]
    if var not in ds: return None
    x = ds[var].sel(**sel)
    if lev is not None: x = x.sel(level=lev)
    la = 'latitude' if 'latitude' in x.dims else 'lat'; lo = 'longitude' if 'longitude' in x.dims else 'lon'
    x = x.sortby(la).transpose(la, lo).values.astype(np.float64) * sc
    if x.shape != (121, 240):                                                                       # coarser archive -> regrid
        lat = np.linspace(-90, 90, x.shape[0]) if x.shape[0] % 2 else (np.arange(x.shape[0]) + 0.5) * 180 / x.shape[0] - 90
        x = WS.to_grid(x.T, np.arange(x.shape[1]) * 360 / x.shape[1], lat)
    return x
if os.environ.get('WX_HRES_ONLY') and os.path.exists('/tmp/cyc_out/wx_truth_2020.npz'):          # truth already built: only score ECMWF
    Zt = np.load('/tmp/cyc_out/wx_truth_2020.npz'); T = {k: Zt['o_' + k] for k in VARS}; CL = {k: Zt['c_' + k] for k in VARS}; DAYS_DONE = True
else: DAYS_DONE = False
if not DAYS_DONE: E = opn([ERA]); C = opn(CLIM); T = {k: np.full((len(DAYS), 121, 240), np.nan, np.float32) for k in VARS}; CL = {k: np.full((len(DAYS), 121, 240), np.nan, np.float32) for k in VARS}
for i, d in enumerate(DAYS if not DAYS_DONE else []):
    for k in VARS:
        try: T[k][i] = grab(E, k, time=np.datetime64(d))
        except Exception as e: log('era5', d, k, repr(e)[:150])
        if C is not None:
            try: CL[k][i] = grab(C, k, dayofyear=min(d.timetuple().tm_yday, 366), hour=0)
            except Exception as e:
                if i == 0: log('clim', k, repr(e)[:150])
    if i % 50 == 0: log('truth', i, d)
os.makedirs('/tmp/cyc_out', exist_ok=True)
if not DAYS_DONE: np.savez_compressed('/tmp/cyc_out/wx_truth_2020.npz', days=np.array([d.strftime('%Y-%m-%dT%H') for d in DAYS]),
                    **{'o_' + k: v for k, v in T.items()}, **{'c_' + k: v for k, v in CL.items()})
log('truth ready', os.path.getsize('/tmp/cyc_out/wx_truth_2020.npz'))
H = opn(HRES); res = []
if H is not None:
    di = {d: i for i, d in enumerate(DAYS)}
    for s in STARTS:
        row = dict(start=s.strftime('%Y-%m-%d'), days={})
        for ld in range(1, 11):
            v = s + dt.timedelta(days=ld); j = di[v]; sc = {}
            for k in VARS:
                try:
                    f = grab(H, k, time=np.datetime64(s, 'ns'), prediction_timedelta=np.timedelta64(ld * 24, 'h').astype('timedelta64[ns]'))
                    if f is not None: sc[k] = WS.scores(f, T[k][j], CL[k][j] if np.isfinite(CL[k][j]).any() else None)
                except Exception as e:
                    if ld == 1 and s == STARTS[0]: log('hres', k, repr(e)[:150])
            row['days'][ld] = sc
        res.append(row); log('hres', row['start'])
json.dump(dict(model='ECMWF IFS HRES (WeatherBench2)', starts=len(res), results=res), open('data/cyclone/wx/hres_2020_scores.json', 'w'))
log('done')
