"""Analyse events: python run.py name [name ...]  (or 'all').  Downloads the ERA5 file if needed, writes diag + figures."""
import json, os, sys, subprocess, datetime as dt, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
import figs, indices
REL = 'https://github.com/sridhar13294-rgb/tn-rainfall-map/releases/download/era5-cases/'
META = {r['name']: r for r in json.load(open(os.path.join(HERE, 'events_meta.json')))}
EXTRA = dict(chennai_2005_dec='Chennai, Dec 2005', delta_2005_nov='Delta, early Nov 2005', south_2000_dec='Shencottai–Ramanathapuram, Dec 2000', delta_2000_nov='Sivagangai–delta, Nov 2000',
             delta_2010_nov='Delta, Nov 2010', delta_2017_oct='Sirkazhi–delta, Oct 2017', delta_2021_nov='Delta–Chennai, Nov 2021', interior_2021_nov='Villupuram–interior, Nov 2021',
             thoothukudi_2021='Thoothukudi, Nov 2021', rameswaram_2024='Rameswaram, Nov 2024', chennai_2024_oct='Chennai, Oct 2024', delta_2021_jan='Delta, Jan 2021',
             avalanche_2019='Nilgiris (Avalanche), Aug 2019', ditwah_2025='Chennai–delta, Ditwah, Dec 2025')
for k, v in EXTRA.items(): META.setdefault(k, {})['label'] = v
LIST = [l.split('#')[0].split() for l in open(f'{REPO}/data/cases/era5/batch1.list')]
DAYS = {a: b for a, b in (x for x in LIST if len(x) == 2)}
DAYS['south_2000_dec'] = '2000-12-27'          # the southern rain fell on 27 Dec (TN SMART 28 Dec report); 28 Dec was Cuddalore
IMD = None
def imd_target(day_file):
    global IMD
    if IMD is None:
        Z = np.load(f'{REPO}/data/cases/era5/imd_tn_2000_2025.npz'); R = Z['rain'].astype(float) * float(Z['scale']); R[R < 0] = np.nan
        IMD = (R, Z['lat'], Z['lon'], [str(d) for d in Z['days']], np.load(os.path.join(HERE, 'imd_tnmask.npy')))
    R, la, lo, days, tn = IMD; k = days.index(day_file); x = np.where(tn, R[k], np.nan); mx = np.nanmax(x)
    m = x >= 0.5 * mx; w = np.where(m, x, 0); LA, LO = np.meshgrid(la, lo, indexing='ij')
    return dict(lat=float((w * LA).sum() / w.sum()), lon=float((w * LO).sum() / w.sum()), max=float(mx), top='IMD grid', dist='', n100=int(np.nansum(x >= 100)), n=int(tn.sum()))
def get(name):
    fn = os.path.join(DATA, name + '.npz')
    if not os.path.exists(fn):
        subprocess.run(['curl', '-sSL', '-o', fn, REL + name + '.npz'], check=True)
    if not os.path.exists(os.path.join(DATA, 'era5_clim_daily.npz')):
        subprocess.run(['curl', '-sSL', '-o', os.path.join(DATA, 'era5_clim_daily.npz'), REL + 'era5_clim_daily.npz'], check=True)
    return fn
def target_for(name, D):
    f = (D + dt.timedelta(days=1)).isoformat(); P = target(f)
    if P is None or P['n'] < 50: P = imd_target(f)
    return P
def summarise(E, rows, P):
    R = {}
    for n in (-7, -5, -3, -2, -1, 0):
        t = dt.datetime(E.day.year, E.day.month, E.day.day, 12) + dt.timedelta(days=n)
        rs = [r for r in rows if abs((dt.datetime.strptime(r['t'], '%Y-%m-%d %H') - t).total_seconds()) <= 12 * 3600]
        def mean(k):
            v = [r[k] for r in rs if r.get(k) is not None and np.isfinite(r[k])]; return round(float(np.mean(v)), 1) if v else None
        s = {k: mean(k) for k in ('pw', 'pw_anom', 'ivt', 'ivt_anom', 'cape', 'olr', 'rh700', 'w500', 'conv925', 'conv850', 'div200', 'shear_kmh', 'sst', 'sst_anom',
                                  'u850_swbay', 'u850_swbay_anom', 'u200_south', 'westerly_edge500', 'westerly_edge200', 'wd_lon', 'wd_depth', 'wd_anom_min', 'wd_anom_lon',
                                  'jet_max', 'jet_lat', 'trough_south_lat', 'vo850', 'vo700', 'vo500', 'msl_min', 'msl_deficit', 'wind10_max_kmh', 'steer_kmh', 'steer_mid_kmh',
                                  'steer_low_kmh', 'steer_up_kmh', 'move_kmh', 'dist_km', 'sys_lat', 'sys_lon')}
        s['n_sys'] = sum('sys_lat' in r for r in rs)
        d = E.day + dt.timedelta(days=n); s.update(indices.mjo(d)); s['oni'] = indices.enso(d); s['dmi'] = indices.iod(d)
        R[str(n)] = s
    return R
def analyse(name, figs_on=True):
    D = dt.date.fromisoformat(DAYS[name]); get(name)
    E = Event(name, D); C = ClimDaily(E.lat, E.lon); P = target_for(name, D)
    rows, path, k0, sp = diagnose(E, C, P)
    out = os.path.join(HERE, 'out', name); os.makedirs(out, exist_ok=True)
    first = min(path) if path else None
    gen = dict(t=E.times[first].strftime('%Y-%m-%d %H'), lat=path[first][0], lon=path[first][1]) if path else None
    S = dict(name=name, day=str(D), target=P, sea_point=sp, genesis_in_window=gen, track_start_is_window_start=(first == 0),
             anchor=dict(t=E.times[k0].strftime('%Y-%m-%d %H'), lat=path[k0][0], lon=path[k0][1], vo=path[k0][2]) if path else None,
             kind=kind_of_system(rows[k0]) if path else 'none', lags=summarise(E, rows, P))
    json.dump(dict(summary=S, rows=rows), open(os.path.join(out, 'diag.json'), 'w'), indent=1, default=float)
    if figs_on:
        lab = META.get(name, {}).get('label', name)
        figs.fig_track(E, rows, P, os.path.join(out, 'track.png'), lab)
        figs.fig_low(E, C, P, rows, os.path.join(out, 'low.png'), lab); figs.fig_up(E, C, P, rows, os.path.join(out, 'up.png'), lab)
        figs.fig_hov(E, C, P, os.path.join(out, 'hov.png'), lab)
    return S
if __name__ == '__main__':
    names = list(DAYS) if sys.argv[1:] == ['all'] else sys.argv[1:]
    for n in names:
        try:
            S = analyse(n, figs_on=os.environ.get('FIGS', '1') == '1'); L = S['lags']
            print(n, S['kind'], 'anchor', S['anchor'], '| D-3 pw', L['-3']['pw'], L['-3']['pw_anom'], '| D pw', L['0']['pw'], 'steer_mid', L['0']['steer_mid_kmh'], 'move', L['0']['move_kmh'], flush=True)
        except Exception as e:
            import traceback; traceback.print_exc(); print(n, 'FAILED', repr(e)[:300])
