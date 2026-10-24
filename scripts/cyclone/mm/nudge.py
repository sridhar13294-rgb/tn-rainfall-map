"""Observations into the model's start: observation operator, optimal-interpolation (OI) analysis of the starting fields,
and latent-heat nudging (LHN) for the first forecast hours.

numpy throughout (the OI runs once per forecast, on CPU, before Model.init). The observation operator and the LHN
functions take an array module `xp` (numpy or jax.numpy) and use no in-place writes, so they also run inside jit.

Observations come from scripts/cyclone/obs_fetch.py (obs_<run>.npz; load_obs below). Units inside: Pa, K, kg/kg, m/s, m.

1. Observation operator  H(x): model fields -> observation space
   horizontal: bilinear on the (Gaussian or regular) lat/lon grid (periodic in longitude);
   vertical:   linear in log(pressure); no extrapolation (values beyond the end levels are held);
   MSLP:       ps * exp(g zs / (Rd (T_low + 0.0065 zs / 2))) - exactly mm2.run's post();
   surface:    T, q and wind at the lowest model level (sigma 0.99, ~85 m), T corrected by 6.5 K/km for the height
               difference between that level and the station; 10-m wind = 0.85 x lowest-level wind (sea).
2. OI analysis (oi_analysis): innovations d = y - H(xb) -> increments for T, q, u, v on the pressure levels and for the
   surface pressure, to add to the 4-centre consensus fields before Model.init. Univariate (no wind-mass balance; the
   model's digital filter removes the resulting gravity-wave noise), Gaussian horizontal and vertical correlations,
   background errors by variable and level (optionally raised to the spread among the centres), observation errors by
   type, gross-error check, superobbing. Local solves in 10 x 10 degree boxes with a halo.
3. LHN (lhn_*): heating/moistening tendencies that pull the model's rain toward observed rain (satellite rain, with
   lightning as a proxy where the satellite has none), for the lead to add in the time loop during the first hours.

Numbers (errors, length scales) and where they come from: docs/obs_assimilation.md."""
import math, json, numpy as np

G, RD, RV, CP, LV = 9.80616, 287.04, 461.5, 1004.6, 2.5e6
REARTH = 6371.0                                                     # km
STD_LEVS = (1000, 925, 850, 700, 500, 400, 300, 250, 200, 150, 100, 50)

# =============================================================================================== errors
# Observation error standard deviations (total = instrument + representativeness for a ~150 km grid). Same order as the
# NCEP GSI conventional error table and ECMWF's (radiosonde T ~1-1.5 K, winds 2-3 m/s, surface pressure ~1 hPa,
# scatterometer ~1.5-2 m/s); rounded, to be re-tuned from our own O-B statistics (docs/obs_assimilation.md).
def _prof(p_hpa, table):
    """piecewise-linear in log p through {level hPa: value}."""
    lv = np.array(sorted(table), float); val = np.array([table[k] for k in sorted(table)], float)
    return np.interp(np.log(np.clip(np.asarray(p_hpa, float), lv[0], lv[-1])), np.log(lv), val)
SONDE_T = {1000: 1.3, 850: 1.1, 700: 1.0, 500: 0.9, 300: 1.0, 250: 1.1, 200: 1.2, 150: 1.3, 100: 1.5, 50: 1.6}
SONDE_UV = {1000: 2.2, 850: 2.3, 700: 2.4, 500: 2.7, 400: 2.9, 300: 3.1, 250: 3.2, 200: 3.1, 150: 2.9, 100: 2.6, 50: 2.6}
SONDE_Z = {1000: 8.0, 850: 9.0, 700: 11.0, 500: 14.0, 300: 20.0, 200: 26.0, 100: 35.0, 50: 45.0}
OBS_ERR_SFC = {                                                     # type -> var -> sigma (SI); None = not used by default
    'synop': dict(mslp=100.0, ps=100.0, t=2.0, td=1.6, u=3.0, v=3.0),
    'metar': dict(mslp=120.0, ps=120.0, t=2.0, td=1.8, u=3.0, v=3.0),
    'ship':  dict(mslp=160.0, ps=160.0, t=2.0, td=2.0, u=2.6, v=2.6),
    'buoy':  dict(mslp=100.0, ps=100.0, t=1.5, td=2.0, u=2.4, v=2.4),
    'scat':  dict(u=1.8, v=1.8)}
Q_REL_ERR = {'synop': 0.11, 'metar': 0.12, 'ship': 0.13, 'buoy': 0.13, 'temp': 0.10}   # q error as a fraction of qsat
TIME_ERR = dict(mslp=30.0, ps=30.0, t=0.25, td=0.3, u=0.5, v=0.5, z=3.0, q=0.02)          # added per hour from the analysis time

def obs_error(typ, var, p_hpa=None, z_m=None):
    """sigma_o for one observation (SI units of var; for 'q' a fraction of qsat). Station height raises pressure errors."""
    if typ == 'temp':
        p = 500.0 if p_hpa is None or not np.isfinite(p_hpa) else float(p_hpa)
        if var == 't': return float(_prof(p, SONDE_T))
        if var in ('u', 'v'): return float(_prof(p, SONDE_UV))
        if var == 'z': return float(_prof(p, SONDE_Z))
        if var == 'td': return 2.0 if p >= 500 else 4.0
        if var == 'q': return Q_REL_ERR['temp']
        return float('nan')
    if var == 'q': return Q_REL_ERR.get(typ, 0.12)
    e = OBS_ERR_SFC.get(typ, {}).get(var)
    if e is None: return float('nan')
    if var in ('mslp', 'ps') and z_m is not None and np.isfinite(z_m) and z_m > 0:
        e = e + 100.0 * z_m / 1000.0                                # reduction to sea level gets worse with height
    return float(e)

# Background error standard deviations by level. 'analysis': the background is the consensus of other centres' analyses
# (analysis-error size, ~0.6-0.7 of a 6-h forecast error); 'forecast6h': when we cycle our own 6-h forecast.
SIGB = {
    'analysis': dict(t={1000: 0.9, 850: 0.7, 700: 0.6, 500: 0.55, 300: 0.7, 250: 0.8, 200: 0.9, 150: 1.0, 100: 1.1, 50: 1.2},
                     uv={1000: 1.5, 850: 1.6, 700: 1.6, 500: 1.8, 400: 2.0, 300: 2.4, 250: 2.6, 200: 2.6, 150: 2.4, 100: 2.2, 50: 2.2},
                     q_rel=0.08, ps=60.0),
    'forecast6h': dict(t={1000: 1.2, 850: 1.0, 700: 0.9, 500: 0.8, 300: 1.0, 250: 1.1, 200: 1.2, 150: 1.3, 100: 1.4, 50: 1.5},
                       uv={1000: 2.0, 850: 2.3, 700: 2.3, 500: 2.6, 400: 2.9, 300: 3.3, 250: 3.5, 200: 3.5, 150: 3.2, 100: 2.9, 50: 2.8},
                       q_rel=0.12, ps=100.0)}

