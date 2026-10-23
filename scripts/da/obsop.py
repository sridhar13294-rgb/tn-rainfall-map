"""Observation operators H(x) from mm2's model state (nodal fields on its Gaussian grid, 32 sigma levels) to the
observations of obs_fetch.py, plus observation errors and quality control, for the LETKF.

Works on a whole ensemble at once: fields have a leading member axis [K, L, X, Y] (X = longitude, Y = latitude, mm2's
nodal layout) or none. Array module `xp` = numpy (CPU, tests) or jax.numpy (GPU); no in-place writes.

Operators (SI units: Pa, K, kg/kg, m/s, m):
  horizontal       bilinear on the Gaussian grid, periodic in longitude (geometry built once per observation set);
  ps  (station)    model surface pressure moved hypsometrically from the model terrain height to the station height,
                   with the mean virtual temperature of the layer between (surface T = lowest-level T + 6.5 K/km x its height);
  mslp             ps x exp(g zs / (Rd (T_low + 0.0065 zs / 2))) - the reduction nudge.py and obs_fetch.py use, so observed
                   and model MSLP are made the same way (used only when a report has no station pressure);
  t (surface)      2-m temperature: lowest-level T + 6.5 K/km x (lowest-level height - station height + ... 2 m);
  q (surface)      lowest-level specific humidity (dew points are turned into q first: q = qsat(Td, p_station));
  u, v (surface)   10-m wind from the lowest level (sigma 0.99, ~80 m) with a neutral log profile:
                   ln(10/z0) / ln(z1/z0), z0 = 2e-4 m sea (factor ~0.84), 0.1 m land (~0.68);
  scat (u, v)      the same over sea only;
  temp (t, q, u, v) radiosonde level: linear in ln p between model levels; levels below the model ground or above the
                   top level are rejected.
Vertical position of each observation for localisation: ln(p_obs / ps_model) (= ln sigma; surface obs at the lowest level).
Errors: nudge.py's tables (NCEP GSI / ECMWF-like; docs/obs_assimilation.md) - one source for OI and LETKF."""
import os, sys, math, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'cyclone', 'mm'))
import nudge as NG                                     # numpy only: error tables, qsat, td -> q

G, RD, CP = 9.80616, 287.04, 1004.6
LAPSE = 0.0065
Z0_SEA, Z0_LAND = 2e-4, 0.1
SURFACE_TYPES = ('synop', 'metar', 'ship', 'buoy', 'scat')
MARINE = ('ship', 'buoy', 'scat')

class Geometry:
    """bilinear weights from the model grid (lon [X], lat [Y]; fields [..., X, Y]) to observation points."""
    def __init__(self, lon, lat, olat, olon):
        lat = np.asarray(lat, float); lon = np.asarray(lon, float) % 360.0; self.nx, self.ny = len(lon), len(lat)
        asc = lat[0] < lat[-1]; la = lat if asc else lat[::-1]
        olat = np.clip(np.asarray(olat, float), la[0], la[-1]); olon = np.asarray(olon, float) % 360.0
        j1 = np.clip(np.searchsorted(la, olat), 1, len(la) - 1); j0 = j1 - 1
        wy = (olat - la[j0]) / np.maximum(la[j1] - la[j0], 1e-9)
        if not asc: j0, j1 = len(la) - 1 - j0, len(la) - 1 - j1
        order = np.argsort(lon); lo = lon[order]; ext = np.concatenate([lo, [lo[0] + 360.0]])
        o = np.where(olon < lo[0], olon + 360.0, olon)
        i1 = np.clip(np.searchsorted(ext, o, side='right'), 1, len(ext) - 1); i0 = i1 - 1
        wx = (o - ext[i0]) / np.maximum(ext[i1] - ext[i0], 1e-9)
        i0 = order[i0 % len(lo)]; i1 = order[i1 % len(lo)]
        self.fi = np.stack([i0 * self.ny + j0, i1 * self.ny + j0, i0 * self.ny + j1, i1 * self.ny + j1]).astype(np.int32)
        self.w = np.stack([(1 - wy) * (1 - wx), (1 - wy) * wx, wy * (1 - wx), wy * wx]).astype(np.float32)
        self.n = len(olat)
    def apply(self, F, xp=np):
        """F [..., X, Y] -> [..., n]."""
        Ff = xp.reshape(F, F.shape[:-2] + (-1,)); out = 0.0
        for k in range(4): out = out + xp.take(Ff, xp.asarray(self.fi[k]), axis=-1) * xp.asarray(self.w[k])
        return out

