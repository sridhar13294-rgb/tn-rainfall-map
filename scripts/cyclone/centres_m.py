"""More global starting analyses for the moist multi-level model, on exactly the grid, levels and variables of
live_GFSM_<run>.npz (ours_fetch_m.py): 1.5 deg global (lats -90..90, lons 0..358.5), 13 pressure levels 50-1000 hPa;
temperature (K), specific humidity (kg/kg), u, v (m/s), geopotential (m2/s2); surface pressure (Pa), sea temperature (K, sea
only), land-sea mask (0-1), surface geopotential (m2/s2). Called from ours_fetch_m.py (RUN word "oursm"): fetch_all(run, gfs_f2).

ICON  DWD ICON global, 13 km icosahedral grid (R03B07, 2,949,120 cells). The analysis (step 0) of the GFS cycle if it is out,
      else the newest run's 6/12/18 h forecast valid then. Per field two routes are tried:
        1. DWD open data "v1" tree (plain GRIB2, CCSDS packing, ~27 h retention):
           https://opendata.dwd.de/weather/nwp/v1/m/icon/p/<FIELD>[/lvt1/100/lv1/<Pa>]/r/<YYYY-MM-DDTHH:MM>/s/PT<hhh>H00M.grib2
        2. the legacy bz2 tree (DWD stops it after 2026-11-30; some of its folders are already stale, so file names must carry
           the run): https://opendata.dwd.de/weather/nwp/icon/grib/<HH>/<field>/
           icon_global_icosahedral_<pressure-level|single-level>_<YYYYMMDDHH>_<hhh>[_<hPa>]_<FIELD>.grib2.bz2, and
           icon_global_icosahedral_time-invariant_<any date>_<CLAT|CLON|HSURF|FR_LAND>.grib2.bz2
      Pressure levels give T, RELHUM, U, V, FI (no QV on pressure levels): specific humidity is computed from RELHUM, which
      DWD defines over water, with ICON's own saturation formula. Surface: PS, T_G (= sea temperature over sea), HSURF, FR_LAND.
      Regridding: nearest ICON cell to each 1.5 deg point (KD-tree on the unit sphere, from the CLAT/CLON cell centres) - the
      same point sampling as the GFS/ECMWF files. The index is cached in data/cyclone/icon_nn_index.npz for runs where
      CLAT/CLON cannot be fetched.
CMC   Environment Canada GDPS, 15 km (0.15 deg lat-lon, 2400 x 1201), MSC Datamart layout since 2025:
        https://dd.weather.gc.ca/<YYYYMMDD>/WXO-DD/model_gdps/15km/<HH>/<hhh>/<YYYYMMDD>T<HH>Z_MSC_GDPS_<VAR>_<LEVEL>_LatLon0.15_PT<hhh>H.grib2
      (also tried: the hpfx.collab.science.gc.ca mirror of that tree and the old model_gem_global/CMC_glb_* tree). Runs are
      00/12 UTC only, so 06/18 UTC starts use the previous run's 6 h forecast. Variable names are matched against known
      names (old and new style); any still missing are identified from the GRIB parameter codes of a probe file at 500 hPa
      (or at the surface), and the names found are logged.
Missing surface fields: surface pressure from the centre's own geopotential profile at its terrain; otherwise, and for sea
temperature / land mask / terrain, the GFS field (each substitute is listed in 'notes' and in the log).
Output: /tmp/cyc_out/live_ICON_<run>.npz, live_CMC_<run>.npz with the keys of live_GFSM (f3 [1, var, lev, lat, lon], f2 [1, var,
lat, lon], times, lats, lons, v3, v2, levs) plus source ('<centre run>+<lag>h'), lag_h and notes. ~6-7 MB each.
Log: data/cyclone/fetch_status.json, keys ICON and CMC (other keys in that file are kept)."""
import os, re, sys, bz2, json, time, html, urllib.parse, datetime as dt, concurrent.futures as cf, threading
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import cyc_fetch as C

LATS = np.arange(-90, 90.1, 1.5); LONS = np.arange(0, 360, 1.5)
LEVS = [50, 100, 150, 200, 250, 300, 400, 500, 600, 700, 850, 925, 1000]
V3 = ['temperature', 'specific_humidity', 'u_component_of_wind', 'v_component_of_wind', 'geopotential']
V2 = ['surface_pressure', 'sea_surface_temperature', 'land_sea_mask', 'geopotential_at_surface']
G = 9.80665; RD = 287.04; EPS = 287.04 / 461.51
OUT = '/tmp/cyc_out'; MAX_S = float(os.environ.get('CENTRES_MAX_S', '1500'))           # time budget per centre (s)
def std_z(p_hpa):
    """standard-atmosphere height (m) of a pressure level (troposphere, then the isothermal layer above 226 hPa)."""
    return 44330.8 * (1 - (p_hpa / 1013.25) ** 0.190263) if p_hpa >= 226.32 else 11000.0 + 6341.6 * np.log(226.32 / p_hpa)
