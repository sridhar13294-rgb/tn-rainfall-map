"""Checks of radcloud.py with numpy (no JAX needed):  python test_radcloud.py
1. tropical clear sky (AFGL tropical standard atmosphere, Anderson et al. 1986, Ts = 300 K) on mm2's 32 sigma levels
2. mid-latitude summer clear sky (AFGL MLS, Ts = 294 K)
3. deep convective column (tropical, moist, active convection to 150 hPa, 40 mm/day convective rain)
Prints OLR, surface fluxes, heating-rate profiles and compares with reference values; checks energy closure;
times one call on a 256 x 128 x 32 array.   python test_radcloud.py --refit   re-derives the long-wave coefficient table."""
import sys, os, time, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import radcloud as R

def sigma_bounds(n=32):                                           # as in mm2.py
    e = np.linspace(0, 1, n + 1); return (0.6 * e + 0.4 * (1 - (1 - e) ** 2))
SB_ = sigma_bounds(); SIG = 0.5 * (SB_[1:] + SB_[:-1]); DSIG = np.diff(SB_)

# AFGL standard atmospheres (Anderson et al. 1986): p (hPa), T (K), H2O (ppmv)
TROP = np.array([
    [1013, 299.7, 2.593e4], [904, 293.7, 1.949e4], [805, 287.7, 1.534e4], [715, 283.7, 8.600e3], [633, 277.0, 4.441e3],
    [559, 270.3, 3.346e3], [492, 263.6, 2.101e3], [432, 257.0, 1.289e3], [378, 250.3, 7.637e2], [329, 243.6, 4.098e2],
    [286, 237.0, 1.912e2], [247, 230.1, 7.306e1], [213, 223.6, 2.905e1], [182, 217.0, 9.900], [156, 210.3, 6.220],
    [132, 203.7, 4.000], [111, 197.0, 3.000], [93.7, 194.8, 2.900], [78.9, 198.8, 2.750], [66.6, 202.7, 2.600],
    [56.5, 206.7, 2.600], [48.0, 210.7, 2.650], [40.9, 214.6, 2.800], [35.0, 217.0, 2.900], [30.0, 219.2, 3.200],
    [25.7, 221.4, 3.250], [12.2, 232.3, 4.0], [6.0, 243.1, 4.5], [3.05, 254.0, 5.0], [0.854, 270.2, 5.5], [0.01, 270.0, 5.5]])
MLS = np.array([
    [1013, 294.2, 1.876e4], [902, 289.7, 1.379e4], [802, 285.2, 9.629e3], [710, 279.2, 6.315e3], [628, 273.2, 3.782e3],
    [554, 267.2, 2.032e3], [487, 261.2, 1.141e3], [426, 254.7, 6.162e2], [372, 248.2, 3.010e2], [324, 241.7, 1.290e2],
    [281, 235.3, 4.877e1], [243, 228.8, 1.767e1], [209, 222.3, 7.630], [179, 215.8, 4.0], [153, 215.7, 4.0],
    [130, 215.7, 4.0], [111, 215.7, 4.0], [95.0, 216.8, 4.0], [81.2, 217.9, 4.0], [69.5, 219.2, 4.0], [59.5, 220.4, 4.0],
    [51.0, 221.6, 4.0], [43.7, 222.8, 4.0], [37.6, 223.9, 4.0], [32.2, 225.1, 4.0], [27.7, 228.5, 4.0], [13.2, 235.1, 4.5],
    [6.52, 247.4, 5.0], [3.33, 262.1, 5.0], [0.951, 274.0, 5.5], [0.01, 270.0, 5.5]])

def on_sigma(tab, ps=101300.0):
    p = SIG * ps; lp = np.log(tab[::-1, 0] * 100.0)
    T = np.interp(np.log(p), lp, tab[::-1, 1]); x = np.exp(np.interp(np.log(p), lp, np.log(tab[::-1, 2]))) * 1e-6
    q = 0.622 * x / (1 - x + 0.622 * x)
    return T, q, p, DSIG * ps