def interp_lnp(col, lpcol, lpo, xp=np):
    """col, lpcol [..., L, n] (levels top -> bottom, ln p increasing); lpo [..., n] -> [..., n], linear in ln p, held at the ends."""
    L = col.shape[-2]; idx = xp.sum(lpcol < lpo[..., None, :], axis=-2)
    k1 = xp.clip(idx, 1, L - 1); k0 = k1 - 1
    g = lambda X, k: xp.take_along_axis(X, k[..., None, :], axis=-2)[..., 0, :]
    a0, a1 = g(lpcol, k0), g(lpcol, k1)
    w = xp.clip((lpo - a0) / (a1 - a0), 0.0, 1.0)
    return g(col, k0) + w * (g(col, k1) - g(col, k0))

class Operator:
    """H for one observation set. static: dict zs [X, Y] (m, the model's own smoothed terrain), land [X, Y] (0/1),
    sig [L] (layer centres, top -> bottom), lon [X], lat [Y]. obs: dict of arrays type, var, lat, lon, p (hPa; radiosonde
    level, NaN for surface), z (station height m)."""
    def __init__(self, static, obs):
        self.geo = Geometry(static['lon'], static['lat'], obs['lat'], obs['lon'])
        self.sig = np.asarray(static['sig'], np.float32); self.n = self.geo.n
        self.zsb = self.geo.apply(np.asarray(static['zs'], np.float32)); self.landf = self.geo.apply(np.asarray(static['land'], np.float32))
        t = np.asarray(obs['type']).astype(str); v = np.asarray(obs['var']).astype(str)
        self.type, self.var = t, v
        p = np.asarray(obs['p'], float); self.upper = (t == 'temp') & np.isfinite(p)
        self.pobs = np.where(self.upper, p * 100.0, np.nan)
        self.zst = np.where(np.isfinite(np.asarray(obs['z'], float)), np.asarray(obs['z'], float), self.zsb)
        lf = np.where(t == 'scat', 0.0, np.where(np.isin(t, MARINE), 0.0, self.landf))
        self.z0 = np.exp(lf * math.log(Z0_LAND) + (1 - lf) * math.log(Z0_SEA))
    def __call__(self, F, xp=np):
        """F: dict t, q, u, v [..., L, X, Y], ps [..., X, Y] (Pa). Returns hx [..., n] (NaN where undefined) and the
        vertical coordinate ln(p_obs / ps_model) [..., n] for localisation."""
        A = lambda X: self.geo.apply(X, xp)
        ps = A(F['ps']); col = {k: A(F[k]) for k in ('t', 'q', 'u', 'v')}               # [..., L, n]
        Tl, ql, ul, vl = (col[k][..., -1, :] for k in ('t', 'q', 'u', 'v'))
        zsb = xp.asarray(self.zsb); zst = xp.asarray(self.zst, np.float32); sl = float(self.sig[-1])
        z1 = RD * Tl * (1 + 0.608 * ql) / G * math.log(1.0 / sl)                         # lowest level above the model ground
        Ts = Tl + LAPSE * z1; dz = zst - zsb
        p_stn = ps * xp.exp(-G * dz / (RD * (Ts - LAPSE * dz / 2) * (1 + 0.608 * ql)))
        mslp = ps * xp.exp(G * zsb / (RD * (Tl + LAPSE * zsb / 2)))
        t2 = Tl + LAPSE * (z1 - dz - 2.0)
        z0 = xp.asarray(self.z0, np.float32); f10 = xp.log(10.0 / z0) / xp.log(xp.maximum(z1, 20.0) / z0)
        lp = xp.log(xp.asarray(self.sig)[:, None]) + xp.log(ps)[..., None, :]               # [..., L, n]
        lpo = xp.log(xp.asarray(np.where(self.upper, self.pobs, 1e5), np.float32)) + 0.0 * ps
        up = {k: interp_lnp(col[k], lp, lpo, xp) for k in ('t', 'q', 'u', 'v')}
        v, U = self.var, self.upper
        hx = xp.full(ps.shape, xp.nan, dtype=ps.dtype)
        def put(h, m, val): return xp.where(xp.asarray(m), val, h)
        hx = put(hx, (v == 'ps') & ~U, p_stn); hx = put(hx, (v == 'mslp') & ~U, mslp)
        hx = put(hx, (v == 't') & ~U, t2); hx = put(hx, (v == 'q') & ~U, ql)
        hx = put(hx, (v == 'u') & ~U, f10 * ul); hx = put(hx, (v == 'v') & ~U, f10 * vl)
        for k in ('t', 'q', 'u', 'v'): hx = put(hx, (v == k) & U, up[k])
        # validity: radiosonde level inside the model column
        inside = (lpo <= lp[..., -1, :] + 0.005) & (lpo >= lp[..., 0, :])
        hx = xp.where(xp.asarray(U) & ~inside, xp.nan, hx)
        vert = xp.where(xp.asarray(U), lpo - xp.log(ps), math.log(sl))
        return hx, vert