def sigma_b_profile(var, p_hpa, table='analysis'):
    """sigma_b for T (K), u/v (m/s) at pressure p_hpa; for q a fraction of qsat; for ps Pa."""
    S = SIGB[table]
    if var == 't': return _prof(p_hpa, S['t'])
    if var in ('u', 'v'): return _prof(p_hpa, S['uv'])
    if var == 'q': return np.full(np.shape(p_hpa), S['q_rel'])
    if var == 'ps': return np.full(np.shape(p_hpa), S['ps'])
    raise KeyError(var)

def sigma_b_from_spread(diffs, var3, levs, ps_diffs=None, factor=1.0, smooth=1.0):
    """flow-dependent sigma_b from the spread among the centres (consensus.py: diffs = {centre: {v3 name: [lev, lat, lon]}},
    ps_diffs = {centre: [lat, lon]}): sqrt(mean over centres of diff^2) x factor, smoothed (gaussian, `smooth` grid cells).
    Returns {'t','q','u','v': [lev, lat, lon], 'ps': [lat, lon]} (q in kg/kg, not relative) or {} without centres."""
    from scipy import ndimage as ndi
    if not diffs: return {}
    out = {}; names = dict(t='temperature', q='specific_humidity', u='u_component_of_wind', v='v_component_of_wind')
    for k, vn in names.items():
        arr = [np.asarray(d[vn], float) for d in diffs.values() if vn in d]
        if not arr: continue
        s = np.sqrt(np.mean([np.nan_to_num(a) ** 2 for a in arr], 0)) * factor
        out[k] = ndi.gaussian_filter(s, (0, smooth, smooth), mode=('nearest', 'nearest', 'wrap'))
    if ps_diffs:
        s = np.sqrt(np.mean([np.nan_to_num(np.asarray(a, float)) ** 2 for a in ps_diffs.values()], 0)) * factor
        out['ps'] = ndi.gaussian_filter(s, smooth, mode=('nearest', 'wrap'))
    return out

# =============================================================================================== thermodynamics
def qsat(T, p, xp=np):
    """saturation specific humidity (kg/kg); T K, p Pa (same formula as mm2.qsat)."""
    es = 611.2 * xp.exp(17.67 * (T - 273.15) / (T - 29.65)); return 0.622 * es / xp.maximum(p - 0.378 * es, 1.0)
def q_from_td(Td, p):
    """specific humidity from dew point (K) and pressure (Pa)."""
    return qsat(np.asarray(Td, float), np.asarray(p, float))
def mslp_from_ps(ps, T_low, zs, xp=np):
    """mean-sea-level pressure as mm2.run's post(): ps * exp(g zs / (Rd (T_low + 0.0065 zs / 2)))."""
    return ps * xp.exp(G * zs / (RD * (T_low + 0.0065 * zs / 2)))

# =============================================================================================== observation operator
class HGrid:
    """horizontal bilinear weights from a lat/lon grid (1-D axes; any monotonic latitudes - Gaussian or regular -
    and longitudes increasing, periodic) to observation points. Built once with numpy; apply() works with numpy or jax
    arrays whose last two axes are (lat, lon) (layout='latlon', the pressure-level files) or (lon, lat) (layout='lonlat',
    mm2's nodal arrays)."""
    def __init__(self, lats, lons, olat, olon, layout='latlon'):
        lats = np.asarray(lats, float); lons = np.asarray(lons, float) % 360.0; self.layout = layout
        self.ny, self.nx = len(lats), len(lons)
        asc = lats[0] < lats[-1]; la = lats if asc else lats[::-1]
        olat = np.clip(np.asarray(olat, float), la[0], la[-1]); olon = np.asarray(olon, float) % 360.0
        j1 = np.clip(np.searchsorted(la, olat), 1, len(la) - 1); j0 = j1 - 1
        wy = (olat - la[j0]) / np.maximum(la[j1] - la[j0], 1e-9)
        if not asc: j0, j1 = len(la) - 1 - j0, len(la) - 1 - j1
        order = np.argsort(lons); lo = lons[order]; ext = np.concatenate([lo, [lo[0] + 360.0]])
        o = np.where(olon < lo[0], olon + 360.0, olon)
        i1 = np.clip(np.searchsorted(ext, o, side='right'), 1, len(ext) - 1); i0 = i1 - 1
        wx = (o - ext[i0]) / np.maximum(ext[i1] - ext[i0], 1e-9)
        i0 = order[i0 % len(lo)]; i1 = order[i1 % len(lo)]
        self.idx = [(j0, i0), (j0, i1), (j1, i0), (j1, i1)]
        self.w = [(1 - wy) * (1 - wx), (1 - wy) * wx, wy * (1 - wx), wy * wx]
        self.n = len(olat)
    def flat(self):
        """flat indices (into a lat x lon or lon x lat field) and weights: 4 x n each."""
        if self.layout == 'latlon': fi = [j * self.nx + i for j, i in self.idx]
        else: fi = [i * self.ny + j for j, i in self.idx]
        return np.stack(fi), np.stack(self.w)
    def apply(self, F, xp=np):
        """F [..., Y, X] -> [..., n]."""
        fi, w = self.flat(); sh = F.shape[:-2]; Ff = xp.reshape(F, sh + (-1,))
        return sum(xp.take(Ff, xp.asarray(fi[k]), axis=-1) * xp.asarray(w[k], Ff.dtype if hasattr(Ff, 'dtype') else None) for k in range(4))

def interp_logp(col, pcol, pobs, xp=np):
    """col, pcol [L, n] (levels ordered top -> bottom, pressure increasing; pcol in the same units as pobs) -> [n].
    Linear in log p; outside the column the end value is held."""
    lp = xp.log(pcol); lt = xp.log(pobs)[None]
    idx = xp.sum(lp < lt, axis=0); L = col.shape[0]
    k1 = xp.clip(idx, 1, L - 1); k0 = k1 - 1
    g = lambda X, k: xp.take_along_axis(X, k[None], axis=0)[0]
    w = xp.clip((lt[0] - g(lp, k0)) / (g(lp, k1) - g(lp, k0)), 0.0, 1.0)
    return g(col, k0) + w * (g(col, k1) - g(col, k0))