GRIB_KEYS = ('discipline', 'parameterCategory', 'parameterNumber', 'typeOfFirstFixedSurface', 'level', 'units', 'shortName', 'gridType',
             'numberOfDataPoints', 'Ni', 'Nj', 'latitudeOfFirstGridPointInDegrees', 'latitudeOfLastGridPointInDegrees',
             'longitudeOfFirstGridPointInDegrees', 'longitudeOfLastGridPointInDegrees', 'dataDate', 'dataTime', 'forecastTime')

# ------------------------------------------------------------------ logging into the fetch log, keeping the other jobs' entries
_SEEDED = [False]
def log(src, *a):
    if not _SEEDED[0]:
        _SEEDED[0] = True
        try:
            old = json.load(open(os.path.join(C.OUT, 'fetch_status.json')))
            with C.LK:
                for k, v in old.items():
                    if k not in C.LOG and k not in ('ICON', 'CMC', 'VITALS'): C.LOG[k] = v
        except Exception: pass
    C.log(src, *a)

# ------------------------------------------------------------------ helpers (no network)
def listing(url, tries=3):
    """names in an HTML directory index (sub-folders keep their trailing '/')."""
    b = C.http(url, tries=tries)
    if not b: return []
    out = []
    for h in re.findall(r'href="([^"]+)"', b.decode('utf-8', 'replace')):
        h = urllib.parse.unquote(html.unescape(h))
        if h.startswith(('?', '#', '../', 'mailto:')) or h in ('/', './'): continue
        if h.startswith(('http://', 'https://', '/')):
            seg = h.rstrip('/').rsplit('/', 1)[-1]
            if not seg: continue
            h = seg + ('/' if h.endswith('/') else '')
        out.append(h)
    return out

def decode(buf):
    """one GRIB message (optionally bz2) -> (values float32 with NaN for missing; 2-D for regular grids, flat otherwise), meta."""
    if buf[:3] == b'BZh': buf = bz2.decompress(buf)
    try:
        import pygrib
        m = pygrib.fromstring(buf); v = m.values; meta = {}
        for k in GRIB_KEYS:
            try: meta[k] = m[k]
            except Exception: pass
    except Exception as e1:
        try:
            import eccodes as E
        except Exception: raise e1
        h = E.codes_new_from_message(buf)
        try:
            meta = {k: E.codes_get(h, k) for k in GRIB_KEYS if E.codes_is_defined(h, k)}
            v = E.codes_get_values(h).astype(np.float64)
            if E.codes_get(h, 'bitmapPresent'): v = np.ma.masked_equal(v, E.codes_get(h, 'missingValue'))
            if meta.get('gridType') == 'regular_ll': v = v.reshape(int(meta['Nj']), int(meta['Ni']))
        finally: E.codes_release(h)
    v = np.where(np.ma.getmaskarray(v), np.nan, np.ma.getdata(v)).astype(np.float32)
    return v, meta

def code(meta):
    return (meta.get('discipline'), meta.get('parameterCategory'), meta.get('parameterNumber'))

def sample_ll(v, meta):
    """field on a regular lat-lon grid -> our 1.5 deg grid, nearest point (exact for 0.15/0.25/0.5 deg grids)."""
    nj, ni = int(meta['Nj']), int(meta['Ni']); v = np.asarray(v).reshape(nj, ni)
    la0, la1 = float(meta['latitudeOfFirstGridPointInDegrees']), float(meta['latitudeOfLastGridPointInDegrees'])
    lo0, lo1 = float(meta['longitudeOfFirstGridPointInDegrees']), float(meta['longitudeOfLastGridPointInDegrees'])
    dla = (la1 - la0) / (nj - 1); dlo = ((lo1 - lo0) % 360) / (ni - 1)
    ii = np.round((LATS - la0) / dla).astype(int); jj = np.round(((LONS - lo0) % 360) / dlo).astype(int) % ni
    ok = (ii >= 0) & (ii < nj); ok &= np.abs(la0 + np.clip(ii, 0, nj - 1) * dla - LATS) <= abs(dla) / 2 + 1e-6
    out = np.full((len(LATS), len(LONS)), np.nan, np.float32); out[ok] = v[np.ix_(ii[ok], jj)]
    return out

