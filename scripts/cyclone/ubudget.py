"""17 Nov: Bay 850-hPa u error-tendency budget, model vs ERA5 (registered rootcause 13:20). Terms on the ERA5 1-deg grid at 850 hPa:
du/dt (12-h centred), horizontal advection -(u du/dx + v du/dy), Coriolis+pressure gradient f v - g dz/dx, residual = rest (friction,
vertical advection, convective momentum, diffusion). Error tendency = model term - ERA5 term, mean over h = 12, 24, 36 and starts."""
import sys, json, datetime as dt, numpy as np
from scipy.interpolate import RegularGridInterpolator as RGI
sys.path.insert(0, '/tmp/claude-0/disp/scripts/cyclone/mm'); import mm2, landinit
Z = dict(np.load('/tmp/claude-0/era5m/libm_wx2020L_fields.npz')); V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]; TT = [str(t) for t in Z['times']]
GRID = sys.argv[1]; STARTS = sys.argv[2].split(',')
M = mm2.Model(GRID, 32, {'T42': 20.0, 'T85': 10.0}[GRID], dict(cmt_mf=1, rd_si=1, map_out=True))
E = np.load('/tmp/claude-0/cases/days_2020.npz'); ET = [str(t) for t in E['times']]; la = np.asarray(E['lat'], float); lo = np.asarray(E['lon'], float)
unq = lambda k: E[k].astype(np.float64) * float(E[k + '__scale']) + float(E[k + '__off'])
EU, EV, EZ = unq('u850'), unq('v850'), unq('z850')
R, OM, G = 6.371e6, 7.292e-5, 9.80665
f = 2 * OM * np.sin(np.radians(la))[:, None]; cl = np.cos(np.radians(la))[:, None]
ddx = lambda F: np.gradient(F, np.radians(lo), axis=1) / (R * cl)
ddy = lambda F: np.gradient(F, np.radians(la), axis=0) / R
def terms(U, V, Zh, i):            # lists over time (12-h spacing); i = centre index
    dudt = (U[i + 1] - U[i - 1]) / (24 * 3600.0)
    adv = -(U[i] * ddx(U[i]) + V[i] * ddy(U[i])); cp = f * V[i] - G * ddx(Zh[i])
    return dict(dudt=dudt, adv=adv, corpgf=cp, res=dudt - adv - cp)
BOX = {'Bay 10-22N 80-95E': (10, 22, 80, 95), 'E of Bay 12-24N 98-110E': (12, 24, 98, 110)}
acc = {}
for s in STARTS:
    k = TT.index(s); t0 = dt.datetime.strptime(s, '%Y-%m-%dT%H'); f2 = Z['f2'][k]; f3 = {v: np.array(Z['f3'][k, V3.index(v)]) for v in V3}
    st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / 9.80616,
                    f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
    M.build(t0); st = M.dfi(st); out = M.run_wx(st, cr, 48, 12)
    ML, MA = np.asarray(M.lon, float), np.asarray(M.lat, float); zs = np.asarray(M.zs); zs = zs if zs.shape == (len(ML), len(MA)) else zs.T
    def on_e(F):                   # model [lon, lat] -> ERA5 grid [lat, lon]
        o = np.argsort(MA); itp = RGI((ML, MA[o]), np.asarray(F)[:, o], bounds_error=False, fill_value=None)
        P = np.stack(np.meshgrid(lo, la), -1).reshape(-1, 2); return itp(P).reshape(len(la), len(lo))
    mask_terr = on_e(zs) < 1000
    MU = [on_e(out['u850'][j]) for j in range(5)]; MV = [on_e(out['v850'][j]) for j in range(5)]; MZ = [on_e(out['z850'][j]) for j in range(5)]
    j0 = ET.index(t0.strftime('%Y%m%d%H')); EUs, EVs, EZs = EU[j0:j0 + 5], EV[j0:j0 + 5], EZ[j0:j0 + 5]
    for i in (1, 2, 3):
        tm, te = terms(MU, MV, MZ, i), terms(EUs, EVs, EZs, i)
        for b, (a0, a1, o0, o1) in BOX.items():
            m = (la[:, None] >= a0) & (la[:, None] <= a1) & (lo[None] >= o0) & (lo[None] <= o1) & mask_terr
            for kk in tm:
                acc.setdefault((b, kk, 'model'), []).append(float(tm[kk][m].mean() * 86400))
                acc.setdefault((b, kk, 'era5'), []).append(float(te[kk][m].mean() * 86400))
        for b, (a0, a1, o0, o1) in BOX.items():
            m = (la[:, None] >= a0) & (la[:, None] <= a1) & (lo[None] >= o0) & (lo[None] <= o1) & mask_terr
            acc.setdefault((b, 'u_err', 'h%d' % (12 * i)), []).append(float((MU[i] - EUs[i])[m].mean()))
    print(s, 'done', flush=True)
out = {}
for b in BOX:
    print(b, '(m/s per day, mean over starts and h=12,24,36)')
    for kk in ('dudt', 'adv', 'corpgf', 'res'):
        mo, er = np.mean(acc[(b, kk, 'model')]), np.mean(acc[(b, kk, 'era5')])
        print(f'   {kk:7s} model {mo:+6.2f}  ERA5 {er:+6.2f}  error {mo - er:+6.2f}'); out[f'{b}|{kk}'] = [mo, er, mo - er]
    print('   u error at h12/24/36:', [round(np.mean(acc[(b, 'u_err', h)]), 2) for h in ('h12', 'h24', 'h36')])
json.dump(out, open(sys.argv[3], 'w'))