SIG_LOW = 0.99                     # the lowest model level (mm2: 32 levels, lowest layer centre ~0.990)
Z_LOW = 85.0                       # its height above the ground (m), for the surface temperature correction
WIND10 = 0.85                      # 10-m wind / lowest-level wind over sea (as mm2's tracker)
LAPSE = 0.0065

def model_equivalents(fields, lats, lons, obs, p3=None, sig=None, layout='latlon', xp=np, wind10=WIND10):
    """H(x) for every observation.
    fields: dict t, q, u, v [L, Y, X] (or [L, X, Y] with layout='lonlat'), ps [Y, X] (Pa), zs [Y, X] (m), optional zg [L, Y, X]
            (geopotential height, m; for radiosonde heights - monitoring only).
    vertical coordinate: p3 [L] or [L, Y, X] in Pa (pressure levels), or sig [L] (sigma levels: p = sig * ps).
    obs: dict of arrays lat, lon, var, type, p (hPa; NaN for surface), z (station height m).
    Returns dict hx [n] (NaN where not defined), plus psb, zsb, Tlow, plow at the obs points (for the analysis)."""
    H = HGrid(lats, lons, obs['lat'], obs['lon'], layout)
    psb = H.apply(fields['ps'], xp); zsb = H.apply(fields['zs'], xp)
    if sig is not None: pcol = xp.asarray(sig)[:, None] * psb[None]
    elif np.ndim(p3) == 1: pcol = xp.asarray(p3, float)[:, None] * xp.ones_like(psb)[None]
    else: pcol = H.apply(p3, xp)
    cols = {k: H.apply(fields[k], xp) for k in ('t', 'q', 'u', 'v') if k in fields}
    if 'zg' in fields: cols['z'] = H.apply(fields['zg'], xp)
    plow = SIG_LOW * psb
    low = {k: interp_logp(c, pcol, plow, xp) for k, c in cols.items()}
    Tlow = low['t']; mslp = mslp_from_ps(psb, Tlow, zsb, xp)
    var = np.asarray(obs['var']).astype(str); typ = np.asarray(obs['type']).astype(str)
    pob = np.asarray(obs['p'], float) * 100.0; zob = np.nan_to_num(np.asarray(obs['z'], float), nan=0.0)
    upper = (typ == 'temp') & np.isfinite(pob)
    pq = xp.asarray(np.where(upper, pob, 1.0e5))
    up = {k: interp_logp(c, pcol, pq, xp) for k, c in cols.items()}
    hx = xp.full(psb.shape, xp.nan)
    def put(mask, val):
        return xp.where(xp.asarray(mask), val, hx)
    zstn = xp.asarray(zob)
    hx = put(var == 'mslp', mslp)
    hx = put(var == 'ps', psb * xp.exp(-G * (zstn - zsb) / (RD * (Tlow + LAPSE * (zstn - zsb) / 2))))
    sfc_t = Tlow + LAPSE * (zsb + Z_LOW - zstn)
    hx = put((var == 't') & ~upper, sfc_t)
    hx = put((var == 't') & upper, up['t'])
    hx = put((var == 'q') & ~upper, low['q']); hx = put((var == 'q') & upper, up['q'])
    for k in ('u', 'v'):
        hx = put((var == k) & ~upper, wind10 * low[k]); hx = put((var == k) & upper, up[k])
    if 'z' in up: hx = put((var == 'z') & upper, up['z'])
    return dict(hx=hx, psb=psb, zsb=zsb, Tlow=Tlow, plow=plow, mslp=mslp, qlow=low['q'], Tup=up['t'])

# =============================================================================================== observations in
def load_obs(path):
    """obs_<run>.npz (obs_fetch.py) -> dict of arrays (records) + 'grids' (rain/lightning) + 'run'."""
    Z = np.load(path, allow_pickle=False); d = {k: Z[k] for k in Z.files}
    for k in ('type', 'var', 'sid'): d[k] = d[k].astype(str)
    return d

def _ang_km(la1, lo1, la2, lo2):
    """great-circle distance (km), broadcasting."""
    p1, p2 = np.radians(la1), np.radians(la2); dl = np.radians(lo2 - lo1)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * REARTH * np.arcsin(np.sqrt(np.clip(a, 0, 1)))

def _xyz(lat, lon):
    la, lo = np.radians(lat), np.radians(lon)
    return np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], -1) * REARTH

# =============================================================================================== OI settings
OI_DEFAULTS = dict(
    table='analysis',            # background error table: 'analysis' (consensus of analyses) or 'forecast6h' (own cycled forecast)
    spread_factor=1.0,           # sigma_b = max(table, spread_factor x centre spread) when sigb_spread is given
    L_sfc=300.0, L_up=500.0,     # horizontal Gaussian length scales (km): near the surface (p/ps >= 0.9) and aloft (p/ps <= 0.7)
    L_ps=300.0,
    Lv={'t': 0.25, 'q': 0.20, 'u': 0.30, 'v': 0.30},   # vertical Gaussian length scale in ln(p)
    gross=5.0,                   # reject |O-B| > gross x sqrt(sigma_o^2 + sigma_b^2)
    thin_deg=1.0,                # superob box (degrees) for surface data; radiosondes keep every station
    superob_corr=0.5,            # error of a superob of n obs: sigma_o^2 (c + (1 - c) / n)
    max_dt_h={'synop': 1.5, 'metar': 1.0, 'ship': 3.0, 'buoy': 3.0, 'temp': 3.0, 'scat': 3.0},
    max_dz_sfc=600.0,            # surface T/q/wind: reject if station and model terrain differ more (m)
    max_dz_p=800.0,              # surface pressure: same for pressure
    max_zstn_p=1500.0,           # pressure obs from stations higher than this are not used
    pressure_obs='mslp',         # which of a report's two pressures is analysed ('mslp' or 'ps' = station pressure); the other is monitored
    use_land_t2m=False,          # land screen temperature: diurnal/inversion biases vs the ~85 m lowest level -> off
    use_land_q2m=True,           # land screen humidity: used, low levels only
    use_land_wind=False,         # land 10-m winds: unrepresentative -> off (as ECMWF)
    use_ship_t=False,            # ship air temperature (deck heating) -> off
    q_top_hpa=300.0,             # no humidity analysis above this level
    box_deg=10.0, halo_L=2.6, max_obs_box=1500,
    region=None,                 # (lat0, lat1, lon0, lon1) to limit the analysed grid (None: wherever there are obs)
    q_cap=1.0,                   # analysed q <= q_cap x qsat
    debias_p=False,              # remove each report type's median pressure O-B before the analysis
)
VMAP3 = dict(t='temperature', q='specific_humidity', u='u_component_of_wind', v='v_component_of_wind')

