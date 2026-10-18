"""Daily warning-sign measures from ERA5 (00 and 12 UTC, 1 deg) for every NE-monsoon day 2000-2025, plus TN SMART outcomes.
Writes days_features.json: {time: {feature: value}} and outcomes.json: {file_date: {region: {...}}}."""
import json, os, sys, glob, datetime as dt, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import unpack, ST, HIST
HERE = os.path.dirname(os.path.abspath(__file__)); DD = os.path.join(HERE, 'days')
REG = {   # region: (districts, offshore box la0, la1, lo0, lo1, coast point)
    'north': (['Chennai', 'Tiruvallur', 'Chengalpattu', 'Kancheepuram'], (11.5, 14.5, 80.5, 83.5), (13.0, 80.3)),
    'delta': (['Villupuram', 'Cuddalore', 'Mayiladuthurai', 'Nagapattinam', 'Thiruvarur', 'Thanjavur', 'Kallakurichi'], (9.5, 12.5, 80.0, 83.0), (11.0, 79.8)),
    'south': (['Ramanathapuram', 'Thoothukudi', 'Tirunelveli', 'Tenkasi', 'Kanniyakumari'], (6.5, 9.5, 78.0, 81.5), (8.8, 78.1)),
}
FIELDS = ['tcwv', 'u925', 'v925', 'u850', 'v850', 'u700', 'v700', 'u500', 'v500', 'u200', 'v200', 'z500', 'vo850', 'd850', 'd200', 'w500', 'msl', 'sst', 'cape', 'q700', 't700', 'ttr']
def load(y):
    Z = np.load(os.path.join(DD, f'days_{y}.npz')); lat = Z['lat'].astype(float); lon = Z['lon'].astype(float)
    times = [dt.datetime.strptime(str(t), '%Y%m%d%H') for t in Z['times']]
    return lat, lon, times, {k: unpack(Z, k) for k in FIELDS if k in Z.files}
print('loading', flush=True)
DATA = {y: load(y) for y in range(2000, 2026)}
lat, lon = DATA[2000][0], DATA[2000][1]
# climatology by (day of season, hour), smoothed +-7 days
def key(t): return (t.month, t.day, t.hour)
CL = {}
for k in FIELDS:
    acc = {}
    for y, (_, _, times, F) in DATA.items():
        for i, t in enumerate(times):
            if (t.month, t.day) == (2, 29): continue
            acc.setdefault(key(t), []).append(F[k][i])
    keys = sorted(acc, key=lambda x: (x[0] if x[0] >= 9 else x[0] + 12, x[1], x[2]))
    M = np.array([np.nanmean(acc[q], 0) for q in keys])
    # smooth along the season for each hour separately
    out = {}
    for h in (0, 12):
        idx = [i for i, q in enumerate(keys) if q[2] == h]; A = M[idx]
        S = np.array([np.nanmean(A[max(0, i - 7):i + 8], 0) for i in range(len(idx))])
        for j, i in enumerate(idx): out[keys[i]] = S[j]
    CL[k] = out
print('climatology done', flush=True)
def box(a, b):
    la0, la1, lo0, lo1 = b; m = ((lat >= la0) & (lat <= la1))[:, None] & ((lon >= lo0) & (lon <= lo1))[None, :]; return float(np.nanmean(a[m]))