def nn_index(clat, clon):
    """nearest unstructured-grid cell for every point of our grid (KD-tree on the unit sphere) -> (index [lat, lon], max distance deg)."""
    from scipy.spatial import cKDTree
    clat = np.asarray(clat, float).ravel(); clon = np.asarray(clon, float).ravel()
    if np.nanmax(np.abs(clat)) <= np.pi / 2 + 1e-6 and np.nanmax(np.abs(clon)) <= 2 * np.pi + 1e-6:      # radians -> degrees
        clat, clon = np.degrees(clat), np.degrees(clon)
    def xyz(la, lo):
        la, lo = np.radians(la), np.radians(lo); return np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], -1)
    LO, LA = np.meshgrid(LONS, LATS); d, idx = cKDTree(xyz(clat, clon)).query(xyz(LA.ravel(), LO.ravel()))
    return idx.reshape(LA.shape).astype(np.int64), float(np.degrees(2 * np.arcsin(min(1.0, np.max(d) / 2))))

def es_water(T):
    """saturation vapour pressure over water (Pa), ICON's Tetens constants."""
    return 610.78 * np.exp(17.269 * (T - 273.16) / (T - 35.86))

def q_from_e(e, p):
    e = np.minimum(e, 0.5 * p); return EPS * e / (p - (1 - EPS) * e)

def q_from_rh(rh_pct, T, p):
    return q_from_e(np.clip(rh_pct, 0, 110) / 100.0 * es_water(T), p)

def to_geopotential(a, lev):
    """geopotential height (m), decametres or geopotential -> geopotential (m2/s2), from the magnitude at this level."""
    med = float(np.nanmedian(a)); want = G * std_z(lev)
    if not np.isfinite(med) or med == 0: return a, 1.0
    f = min((1.0, G, 10 * G), key=lambda f: abs(np.log(abs(med * f) / want)))
    return a * f, f

def ps_from_profile(phi, T, levs, phis):
    """surface pressure (Pa) where the geopotential profile [lev, ...] meets the terrain geopotential phis: log-p
    interpolation between levels, hypsometric (lowest level's temperature) below the lowest level."""
    p = np.asarray(levs, float) * 100.0; o = np.argsort(-p); p, ph, t = p[o], phi[o], T[o]
    ps = np.where(phis <= ph[0], p[0] * np.exp((ph[0] - phis) / (RD * np.maximum(t[0], 180.0))), np.nan)
    for k in range(len(p) - 1):
        a, b = ph[k], ph[k + 1]; m = (phis > a) & (phis <= b) & np.isnan(ps)
        w = (phis - a) / np.where(b - a == 0, 1.0, b - a)
        ps = np.where(m, np.exp(np.log(p[k]) + w * (np.log(p[k + 1]) - np.log(p[k]))), ps)
    return ps.astype(np.float32)

BOUNDS3 = {'temperature': (150, 340), 'specific_humidity': (-1e-4, 0.05), 'u_component_of_wind': (-150, 150), 'v_component_of_wind': (-150, 150)}
def plausible(f3, f2, src):
    """physical bounds point by point (outside -> NaN); a field with <90% valid points is dropped. Returns notes."""
    notes = []
    for i, v in enumerate(V3):
        for k, lev in enumerate(LEVS):
            a = f3[i, k]
            if not np.isfinite(a).any(): continue
            lo, hi = BOUNDS3.get(v) or (G * (std_z(lev) - 5000), G * (std_z(lev) + 5000))
            bad = np.isfinite(a) & ((a < lo) | (a > hi)); a[bad] = np.nan
            if np.isfinite(a).mean() < 0.9: log(src, 'dropped', v, lev, 'valid', round(float(np.isfinite(a).mean()), 3)); a[:] = np.nan; notes.append(f'{v} {lev} dropped')
            elif bad.any(): log(src, v, lev, 'out-of-range points set missing', int(bad.sum()))
    for i, (lo, hi) in enumerate([(40000, 110000), (260, 320), (0, 1), (-600 * G, 9000 * G)]):
        a = f2[i]; bad = np.isfinite(a) & ((a < lo) | (a > hi)); a[bad] = np.nan
        if bad.any(): log(src, V2[i], 'out-of-range points set missing', int(bad.sum()))
    return notes