def _L_of_s(s, cfg):
    """horizontal length scale (km) from p/ps (1 at the ground)."""
    return cfg['L_up'] + (cfg['L_sfc'] - cfg['L_up']) * np.clip((s - 0.7) / 0.2, 0.0, 1.0)

def _corr(X1, L1, lp1, X2, L2, lp2, Lv):
    """non-stationary Gaussian correlation (Paciorek-Schervish form in 3-D chord distance, so it stays positive definite
    with a length scale that varies with height) x Gaussian in ln p. X: [n, 3] km; L: [n] km; lp: [n] ln p (or None)."""
    d2 = ((X1[:, None, :] - X2[None, :, :]) ** 2).sum(-1); S = L1[:, None] ** 2 + L2[None, :] ** 2
    C = (2 * L1[:, None] * L2[None, :] / S) ** 1.5 * np.exp(-d2 / S)
    if lp1 is not None: C = C * np.exp(-(lp1[:, None] - lp2[None, :]) ** 2 / (2 * Lv ** 2))
    return C

# =============================================================================================== innovations
def innovations(f3, levs, lats, lons, ps, zs, obs, t0_unix=None, cfg=None, sigb_spread=None, land=None):
    """O-B for every usable observation, with QC. Returns dict of arrays (one row per accepted or rejected obs) and the
    background equivalents. f3: {v3 name: [lev, lat, lon]} (levs hPa, top -> bottom order not required), ps Pa, zs m."""
    cfg = dict(OI_DEFAULTS, **(cfg or {}))
    levs = np.asarray(levs, float); order = np.argsort(levs); lv = levs[order]
    fld = {k: np.asarray(f3[VMAP3[k]], float)[order] for k in VMAP3}
    if 'geopotential' in f3: fld['zg'] = np.asarray(f3['geopotential'], float)[order] / G
    fld['ps'] = np.asarray(ps, float); fld['zs'] = np.asarray(zs, float)
    n0 = len(obs['lat'])
    var = np.asarray(obs['var']).astype(str); typ = np.asarray(obs['type']).astype(str)
    # time window
    if t0_unix is None: t0_unix = float(np.median(obs['time'])) if n0 else 0.0
    dt_h = (np.asarray(obs['time'], float) - t0_unix) / 3600.0
    keep = np.array([abs(dt_h[i]) <= cfg['max_dt_h'].get(typ[i], 3.0) for i in range(n0)], bool) if n0 else np.zeros(0, bool)
    O = {k: np.asarray(obs[k])[keep] for k in ('lat', 'lon', 'p', 'z', 'value', 'type', 'var', 'sid', 'time')}
    O['type'] = O['type'].astype(str); O['var'] = O['var'].astype(str); O['sid'] = O['sid'].astype(str); dt_h = dt_h[keep]
    O['lon'] = O['lon'] % 360.0
    # one report per station / variable / level: the one closest to the analysis time
    key = np.array([f'{a}|{b}|{c}|{(round(float(d)) if (a == "temp" and np.isfinite(d)) else -1)}' for a, b, c, d in zip(O['type'], O['sid'], O['var'], O['p'])])
    best = {}
    for i, k in enumerate(key):
        if O['type'][i] == 'scat' or O['sid'][i] in ('', 'NIL'): best[(k, i)] = i; continue
        if k not in best or abs(dt_h[i]) < abs(dt_h[best[k]]): best[k] = i
    sel = np.array(sorted(best.values()), int)
    O = {k: v[sel] for k, v in O.items()}; dt_h = dt_h[sel]
    # td -> q (needs a pressure: the level, or the station pressure from the background)
    E = model_equivalents(fld, lats, lons, dict(O, var=np.where(O['var'] == 'td', 'q', O['var'])), p3=lv * 100.0)
    hx, psb, zsb, plow, Tlow = E['hx'], E['psb'], E['zsb'], E['plow'], E['Tlow']
    upper = (O['type'] == 'temp') & np.isfinite(O['p'].astype(float))
    pobs = np.where(upper, O['p'].astype(float) * 100.0, plow)                                    # Pa, where the obs acts
    val = O['value'].astype(float).copy(); avar = O['var'].copy()
    zst = np.nan_to_num(O['z'].astype(float), nan=0.0)
    p_stn = psb * np.exp(-G * (zst - zsb) / (RD * Tlow))
    istd = avar == 'td'
    val[istd] = q_from_td(val[istd], np.where(upper[istd], pobs[istd], p_stn[istd])); avar[istd] = 'q'
    d = val - hx
    # analysis variable and observation errors
    sig_o = np.array([obs_error(t, v, (p if np.isfinite(p) else None), z) for t, v, p, z in zip(O['type'], avar, O['p'].astype(float), zst)])
    Tb_obs = np.where(upper, E['Tup'], Tlow); qs_obs = qsat(Tb_obs, pobs)
    isq = avar == 'q'; sig_o = np.where(isq, sig_o * qs_obs, sig_o)
    sig_o = np.sqrt(sig_o ** 2 + (np.array([TIME_ERR.get(v, 0.0) for v in avar]) * np.where(isq, qs_obs, 1.0) * dt_h) ** 2)
    ana = np.where(np.isin(avar, ('mslp', 'ps')), 'ps', avar)
    # pressure obs act on the surface pressure: dps = d(mslp) * ps/mslp (or d(p_stn) * ps/p_stn)
    den = np.where((avar == 'ps') & np.isfinite(hx) & (hx > 0), hx, psb)
    scale = np.where(avar == 'mslp', psb / E['mslp'], np.where(avar == 'ps', psb / den, 1.0))
    d = d * scale; sig_o = sig_o * scale
    # background error at the obs
    sb = np.full(len(d), np.nan)
    for v in ('t', 'u', 'v'): m = ana == v; sb[m] = sigma_b_profile(v, pobs[m] / 100.0, cfg['table'])
    sb[isq] = sigma_b_profile('q', pobs[isq] / 100.0, cfg['table']) * qs_obs[isq]
    sb[ana == 'ps'] = SIGB[cfg['table']]['ps']
    if sigb_spread:
        H = HGrid(lats, lons, O['lat'], O['lon'])
        for v in ('t', 'q', 'u', 'v'):
            if v in sigb_spread:
                m = ana == v
                if m.any():
                    col = H.apply(np.asarray(sigb_spread[v], float)[order])[:, m]
                    pc = lv[:, None] * 100.0 * np.ones((1, m.sum()))
                    sb[m] = np.maximum(sb[m], cfg['spread_factor'] * interp_logp(col, pc, pobs[m]))
        if 'ps' in sigb_spread:
            m = ana == 'ps'; sb[m] = np.maximum(sb[m], cfg['spread_factor'] * H.apply(np.asarray(sigb_spread['ps'], float))[m])
    # QC
    why = np.full(len(d), '', dtype='<U12')
    marine =np.isin(O['type'], ('ship', 'buoy', 'scat'))
    why[avar == 'z'] = 'monitor'                                     # heights: monitoring only (univariate analysis of T)
    why[(why == '') & (~np.isfinite(d) | ~np.isfinite(sig_o))] = 'undefined'
    why[(why == '') & (avar == ('ps' if cfg['pressure_obs'] == 'mslp' else 'mslp'))] = 'monitor'   # one pressure per report
    sfc = ~upper
    why[(why == '') & sfc & (ana == 'ps') & ((zst > cfg['max_zstn_p']) | (np.abs(zst - zsb) > cfg['max_dz_p']))] = 'height'
    why[(why == '') & sfc & np.isin(ana, ('t', 'q', 'u', 'v')) & ~marine & (np.abs(zst - zsb) > cfg['max_dz_sfc'])] = 'height'
    why[(why == '') & sfc & (ana == 't') & ~marine & (not cfg['use_land_t2m'])] = 'off'
    why[(why == '') & sfc & (ana == 't') & marine & (not cfg['use_ship_t'])] = 'off'
    why[(why == '') & sfc & (ana == 'q') & ~marine & (not cfg['use_land_q2m'])] = 'off'
    why[(why == '') & sfc & np.isin(ana, ('u', 'v')) & ~marine & (not cfg['use_land_wind'])] = 'off'
    why[(why == '') & upper & (pobs > psb + 500.0)] = 'below_ground'
    why[(why == '') & (ana == 'q') & (pobs < cfg['q_top_hpa'] * 100.0)] = 'q_top'
    gross = np.abs(d) > cfg['gross'] * np.sqrt(sig_o ** 2 + sb ** 2)
    why[(why == '') & gross] = 'gross'
    # a wind component failing the check takes its partner with it
    for i in np.where(why == 'gross')[0]:
        if ana[i] in ('u', 'v'):
            j = np.where((O['sid'] == O['sid'][i]) & (O['type'] == O['type'][i]) & (ana == ('v' if ana[i] == 'u' else 'u'))
                         & (O['time'] == O['time'][i]) & (np.nan_to_num(O['p'].astype(float)) == np.nan_to_num(float(O['p'][i])))
                         & (O['lat'] == O['lat'][i]) & (O['lon'] == O['lon'][i]))[0]
            why[j[why[j] == '']] = 'gross'
    s_rel = pobs / psb
    return dict(lat=O['lat'].astype(float), lon=O['lon'].astype(float), p=pobs, s=s_rel, d=d, so=sig_o, sb=sb, ana=ana, var=avar,
                type=O['type'], sid=O['sid'], dt_h=dt_h, why=why, hx=hx, upper=upper, zst=zst, n_in=n0, n_window=int(keep.sum()))