LA, LO = np.meshgrid(lat, lon, indexing='ij')
def feats(F, i, t):
    A = lambda k: F[k][i] - CL[k][key(t)] if key(t) in CL[k] else F[k][i] * np.nan
    r = {}
    swb = (8, 14, 81, 86)
    r['u850_swbay'] = box(F['u850'][i], swb); r['u850_swbay_anom'] = box(A('u850'), swb)
    r['sst_anom_swbay'] = box(A('sst'), swb)
    r['steer_mid'] = box(np.hypot((F['u700'][i] + F['u500'][i]) / 2, (F['v700'][i] + F['v500'][i]) / 2), (8, 14, 78, 86))
    r['u200_south'] = box(F['u200'][i], (8, 12, 76, 82))
    um = np.nanmean(F['u200'][i][:, (lon >= 76) & (lon <= 86)], 1); e = None
    for j in np.where((lat >= 0) & (lat <= 35))[0][::-1]:
        if um[j] > 0: e = float(lat[j])
        else: break
    r['westerly_edge200'] = e
    za = A('z500'); m = ((LA >= 25) & (LA <= 35) & (LO >= 60) & (LO <= 85)); r['wd_anom'] = float(np.nanmin(za[m])); r['wd_lon'] = float(LO[m][np.nanargmin(za[m])])
    m2 = ((LA >= 15) & (LA <= 25) & (LO >= 70) & (LO <= 90)); r['trough_south'] = float(np.nanmin(za[m2]))
    r['jet'] = float(np.nanmax(np.hypot(F['u200'][i], F['v200'][i])[(LA >= 20) & (LA <= 40)]))
    sw = (LA >= 3) & (LA <= 17) & (LO >= 77) & (LO <= 92); vo = F['vo850'][i]
    j = np.nanargmax(np.where(sw, vo, -np.inf)); r['vo_max'] = float(vo.ravel()[j]); r['vo_lat'] = float(LA.ravel()[j]); r['vo_lon'] = float(LO.ravel()[j])
    r['msl_anom_min'] = float(np.nanmin(A('msl')[sw]))
    es = 6.112 * np.exp(17.67 * (F['t700'][i] - 273.15) / (F['t700'][i] - 29.65)); rh = 100 * F['q700'][i] / 1000 / (0.622 * es / (700 - 0.378 * es))
    for rg, (_, b, (cla, clo)) in REG.items():
        r[f'{rg}_pw'] = box(F['tcwv'][i], b); r[f'{rg}_pw_anom'] = box(A('tcwv'), b)
        r[f'{rg}_onshore925'] = -box(F['u925'][i], b) * 3.6; r[f'{rg}_wind850'] = box(np.hypot(F['u850'][i], F['v850'][i]), b) * 3.6
        lb = (cla - 1.5, cla + 1.5, clo - 1.5, clo + 1.5)
        r[f'{rg}_conv850'] = -box(F['d850'][i], lb); r[f'{rg}_div200'] = box(F['d200'][i], lb); r[f'{rg}_rise500'] = -box(F['w500'][i], lb)
        r[f'{rg}_rh700'] = box(rh, lb); r[f'{rg}_cape'] = box(F['cape'][i], b); r[f'{rg}_olr'] = box(F['ttr'][i], lb)
        d = np.hypot((LA - cla) * 110.6, (LO - clo) * 111.3 * np.cos(np.radians(cla))); near = sw & (d <= 600)
        r[f'{rg}_vo_near'] = float(np.nanmax(np.where(near, vo, -np.inf)))
        jj = np.nanargmax(np.where(sw, vo, -np.inf)); r[f'{rg}_vo_dist'] = float(d.ravel()[jj])
    return r
OUTF = {}
for y, (_, _, times, F) in DATA.items():
    for i, t in enumerate(times): OUTF[t.strftime('%Y%m%d%H')] = feats(F, i, t)
    print(y, flush=True)
json.dump(OUTF, open(os.path.join(HERE, 'days_features.json'), 'w'))
# outcomes from TN SMART files (24 h to 08:30 IST of the file date)
OC = {}
for f in sorted(glob.glob(HIST + '*.json')):
    d = json.load(open(f)); day = os.path.basename(f)[:10]; o = {}
    allv = [v for k, v in d.items() if v is not None and k in ST]
    o['tn'] = dict(max=max(allv) if allv else None, n=len(allv), n100=sum(v >= 100 for v in allv), n200=sum(v >= 200 for v in allv))
    for rg, (dists, _, _) in REG.items():
        v = [x for k, x in d.items() if x is not None and k in ST and ST[k]['district'] in dists]
        o[rg] = dict(max=max(v) if v else None, mean=float(np.mean(v)) if v else None, n=len(v), n100=sum(x >= 100 for x in v))
    OC[day] = o
json.dump(OC, open(os.path.join(HERE, 'outcomes.json'), 'w'))
print('done', len(OUTF), len(OC))