def finish(src, run, r0, lag, f3, f2, gfs_f2, notes, raw):
    """unit fixes, humidity, surface substitutes, checks, save."""
    iT, iQ, iZ = V3.index('temperature'), V3.index('specific_humidity'), V3.index('geopotential')
    for k, lev in enumerate(LEVS):
        if np.isfinite(f3[iT, k]).any() and np.nanmedian(f3[iT, k]) < 150: f3[iT, k] += 273.15; notes.append(f'T {lev} C->K')
        if np.isfinite(f3[iZ, k]).any():
            f3[iZ, k], fac = to_geopotential(f3[iZ, k], lev)
            if lev == 500: log(src, 'geopotential factor at 500 hPa', round(fac, 4))
        p = lev * 100.0
        if np.isfinite(f3[iQ, k]).any():
            if np.nanmax(f3[iQ, k]) > 0.1: f3[iQ, k] /= 1000.0; notes.append(f'q {lev} g/kg->kg/kg')
        elif 'rh' in raw and np.isfinite(raw['rh'][k]).any() and np.isfinite(f3[iT, k]).any():
            rh = raw['rh'][k] * (100.0 if np.nanmax(raw['rh'][k]) <= 1.5 else 1.0)
            f3[iQ, k] = q_from_rh(rh, f3[iT, k], p)
            if 'q from RH (over water)' not in notes: notes.append('q from RH (over water)')
        elif 'depr' in raw and np.isfinite(raw['depr'][k]).any() and np.isfinite(f3[iT, k]).any():
            f3[iQ, k] = q_from_e(es_water(f3[iT, k] - raw['depr'][k]), p)
            if 'q from dew-point depression' not in notes: notes.append('q from dew-point depression')
    # surface fields
    if np.isfinite(f2[3]).mean() < 0.9 and gfs_f2 is not None: f2[3] = gfs_f2[3]; notes.append('geopotential_at_surface from GFS')
    if np.isfinite(f2[2]).mean() < 0.9 and gfs_f2 is not None: f2[2] = gfs_f2[2]; notes.append('land_sea_mask from GFS')
    if np.isfinite(f2[0]).mean() < 0.9:
        ok = np.isfinite(f3[iZ]).all(0) & np.isfinite(f3[iT]).all(0) & np.isfinite(f2[3])
        if ok.mean() > 0.95:
            f2[0] = np.where(ok, ps_from_profile(f3[iZ], f3[iT], LEVS, f2[3]), np.nan); notes.append('surface_pressure from own geopotential profile')
        elif gfs_f2 is not None: f2[0] = gfs_f2[0]; notes.append('surface_pressure from GFS')
    if np.isfinite(f2[0]).any() and np.nanmedian(f2[0]) < 2000: f2[0] *= 100.0; notes.append('ps hPa->Pa')
    land = f2[2] > 0.5
    if np.isfinite(f2[1]).mean() < 0.3 and gfs_f2 is not None: f2[1] = gfs_f2[1]; notes.append('sea_surface_temperature from GFS')
    f2[1] = np.where(land, np.nan, f2[1])                                                     # sea temperature only over sea
    notes += plausible(f3, f2, src)
    cov3 = {v: round(float(np.isfinite(f3[i]).mean()), 3) for i, v in enumerate(V3)}; cov2 = {v: round(float(np.isfinite(f2[i]).mean()), 3) for i, v in enumerate(V2)}
    log(src, 'coverage 3d', cov3, '2d', cov2)
    if min(cov3.values()) < 0.5: log(src, 'NOT saved: too little coverage'); return None
    os.makedirs(OUT, exist_ok=True); fn = f'{OUT}/live_{src}_{run:%Y%m%d%H}.npz'
    np.savez_compressed(fn, f3=f3[None], f2=f2[None], times=np.array([f'{run:%Y-%m-%dT%H}']), lats=LATS, lons=LONS, v3=np.array(V3),
                        v2=np.array(V2), levs=np.array(LEVS), source=f'{r0:%Y%m%d%H}+{lag}h', lag_h=int(lag), notes=np.array(notes or ['']))
    log(src, 'saved', fn, os.path.getsize(fn) // 1000, 'kB; run', f'{r0:%Y%m%d%H}+{lag}h', 'notes', notes)
    return fn

def run_jobs(src, jobs, fn, t0, par=6):
    """jobs in parallel, each skipped once the time budget is used; returns the number that worked."""
    def one(j):
        if time.time() - t0 > MAX_S: return 0
        try: return 1 if fn(j) else 0
        except Exception as e: log(src, 'job', str(j)[:80], 'failed', repr(e)[:150]); return 0
    with cf.ThreadPoolExecutor(par) as ex: return sum(ex.map(one, jobs))

# ------------------------------------------------------------------ DWD ICON global
DWD1 = 'https://opendata.dwd.de/weather/nwp/v1/m/icon/p'
DWD0 = 'https://opendata.dwd.de/weather/nwp/icon/grib'
IDX_CACHE = os.path.join(C.OUT, 'icon_nn_index.npz')
class Icon:
    PL = {'T': 'temperature', 'U': 'u_component_of_wind', 'V': 'v_component_of_wind', 'FI': 'geopotential', 'RELHUM': 'rh'}
    def __init__(self):
        self.lv = None; self.pref = {}; self.lock = threading.Lock(); self.routes = {}
    def lvname(self, hpa):
        if self.lv is None:
            names = [n.rstrip('/') for n in listing(f'{DWD1}/T/lvt1/100/lv1/') if n.endswith('/')]
            vals = {}
            for n in names:
                try: vals[float(n)] = n
                except ValueError: pass
            pa = max(vals, default=0) > 2000
            self.lv = {(x / 100.0 if pa else x): n for x, n in vals.items()}
            log('ICON', 'v1 pressure-level folders', len(self.lv), sorted(self.lv)[:30])
        return self.lv.get(float(hpa), str(int(hpa * 100)))
    def v1(self, F, r, step, hpa=None):
        if hpa is not None: lv = f'/lvt1/100/lv1/{self.lvname(hpa)}'
        else:
            lv = self.prefix(F)
            if lv is None: lv = ''
        return f'{DWD1}/{F}{lv}/r/{r:%Y-%m-%dT%H:%M}/s/PT{step:03d}H00M.grib2'
    def prefix(self, F):
        """folder path between p/<F> and r/ for a field without a pressure level ('' or '/lvt1/<t>/lv1/<v>'); None if unknown."""
        with self.lock:
            if F in self.pref: return self.pref[F]
        pre = None; base = f'{DWD1}/{F}'; names = [n.rstrip('/') for n in listing(base + '/')]
        if 'r' in names: pre = ''
        elif 'lvt1' in names:
            t = [n.rstrip('/') for n in listing(base + '/lvt1/') if n.endswith('/')]
            t1 = '1' if '1' in t else (t[0] if t else None)
            if t1:
                l = [n.rstrip('/') for n in listing(f'{base}/lvt1/{t1}/lv1/') if n.endswith('/')]
                l1 = '0' if '0' in l else (l[0] if l else None)
                if l1: pre = f'/lvt1/{t1}/lv1/{l1}'
        with self.lock: self.pref[F] = pre
        log('ICON', 'v1 folder for', F, repr(pre), 'top entries', names[:8])
        return pre
    def legacy(self, F, r, step, hpa=None):
        kind = 'pressure-level' if hpa is not None else 'single-level'
        return f"{DWD0}/{r:%H}/{F.lower()}/icon_global_icosahedral_{kind}_{r:%Y%m%d%H}_{step:03d}{'_%d' % hpa if hpa is not None else ''}_{F}.grib2.bz2"
    def get(self, F, r, step, hpa=None, head=False):
        for name, u in (('v1', self.v1(F, r, step, hpa)), ('legacy', self.legacy(F, r, step, hpa))):
            b = C.http(u, tries=3, method='HEAD' if head else 'GET')
            if b is not None and (head or len(b) > 100):
                with self.lock: self.routes[name] = self.routes.get(name, 0) + 1
                return b if not head else u
        return None
    def invariant(self, F, r):
        """time-invariant field: v1 at this run (or its newest run), else the legacy file of any date."""
        b = C.http(self.v1(F, r, 0), tries=2)
        if b: return b, 'v1 ' + f'{r:%Y%m%d%H}'
        pre = self.prefix(F)
        if pre is not None:
            runs = sorted(n.rstrip('/') for n in listing(f'{DWD1}/{F}{pre}/r/') if n.endswith('/'))
            for rr in runs[::-1][:3]:
                steps = [n for n in listing(f'{DWD1}/{F}{pre}/r/{rr}/s/') if n.endswith('.grib2')]
                for s in sorted(steps)[:1]:
                    b = C.http(f'{DWD1}/{F}{pre}/r/{rr}/s/{s}', tries=2)
                    if b: return b, f'v1 {rr} {s}'
        for hh in dict.fromkeys([r.hour, 0, 6, 12, 18]):
            base = f'{DWD0}/{hh:02d}/{F.lower()}/'
            for n in sorted(listing(base))[::-1]:
                if re.match(rf'icon_global_icosahedral_time-invariant_\d{{10}}_{F}\.grib2\.bz2$', n):
                    b = C.http(base + n, tries=2)
                    if b: return b, 'legacy ' + n
        return None, None
    def grid_index(self, r):
        clat, sl = self.invariant('CLAT', r); clon, so = self.invariant('CLON', r)
        if clat and clon:
            a, _ = decode(clat); o, _ = decode(clon)
            if a.size == o.size:
                idx, dmax = nn_index(a, o); log('ICON', 'grid from', sl, '/', so, 'cells', a.size, 'max distance to a cell %.3f deg' % dmax)
                try:
                    old = np.load(IDX_CACHE) if os.path.exists(IDX_CACHE) else None
                    if old is None or int(old['ncell']) != a.size or not np.array_equal(old['idx'], idx):
                        np.savez_compressed(IDX_CACHE, idx=idx.astype(np.int32), ncell=a.size, lats=LATS, lons=LONS)
                except Exception as e: log('ICON', 'index cache not written', repr(e)[:100])
                return idx, a.size
        if os.path.exists(IDX_CACHE):
            Z = np.load(IDX_CACHE)
            if Z['idx'].shape == (len(LATS), len(LONS)) and np.allclose(Z['lats'], LATS) and np.allclose(Z['lons'], LONS):
                log('ICON', 'CLAT/CLON not found: cached grid index', IDX_CACHE); return Z['idx'].astype(np.int64), int(Z['ncell'])
        return None, None
    def fetch(self, run, gfs_f2):
        t0 = time.time(); r0 = lag = None
        for lg in (0, 6, 12, 18):
            rr = run - dt.timedelta(hours=lg); u = self.get('T', rr, lg, 500, head=True)
            if u: r0, lag = rr, lg; log('ICON', 'run', f'{rr:%Y%m%d%H}', 'step', lg, 'found at', u); break
        if r0 is None: log('ICON', 'no run found for', f'{run:%Y%m%d%H}'); return None
        idx, ncell = self.grid_index(r0)
        if idx is None: log('ICON', 'no grid (CLAT/CLON) and no cached index: stop'); return None
        f3 = np.full((len(V3), len(LEVS), len(LATS), len(LONS)), np.nan, np.float32); f2 = np.full((len(V2), len(LATS), len(LONS)), np.nan, np.float32)
        raw = {'rh': np.full((len(LEVS), len(LATS), len(LONS)), np.nan, np.float32)}; notes = []
        def put(j):
            F, hpa = j
            b = (self.invariant(F, r0)[0] if F in ('HSURF', 'FR_LAND') else self.get(F, r0, lag, hpa))
            if not b: log('ICON', 'missing', F, hpa); return False
            v, meta = decode(b); v = v.ravel()
            if v.size != ncell: log('ICON', F, hpa, 'size', v.size, '!= grid', ncell); return False
            if hpa is not None and meta.get('typeOfFirstFixedSurface') == 100 and meta.get('level') not in (None, hpa, hpa * 100):
                log('ICON', F, hpa, 'level in file', meta.get('level')); return False
            a = v[idx]; k = LEVS.index(hpa) if hpa is not None else None
            if F == 'RELHUM': raw['rh'][k] = a
            elif F in self.PL: f3[V3.index(self.PL[F]), k] = a
            elif F == 'PS': f2[0] = a
            elif F == 'T_G': f2[1] = a
            elif F == 'FR_LAND': f2[2] = a
            elif F == 'HSURF': f2[3] = a * G
            return True
        jobs = [(F, h) for F in self.PL for h in LEVS] + [('PS', None), ('T_G', None), ('HSURF', None), ('FR_LAND', None)]
        n = run_jobs('ICON', jobs, put, t0); log('ICON', 'fields', n, 'of', len(jobs), 'in', int(time.time() - t0), 's; routes', self.routes)
        return finish('ICON', run, r0, lag, f3, f2, gfs_f2, notes, raw)

# ------------------------------------------------------------------ Environment Canada GDPS
CMC_BASES = ['https://dd.weather.gc.ca/{d}/WXO-DD/model_gdps/15km/{H}/{s}/', 'https://hpfx.collab.science.gc.ca/{d}/WXO-DD/model_gdps/15km/{H}/{s}/',
             'https://dd.weather.gc.ca/model_gem_global/15km/grib2/lat_lon/{H}/{s}/']
NEW = re.compile(r'^(\d{8})T(\d{2})Z_MSC_GDPS_(.+)_(LatLon[0-9.]+)_PT(\d{3})H\.grib2$')
OLD = re.compile(r'^CMC_glb_([A-Za-z0-9-]+)_(.+)_latlon[0-9.x]+_(\d{10})_P(\d{3})\.grib2$')
CAND3 = {'temperature': ['AirTemp', 'TMP', 'Temp', 'Temperature', 'AirTemperature'],
         'specific_humidity': ['SpecificHumidity', 'SPFH', 'SpecHum', 'SpecificHum'],
         'u_component_of_wind': ['WindU', 'UGRD', 'UWind', 'WindUComponent', 'U-Wind', 'WindComponentU', 'Wind-U'],
         'v_component_of_wind': ['WindV', 'VGRD', 'VWind', 'WindVComponent', 'V-Wind', 'WindComponentV', 'Wind-V'],
         'geopotential': ['GeopotentialHeight', 'HGT', 'GeopHeight', 'Geopotential', 'GPH'],
         'rh': ['RelativeHumidity', 'RH', 'RelHum'], 'depr': ['DewPointDepression', 'DEPR', 'DewPointDep', 'DPD']}
CODE3 = {'temperature': [(0, 0, 0)], 'specific_humidity': [(0, 1, 0)], 'u_component_of_wind': [(0, 2, 2)], 'v_component_of_wind': [(0, 2, 3)],
         'geopotential': [(0, 3, 5), (0, 3, 4)], 'rh': [(0, 1, 1)], 'depr': [(0, 0, 7)]}
CAND2 = {'ps': ['Pressure', 'PRES', 'SurfacePressure', 'Pres', 'SfcPressure'],
         'lsm': ['LandWaterMask', 'LAND', 'LandSeaMask', 'LandFraction', 'LandCover', 'Land', 'LandMask'],
         'zs': ['GeopotentialHeight', 'HGT', 'Topography', 'ModelTopography', 'Orography', 'TerrainHeight', 'Height', 'SfcHeight'],
         'sst': ['WaterTemp', 'SeaSfcTemp', 'SeaSurfaceTemp', 'SST', 'WTMP', 'SkinTemp', 'SurfaceTemp', 'AirTemp', 'TMP', 'Temp']}
CODE2 = {'ps': [(0, 3, 0)], 'lsm': [(2, 0, 0)], 'zs': [(0, 3, 5), (0, 3, 4), (2, 0, 7)], 'sst': [(10, 3, 0), (0, 0, 17), (0, 0, 0)]}
HINT2 = ('pres', 'land', 'mask', 'topo', 'oro', 'height', 'geop', 'hgt', 'temp', 'tmp', 'skin', 'sea', 'water')
def parse_cmc(name):
    m = NEW.match(name)
    if m:
        vl = m.group(3).rsplit('_', 1); return (vl[0], vl[1]) if len(vl) == 2 else None
    m = OLD.match(name)
    return (m.group(1), m.group(2)) if m else None
def lev_hpa(lev):
    m = re.match(r'^isbl[-_]0*(\d+(?:\.\d+)?)$', lev, re.I)
    return float(m.group(1)) if m else None
def is_sfc(lev): return lev.lower() in ('sfc', 'sfc_0', 'sfc-0', 'surface')
class Cmc:
    def find(self, run):
        for lag in ((0, 12) if run.hour in (0, 12) else (6, 18)):
            r0 = run - dt.timedelta(hours=lag)
            for b in CMC_BASES:
                url = b.format(d=f'{r0:%Y%m%d}', H=f'{r0:%H}', s=f'{lag:03d}')
                names = [n for n in listing(url) if n.endswith('.grib2') and (f'{r0:%Y%m%d}T{r0:%H}Z' in n or f'{r0:%Y%m%d%H}_P{lag:03d}' in n)]
                if len(names) > 20: return r0, lag, url, names
                log('CMC', 'nothing usable at', url, len(names))
        return None
    def fetch(self, run, gfs_f2):
        t0 = time.time(); fd = self.find(run)
        if fd is None: log('CMC', 'no GDPS run found for', f'{run:%Y%m%d%H}'); return None
        r0, lag, url, names = fd; log('CMC', 'run', f'{r0:%Y%m%d%H}', 'step', lag, url, 'files', len(names))
        cat = {}
        for n in names:
            p = parse_cmc(n)
            if p: cat[p] = n
        iso = {}
        for (var, lev), n in cat.items():
            h = lev_hpa(lev)
            if h is not None: iso.setdefault(var, {})[h] = n
        sfc = {var: n for (var, lev), n in cat.items() if is_sfc(lev)}
        log('CMC', 'isobaric variables', sorted(iso)[:60]); log('CMC', 'surface variables', sorted(sfc)[:80])
        low3 = {v.lower(): v for v in iso if sum(h in iso[v] for h in LEVS) >= 8}; got3 = {}
        for key, cands in CAND3.items():
            for c in cands:
                if c.lower() in low3: got3[key] = low3[c.lower()]; break
        low2 = {v.lower(): v for v in sfc}; got2 = {}
        for key, cands in CAND2.items():
            for c in cands:
                if c.lower() in low2 and low2[c.lower()] not in got2.values(): got2[key] = low2[c.lower()]; break
        def probe(got, pool, wanted, codes, sfc_type, limit):
            """identify still-missing variables from the GRIB codes of one file each."""
            for var, n in pool[:limit]:
                if not [k for k in wanted if k not in got]: break
                b = C.http(url + n, tries=2)
                if not b: continue
                try: _, meta = decode(b)
                except Exception: continue
                cd = code(meta); tf = meta.get('typeOfFirstFixedSurface')
                for k in wanted:
                    if k not in got and cd in codes[k] and (sfc_type is None or tf in (None, sfc_type)): got[k] = var; log('CMC', 'identified', k, '=', var, 'codes', cd); break
        need3 = [k for k in ('temperature', 'u_component_of_wind', 'v_component_of_wind', 'geopotential') if k not in got3]
        if not any(k in got3 for k in ('specific_humidity', 'rh', 'depr')): need3 += ['specific_humidity', 'rh', 'depr']
        if need3:
            pool = [(v, iso[v][500.0]) for v in sorted(low3.values()) if v not in got3.values() and 500.0 in iso[v]]
            probe(got3, pool, need3, CODE3, 100, 30)
        need2 = [k for k in CAND2 if k not in got2]
        if need2:
            pool = [(v, n) for v, n in sorted(sfc.items()) if v not in got2.values() and any(h in v.lower() for h in HINT2)]
            probe(got2, pool, need2, CODE2, 1, 25)
        log('CMC', 'names used: isobaric', got3, 'surface', got2)
        hum = next((k for k in ('specific_humidity', 'rh', 'depr') if k in got3), None)
        f3 = np.full((len(V3), len(LEVS), len(LATS), len(LONS)), np.nan, np.float32); f2 = np.full((len(V2), len(LATS), len(LONS)), np.nan, np.float32)
        raw = {k: np.full((len(LEVS), len(LATS), len(LONS)), np.nan, np.float32) for k in ('rh', 'depr')}; notes = []
        jobs = [(k, h, url + iso[got3[k]][float(h)]) for k in ('temperature', 'u_component_of_wind', 'v_component_of_wind', 'geopotential', hum)
                if k in got3 for h in LEVS if float(h) in iso[got3[k]]] + [(k, None, url + sfc[got2[k]]) for k in got2]
        if lag and any(k not in got2 for k in ('zs', 'lsm')):                                  # topography (and land mask) come at hour 000 only
            u0 = url.replace(f'/{lag:03d}/', '/000/'); s0 = {}
            for n in listing(u0):
                p = parse_cmc(n) if n.endswith('.grib2') else None
                if p and is_sfc(p[1]): s0[p[0]] = n
            low0 = {v.lower(): v for v in s0}
            for key in ('zs', 'lsm'):
                c = None if key in got2 else next((low0[c.lower()] for c in CAND2[key] if c.lower() in low0), None)
                if c: jobs.append((key, None, u0 + s0[c])); log('CMC', key, 'from hour 000:', s0[c])
        def put(j):
            k, h, u = j; n = u.rsplit('/', 1)[-1]
            b = C.http(u, tries=4)
            if not b: log('CMC', 'missing', u); return False
            v, meta = decode(b)
            if h is not None and meta.get('typeOfFirstFixedSurface') == 100 and meta.get('level') not in (None, h, h * 100):
                log('CMC', n, 'level in file', meta.get('level')); return False
            a = sample_ll(v, meta)
            if h is not None:
                if k in raw: raw[k][LEVS.index(h)] = a
                else: f3[V3.index(k), LEVS.index(h)] = a
            elif k == 'ps': f2[0] = a
            elif k == 'sst': f2[1] = a
            elif k == 'lsm': f2[2] = a
            elif k == 'zs':
                u = str(meta.get('units', '')).lower(); f2[3] = a * (1.0 if 'm**2' in u or 'm2' in u else 10 * G if 'dam' in u else G)
            return True
        n = run_jobs('CMC', jobs, put, t0); log('CMC', 'fields', n, 'of', len(jobs), 'in', int(time.time() - t0), 's')
        return finish('CMC', run, r0, lag, f3, f2, gfs_f2, notes, raw)

# ------------------------------------------------------------------ entry point
def fetch_all(run, gfs_f2=None, levs=None, lats=None, lons=None, which=('ICON', 'CMC')):
    """fetch ICON and CMC in parallel; never raises. gfs_f2: the GFS surface fields [V2, lat, lon] for substitutes."""
    global LEVS, LATS, LONS
    if levs is not None and list(levs) != LEVS: LEVS = [int(x) for x in levs]
    if lats is not None: LATS = np.asarray(lats, float)
    if lons is not None: LONS = np.asarray(lons, float)
    if gfs_f2 is not None: gfs_f2 = np.asarray(gfs_f2, np.float32)
    jobs = {'ICON': lambda: Icon().fetch(run, gfs_f2), 'CMC': lambda: Cmc().fetch(run, gfs_f2)}; res = {}
    with cf.ThreadPoolExecutor(len(which)) as ex:
        fut = {w: ex.submit(jobs[w]) for w in which}
        for w, f in fut.items():
            try: res[w] = f.result()
            except Exception as e:
                import traceback; log(w, 'FAILED', repr(e)[:300], traceback.format_exc()[-600:]); res[w] = None
    return res

if __name__ == '__main__':                                                                    # python centres_m.py [YYYYMMDDHH] [ICON|CMC]
    r = dt.datetime.strptime(sys.argv[1], '%Y%m%d%H') if len(sys.argv) > 1 else C.latest_run(lambda r: C.http(C.gfs_url(r, 0) + '.idx', method='HEAD') is not None)
    print(fetch_all(r, which=tuple(sys.argv[2:]) or ('ICON', 'CMC')))
