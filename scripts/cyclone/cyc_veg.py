"""ERA5 vegetation fields for the IFS canopy resistance (P5b land_rs fix, 22 Nov): types, covers and monthly LAI of high and
low vegetation from ARCO-ERA5 0.25 deg, put on the library grid (240 x 121, 1.5 deg, with poles). Covers and LAI: area mean of
the 0.25 deg points in each 1.5 deg box; types: the most common type in the box (by its cover). Runs on GitHub Actions
('veg fields'); output /tmp/cyc_out/veg_static.npz -> release era5-cases."""
import os, numpy as np, xarray as xr
ARCO = 'gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3'
LATS = np.linspace(-90, 90, 121); LONS = np.arange(240) * 1.5
A = xr.open_zarr(ARCO, storage_options={'token': 'anon'}, chunks=None)
NAMES = ['type_of_high_vegetation', 'type_of_low_vegetation', 'high_vegetation_cover', 'low_vegetation_cover',
         'leaf_area_index_high_vegetation', 'leaf_area_index_low_vegetation']
print('present', {n: n in A for n in NAMES}, flush=True)
la = A.latitude.values; lo = A.longitude.values
il = np.abs(la[:, None] - LATS[None]).argmin(0); io = np.abs(lo[:, None] - LONS[None]).argmin(0)
def box(v):                                      # mean of the 0.25 deg points within +-0.75 deg (6 x 6 box) of each target point
    from scipy.ndimage import uniform_filter
    return uniform_filter(v, size=[6, 6], mode=['nearest', 'wrap'])[il][:, io]
def mode_box(t, c):                              # type with the largest cover-weighted area in the box (0 = none)
    best = np.zeros((len(LATS), len(LONS)), np.float32); out = np.zeros_like(best)
    for k in np.unique(t[np.isfinite(t)]).astype(int):
        if k == 0: continue
        s = box(np.where(t == k, c, 0.0)); out = np.where(s > best, k, out); best = np.maximum(best, s)
    return out
T0 = np.datetime64('2020-01-15T00'); x = {n: A[n].sel(time=T0).values.astype(np.float32) for n in NAMES[:4]}
res = dict(lats=LATS, lons=LONS)
for typ, cov, nm in (('type_of_high_vegetation', 'high_vegetation_cover', 'tvh'), ('type_of_low_vegetation', 'low_vegetation_cover', 'tvl')):
    res[nm] = mode_box(np.round(x[typ]), x[cov])
res['cvh'] = box(x['high_vegetation_cover']); res['cvl'] = box(x['low_vegetation_cover'])
for n, nm in (('leaf_area_index_high_vegetation', 'laih'), ('leaf_area_index_low_vegetation', 'lail')):
    res[nm] = np.stack([box(A[n].sel(time=np.datetime64('2020-%02d-15T00' % m)).values.astype(np.float32)) for m in range(1, 13)])
for k, v in res.items(): print(k, np.shape(v), float(np.nanmin(v)), float(np.nanmax(v)), flush=True)
os.makedirs('/tmp/cyc_out', exist_ok=True); np.savez_compressed('/tmp/cyc_out/veg_static.npz', **res); print('saved')
