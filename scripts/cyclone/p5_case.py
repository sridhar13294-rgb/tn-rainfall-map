"""P5 case audit (5 Nov; peer review): model forecast maps vs ERA5 case file, EVERY 6 h, with the SAME storm removal
in both. Per time: storm centre (MSLP minimum near the previous centre, each data set its own), environmental steering
= mean wind over the 200-600 km ring around ITS centre (850, 500, 200 hPa and the 850-200 mean), ridge axis =
latitude of the z500 maximum along 80-95 E (10-30 N) after masking everything within 600 km of the storm, ridge
strength = that maximum minus the z500 mean at 10 N, trough axis = longitude of the z500 minimum along 25-35 N
(55-95 E), trough depth; then propagation = 6-h displacement of the ridge/trough axes (model minus ERA5).
python p5_case.py MODEL_MAPS_NPZ ERA5_CASE_NPZ INIT(YYYY-MM-DDTHH) OUT_JSON"""
import datetime as dt, json, sys
import numpy as np
MOD, ERA, INIT, OUT = sys.argv[1:5]; t0 = dt.datetime.strptime(INIT, '%Y-%m-%dT%H')
E = np.load(ERA); ev = lambda k: E[k].astype(float) * float(E[k + '__scale']) + float(E[k + '__off'])
ela, elo = E['lat'].astype(float), E['lon'].astype(float); et = [str(t) for t in E['times']]
A = np.load(MOD); mla = A['lat'].astype(float); mlo = A['lon'].astype(float); o = np.argsort(mla); mla = mla[o]; H = A['hours']
mg = lambda k, t: A[k][t].T[o].astype(np.float64)                  # maps are float16: convert before sums
def dist(la, lo, a, b):
    LA, LO = np.meshgrid(la, lo, indexing='ij'); return 111.2 * np.hypot(LA - a, ((LO - b + 180) % 360 - 180) * np.cos(np.radians(a)))
def centre(msl, la, lo, a, b, r=400.0):
    d = dist(la, lo, a, b); x = np.where(d < r, msl, np.inf); i = np.unravel_index(np.argmin(x), x.shape)
    LA, LO = np.meshgrid(la, lo, indexing='ij'); return float(LA[i]), float(LO[i]), float(msl[i])
def ring(F, la, lo, a, b): d = dist(la, lo, a, b); m = (d >= 200) & (d <= 600); return float(F[m].mean())
def ridge(z, la, lo, a, b):
    zz = np.where(dist(la, lo, a, b) < 600, np.nan, z); band = (lo >= 80) & (lo <= 95); prof = np.nanmean(zz[:, band], 1)
    s = (la >= 10) & (la <= 30); L, P = la[s], prof[s]
    if np.all(np.isnan(P)): return None, None
    i = int(np.nanargmax(P)); ref = prof[np.argmin(abs(la - 10))]
    return float(L[i]), float(P[i] - ref) if np.isfinite(ref) else None
def trough(z, la, lo):
    s = (la >= 25) & (la <= 35); band = (lo >= 55) & (lo <= 95); prof = z[s][:, band].mean(0); L = lo[band]
    i = int(np.argmin(prof)); return float(L[i]), float(prof[i] - prof.mean())
rows = []; ce = cm = None
for t, h in enumerate(H):
    tt = (t0 + dt.timedelta(hours=int(h))).strftime('%Y%m%d%H')
    if tt not in et: continue
    i = et.index(tt); emsl = ev('msl')[i]; emsl = emsl / 100 if np.nanmax(emsl) > 2000 else emsl
    mmsl = mg('mslp', t); mmsl = mmsl / 100 if np.nanmax(mmsl) > 2000 else mmsl
    if ce is None: ce = centre(emsl, ela, elo, 12, 86, 1500)[:2]; cm = centre(mmsl, mla, mlo, ce[0], ce[1], 600)[:2]
    ce = centre(emsl, ela, elo, *ce)[:2]; cm = centre(mmsl, mla, mlo, *cm)[:2]
    r = dict(h=int(h), era_centre=ce, mod_centre=cm)
    for lev in (850, 500, 200):
        r[f'steer{lev}'] = dict(era=[round(ring(ev(f'u{lev}')[i], ela, elo, *ce), 2), round(ring(ev(f'v{lev}')[i], ela, elo, *ce), 2)],
                              mod=[round(ring(mg(f'u{lev}', t), mla, mlo, *cm), 2), round(ring(mg(f'v{lev}', t), mla, mlo, *cm), 2)])
    r['steer_deep'] = {s_: [round(np.mean([r[f'steer{l}'][s_][c] for l in (850, 500, 200)]), 2) for c in (0, 1)] for s_ in ('era', 'mod')}
    ze = ev('z500')[i]; zm = mg('z500', t)
    r['ridge'] = dict(era=ridge(ze, ela, elo, *ce), mod=ridge(zm, mla, mlo, *cm)); r['trough'] = dict(era=trough(ze, ela, elo), mod=trough(zm, mla, mlo))
    rows.append(r)
for a, b in zip(rows[:-1], rows[1:]):                                                         # 6-h propagation of the axes
    b['ridge_move_deg'] = {s_: (round(b['ridge'][s_][0] - a['ridge'][s_][0], 2) if b['ridge'][s_][0] is not None and a['ridge'][s_][0] is not None else None) for s_ in ('era', 'mod')}
    b['trough_move_deg'] = {s_: round(b['trough'][s_][0] - a['trough'][s_][0], 2) for s_ in ('era', 'mod')}
json.dump(rows, open(OUT, 'w'), indent=1)
for r in rows:
    print(f"+{r['h']:3d}h storm E {r['era_centre']} M {r['mod_centre']} | deep steer E {r['steer_deep']['era']} M {r['steer_deep']['mod']} | 500 steer E {r['steer500']['era']} M {r['steer500']['mod']} | ridge E {r['ridge']['era']} M {r['ridge']['mod']} | trough E {r['trough']['era']} M {r['trough']['mod']}")
