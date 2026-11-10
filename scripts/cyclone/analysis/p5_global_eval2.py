"""Global circulation check, per start (10 Nov 17:20, Sridhar): for each semi-permanent high/low - POSITION (model vs ERA5
centre, km), STRENGTH (central MSLP model - ERA5, hPa), WIND (mean 850-hPa speed in the system's box, model - ERA5, m/s),
EVOLUTION (days 0..N); for each trade belt the u850 bias. Every start shown individually plus mean and the number of starts
beyond the registered limits (2 hPa / 2 m/s; centre shift > 500 km).
python p5_global_eval2.py P5_WIDE_NPZ TRUTH_NPZ"""
import sys, math, datetime as dt, numpy as np
Z = np.load(sys.argv[1]); TR = np.load(sys.argv[2]); DI = {str(d): i for i, d in enumerate(TR['days'])}
la, lo = Z['lat'], Z['lon'] % 360; starts = [str(s) for s in Z['starts']]
days = sorted({int(k.split('_d')[1]) for k in Z.files if k.startswith('ps_mslp_d')})
def km(a, b, c, d): return 6371 * math.acos(min(1, math.sin(math.radians(a)) * math.sin(math.radians(c)) + math.cos(math.radians(a)) * math.cos(math.radians(c)) * math.cos(math.radians(b - d))))
def sel(a, b, c, d):
    lm = (la >= a) & (la <= b); om = ((lo >= c) & (lo <= d)) if c <= d else ((lo >= c) | (lo <= d)); return lm, om
def truth(var, s, d):
    t = (dt.datetime.strptime(s, '%Y-%m-%dT%H') + dt.timedelta(days=d)).strftime('%Y-%m-%dT%H'); return np.asarray(TR['o_' + var][DI[t]], float)
SYS = [('Siberian High', 'H', 40, 65, 70, 130), ('North Pacific High', 'H', 20, 45, 170, 240), ('Azores High', 'H', 20, 45, 310, 355),
       ('South Pacific High', 'H', -45, -20, 240, 290), ('South Atlantic High', 'H', -40, -15, 330, 15), ('Mascarene High', 'H', -45, -20, 40, 100),
       ('Aleutian Low', 'L', 40, 65, 160, 220), ('Icelandic Low', 'L', 50, 75, 300, 350)]
TRADES = [('N Pacific trades', 5, 20, 180, 240), ('S Pacific trades', -20, -5, 200, 260), ('N Atlantic trades', 5, 20, 300, 340),
          ('S Atlantic trades', -20, -5, 330, 360), ('S Indian trades', -20, -5, 60, 100), ('Arabian Sea NE monsoon', 5, 15, 60, 75),
          ('Bay of Bengal', 10, 20, 82, 95), ('S China Sea / Indochina', 12, 24, 105, 120), ('China 25-40N 100-120E', 25, 40, 100, 120)]
for name, kind, a, b, c, d in SYS:
    lm, om = sel(a, b, c, d); LA = la[lm]; LO = lo[om]; w = np.cos(np.radians(LA))[:, None] * np.ones(len(LO))[None, :]
    print(f'\n=== {name} ({"high" if kind == "H" else "low"}, search box {a}..{b}N {c}..{d}E) ===')
    print('start          ' + ' | '.join(f'day {k}: shift km / dP hPa / dWind m/s' if k == days[0] else f'd{k}' for k in days))
    agg = {k: [] for k in days}
    for i, s in enumerate(starts):
        cells = []
        for k in days:
            P_t = truth('mslp', s, k) / 100; P_m = P_t + np.asarray(Z[f'ps_mslp_d{k}'][i], float)
            U_t, V_t = truth('u850', s, k), truth('v850', s, k)
            U_m = U_t + np.asarray(Z[f'ps_u850_d{k}'][i], float); V_m = V_t + np.asarray(Z[f'ps_v850_d{k}'][i], float)
            Pt, Pm = P_t[np.ix_(lm, om)], P_m[np.ix_(lm, om)]
            f = np.nanargmax if kind == 'H' else np.nanargmin
            it, jt = np.unravel_index(f(Pt), Pt.shape); im, jm = np.unravel_index(f(Pm), Pm.shape)
            shift = km(LA[it], LO[jt], LA[im], LO[jm]); dP = float(Pm[im, jm] - Pt[it, jt])
            St = np.hypot(U_t, V_t)[np.ix_(lm, om)]; Sm = np.hypot(U_m, V_m)[np.ix_(lm, om)]; ok = np.isfinite(St) & np.isfinite(Sm)
            dW = float(((Sm - St) * w)[ok].sum() / w[ok].sum()); agg[k].append((shift, dP, dW)); cells.append(f'{shift:5.0f} {dP:+5.1f} {dW:+5.1f}')
        print(f'{s}  ' + ' | '.join(cells))
    print('MEAN           ' + ' | '.join(f'{np.mean([x[0] for x in agg[k]]):5.0f} {np.mean([x[1] for x in agg[k]]):+5.1f} {np.mean([x[2] for x in agg[k]]):+5.1f}' for k in days))
    print('FAILING starts ' + ' | '.join(f'{sum(1 for x in agg[k] if x[0] > 500 or abs(x[1]) > 2 or abs(x[2]) > 2):2d}/{len(starts)}           ' for k in days))
print('\n=== Trade-wind / regional u850 bias (m/s, negative = too easterly), per start ===')
for name, a, b, c, d in TRADES:
    lm, om = sel(a, b, c, d); w = np.cos(np.radians(la[lm]))[:, None] * np.ones(om.sum())[None, :]
    rows = np.array([[float((np.asarray(Z[f'ps_u850_d{k}'][i], float)[np.ix_(lm, om)] * w).sum() / w.sum()) for k in days] for i in range(len(starts))])
    print(f'{name:26s} mean ' + ' '.join(f'd{k} {rows[:, j].mean():+5.1f}' for j, k in enumerate(days)) +
          ' | starts beyond +-2: ' + ' '.join(f'd{k} {int((np.abs(rows[:, j]) > 2).sum())}' for j, k in enumerate(days)) +
          ' | worst ' + ' '.join(f'{rows[:, j].min():+5.1f}' for j, k in enumerate(days)))