def superob(I, cfg=None):
    """average accepted surface innovations of the same type class and analysis variable in thin_deg boxes (and the
    same pressure for radiosondes - each sounding level stays). Returns the reduced set (dict of arrays)."""
    cfg = dict(OI_DEFAULTS, **(cfg or {}))
    ok = I['why'] == ''; idx = np.where(ok)[0]; b = cfg['thin_deg']
    groups = {}
    for i in idx:
        if I['upper'][i]: k = ('up', I['sid'][i], I['ana'][i], round(I['p'][i] / 100.0))
        else:
            cls = 'scat' if I['type'][i] == 'scat' else ('sea' if I['type'][i] in ('ship', 'buoy') else 'land')
            k = (cls, I['ana'][i], int(np.floor(I['lat'][i] / b)), int(np.floor((I['lon'][i] % 360) / b)))
        groups.setdefault(k, []).append(i)
    rows = []
    c = cfg['superob_corr']
    for k, ii in groups.items():
        ii = np.asarray(ii); n = len(ii); w = 1.0 / I['so'][ii] ** 2
        X = _xyz(I['lat'][ii], I['lon'][ii]).mean(0); r = np.linalg.norm(X)
        la = math.degrees(math.asin(X[2] / r)); lo = math.degrees(math.atan2(X[1], X[0])) % 360
        so = math.sqrt(1.0 / w.sum() * n * (c + (1 - c) / n))
        rows.append((la, lo, float(np.exp(np.mean(np.log(I['p'][ii])))), float((I['d'][ii] * w).sum() / w.sum()), so,
                     float(I['sb'][ii].mean()), I['ana'][ii[0]], float(I['s'][ii].mean()), n, I['type'][ii[0]]))
    if not rows:
        return dict(lat=np.zeros(0), lon=np.zeros(0), p=np.zeros(0), d=np.zeros(0), so=np.zeros(0), sb=np.zeros(0), ana=np.zeros(0, '<U4'),
                    s=np.zeros(0), n=np.zeros(0, int), type=np.zeros(0, '<U6'))
    R = list(zip(*rows))
    return dict(lat=np.array(R[0]), lon=np.array(R[1]), p=np.array(R[2]), d=np.array(R[3]), so=np.array(R[4]), sb=np.array(R[5]),
                ana=np.array(R[6]), s=np.array(R[7]), n=np.array(R[8], int), type=np.array(R[9]))