# ---------------------------------------------------------------------------------------------------- errors and QC
def obs_errors(obs, qs_ref=None):
    """sigma_o per observation (SI). q errors are a fraction of qsat in the tables: qs_ref [n] (qsat at the obs, from the
    background or the truth) turns them into kg/kg."""
    t = np.asarray(obs['type']).astype(str); v = np.asarray(obs['var']).astype(str); p = np.asarray(obs['p'], float); z = np.asarray(obs['z'], float)
    e = np.array([NG.obs_error(a, b, (c if np.isfinite(c) else None), (d if np.isfinite(d) else None)) for a, b, c, d in zip(t, v, p, z)], float)
    if qs_ref is not None: e = np.where(v == 'q', e * np.asarray(qs_ref, float), e)
    return e

DEFAULT_QC = dict(gross=5.0, max_dz_p=800.0, max_zstn_p=2500.0, max_dz_sfc=600.0, q_top_hpa=300.0, scat_max_land=0.1,
                  use_land_t2m=True, use_land_wind=True, use_mslp_if_ps=False)
def quality_control(op, obs, d, sigo, sprd, cfg=None):
    """d [n] innovations of the ensemble mean, sigo [n], sprd [n] ensemble spread in obs space. Returns (ok [n] bool,
    why [n] str). Order: undefined, configuration (types/variables off), terrain height, radiosonde level, scatterometer
    over land, gross error |d| > gross x sqrt(sigo^2 + spread^2); a rejected wind component takes its partner."""
    c = dict(DEFAULT_QC, **(cfg or {})); n = len(d); why = np.full(n, '', '<U12')
    t, v, U = op.type, op.var, op.upper; marine = np.isin(t, MARINE); dz = np.abs(op.zst - op.zsb)
    why[~np.isfinite(d) | ~np.isfinite(sigo) | (sigo <= 0)] = 'undefined'
    def rej(m, w): why[(why == '') & m] = w
    sid = np.asarray(obs.get('sid', np.arange(n).astype(str))).astype(str)
    if not c['use_mslp_if_ps']:
        has_ps = set(sid[(v == 'ps') & np.isfinite(d)]); rej((v == 'mslp') & np.isin(sid, list(has_ps)), 'dup_pressure')
    rej(~U & np.isin(v, ('ps', 'mslp')) & ((dz > c['max_dz_p']) | (op.zst > c['max_zstn_p'])), 'height')
    rej(~U & np.isin(v, ('t', 'q', 'u', 'v')) & ~marine & (dz > c['max_dz_sfc']), 'height')
    if not c['use_land_t2m']: rej(~U & (v == 't') & ~marine, 'off')
    if not c['use_land_wind']: rej(~U & np.isin(v, ('u', 'v')) & ~marine, 'off')
    rej((t == 'scat') & (op.landf > c['scat_max_land']), 'land')
    rej(U & (v == 'q') & (np.nan_to_num(op.pobs, nan=1e5) < c['q_top_hpa'] * 100.0), 'q_top')
    rej(np.abs(np.nan_to_num(d)) > c['gross'] * np.sqrt(sigo ** 2 + sprd ** 2), 'gross')
    # wind pairs: same type, station, level
    w = np.isin(v, ('u', 'v')); key = np.array([f'{a}|{b}|{e:.6g}|{f:.6g}|{g:.6g}' for a, b, e, f, g in zip(t, sid, np.nan_to_num(op.pobs), np.asarray(obs['lat'], float), np.asarray(obs['lon'], float))])
    bad = set(key[w & (why != '')]); why[(why == '') & w & np.isin(key, list(bad))] = 'pair'
    return why == '', why

