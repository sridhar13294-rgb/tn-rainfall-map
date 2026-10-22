"""Multi-centre consensus of the moist model's starting analyses (numpy only).
Centre files of one run (ours_fetch_m.py, RUN word "oursm"), all on the 1.5 deg grid and 13 levels of live_GFSM:
  GFSM  live_GFSM_<run>.npz  GFS analysis (f3, f2)              ECM  live_ECM_<run>.npz  ECMWF (f3 and sp only, no f2)
  ICON  live_ICON_<run>.npz  DWD ICON (f3, f2)                  CMC  live_CMC_<run>.npz  Canadian GDPS (f3, f2)
load_centres(folder, run)    -> {name: dict(f3 [var, lev, lat, lon], v3, levs, lats, lons, source, and the f2 fields by name)}
                                on the reference centre's variable/level order (GFSM if present)
consensus(C, weights=None)   -> dict(f3={var: [lev, lat, lon]} consensus mean, f2={v2 name: [lat, lon]},
                                diffs={centre: {var: centre - mean}} (0 where the centre's field was not used),
                                ps_diffs={centre: [lat, lon]}, used, dropped=[(centre, var, lev, reason, value)], report, ...)
member_start(CN, k, scale)   -> (f3 dict, ps) for ensemble member k: mean + random mix of the centre differences (k=0: the mean)
centre_start(CN, centre, a)  -> (f3 dict, ps): mean + a * (centre - mean)
report_text(CN['report'])    -> printable lines;   save_livem(CN, path) -> a live_GFSM-format npz of the consensus
Checks for every variable and level, on points above ground (level pressure below the centres' median surface pressure):
  1. coverage: a field with fewer than min_cover finite points is not used ('nan');
  2. bounds: physically impossible values are set missing; more than 2 % of points -> field not used ('bounds');
  3. with >= 3 centres, a robust z for each centre: its area-weighted RMS distance from the point-by-point median of the OTHER
     centres, divided by the median pairwise RMS distance among those other centres (leave-one-out, so one bad centre cannot
     hide in the scale; honest centres score ~0.8-1.5, gross errors 5-1000). z > z_max -> field not used ('outlier').
     With 2 centres an outlier cannot be identified, so only 1-2 apply.
  Optional z_point: single points further than z_point * scale from the others' median are left out of the mean (off by
  default - real differences near a cyclone are exactly what the members should sample).
Surface pressure is compared and averaged on the reference terrain: a centre's own surface pressure times the ratio of its
own profile's pressures (from its geopotential and temperature) at the reference terrain and at its own terrain; ECMWF, whose
file has no terrain, uses its profile's pressure at the reference terrain (scaled by the reference's own ps/profile ratio). Land mask and terrain: the reference's. Sea temperature: mean of the centres that
have it, on the reference's sea points. Surface fields a centre file lists in its notes as filled in 'from GFS' are ignored for
that centre (they would vote twice for GFS)."""
import os, re, sys, json, warnings, numpy as np
V3 = ['temperature', 'specific_humidity', 'u_component_of_wind', 'v_component_of_wind', 'geopotential']
V2 = ['surface_pressure', 'sea_surface_temperature', 'land_sea_mask', 'geopotential_at_surface']
CENTRES = ('GFSM', 'ECM', 'ICON', 'CMC')
G = 9.80665; RD = 287.04
BOUNDS = {'temperature': (150.0, 340.0), 'specific_humidity': (-1e-4, 0.05), 'u_component_of_wind': (-150.0, 150.0),
          'v_component_of_wind': (-150.0, 150.0), 'surface_pressure': (40000.0, 110000.0), 'sea_surface_temperature': (260.0, 320.0)}
FLOOR = {'temperature': 0.05, 'specific_humidity': 2e-6, 'u_component_of_wind': 0.1, 'v_component_of_wind': 0.1, 'geopotential': 2.0,
         'surface_pressure': 10.0, 'sea_surface_temperature': 0.05}                     # smallest scale used in the z-score