# =============================================================================================== OI
def oi_solve(S, grid_lat, grid_lon, grid_p, grid_s, grid_sb, cfg, var):
    """increments on grid points (flat arrays: lat, lon, p (Pa) or None for 2-D, s = p/ps, sigma_b) from superobs S of
    one analysis variable. Local solves in box_deg boxes; obs within (box half-diagonal + halo_L x L) of the box centre."""
    cfg = dict(OI_DEFAULTS, **(cfg or {}))
    m = S['ana'] == var; n = int(m.sum()); inc = np.zeros(len(grid_lat))
    if n == 0: return inc, 0
    ola, olo, od, oso, osb = S['lat'][m], S['lon'][m], S['d'][m], S['so'][m], S['sb'][m]
    three = grid_p is not None
    oL = np.full(n, cfg['L_ps']) if var == 'ps' else _L_of_s(S['s'][m], cfg)
    oX = _xyz(ola, olo); olp = np.log(S['p'][m]) if three else None
    gL = np.full(len(grid_lat), cfg['L_ps']) if var == 'ps' else _L_of_s(grid_s, cfg)
    gX = _xyz(grid_lat, grid_lon); glp = np.log(grid_p) if three else None
    Lv = cfg['Lv'].get(var, 0.25); B = cfg['box_deg']; used = 0
    blat = np.floor((grid_lat + 90.0) / B).astype(int); blon = np.floor((grid_lon % 360.0) / B).astype(int)
    for key in sorted(set(zip(blat, blon))):
        gi = np.where((blat == key[0]) & (blon == key[1]))[0]
        cla = -90.0 + (key[0] + 0.5) * B; clo = (key[1] + 0.5) * B
        half = _ang_km(cla, clo, cla - B / 2, clo - B / 2)
        rad = half + cfg['halo_L'] * (cfg['L_ps'] if var == 'ps' else max(cfg['L_up'], cfg['L_sfc']))
        dist = _ang_km(cla, clo, ola, olo); oi = np.where(dist <= rad)[0]
        if len(oi) == 0: continue
        if len(oi) > cfg['max_obs_box']: oi = oi[np.argsort(dist[oi])[:cfg['max_obs_box']]]
        Coo = _corr(oX[oi], oL[oi], olp[oi] if three else None, oX[oi], oL[oi], olp[oi] if three else None, Lv)
        A = osb[oi][:, None] * osb[oi][None, :] * Coo + np.diag(oso[oi] ** 2)
        try:
            Lc = np.linalg.cholesky(A); w = np.linalg.solve(Lc.T, np.linalg.solve(Lc, od[oi]))
        except np.linalg.LinAlgError:
            w = np.linalg.lstsq(A, od[oi], rcond=None)[0]
        Cgo = _corr(gX[gi], gL[gi], glp[gi] if three else None, oX[oi], oL[oi], olp[oi] if three else None, Lv)
        inc[gi] = grid_sb[gi] * (Cgo @ (osb[oi] * w)); used += len(oi)
    return inc, n

def oi_analysis(f3, levs, lats, lons, ps, zs, obs, t0_unix=None, cfg=None, sigb_spread=None, verbose=False):
    """Optimal interpolation of observation-minus-background innovations onto the pressure-level start fields.
    f3: {temperature, specific_humidity, u_component_of_wind, v_component_of_wind[, geopotential]: [lev, lat, lon]},
    levs (hPa), lats, lons (1-D), ps [lat, lon] Pa, zs [lat, lon] m (terrain height), obs: load_obs() dict.
    sigb_spread: optional sigma_b_from_spread(...) result (flow-dependent background errors).
    Returns (inc {v3 name: [lev, lat, lon]}, dps [lat, lon] Pa, report dict). Add with apply_increments()."""
    cfg = dict(OI_DEFAULTS, **(cfg or {}))
    levs = np.asarray(levs, float); lats = np.asarray(lats, float); lons = np.asarray(lons, float)
    I = innovations(f3, levs, lats, lons, ps, zs, obs, t0_unix, cfg, sigb_spread)
    if cfg.get('debias_p', False):                                    # bias correction (as VarBC does for pressure): remove each report type's mean O-B
        I = dict(I); I['d'] = np.array(I['d'], float)
        for ty in np.unique(I['type']):
            m = (I['type'] == ty) & np.isin(I['ana'], ('ps', 'mslp')) & (I['why'] == '') & np.isfinite(I['d'])
            if m.sum() >= 20: b = float(np.median(I['d'][m])); I['d'][m] -= b; print(f'  OI pressure bias removed for {ty}: {b / 100:+.2f} hPa', flush=True)
    S = superob(I, cfg)
    ny, nx = len(lats), len(lons); LA, LO = np.meshgrid(lats, lons, indexing='ij')
    if cfg['region'] is not None:
        a0, a1, o0, o1 = cfg['region']; reg = (LA >= a0) & (LA <= a1) & (((LO - o0) % 360) <= ((o1 - o0) % 360))
    else:
        reg = np.zeros((ny, nx), bool)
        if len(S['lat']):                                            # grid points within reach of some observation
            from scipy.spatial import cKDTree
            near, _ = cKDTree(_xyz(S['lat'], S['lon'])).query(_xyz(LA.ravel(), LO.ravel()), k=1)   # chord km
            reg = (near <= cfg['halo_L'] * max(cfg['L_up'], cfg['L_sfc'], cfg['L_ps']) * 1.1).reshape(ny, nx)
    jj, ii = np.where(reg)
    inc = {VMAP3[v]: np.zeros((len(levs), ny, nx)) for v in ('t', 'q', 'u', 'v')}; dps = np.zeros((ny, nx))
    psa = np.asarray(ps, float); T = np.asarray(f3['temperature'], float)
    counts = {}
    if len(jj):
        # 2-D surface pressure
        sbps = np.full(len(jj), SIGB[cfg['table']]['ps'])
        if sigb_spread and 'ps' in sigb_spread: sbps = np.maximum(sbps, cfg['spread_factor'] * np.asarray(sigb_spread['ps'])[jj, ii])
        x, counts['ps'] = oi_solve(S, LA[jj, ii], LO[jj, ii], None, None, sbps, cfg, 'ps'); dps[jj, ii] = x
        # 3-D variables on every level
        K = len(levs); gl = np.repeat(LA[jj, ii][None], K, 0).ravel(); go = np.repeat(LO[jj, ii][None], K, 0).ravel()
        gp = (levs[:, None] * 100.0 * np.ones((1, len(jj)))).ravel(); gs = (gp.reshape(K, -1) / psa[jj, ii][None]).ravel()
        for v in ('t', 'q', 'u', 'v'):
            sb = np.repeat(sigma_b_profile(v if v != 'q' else 'q', levs, cfg['table'])[:, None], len(jj), 1)
            if v == 'q': sb = sb * qsat(T[:, jj, ii], levs[:, None] * 100.0) * (levs[:, None] >= cfg['q_top_hpa'])
            if sigb_spread and v in sigb_spread: sb = np.maximum(sb, cfg['spread_factor'] * np.asarray(sigb_spread[v])[:, jj, ii])
            x, counts[v] = oi_solve(S, gl, go, gp, gs, sb.ravel(), cfg, v)
            a = inc[VMAP3[v]]; a[:, jj, ii] = x.reshape(K, -1)
    # report: O-B and O-A by type and variable
    A = apply_increments(dict(f3=f3, ps=ps, levs=levs), inc, dps, cfg)
    Ia = innovations(A['f3'], levs, lats, lons, A['ps'], zs, obs, t0_unix, cfg, sigb_spread)
    rep = report(I, Ia, S, counts)
    if verbose: print(report_text(rep), flush=True)
    return inc, dps, rep

