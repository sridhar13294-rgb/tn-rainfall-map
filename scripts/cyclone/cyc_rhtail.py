"""18 Nov (A): ERA5 instantaneous RH at 850 hPa (from T, q; mm2/radcloud water saturation) for the screen starts +0/24/48 h:
area fraction with RH > 0.74 (the cloud scheme's critical RH at 850) at 0.25° and on 1.5° boxes (mean T, q), globe and 40S-40N.
GitHub 'rh tail' -> data/cyclone/wx/rh_tail.json"""
import json, os, numpy as np, xarray as xr
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
qs = lambda T, p: 0.622 * 611.2 * np.exp(17.67 * (T - 273.15) / (T - 29.65)) / np.maximum(p - 0.378 * 611.2 * np.exp(17.67 * (T - 273.15) / (T - 29.65)), 1.0)
la = A.latitude.values[:720]; W = np.cos(np.radians(la))[:, None] * np.ones((1, 1440)); Wc = W.reshape(120, 6, 240, 6).mean((1, 3))
lac = la.reshape(120, 6).mean(1); out = {}
for s in ('2020-10-07', '2020-11-01', '2020-11-26'):
    for h in (0, 24, 48):
        t = np.datetime64(s + 'T00') + np.timedelta64(h, 'h')
        T = A['temperature'].sel(time=t, level=850).values[:720]; q = A['specific_humidity'].sel(time=t, level=850).values[:720]
        sp = A['surface_pressure'].sel(time=t).values[:720]; ok = sp > 85000.0
        rh = q / qs(T, 85000.0); Tc = T.reshape(120, 6, 240, 6).mean((1, 3)); qc = q.reshape(120, 6, 240, 6).mean((1, 3)); okc = ok.reshape(120, 6, 240, 6).mean((1, 3)) > 0.5
        rhc = qc / qs(Tc, 85000.0); r = {}
        for nm, m, mc in (('globe', ok, okc), ('40S-40N', ok & (np.abs(la)[:, None] <= 40), okc & (np.abs(lac)[:, None] <= 40))):
            r[nm] = dict(mean_rh=round(float((rh * W * m).sum() / (W * m).sum()), 4), frac_gt074=round(float(((rh > 0.74) * W * m).sum() / (W * m).sum()), 4),
                         mean_rh_15=round(float((rhc * Wc * mc).sum() / (Wc * mc).sum()), 4), frac_gt074_15=round(float(((rhc > 0.74) * Wc * mc).sum() / (Wc * mc).sum()), 4))
        out[f'{s}_{h:02d}'] = r; print(s, h, r, flush=True)
os.makedirs('data/cyclone/wx', exist_ok=True); json.dump(out, open('data/cyclone/wx/rh_tail.json', 'w'), indent=1)