def col(a, n=1): return np.repeat(np.asarray(a, np.float64)[:, None, None], n, 1)

def run(T, q, p, dp, ps, Ts, mu0, sea=True, **kw):
    n = len(mu0)
    return R.radiation(col(T, n), col(q, n), col(p, n), col(dp, n), np.full((n, 1), ps), np.full((n, 1), Ts), np.full((n, 1), sea),
                       np.asarray(mu0, float)[:, None], xp=np, clear_sky=True, **kw)

def profile(o, key, p, every=3):
    h = o[key][:, 0, 0] * 86400.0; return '  '.join(f'{p[k] / 100:5.0f}:{h[k]:+5.2f}' for k in range(0, len(p), every))

def closure(o, dp):
    lw = (o['lw_heating'] * dp[:, None, None] * R.CP / R.G).sum(0); lw_ref = (o['lw_up_sfc'] - o['lw_dn_sfc']) - o['olr']
    sw = (o['sw_heating'] * dp[:, None, None] * R.CP / R.G).sum(0); sw_ref = o['sw_toa_dn'] - o['sw_toa_up'] - o['sw_net_sfc']
    return float(np.abs(lw - lw_ref).max()), float(np.abs(sw - sw_ref).max())


def refit():
    """Re-derive radcloud._LW_FIT: per long-wave term, effective H2O-line, CO2 (or continuum) coefficients fitted by grid search
    to the 1 cm-1 simple spectral model (x SSM_LINE_FAC, SSM_CNT_FAC) on four clear columns. Each term is a disjoint set of
    1 cm-1 bins, so its reference is the fine model restricted to those bins (about 2 minutes)."""
    LF, CF = R.SSM_LINE_FAC, R.SSM_CNT_FAC; nu = R._NU; bins = [nu == x for x in nu]
    h, c, kb = 6.62607015e-34, 2.99792458e8, 1.380649e-23; Tg = np.arange(140.0, 361.0, 1.0); nm = nu * 100
    piB = 2 * np.pi * h * c ** 2 * nm[None] ** 3 / np.expm1(h * c * nm[None] / (kb * Tg[:, None])) * 100
    def pcoef(groups):
        fr = np.stack([piB[:, m].sum(1) for m in groups], 1) / piB.sum(1, keepdims=True); x = (Tg - 250) / 100
        return np.stack([np.polyfit(x, fr[:, g], 5) for g in range(len(groups))])
    profs = []
    for tab, Ts, f in ((TROP, 300.0, None), (MLS, 294.0, None), (TROP, 300.0, 'dry'), (TROP, 302.0, 'moist')):
        T, q, p, dp = on_sigma(tab)
        if f == 'dry': q = np.where(p < 85000, q * 0.3, q)
        if f == 'moist': q = np.minimum(q * 1.3, 0.95 * R.qsat(T, p)); T = T + 2
        profs.append((T, q, p, dp, Ts))
    saved = (R.LW_KH2O, R.LW_KCO2, R.LW_KCNT, R.LW_O3, R.LW_PCOEF)
    def run(kh, kc, kn, ko, pc, pr):
        T, q, p, dp, Ts = pr; R.LW_KH2O, R.LW_KCO2, R.LW_KCNT, R.LW_O3, R.LW_PCOEF = kh, kc, kn, ko, pc
        z = col(T) * 0; cl = dict(c=z, lwp=z, iwp=z, re_i=z + 30e-6)
        o = R.longwave(col(T), col(q), col(p), col(dp), np.full((1, 1), 101300.0), np.full((1, 1), Ts), cl, np)
        return np.concatenate([[o['olr'][0, 0], o['dn_sfc'][0, 0]], o['heating'][:, 0, 0] * dp * R.CP / R.G])
    lm = lambda k, m: float(np.exp(np.mean(np.log(k[m] + 1e-12)))); rows = []
    for g, m in enumerate(R._LW_GROUPS):
        sel = np.where(m)[0]; ko = float(R._O3[m].mean() > 0.5)
        ref = [run(R._KH[sel] * LF, R._KC[sel] * LF, R._KN[sel] * CF, R._O3[sel].astype(float), pcoef([bins[i] for i in sel]), pr) for pr in profs]
        kh0 = lm(R._KH, m) * LF; kc0 = lm(R._KC, m) * LF if R._KC[m].max() > 0 else 0.0; kn0 = R._KN[m].mean() * CF; co2 = kc0 > 1e-6
        best = None; pg = pcoef([m])
        for a in np.exp(np.linspace(np.log(0.1), np.log(30), 37)):
            for b in np.exp(np.linspace(np.log(0.1), np.log(30), 37) if co2 else np.linspace(np.log(0.2), np.log(5), 11)):
                kc, kn = (kc0 * b, kn0) if co2 else (0.0, kn0 * b); err = 0.0
                for pr, rf in zip(profs, ref):
                    d = run(np.array([kh0 * a]), np.array([kc]), np.array([kn]), np.array([ko]), pg, pr) - rf
                    err += d[0] ** 2 + d[1] ** 2 + 4 * np.sum(d[7:] ** 2)
                if best is None or err < best[0]: best = (err, kh0 * a, kc, kn)
        rows.append(best[1:]); print(f'{R.LW_NAMES[g]:9s} [{best[1]:.4g}, {best[2]:.4g}, {best[3]:.4g}]  cost {best[0]:.2f}', flush=True)
    R.LW_KH2O, R.LW_KCO2, R.LW_KCNT, R.LW_O3, R.LW_PCOEF = saved
    return np.array(rows)