def apply_increments(state, inc, dps, cfg=None):
    """state: dict(f3={v3 name: [lev, lat, lon]}, ps=[lat, lon]) -> new dict with increments added (q kept between 0 and
    q_cap x qsat; the geopotential field is left as it is - Model.init does not use it)."""
    cfg = dict(OI_DEFAULTS, **(cfg or {}))
    f3 = {k: np.array(v, float) for k, v in state['f3'].items()}
    for k, a in inc.items():
        if k in f3: f3[k] = f3[k] + np.nan_to_num(a)
    ps =np.asarray(state['ps'], float) + np.nan_to_num(dps)
    out = dict(state); out['f3'] = f3; out['ps'] = ps
    if 'specific_humidity' in f3:
        f3['specific_humidity'] = np.maximum(f3['specific_humidity'], 0.0)
        levs = state.get('levs')
        if levs is not None:
            qs = qsat(f3['temperature'], np.asarray(levs, float)[:, None, None] * 100.0)
            f3['specific_humidity'] = np.minimum(f3['specific_humidity'], cfg['q_cap'] * qs)
    return out

def apply_to_consensus(CN, inc, dps, cfg=None):
    """consensus.py's CN dict -> the same dict with the analysed mean (member_start then perturbs around it)."""
    st = apply_increments(dict(f3=CN['f3'], ps=CN['f2']['surface_pressure'], levs=CN['levs']), inc, dps, cfg)
    CN2 = dict(CN); CN2['f3'] = st['f3']; f2 = dict(CN['f2']); f2['surface_pressure'] = st['ps']; CN2['f2'] = f2
    CN2['obs_analysis'] = True
    return CN2

def analyse_consensus(CN, obs_path, t0, cfg=None, use_spread=True, verbose=True):
    """one call for live2.py: CN (consensus.consensus()) + obs_<run>.npz -> (CN with the analysed mean, report).
    t0: datetime (UTC) of the start. Returns (CN, None) unchanged if the file is missing or has no observations."""
    import os, calendar
    if not obs_path or not os.path.exists(obs_path): return CN, None
    ob = load_obs(obs_path)
    if len(ob['lat']) == 0: return CN, None
    zs = np.asarray(CN['f2']['geopotential_at_surface'], float) / G
    sp = sigma_b_from_spread(CN.get('diffs'), None, CN['levs'], CN.get('ps_diffs')) if use_spread else None
    inc, dps, rep = oi_analysis(CN['f3'], CN['levs'], CN['lats'], CN['lons'], CN['f2']['surface_pressure'], zs, ob,
                                t0_unix=calendar.timegm(t0.timetuple()), cfg=cfg, sigb_spread=sp, verbose=verbose)
    return apply_to_consensus(CN, inc, dps, cfg), rep

def centre_fit(CN, obs, t0_unix, cfg=None):
    """how well each centre's analysis (consensus mean + its difference) and the mean fit the observations: normalised
    RMS of O-B (|d| / sqrt(sigma_o^2 + sigma_b^2)) by analysis variable, over observations that pass QC against the mean.
    {centre: {'ps': x, 't': x, 'q': x, 'u': x, 'v': x, 'all': x}} - smaller is better; ~1 is as expected. Can set the
    consensus weights (e.g. w = 1 / all^2)."""
    zs = np.asarray(CN['f2']['geopotential_at_surface'], float) / G; out = {}
    I0 = innovations(CN['f3'], CN['levs'], CN['lats'], CN['lons'], CN['f2']['surface_pressure'], zs, obs, t0_unix, cfg)
    ok = I0['why'] == ''
    for c in ['mean'] + list(CN.get('diffs', {})):
        if c == 'mean': f3, ps = CN['f3'], CN['f2']['surface_pressure']
        else: f3 = {v: np.asarray(a) + CN['diffs'][c][v] for v, a in CN['f3'].items()}; ps = np.asarray(CN['f2']['surface_pressure']) + CN['ps_diffs'][c]
        I = I0 if c == 'mean' else innovations(f3, CN['levs'], CN['lats'], CN['lons'], ps, zs, obs, t0_unix, cfg)
        z = np.abs(I['d']) / np.sqrt(I['so'] ** 2 + I['sb'] ** 2); r = {}
        for v in ('ps', 't', 'q', 'u', 'v'):
            m = ok & (I0['ana'] == v) & np.isfinite(z)
            if m.any(): r[v] = float(np.sqrt(np.mean(z[m] ** 2)))
        m = ok & np.isfinite(z); r['all'] = float(np.sqrt(np.mean(z[m] ** 2))) if m.any() else None; r['n'] = int(m.sum()); out[c] = r
    return out

def report(I, Ia, S, counts):
    out = dict(n_in=int(I['n_in']), n_window=int(I['n_window']), n_checked=int(len(I['d'])), n_superobs=int(len(S['d'])), solved=counts, rows=[])
    rej = {}
    for w in np.unique(I['why']):
        if w: rej[str(w)] = int((I['why'] == w).sum())
    out['rejected'] = rej
    for t in np.unique(I['type']):
        for v in np.unique(I['var']):
            m = (I['type'] == t) & (I['var'] == v) & (I['why'] == '')
            if not m.any(): continue
            ma = m & np.isfinite(Ia['d'])
            sc = 0.01 if v in ('mslp', 'ps') else (1000.0 if v == 'q' else 1.0)
            out['rows'].append(dict(type=str(t), var=str(v), n=int(m.sum()), omb_mean=float(np.mean(I['d'][m]) * sc), omb_rms=float(np.sqrt(np.mean(I['d'][m] ** 2)) * sc),
                                    oma_rms=float(np.sqrt(np.mean(Ia['d'][ma] ** 2)) * sc) if ma.any() else None,
                                    units='hPa' if v in ('mslp', 'ps') else ('g/kg' if v == 'q' else ('m' if v == 'z' else ('K' if v == 't' else 'm/s')))))
    return out

def report_text(rep):
    L = [f"obs: {rep['n_in']} in file, {rep['n_window']} in time window, {rep['n_checked']} checked, {rep['n_superobs']} superobs used; "
         f"rejected {rep['rejected']}; solved {rep['solved']}"]
    for r in rep['rows']:
        L.append(f"  {r['type']:6s} {r['var']:4s} n={r['n']:6d}  O-B mean {r['omb_mean']:+.2f} rms {r['omb_rms']:.2f}  O-A rms "
                 f"{'-' if r['oma_rms'] is None else '%.2f' % r['oma_rms']} {r['units']}")
    return '\n'.join(L)

