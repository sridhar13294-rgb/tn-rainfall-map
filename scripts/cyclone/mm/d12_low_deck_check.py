"""D12 offline check (P1 mechanism): does F2's day-5 moisture/temperature error at 850 hPa create a low cloud deck through
the RH-based large-scale cloud (radcloud.clouds, the model's own formula and defaults)?
Method: ERA5 at the 6 verifying times (start + 5 days, starts 1-26 Jan 2020) + the model's tropics-mean day-5 T and q
biases (tn-evo-ctl / tn-evo-f2) at each pressure level -> large-scale cloud fraction c_ls per level, tropics |lat| < 20.
Only the RH (large-scale) cloud is evaluated - convective tower/anvil cloud needs the convection state and is left out.
python d12_low_deck_check.py EVO_DIR LIB_NPZ"""
import json, sys, numpy as np
sys.path.insert(0, __import__('os').path.dirname(__file__))
import radcloud
EVO, LIB = sys.argv[1], sys.argv[2]
Z = np.load(LIB); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
lev = Z['levs'].astype(float); lat = Z['lats']; trop = np.abs(lat) < 20; w = np.cos(np.radians(lat[trop]))
ver = ['2020-01-06T00', '2020-01-11T00', '2020-01-16T00', '2020-01-21T00', '2020-01-26T00', '2020-01-31T00']
bias = {r: tuple(np.mean([j['d5']['tropics'][v] for j in json.load(open(f'{EVO}/tn-evo-{r}/prof.json'))[r]], 0) for v in ('T', 'q'))
        for r in ('ctl', 'f2')}
res = {}
for name in ('ERA5', 'ctl', 'f2'):
    C = []
    for t in ver:
        k = TT.index(t); f = Z['f3'][k][:, :, trop]; ps = Z['f2'][k, V2.index('surface_pressure')][trop]
        T = f[V3.index('temperature')].astype(float); q = f[V3.index('specific_humidity')].astype(float)
        if name != 'ERA5':
            T = T + bias[name][0][:, None, None]; q = np.maximum(q + bias[name][1][:, None, None], 0.0)
        p = lev[:, None, None] * 100.0 * np.ones_like(T); ok = p < ps[None] - 500.0               # level above ground
        dp = np.full_like(T, 5000.0); sea = Z['f2'][k, V2.index('land_sea_mask')][trop] < 0.5
        cl = radcloud.clouds(T, q, p, dp, ps, sea)
        c = np.where(ok, cl['c_ls'], np.nan)
        C.append([np.nansum(np.nanmean(c[i], 1) * w) / np.sum(w * np.isfinite(np.nanmean(c[i], 1))) for i in range(len(lev))])
    res[name] = np.mean(C, 0)
print('large-scale (RH) cloud fraction, tropics |lat|<20, day 5, mean of 6 verifying times')
print('level  ' + '  '.join(f'{n:>6s}' for n in res))
for i, l in enumerate(lev):
    if l >= 500: print(f'{l:5.0f}  ' + '  '.join(f'{res[n][i]:6.3f}' for n in res))
json.dump({n: dict(zip(lev.tolist(), v.round(4).tolist())) for n, v in res.items()}, open('d12_result.json', 'w'), indent=1)