# ---------------------------------------------------------------------------------------------------- real observations
def prepare_real(obs, t0_unix, max_dt_h=None):
    """obs_<run>.npz records (nudge.load_obs) -> the records the LETKF uses: inside the time window, one report per
    station / variable / level (closest to t0), dew point -> q (station pressure from the report's 'p', else 1000 hPa
    standard-atmosphere guess from the height), heights dropped (monitoring only)."""
    mdt = dict(synop=1.5, metar=1.0, ship=3.0, buoy=3.0, temp=3.0, scat=3.0); mdt.update(max_dt_h or {})
    t = np.asarray(obs['type']).astype(str); v = np.asarray(obs['var']).astype(str); dt_h = (np.asarray(obs['time'], float) - t0_unix) / 3600.0
    keep = np.array([abs(a) <= mdt.get(b, 3.0) for a, b in zip(dt_h, t)], bool) & (v != 'z')
    O = {k: np.asarray(obs[k])[keep] for k in ('type', 'sid', 'lat', 'lon', 'p', 'z', 'time', 'var', 'value')}
    for k in ('type', 'sid', 'var'): O[k] = O[k].astype(str)
    dt_h = dt_h[keep]; best = {}
    for i in range(len(dt_h)):
        if O['type'][i] == 'scat': best[('s', i)] = i; continue
        k = (O['type'][i], O['sid'][i], O['var'][i], round(float(O['p'][i])) if O['type'][i] == 'temp' and np.isfinite(O['p'][i]) else -1)
        if k not in best or abs(dt_h[i]) < abs(dt_h[best[k]]): best[k] = i
    sel = np.array(sorted(best.values()), int); O = {k: a[sel] for k, a in O.items()}; dt_h = dt_h[sel]
    O['value'] = O['value'].astype(float); O['p'] = O['p'].astype(float); O['z'] = O['z'].astype(float); O['lon'] = O['lon'].astype(float) % 360.0
    td = O['var'] == 'td'
    up = O['type'] == 'temp'
    pq = np.where(up, O['p'] * 100.0, np.where(np.isfinite(O['p']), O['p'] * 100.0, 101325.0 * np.exp(-np.nan_to_num(O['z']) / 8000.0)))
    O['value'] = np.where(td, NG.q_from_td(O['value'], pq), O['value']); O['var'] = np.where(td, 'q', O['var'])
    O['p'] = np.where(up, O['p'], np.nan)                                             # surface reports: level unused
    O['dt_h'] = dt_h; return O