if '--refit' in sys.argv: refit(); sys.exit()
mu_day = np.clip(np.cos(np.radians(15.0 * (np.arange(48) / 2.0 + 0.25 - 12.0))), 0, None)   # equator, equinox, half-hourly
res = {}
print(f'LW terms ({R.NG_LW}): ' + ', '.join(f'{n}[kh={kh:.3g} kc={kc:.3g}]' for n, kh, kc in zip(R.LW_NAMES, R.LW_KH2O, R.LW_KCO2)))
print(f'Planck-fraction polynomial max error {R.LW_PFIT_ERR:.1e}')
for name, tab, Ts in (('tropical', TROP, 300.0), ('mid-lat summer', MLS, 294.0)):
    T, q, p, dp = on_sigma(tab); pw = (q * dp).sum() / R.G
    o3 = R.ozone_layer_mass(p[:, None, None], dp[:, None, None]).sum() / 2.1415e-5         # Dobson units (1 DU = 2.1415e-5 kg m-2)
    o1 = run(T, q, p, dp, 101300.0, Ts, [1.0]); od = run(T, q, p, dp, 101300.0, Ts, mu_day)
    m = lambda k: float(od[k].mean())
    print(f'\n=== {name}: Ts {Ts} K, precipitable water {pw:.1f} kg m-2, ozone {o3:.0f} DU')
    print(f' clear-sky LW: OLR {float(o1["olr_clr"][0, 0]):.1f}  surface down {float(o1["lw_dn_sfc_clr"][0, 0]):.1f}  surface up {float(o1["lw_up_sfc"][0, 0]):.1f} W m-2')
    print(f' all-sky (diagnosed clouds, cover {float(o1["cover"][0, 0]):.2f}): OLR {float(o1["olr"][0, 0]):.1f}  surface down {float(o1["lw_dn_sfc"][0, 0]):.1f}')
    print(f' clear-sky SW, overhead sun: TOA in 1361, reflected {float(o1["sw_toa_up_clr"][0, 0]):.1f}, surface net {float(o1["sw_net_sfc_clr"][0, 0]):.1f}, '
          f'atmosphere absorbs {1361 - float(o1["sw_toa_up_clr"][0, 0]) - float(o1["sw_net_sfc_clr"][0, 0]):.1f}')
    print(f' clear-sky SW, diurnal mean equator equinox: TOA in {m("sw_toa_dn"):.1f}, reflected {m("sw_toa_up_clr"):.1f}, surface net {m("sw_net_sfc_clr"):.1f}, '
          f'atmosphere absorbs {m("sw_toa_dn") - m("sw_toa_up_clr") - m("sw_net_sfc_clr"):.1f}')
    print(' clear LW heating K/day (hPa:K/day):', profile(o1, 'lw_heating_clr', p))
    hd = dict(sw_heating_clr=od['sw_heating_clr'].mean(1, keepdims=True))
    print(' clear SW heating, diurnal mean    :', profile(hd, 'sw_heating_clr', p))
    trop = (p > 30000) & (p < 80000); lwc = o1['lw_heating_clr'][:, 0, 0] * 86400
    print(f' mean clear LW cooling 800-300 hPa: {lwc[trop].mean():.2f} K/day; net (LW + diurnal SW) {lwc[trop].mean() + hd["sw_heating_clr"][:, 0, 0][trop].mean() * 86400:.2f} K/day')
    print(' energy closure |error| (LW, SW) W m-2:', closure(o1, dp), closure(od, dp))
    res[name] = dict(olr=float(o1['olr_clr'][0, 0]), dlr=float(o1['lw_dn_sfc_clr'][0, 0]), cool=float(lwc[trop].mean()), swsfc=m('sw_net_sfc_clr'),
                     net=float(lwc[trop].mean() + hd['sw_heating_clr'][:, 0, 0][trop].mean() * 86400))

