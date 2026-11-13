"""14 Nov: is the 13-level start data too dry/cold in the boundary layer? ERA5 (ARCO 37 levels) tropical-ocean means at
975/950/900/875 hPa vs log-p linear interpolation from the 13 WB2 levels (1000/925/850) that MEGAM starts from.
Also the test-parcel source: mean q and T at the levels MEGAM uses (sigma 0.971/0.951 ~ 980/960 hPa)."""
import math, numpy as np, xarray as xr
ARCO = 'gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3'
A = xr.open_zarr(ARCO, storage_options={'token': 'anon'}, chunks=None)
LV = [1000, 975, 950, 925, 900, 875, 850]
out = []
for t in ('2020-10-27T00', '2020-11-01T00', '2020-11-06T00'):
    sl = dict(time=t, latitude=slice(20, -20.01))
    lsm = A['land_sea_mask'].sel(**sl).values[::4, ::4]; sea = lsm < 0.1
    lat = A.latitude.sel(latitude=slice(20, -20.01)).values[::4]; w = np.cos(np.radians(lat))[:, None] * sea
    for v, s, nm in (('specific_humidity', 1000.0, 'q g/kg'), ('temperature', 1.0, 'T K')):
        m = {}
        for l in LV:
            x = A[v].sel(level=l, **sl).values[::4, ::4] * s; m[l] = float((x * w).sum() / w.sum())
        lp = lambda a, b, p: m[a] + (m[b] - m[a]) * math.log(p / a) / math.log(b / a)
        out.append(f"{t} {nm}: " + ' '.join(f"{l}:{m[l]:.2f}" for l in LV))
        for p, a, b in ((975, 1000, 925), (950, 1000, 925), (900, 925, 850), (875, 925, 850)):
            out.append(f"   {p} hPa true {m[p]:.2f}  13-level interp {lp(a, b, p):.2f}  error {lp(a, b, p) - m[p]:+.2f}")
    print('\n'.join(out[-10:]), flush=True)
import os; os.makedirs('data/cyclone/wx', exist_ok=True)
open('data/cyclone/wx/bl_levels.txt', 'w').write('\n'.join(out) + '\n')