SHOW = {'temperature': (1.0, 'K'), 'specific_humidity': (1000.0, 'g/kg'), 'u_component_of_wind': (1.0, 'm/s'),
        'v_component_of_wind': (1.0, 'm/s'), 'geopotential': (1 / G, 'm'), 'surface_pressure': (0.01, 'hPa'), 'sea_surface_temperature': (1.0, 'K')}

def std_z(p_hpa):
    return 44330.8 * (1 - (p_hpa / 1013.25) ** 0.190263) if p_hpa >= 226.32 else 11000.0 + 6341.6 * np.log(226.32 / p_hpa)

def bounds(v, lev=None):
    if v == 'geopotential': return G * (std_z(lev) - 5000), G * (std_z(lev) + 5000)
    return BOUNDS.get(v, (-np.inf, np.inf))

# ------------------------------------------------------------------ loading
def unpack(Z, name='?'):
    """an npz (or dict) in the live_GFSM / live_ECM layout -> centre dict."""
    files = Z.files if hasattr(Z, 'files') else list(Z)
    f3 = np.asarray(Z['f3'], np.float64); f3 = f3[0] if f3.ndim == 5 else f3
    d = dict(f3=f3, v3=[str(v) for v in Z['v3']], levs=[int(x) for x in Z['levs']], lats=np.asarray(Z['lats'], float),
             lons=np.asarray(Z['lons'], float), source=str(Z['source']) if 'source' in files else name)
    if 'f2' in files and 'v2' in files:
        f2 = np.asarray(Z['f2'], np.float64); f2 = f2[0] if f2.ndim == 4 else f2; v2 = [str(v) for v in Z['v2']]
        for k in V2:
            if k in v2: d[k] = f2[v2.index(k)]
    if 'times' in files: d['times'] = np.asarray(Z['times'])
    if 'notes' in files and name != 'GFSM':                                       # fields filled in from GFS are not independent:
        for nt in np.atleast_1d(Z['notes']):                                      # leave them out of this centre
            m = re.match(r'^(\w+) from GFS$', str(nt))
            if m and m.group(1) in V2: d[m.group(1)] = None; d.setdefault('substituted', []).append(m.group(1))
    if 'sp' in files and 'surface_pressure' not in d:
        sp = np.asarray(Z['sp'], np.float64); d['surface_pressure'] = sp[0] if sp.ndim == 3 else sp
    return d

def align(C, ref='GFSM'):
    """put every centre on the reference's variable and level order; centres on another grid are left out."""
    if not C: return C
    r = ref if ref in C else next(iter(C)); R = C[r]; out = {}
    for n, d in C.items():
        if d['f3'].shape[-2:] != R['f3'].shape[-2:] or not (np.allclose(d['lats'], R['lats']) and np.allclose(d['lons'], R['lons'])):
            print('consensus:', n, 'is on another grid - left out', flush=True); continue
        f3 = np.full((len(R['v3']), len(R['levs'])) + R['f3'].shape[-2:], np.nan)
        for i, v in enumerate(R['v3']):
            if v not in d['v3']: continue
            for k, lev in enumerate(R['levs']):
                if lev in d['levs']: f3[i, k] = d['f3'][d['v3'].index(v), d['levs'].index(lev)]
        e = dict(d); e.update(f3=f3, v3=list(R['v3']), levs=list(R['levs']), lats=R['lats'], lons=R['lons']); out[n] = e
    return out

def load_centres(folder, run, names=CENTRES, ref='GFSM'):
    C = {}
    for n in names:
        fn = os.path.join(folder, f'live_{n}_{run}.npz')
        if not os.path.exists(fn): continue
        try: C[n] = unpack(np.load(fn), n)
        except Exception as e: print('consensus: cannot read', fn, repr(e)[:150], flush=True)
    return align(C, ref)