# ---- 3. deep convective column: tropical temperature, RH >= 90 % below 150 hPa, convection from the surface layer to 150 hPa
T, q, p, dp = on_sigma(TROP); qs = R.qsat(T, p)
q = np.where(p > 15000, np.maximum(q, 0.9 * qs), q)
cm = (p > 14000) & (p < 97000)
def deep(mm, mu):
    Pc = mm / 86400.0; src = np.where(cm, dp, 0.0); src = src / src.sum() * Pc; n = len(mu)
    return R.radiation(col(T, n), col(q, n), col(p, n), col(dp, n), np.full((n, 1), 101300.0), np.full((n, 1), 301.0), np.full((n, 1), True), np.asarray(mu)[:, None],
                       conv_mask=col(cm, n).astype(bool), conv_rain=np.full((n, 1), Pc), conv_src=col(src, n), xp=np, clear_sky=True)
print('\n=== deep convective column (top 150 hPa, RH >= 90 %, SST 301 K): convective rain sweep, overhead sun')
for mm in (2, 5, 10, 20, 40, 80):
    o = deep(mm, [1.0])
    print(f' {mm:3d} mm/day: total cover {float(o["cover"][0, 0]):.2f}, max layer cloud {float(o["cloud"][:, 0, 0].max()):.2f}, grid IWP {1000 * float(o["iwp"][0, 0]):5.0f} '
          f'LWP {1000 * float(o["lwp"][0, 0]):5.0f} g m-2, OLR {float(o["olr"][0, 0]):6.1f}, albedo {float(o["sw_toa_up"][0, 0]) / 1361:.2f}, surface LW down {float(o["lw_dn_sfc"][0, 0]):.0f}')
    res[f'deep{mm}'] = float(o['olr'][0, 0])
o = deep(40, np.concatenate([[1.0], mu_day]))
print(' 40 mm/day cloud fraction (hPa:c):', '  '.join(f'{p[k] / 100:4.0f}:{o["cloud"][k, 0, 0]:.2f}' for k in range(4, 32, 2)))
print(f' 40 mm/day: OLR clear {float(o["olr_clr"][0, 0]):.1f}; diurnal mean surface net SW {float(o["sw_net_sfc"][1:].mean()):.1f} (clear {float(o["sw_net_sfc_clr"][1:].mean()):.1f}), '
      f'SW cloud forcing at TOA {float((o["sw_toa_up_clr"][1:] - o["sw_toa_up"][1:]).mean()):.1f} W m-2')