# =============================================================================================== latent-heat nudging
# Standard LHN (Jones & Macpherson 1997, Met Office; Stephan et al. 2008, DWD COSMO): where the model rains, scale its own
# latent-heating profile by the ratio of observed to model rain (clipped 0.3-3); where it does not rain but rain is
# observed, add a default convective heating profile that would produce the observed rain; humidity is changed with the
# temperature so that relative humidity stays the same (the extra heating then comes with the moisture to sustain it).
def default_heating_profile(sig, xp=np, top=0.15, base=0.95, peak=0.5):
    """dimensionless convective heating shape on sigma levels: zero below `base` and above `top`, maximum near `peak`
    (a skewed sine, as tropical deep-convective heating, peaking ~450-500 hPa)."""
    s = xp.asarray(sig)
    x = xp.clip((base - s) / (base - top), 0.0, 1.0)
    xp_ = (base - peak) / (base - top)                                        # where the maximum is, in x
    a = math.log(0.5) / math.log(xp_)                                         # x**a puts the sine's peak at xp_
    return xp.sin(math.pi * x ** a) * (s < base) * (s > top)

def lhn_ratio(rain_model, rain_obs, clip=(0.3, 3.0), rmin=0.1 / 3600.0, xp=np):
    """observed / model rain, clipped; 1 where neither rains. rain in kg m-2 s-1 (= mm/s)."""
    r = rain_obs / xp.maximum(rain_model, rmin)
    r = xp.clip(r, clip[0], clip[1])
    return xp.where((rain_model < rmin) & (rain_obs < rmin), 1.0, r)

def lhn_tendency(lh, rain_model, rain_obs, T, q, p, dsig, ps, sig, clip=(0.3, 3.0), rmin=0.1 / 3600.0, max_rate=3.0e-3,
                 shape=None, xp=np, moisten=True):
    """LHN increments as tendencies (K/s, kg/kg/s), all on the model grid [L, X, Y] (or [L, ...]):
    lh   model latent-heating rate profile (K/s; condensation + convective heating - re-evaporation) over the last ~hour;
    rain_model, rain_obs  surface rain rates [X, Y] (kg m-2 s-1), the model's a running mean over the same time;
    T, q, p  current temperature, humidity, pressure (Pa) [L, X, Y]; dsig [L] layer thickness; ps [X, Y] Pa; sig [L].
    - model rain >= rmin: dT = (alpha - 1) lh, alpha = clip(obs/model)  (alpha < 1 also cools: less rain);
    - model rain < rmin, obs rain >= rmin: dT = default profile with column heating L_v * obs rain (the rain it would make);
    - moistening keeps relative humidity: dq = RH * dqsat/dT * dT;  rates capped at +-max_rate K/s (~11 K/h)."""
    sig_ = xp.asarray(sig)
    if lh.ndim == 3: sh = (-1, 1, 1)
    else: sh = (-1,) + (1,) * (lh.ndim - 1)
    sig_ = xp.reshape(sig_, sh); dsig_ = xp.reshape(xp.asarray(dsig), sh)
    alpha = lhn_ratio(rain_model, rain_obs, clip, rmin, xp)
    scaled = (alpha - 1.0)[None] * lh
    h = default_heating_profile(sig_, xp) if shape is None else xp.reshape(xp.asarray(shape), sh)
    norm = xp.sum(h * dsig_, axis=0) * ps / G * CP                            # J m-2 per (K/s) of the shape
    amp = LV * rain_obs / xp.maximum(norm, 1e-6)                              # K/s at the shape's maximum
    fill = h * amp[None]
    # no own rain (or no heating profile to scale): the default profile
    own = (rain_model >= rmin) & (xp.sum(xp.abs(lh) * dsig_, axis=0) > 1e-9)
    dT = xp.where(own[None], scaled, xp.where((rain_obs >= rmin)[None], fill, 0.0))
    dT = xp.clip(dT, -max_rate, max_rate)
    if not moisten: return dT, xp.zeros_like(dT)
    qs = qsat(T, p, xp); rh = xp.clip(q / xp.maximum(qs, 1e-12), 0.0, 1.0)
    dqs_dT = qs * 17.67 * 243.5 / (T - 29.65) ** 2
    dq = rh * dqs_dT * dT
    return dT, dq

def lhn_weight(t_hours, t_full=3.0, t_end=6.0, xp=np):
    """nudging weight: 1 up to t_full hours, then down linearly to 0 at t_end (xp=jnp inside jit)."""
    return xp.clip((t_end - t_hours) / max(t_end - t_full, 1e-6), 0.0, 1.0)

def running_rain(rmean, rate, dt, tau=3600.0, xp=np):
    """running mean of the model's rain rate (exponential, time scale tau s) - carry it between steps."""
    a = 1.0 - math.exp(-dt / tau); return rmean + a * (rate - rmean)

def obs_rain_rate(rain_mm, hours=6.0):
    """accumulated rain (mm in `hours`) -> rate kg m-2 s-1."""
    return np.asarray(rain_mm, float) / (hours * 3600.0)

def lightning_rain_coef(rain6, ltg6, min_rain=1.0):
    """mm of 6-h rain per lightning strike-cell, fitted on today's data where both satellite rain and lightning exist
    (median of the ratio); None if fewer than 20 such cells."""
    m = np.isfinite(rain6) & (ltg6 > 0) & (rain6 >= min_rain)
    if m.sum() < 20: return None
    return float(np.median(rain6[m] / ltg6[m]))

def merge_rain(rain6, ltg6, coef=None, default_coef=2.0):
    """observed 6-h rain for LHN: the satellite estimate; where it is missing, the lightning proxy (coef mm per
    strike-cell, fitted by lightning_rain_coef or default_coef - a first guess to be calibrated). Also returns a
    'convective' mask (lightning seen) for choosing the heating profile."""
    c = coef if coef is not None else default_coef
    fill = np.where(ltg6 > 0, c * ltg6, 0.0)
    out = np.where(np.isfinite(rain6), rain6, fill)
    return out, ltg6 > 0

def regrid_mean(F, src_lat, src_lon, dst_lat, dst_lon):
    """box mean of a fine regular grid (e.g. the 0.25-deg rain) onto a coarser grid with 1-D axes (Gaussian or regular):
    each fine cell goes to the nearest coarse node. NaN = missing; result NaN where no valid fine cell."""
    F = np.asarray(F, float); dl = np.asarray(dst_lat, float); do = np.asarray(dst_lon, float) % 360
    la = np.asarray(src_lat, float); lo = np.asarray(src_lon, float) % 360
    jy = np.abs(la[:, None] - dl[None]).argmin(1)
    dd = np.abs(((lo[:, None] - do[None]) + 180) % 360 - 180); ix = dd.argmin(1)
    J, I = np.meshgrid(jy, ix, indexing='ij'); ok = np.isfinite(F)
    flat = (J * len(do) + I)[ok]
    s = np.bincount(flat, F[ok], minlength=len(dl) * len(do)); n = np.bincount(flat, minlength=len(dl) * len(do))
    out = np.where(n > 0, s / np.maximum(n, 1), np.nan).reshape(len(dl), len(do))
    return out