# ------------------------------------------------------------------ core
def _wrms(d, w, m):
    m = m & np.isfinite(d)
    return float(np.sqrt(np.sum(w[m] * d[m] ** 2) / np.sum(w[m]))) if m.any() else np.nan

def _check(A, names, v, lev, above, w, z_max, z_point, min_cover, dropped, zrec):
    """A [centre, lat, lon] (modified: impossible / masked points -> NaN). Returns the keep flag per centre."""
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning); return _check1(A, names, v, lev, above, w, z_max, z_point, min_cover, dropped, zrec)
def _check1(A, names, v, lev, above, w, z_max, z_point, min_cover, dropped, zrec):
    nC = len(names); keep = np.ones(nC, bool); lo, hi = bounds(v, lev); nab = max(1, int(above.sum()))
    for c in range(nC):
        a = A[c]; bad = np.isfinite(a) & ((a < lo) | (a > hi))
        if bad[above].sum() > 0.02 * nab: keep[c] = False; dropped.append((names[c], v, lev, 'bounds', round(float(bad[above].mean()), 4)))
        a[bad] = np.nan
        if keep[c]:
            cov = float(np.isfinite(a[above]).mean()) if above.any() else 0.0
            if cov < min_cover: keep[c] = False; dropped.append((names[c], v, lev, 'nan', round(cov, 4)))
    ok = [c for c in range(nC) if keep[c]]
    if len(ok) >= 3:
        P = {}
        for i in ok:
            for j in ok:
                if i < j: P[i, j] = P[j, i] = _wrms(A[i] - A[j], w, above)
        flag = []
        for c in ok:
            oth = [o for o in ok if o != c]; med = np.nanmedian(A[oth], 0)
            s = max(float(np.nanmedian([P[i, j] for i in oth for j in oth if i < j])), FLOOR.get(v, 0.0))
            z = _wrms(A[c] - med, w, above) / s; zrec[(names[c], v, lev)] = round(z, 2)
            if not np.isfinite(z) or z > z_max: flag.append((c, z))
            elif z_point:
                far = np.isfinite(A[c]) & (np.abs(A[c] - med) > z_point * s)
                if far.any(): A[c][far] = np.nan; dropped.append((names[c], v, lev, 'points', int(far.sum())))
        if len(flag) < len(ok) - 1:                                                           # never throw out a majority
            for c, z in flag: keep[c] = False; dropped.append((names[c], v, lev, 'outlier', round(float(z), 1)))
        elif flag: dropped.append(('-', v, lev, 'no majority, all kept', [names[c] for c, _ in flag]))
    return keep

def ps_from_profile(phi, T, levs, phis):
    """pressure (Pa) where a geopotential profile [lev, ...] meets phis (log-p between levels; hypsometric below the lowest)."""
    p = np.asarray(levs, float) * 100.0; o = np.argsort(-p); p, ph, t = p[o], phi[o], T[o]
    ps = np.where(phis <= ph[0], p[0] * np.exp((ph[0] - phis) / (RD * np.maximum(t[0], 180.0))), np.nan)
    for k in range(len(p) - 1):
        a, b = ph[k], ph[k + 1]; m = (phis > a) & (phis <= b) & np.isnan(ps)
        wk = (phis - a) / np.where(b - a == 0, 1.0, b - a); ps = np.where(m, np.exp(np.log(p[k]) + wk * (np.log(p[k + 1]) - np.log(p[k]))), ps)
    return ps