print(' 40 mm/day LW heating K/day:', profile(o, 'lw_heating', p))
print(' energy closure |error| (LW, SW) W m-2:', closure(o, dp))

# ---- comparison with targets
print('\n=== comparison with targets')
chk = [('tropical clear OLR', res['tropical']['olr'], 285, 290, 'task target; ERBE clear-sky OLR over 300 K SST ~290 (Raval & Ramanathan 1989)'),
       ('tropical clear surface LW down', res['tropical']['dlr'], 400, 420, 'task target; tropical-ocean clear-sky DLR'),
       ('tropical clear LW cooling 800-300 hPa', -res['tropical']['cool'], 1.5, 2.0, 'K/day, task target; ~2 K/day RRTMG aquaplanet (Williams 2025)'),
       ('tropical clear net (LW + diurnal SW) cooling 800-300 hPa', -res['tropical']['net'], 1.5, 2.0, 'K/day, same target read as net radiative cooling'),
       ('tropical clear surface net SW (diurnal mean)', res['tropical']['swsfc'], 280, 330, 'plausible: 433 in x (1 - ~0.2 absorbed - ~0.07 reflected)'),
       ('mid-lat summer clear OLR', res['mid-lat summer']['olr'], 275, 295, 'approx. ICRCCM/RRTM MLS ~285 (from memory)'),
       ('mid-lat summer clear surface LW down', res['mid-lat summer']['dlr'], 330, 360, 'approx. ICRCCM/RRTM MLS ~345 (from memory)'),
       ('deep convective OLR, 20 mm/day', res['deep20'], 120, 150, 'task target; deep convection OLR 100-150 (Hartmann et al. 1992)'),
       ('deep convective OLR, 40 mm/day', res['deep40'], 120, 150, 'task target')]
ok = True
for name, v, lo, hi, ref in chk:
    good = lo <= v <= hi; ok &= good; print(f' {"OK  " if good else "MISS"} {name}: {v:.1f}  target {lo}-{hi}  ({ref})')

# ---- cost
rng = np.random.default_rng(0); NX, NY = 256, 128
T, q, p, dp = on_sigma(TROP)
TT = (T[:, None, None] + rng.normal(0, 1, (32, NX, NY))).astype(np.float32); QQ = (q[:, None, None] * rng.uniform(0.6, 1.2, (32, NX, NY))).astype(np.float32)
PS = np.full((NX, NY), 101300.0, np.float32); PP = (SIG[:, None, None] * PS).astype(np.float32); DP = (DSIG[:, None, None] * PS).astype(np.float32)
MU = np.clip(rng.uniform(-1, 1, (NX, NY)), 0, 1).astype(np.float32); SEA = rng.uniform(size=(NX, NY)) < 0.7
CM = (PP > 15000) & (PP < 97000) & (rng.uniform(size=(NX, NY)) < 0.1)[None]
args = (TT, QQ, PP, DP, PS, (PS * 0 + 300.0).astype(np.float32), SEA, MU)
kw = dict(conv_mask=CM, conv_rain=np.full((NX, NY), 1e-4, np.float32), ls_cond=np.zeros_like(TT), xp=np)
R.radiation(*args, **kw); t0 = time.time(); o = R.radiation(*args, **kw); dtc = time.time() - t0
print(f'\n=== cost: one call on 256x128x32 float32 numpy: {dtc:.2f} s ({dtc / (NX * NY) * 1e6:.1f} us per column); '
      f'output dtype {o["heating"].dtype}, finite {bool(np.isfinite(o["heating"]).all())}')
print(' GPU estimate (not measured: no JAX here): the sweeps are memory-bound; per call ~2.5 GB (LW) + ~4 GB (SW) of carry and\n'
      ' input traffic at T170 (512x256x32) -> roughly 30-40 ms on a T4 (+-2x), ~4x less at 256x128. Benchmark with gpu_bench.py.')
print('ALL TARGETS MET' if ok else 'SOME TARGETS MISSED')
