"""Every NE-monsoon day for testing warning signs, from ARCO-ERA5 (Google's public copy): 23 Sep - 31 Dec of each year,
00 and 12 UTC, averaged onto a 1 deg grid (0-40N, 50-110E).  Pressure levels 925/850/700/500/300/200: wind, height,
humidity, temperature, vertical motion; spin and divergence at 850/500/200 from the 0.25 deg winds; surface: pressure,
water vapour, sea temperature, CAPE, moisture flux, outgoing longwave.  Usage: python scripts/era5_arco_days.py YEAR [YEAR...]
Each year -> days_YEAR.npz on the era5-cases release; log in data/cases/era5/days_YEAR.json."""
import json, os, sys, time, datetime as dt, subprocess, concurrent.futures as cf
import numpy as np
from scipy import ndimage as nd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from era5_lib import OUT, pack, scale
import era5_arco as A
TMP = '/tmp/era5_out'; os.makedirs(TMP, exist_ok=True)
SLD = {k: v for k, v in A.SL.items() if k not in ('u10', 'v10')}
def coarse(a):                                            # 0.25 deg (rows 40N..0) -> 1 deg box means, rows 0..40N
    return nd.uniform_filter(a, size=(1,) * (a.ndim - 2) + (5, 5), mode='nearest')[..., ::-4, ::4]
def year(Y, par):
    LOG = []
    def log(*a):
        m = ' '.join(str(x) for x in a); print(Y, m, flush=True); LOG.append(m[:600])
        json.dump(dict(year=Y, log=LOG), open(os.path.join(OUT, f'days_{Y}.json'), 'w'), indent=1)
    d0, d1 = dt.date(Y, 9, 23), dt.date(Y, 12, 31); T = []
    d = d0
    while d <= d1:
        T += [dt.datetime(d.year, d.month, d.day, 0), dt.datetime(d.year, d.month, d.day, 12)]; d += dt.timedelta(days=1)
    t0 = time.time(); F = {}
    def work(t):
        out = {}
        R = {k: A.read(A.PL[k], t, A.LEV) for k in ('u', 'v', 'z', 'q', 't', 'w') if A.PL[k] in A.HAVE}
        for k, a in R.items():
            c = coarse(a)
            for i, p in enumerate(A.LEV): out[f'{k}{p}'] = scale(f'{k}{p}', c[i])
        for i, p in enumerate(A.LEV):
            if p in (850, 500, 200):
                vo, dv = A.vort_div(R['u'][i], R['v'][i]); out[f'vo{p}'] = scale('vo', coarse(vo)); out[f'd{p}'] = scale('d', coarse(dv))
        for k, var in SLD.items():
            if var in A.HAVE: out[k] = scale(k, coarse(A.read(var, t)))
        return t, out
    with cf.ThreadPoolExecutor(par) as ex:
        for n, (t, out) in enumerate(ex.map(work, T)):
            for k, a in out.items(): F.setdefault(k, {})[t] = a
            if n % 40 == 0: log('time', n, 'of', len(T), int(time.time() - t0), 's')
    lat = A.LAT[::-4]; lon = A.LON[::4]; res = dict(lat=lat, lon=lon, times=np.array([t.strftime('%Y%m%d%H') for t in T]))
    for k, d in F.items():
        q, off, s = pack(np.stack([d[t] for t in T])); res[k] = q; res[k + '__off'] = off; res[k + '__scale'] = s
    fn = os.path.join(TMP, f'days_{Y}.npz'); np.savez_compressed(fn, **res)
    log('SAVED', len(T), 'times', len(F), 'fields', os.path.getsize(fn) // 1000, 'kB in', int(time.time() - t0), 's')
    r = subprocess.run(['gh', 'release', 'upload', 'era5-cases', fn, '--clobber'], capture_output=True, text=True)
    if r.returncode == 0: os.remove(fn); log('uploaded')
    else: log('upload failed', r.stderr[:300])
if __name__ == '__main__':
    for Y in sys.argv[1:]:
        try: year(int(Y), int(os.environ.get('ARCO_PAR', '12')))
        except Exception as e: print(Y, 'FAILED', repr(e)[:500], flush=True)
