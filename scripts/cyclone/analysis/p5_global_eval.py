"""Global circulation check (10 Nov, Sridhar: 'not only the Siberian High - other global highs and trade winds').
python p5_global_eval.py p5_wide.npz -> model-minus-ERA5 bias by day (0..N) for the semi-permanent highs/lows (MSLP, hPa)
and the trade-wind belts (u850, m/s), 12 Oct-Nov 2020 starts, T170. Registered reading (docs/rootcause.md 10 Nov 16:35):
REPRODUCED if |bias| <= 2 (hPa or m/s) through day 3 and the MSLP bias grows by < 1 hPa/day; otherwise FLAGGED."""
import sys, numpy as np
Z = np.load(sys.argv[1]); la, lo = Z['lat'], Z['lon'] % 360
def box(F, a, b, c, d):
    lm = (la >= a) & (la <= b); om = ((lo >= c) & (lo <= d)) if c <= d else ((lo >= c) | (lo <= d))
    w = np.cos(np.radians(la[lm]))[:, None] * np.ones(om.sum())[None, :]
    X = F[np.ix_(lm, om)]; ok = np.isfinite(X); return float((X * w)[ok].sum() / w[ok].sum())
HIGHS = [('Siberian High', 45, 60, 80, 120), ('North Pacific High', 25, 40, 180, 230), ('Azores High', 25, 40, 320, 350),
         ('South Pacific High', -40, -25, 255, 280), ('South Atlantic High', -35, -20, 340, 10), ('Mascarene High', -40, -25, 50, 90),
         ('Aleutian Low', 45, 60, 170, 210), ('Icelandic Low', 55, 70, 310, 340), ('China 25-40N 100-120E', 25, 40, 100, 120),
         ('Myanmar 18-28N 92-100E', 18, 28, 92, 100), ('Bay of Bengal 10-20N 82-95E', 10, 20, 82, 95)]
TRADES = [('N Pacific trades 5-20N 180-240E', 5, 20, 180, 240), ('S Pacific trades 5-20S 200-260E', -20, -5, 200, 260),
          ('N Atlantic trades 5-20N 300-340E', 5, 20, 300, 340), ('S Atlantic trades 5-20S 330-360E', -20, -5, 330, 360),
          ('S Indian trades 5-20S 60-100E', -20, -5, 60, 100), ('NE monsoon Arabian Sea 5-15N 60-75E', 5, 15, 60, 75),
          ('Bay of Bengal 10-20N 82-95E', 10, 20, 82, 95), ('S China Sea / Indochina 12-24N 105-120E', 12, 24, 105, 120)]
days = sorted({int(k.split('_d')[1]) for k in Z.files if '_d' in k})
def row(name, var, a, b, c, d, unit):
    v = [box(Z[f'{var}_d{k}'], a, b, c, d) for k in days]; d3 = [x for k, x in zip(days, v) if k <= 3]
    grow = (v[min(3, days[-1])] - v[0]) / max(min(3, days[-1]), 1) if var == 'mslp' else 0.0
    flag = 'REPRODUCED' if max(abs(x) for x in d3) <= 2 and (var != 'mslp' or abs(grow) < 1) else 'FLAGGED'
    print(f'{name:42s} ' + ' '.join(f'd{k} {x:+5.1f}' for k, x in zip(days, v)) + f' {unit}  -> {flag}')
print('MSLP bias (hPa), model - ERA5:'); [row(n, 'mslp', *b, 'hPa') for n, *b in HIGHS]
print('\nu850 bias (m/s), model - ERA5 (negative = too easterly):'); [row(n, 'u850', *b, 'm/s') for n, *b in TRADES]