def consensus(C, weights=None, ref='GFSM', z_max=4.0, z_point=None, min_cover=0.98, region=(0.0, 30.0, 60.0, 100.0)):
    """C: {centre: dict} from load_centres (or unpack/align). weights: {centre: w} (default 1 each)."""
    if not C: raise ValueError('no centre files')
    names = list(C); rn = ref if ref in C else names[0]; R = C[rn]
    v3, levs, lats, lons = R['v3'], R['levs'], R['lats'], R['lons']; nC = len(names); ny, nx = len(lats), len(lons)
    W = np.array([float((weights or {}).get(n, 1.0)) for n in names])
    w = np.repeat(np.cos(np.radians(lats))[:, None], nx, 1); dropped = []; zrec = {}
    pss = [C[n]['surface_pressure'] for n in names if C[n].get('surface_pressure') is not None]
    ps_med = np.nanmedian(np.stack(pss), 0) if pss else np.full((ny, nx), 101325.0)
    ps_med = np.where(np.isfinite(ps_med), ps_med, 101325.0)
    X = np.stack([C[n]['f3'] for n in names]).astype(np.float64)                               # [centre, var, lev, lat, lon] (a copy)
    KEEP = np.zeros((nC, len(v3), len(levs)), bool)
    for i, v in enumerate(v3):
        for k, lev in enumerate(levs):
            above = lev * 100.0 <= ps_med
            if above.sum() < 10: above = np.ones((ny, nx), bool)
            KEEP[:, i, k] = _check(X[:, i, k], names, v, lev, above, w, z_max, z_point, min_cover, dropped, zrec)
    V = KEEP[:, :, :, None, None] & np.isfinite(X)                                             # usable points
    num = np.einsum('c,cvlyx->vlyx', W, np.where(V, X, 0.0)); den = np.einsum('c,cvlyx->vlyx', W, V.astype(float))
    M = np.where(den > 0, num / np.where(den > 0, den, 1.0), C[rn]['f3'])                       # nowhere usable -> the reference
    holes = int((den == 0).sum())
    if 'specific_humidity' in v3: M[v3.index('specific_humidity')] = np.maximum(M[v3.index('specific_humidity')], 0.0)
    D = np.where(V, X - M[None], 0.0).astype(np.float32)
    # ---- surface pressure on the reference terrain
    zs_ref = R.get('geopotential_at_surface'); ps_ref = R.get('surface_pressure'); iT, iZ = v3.index('temperature'), v3.index('geopotential')
    PS = np.full((nC, ny, nx), np.nan); rc = names.index(rn)
    full = lambda c: KEEP[c, iT].all() and KEEP[c, iZ].all() and np.isfinite(X[c, iZ]).all() and np.isfinite(X[c, iT]).all()
    prof = lambda c, zs: ps_from_profile(X[c, iZ], X[c, iT], levs, zs)
    ratio_ref = (ps_ref / prof(rc, zs_ref)) if (ps_ref is not None and zs_ref is not None and full(rc)) else None
    for c, n in enumerate(names):
        own, zs = C[n].get('surface_pressure'), C[n].get('geopotential_at_surface')
        if n == rn or zs_ref is None: PS[c] = own if own is not None else np.nan
        elif own is not None and zs is not None:                                                  # own ps, moved to the reference terrain
            PS[c] = own * (prof(c, zs_ref) / prof(c, zs) if full(c) else np.exp((zs - zs_ref) / (RD * 285.0)))
        elif full(c) and ratio_ref is not None: PS[c] = prof(c, zs_ref) * ratio_ref              # no terrain (ECMWF): its profile at the
        elif own is not None: PS[c] = np.where(np.abs(zs_ref) < 300 * G, own, np.nan)          # reference terrain; else low ground only
    allp = np.ones((ny, nx), bool)
    kps = _check(PS, names, 'surface_pressure', None, allp, w, z_max, z_point, 0.5, dropped, zrec)
    VP = kps[:, None, None] & np.isfinite(PS); dp = np.einsum('c,cyx->yx', W, VP.astype(float))
    PSM = np.where(dp > 0, np.einsum('c,cyx->yx', W, np.where(VP, PS, 0.0)) / np.where(dp > 0, dp, 1.0), ps_ref if ps_ref is not None else np.nan)
    DPS = np.where(VP, PS - PSM[None], 0.0).astype(np.float32)
    # ---- sea temperature: mean on the reference's sea points; land mask and terrain from the reference
    sst = np.full((nC, ny, nx), np.nan)
    for c, n in enumerate(names):
        if C[n].get('sea_surface_temperature') is not None: sst[c] = C[n]['sea_surface_temperature']
    has = [c for c in range(nC) if np.isfinite(sst[c]).any()]
    sea_ref = np.isfinite(R['sea_surface_temperature']) if R.get('sea_surface_temperature') is not None else np.ones((ny, nx), bool)
    SSTM = np.full((ny, nx), np.nan)
    if has:
        S = sst[has]; ks = _check(S, [names[c] for c in has], 'sea_surface_temperature', None, sea_ref, w, z_max, None, 0.5, dropped, zrec)
        VS = ks[:, None, None] & np.isfinite(S); Ws = W[has]; ds = np.einsum('c,cyx->yx', Ws, VS.astype(float))
        SSTM = np.where(sea_ref & (ds > 0), np.einsum('c,cyx->yx', Ws, np.where(VS, S, 0.0)) / np.where(ds > 0, ds, 1.0), np.nan)
    f2 = {'surface_pressure': PSM, 'sea_surface_temperature': SSTM,
          'land_sea_mask': R.get('land_sea_mask'), 'geopotential_at_surface': zs_ref}
    used = [n for c, n in enumerate(names) if KEEP[c].any()]
    CN = dict(f3={v: M[i] for i, v in enumerate(v3)}, f2=f2, diffs={n: {v: D[c, i] for i, v in enumerate(v3)} for c, n in enumerate(names) if n in used},
              ps_diffs={n: DPS[c] for c, n in enumerate(names) if n in used}, used=used, ref=rn, dropped=dropped, z=zrec, holes=holes,
              weights={n: float(W[c]) for c, n in enumerate(names)}, v3=list(v3), v2=list(V2), levs=list(levs), lats=lats, lons=lons,
              sources={n: C[n].get('source', n) for n in names}, times=C[rn].get('times'))
    CN['report'] = spread_report(CN, region)
    return CN

