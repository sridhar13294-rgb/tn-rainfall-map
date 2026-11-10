"""Resting-atmosphere test over real orography (10 Nov, P5): horizontally uniform standard atmosphere T(p), no wind, no
moisture, surface pressure in hydrostatic balance with the terrain, physics OFF, no DFI. Exact dynamics keeps it at rest;
any wind that appears is numerical (pressure-gradient error of terrain-following levels, IFS Part III D2/D4).
python rest_test.py LIB_NPZ GRID [HOURS]  -> |u850| statistics by region at each 6 h and the 850-hPa u map near the Bay."""
import sys, datetime as dt, numpy as np
sys.path.insert(0, '.'); import mm2, landinit
Z = np.load(sys.argv[1]); GR = sys.argv[2]; H = int(sys.argv[3]) if len(sys.argv) > 3 else 24
V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]; levs = Z['levs'].astype(float); f2 = Z['f2'][0]
T0, LR, G, R = 288.15, 0.0065, 9.80665, 287.04
def t_std(p_hpa): return np.where(p_hpa > 226.32, T0 * (p_hpa / 1013.25) ** (R * LR / G), 216.65)
zs = f2[V2.index('geopotential_at_surface')] / G
ps = 101325.0 * np.clip(1 - LR * zs / T0, 0.3, None) ** (G / (R * LR))
f3 = {v: np.array(Z['f3'][0, V3.index(v)]) for v in V3}
f3['temperature'][:] = t_std(levs)[:, None, None]; f3['specific_humidity'][:] = 0.0
f3['u_component_of_wind'][:] = 0.0; f3['v_component_of_wind'][:] = 0.0
pz = levs[:, None, None] * 100.0; f3['geopotential'][:] = np.where(levs[:, None, None] > 226.32,
    G * T0 / LR * (1 - (pz / 101325.0) ** (R * LR / G)), G * (11000.0 + R * 216.65 / G * np.log(22632.0 / pz)))
t0 = dt.datetime(2020, 1, 1)
M = mm2.Model(GR, 32, None, {'rd_si': 1, 'phys_off': True})
st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], ps, zs, f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')],
                when=t0, **landinit.land_kwargs(f2, V2))
M.build(t0)
out = M.run_wx(st, cr, H, 6)
la, lo = np.asarray(M.lat), np.asarray(M.lon)
def box(F, a, b, c, d): m = np.ix_((lo >= c) & (lo <= d), (la >= a) & (la <= b)); return np.abs(F[m])
REG = [('SE Tibet flank 20-30N 90-110E', 20, 30, 90, 110), ('north Bay 15-22N 85-95E', 15, 22, 85, 95),
       ('Bay 10-20N 82-95E', 10, 20, 82, 95), ('flat ocean 5S-5N 60-90E', -5, 5, 60, 90), ('Andes 30S-0 70-80W', -30, 0, 280, 290)]
for k in range(1, len(out['u850'])):
    U = np.asarray(out['u850'][k]); V = np.asarray(out['v850'][k])
    print(f'{GR} hour {6*k:3d} ' + ' | '.join(f'{n}: mean|u| {box(U,a,b,c,d).mean():.2f} max {box(U,a,b,c,d).max():.2f}' for n, a, b, c, d in REG), flush=True)
U = np.asarray(out['u850'][-1]); print(f'u850 at hour {H} (rows lat 36..6 N, cols lon 80..120 E):')
for lat in range(36, 2, -3):
    i = int(np.argmin(np.abs(la - lat))); print(f'{lat:3d} ' + ' '.join(f'{U[int(np.argmin(np.abs(lo - x))), i]:+5.1f}' for x in range(80, 121, 5)))