def spread_report(CN, region=(0.0, 30.0, 60.0, 100.0)):
    """area-weighted RMS spread of the centres about the consensus (and each centre's RMS difference) over the region
    (lat0, lat1, lon0, lon1), above ground (consensus surface pressure), in display units."""
    lats, lons = np.asarray(CN['lats']), np.asarray(CN['lons']); la0, la1, lo0, lo1 = region
    box = ((lats >= la0) & (lats <= la1))[:, None] & ((lons >= lo0) & (lons <= lo1))[None, :]
    w = np.cos(np.radians(lats))[:, None] * np.ones((1, len(lons))); ps = CN['f2']['surface_pressure']; rows = []
    def one(name, lev, diffs):
        sc, unit = SHOW.get(name, (1.0, '')); m = box & (np.isfinite(ps) & (lev * 100.0 <= ps) if lev is not None else True)
        if not m.any(): return None
        per = {}; num = np.zeros_like(w); den = np.zeros_like(w)
        for c, d in diffs.items():
            used = d != 0
            if not (used & m).any(): continue
            per[c] = round(_wrms(d * sc, w, m & used), 4); num += CN['weights'].get(c, 1.0) * np.where(used, (d * sc) ** 2, 0.0); den += CN['weights'].get(c, 1.0) * used
        v = np.where(den > 0, num / np.where(den > 0, den, 1.0), np.nan); mm = m & np.isfinite(v)
        spread = round(float(np.sqrt(np.sum(w[mm] * v[mm]) / np.sum(w[mm]))), 4) if mm.any() else None
        return dict(var=name, lev=lev, unit=unit, spread=spread, n=len(per), by_centre=per)
    for v in CN['v3']:
        for k, lev in enumerate(CN['levs']):
            r = one(v, lev, {c: CN['diffs'][c][v][k] for c in CN['diffs']})
            if r: rows.append(r)
    r = one('surface_pressure', None, CN['ps_diffs'])
    if r: rows.append(r)
    return dict(region=list(region), centres=CN['used'], ref=CN['ref'], weights=CN['weights'], rows=rows,
                dropped=[list(d) for d in CN['dropped']], z={f'{a} {b} {c}': z for (a, b, c), z in CN['z'].items()}, holes=CN['holes'])

def report_text(rep):
    L = [f"centres {', '.join(rep['centres'])} (reference {rep['ref']}); spread over {rep['region'][0]:g}-{rep['region'][1]:g}N "
         f"{rep['region'][2]:g}-{rep['region'][3]:g}E"]
    for r in rep['rows']:
        L.append(f"{r['var']:<22}{'' if r['lev'] is None else r['lev']:>5} spread {r['spread'] if r['spread'] is not None else '-':>8} {r['unit']:<5} "
                 + ' '.join(f'{c} {x:.3g}' for c, x in r['by_centre'].items()))
    for d in rep['dropped']: L.append('not used: ' + ' '.join(str(x) for x in d))
    if rep.get('holes'): L.append(f"points with no usable centre (reference kept): {rep['holes']}")
    return '\n'.join(L)

# ------------------------------------------------------------------ ensemble starts
def member_start(CN, k, scale=1.0, seed=2026):
    """member k's start: consensus mean + scale * sum_c eps_c (centre_c - mean) / sqrt(n - 1), eps ~ N(0, 1) (seeded by k) -
    a random draw with the covariance of the centres about their mean. k = 0, or fewer than 2 centres: the mean."""
    f3 = {v: np.array(a, np.float64) for v, a in CN['f3'].items()}; ps = np.array(CN['f2']['surface_pressure'], np.float64)
    cs = list(CN['diffs']); n = len(cs)
    if k == 0 or n < 2: return f3, ps
    c = scale * np.random.default_rng(seed + int(k)).standard_normal(n) / np.sqrt(n - 1)
    for j, cn in enumerate(cs):
        for v in f3: f3[v] += c[j] * CN['diffs'][cn][v]
        ps += c[j] * CN['ps_diffs'][cn]
    if 'specific_humidity' in f3: f3['specific_humidity'] = np.maximum(f3['specific_humidity'], 0.0)
    return f3, ps

def centre_start(CN, centre, a=1.0):
    """consensus mean + a * (centre - mean); a = 1 gives that centre's own fields where they were used."""
    f3 = {v: np.array(x, np.float64) + a * CN['diffs'][centre][v] for v, x in CN['f3'].items()}
    if 'specific_humidity' in f3: f3['specific_humidity'] = np.maximum(f3['specific_humidity'], 0.0)
    return f3, np.array(CN['f2']['surface_pressure'], np.float64) + a * CN['ps_diffs'][centre]

def save_livem(CN, path, run_time=None):
    """the consensus as a live_GFSM-format file (usable as LIVEM by live.py / live2.py)."""
    nan = np.full((len(CN['lats']), len(CN['lons'])), np.nan, np.float32)
    f3 = np.stack([CN['f3'][v] for v in CN['v3']]).astype(np.float32); f2 = np.stack([nan if CN['f2'][v] is None else np.asarray(CN['f2'][v], np.float32) for v in V2])
    t = np.array([run_time]) if run_time else (np.asarray(CN['times']) if CN.get('times') is not None else np.array(['']))
    np.savez_compressed(path, f3=f3[None], f2=f2[None], times=t, lats=CN['lats'], lons=CN['lons'], v3=np.array(CN['v3']), v2=np.array(V2),
                        levs=np.array(CN['levs']), source='consensus ' + ' '.join(CN['used']))
    return path

if __name__ == '__main__':                                       # python consensus.py FOLDER RUN [OUT_NPZ]  -> report (+ consensus file)
    folder, run = sys.argv[1], sys.argv[2]; CN = consensus(load_centres(folder, run)); print(report_text(CN['report']))
    if len(sys.argv) > 3: save_livem(CN, sys.argv[3]); print('saved', sys.argv[3])
