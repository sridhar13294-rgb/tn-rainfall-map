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
ARPEGE Météo-France ARPEGE global 0.25 deg (open data, Licence Ouverte 2.0, 15-day retention), packages of GRIB2 (CCSDS):
        https://meteofrance-pnt.s3.rbx.io.cloud.ovh.net/pnt/<YYYY-MM-DDTHH:MM:SSZ>/arpege/025/<PKG>/arpege__025__<PKG>__000H024H__<same>.grib2
      (also tried: object.data.gouv.fr/meteofrance-pnt/..., and any host the data.gouv.fr API lists for the dataset
      'paquets-arpege-resolution-0-25deg'). No index files: each package is read front to back and kept only at the lead
      wanted, stopping when complete. IP1: T, RH, U, V, Z (34 levels at 3-hourly leads); IP2: q; SP2: surface pressure,
      surface temperature. Runs 00/06/12/18 UTC, ~3-5 h latency.
UKMO  Met Office global deterministic 10 km (AWS open data, CC BY-SA 4.0, no sign-in), one NetCDF per field and lead:
        https://met-office-atmospheric-model-data.s3.eu-west-2.amazonaws.com/global-deterministic-10km/<RUN YYYYMMDDTHHMMZ>/
        <VALID>-PT<hhhh>H00M-<field>.nc  (temperature / relative_humidity / geopotential_height / wind_speed / wind_direction
        _on_pressure_levels, height_of_orography, temperature_at_surface). Read with h5py. No surface pressure or land mask
      files: surface pressure from its own profile, land mask from GFS. ~3-6 h latency.
GEOS  NASA GMAO GEOS-FP analysis by OPeNDAP (GrADS Data Server, no sign-in): https://opendap.nccs.nasa.gov/dods/GEOS-5/fp/0.25_deg/
      assim/inst3_3d_asm_Np (T, QV, U, V, H, PS, PHIS on 42 levels), assim/inst3_2d_asm_Nx (TS), const_2d_asm_Nx (FRLAND,
      FRLANDICE); else the newest fcast/inst3_3d_asm_Np/<init> forecast valid at the time.
NAVGEM US Navy NAVGEM 0.5 deg GRIB2 on NOAA NOMADS (no index):
        https://nomads.ncep.noaa.gov/pub/data/nccf/com/fnmoc/prod/navgem.<YYYYMMDD>/navgem_<YYYYMMDDHH>f<hhh>.grib2
      (unverified here whether these files carry all pressure levels; nothing is saved if they do not).
Missing surface fields: surface pressure from the centre's own geopotential profile at its terrain; otherwise, and for sea
temperature / land mask / terrain, the GFS field (each substitute is listed in 'notes' and in the log). For the four centres
above, below-ground points left undefined are extrapolated (temperature 6.5 K/km, hypsometric geopotential, humidity and
wind from the level above).
Output: /tmp/cyc_out/live_<ICON|CMC|ARPEGE|UKMO|GEOS|NAVGEM>_<run>.npz with the keys of live_GFSM (f3 [1, var, lev, lat, lon],
f2 [1, var, lat, lon], times, lats, lons, v3, v2, levs) plus source ('<centre run>+<lag>h'), lag_h and notes. ~3-7 MB each.
Log: data/cyclone/fetch_status.json, one key per centre (every URL tried is logged; other keys in that file are kept).
Each centre runs in its own thread with its own time budget (CENTRES_MAX_S, default 1500 s); a failure never affects the others."""
import os, re, sys, bz2, json, time, html, urllib.parse, datetime as dt, concurrent.futures as cf, threading
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import cyc_fetch as C

LATS = np.arange(-90, 90.1, 1.5); LONS = np.arange(0, 360, 1.5)
LEVS = [50, 100, 150, 200, 250, 300, 400, 500, 600, 700, 850, 925, 1000]
V3 = ['temperature', 'specific_humidity', 'u_component_of_wind', 'v_component_of_wind', 'geopotential']
V2 = ['surface_pressure', 'sea_surface_temperature', 'land_sea_mask', 'geopotential_at_surface']
G = 9.80665; RD = 287.04; EPS = 287.04 / 461.51
ALL = ('ICON', 'CMC', 'ARPEGE', 'UKMO', 'GEOS', 'NAVGEM')                                         # every centre fetch_all knows
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
                    if k not in C.LOG and k not in ('VITALS',) + ALL: C.LOG[k] = v
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

def extrapolate_below(f3, notes):
    """points missing at a level but present at the level above (GEOS-FP and some others leave below-ground points
    undefined): extrapolated downward as most centres do - temperature with 6.5 K/km, geopotential hypsometric, humidity
    and wind copied from the level above."""
    iT, iZ = V3.index('temperature'), V3.index('geopotential'); o = list(np.argsort(LEVS)); n = 0
    for a, b in zip(o[:-1], o[1:]):                                                          # a: the level above b
        pa, pb = LEVS[a] * 100.0, LEVS[b] * 100.0
        m = ~np.isfinite(f3[iT, b]) & np.isfinite(f3[iT, a]) & np.isfinite(f3[iZ, a])
        if not m.any(): continue
        Ta = f3[iT, a]; Tb = Ta * (pb / pa) ** (RD * 0.0065 / G)
        f3[iT, b][m] = Tb[m]; f3[iZ, b][m] = (f3[iZ, a] - RD * 0.5 * (Ta + Tb) * np.log(pb / pa))[m]
        for i, v in enumerate(V3):
            if v in ('temperature', 'geopotential'): continue
            mm = m & ~np.isfinite(f3[i, b]); f3[i, b][mm] = f3[i, a][mm]
        n += int(m.sum())
    if n: notes.append(f'below-ground points extrapolated ({n})')

def fill_z_hypsometric(f3, notes):
    """fill geopotential on levels where it is missing from the nearest level that has it, layer by layer with the
    hypsometric equation dPhi = Rd * Tv_mean * ln(p_lower / p_upper) (Tv = T (1 + 0.608 q))."""
    iT, iQ, iZ = V3.index('temperature'), V3.index('specific_humidity'), V3.index('geopotential'); L = len(LEVS)
    have = [bool(np.isfinite(f3[iZ, k]).mean() > 0.9) for k in range(L)]
    if all(have) or not any(have) or np.isfinite(f3[iT]).mean() < 0.9: return
    Tv = f3[iT] * (1 + 0.608 * np.nan_to_num(f3[iQ]))
    order = sorted(range(L), key=lambda k: LEVS[k])                                          # top (low p) to bottom
    filled = []
    for _ in range(L):
        for a_, b_ in zip(order, order[1:]):                                                 # a_ above b_
            if have[a_] and not have[b_]:
                f3[iZ, b_] = f3[iZ, a_] - 287.04 * 0.5 * (Tv[a_] + Tv[b_]) * np.log(LEVS[b_] / LEVS[a_]); have[b_] = True; filled.append(LEVS[b_])
            elif have[b_] and not have[a_]:
                f3[iZ, a_] = f3[iZ, b_] + 287.04 * 0.5 * (Tv[a_] + Tv[b_]) * np.log(LEVS[b_] / LEVS[a_]); have[a_] = True; filled.append(LEVS[a_])
    if filled: notes.append('geopotential from hypsometric equation at ' + ','.join(str(int(x)) for x in sorted(filled)))
def finish(src, run, r0, lag, f3, f2, gfs_f2, notes, raw, fill_below=False):
    """unit fixes, humidity, surface substitutes, checks, save. fill_below: extrapolate missing below-ground points."""
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
            rh = raw['rh'][k] * (100.0 if np.nanmax(raw['rh']) <= 1.5 else 1.0)                  # fraction or %: judged on all levels (a dry top level alone misleads)
            f3[iQ, k] = q_from_rh(rh, f3[iT, k], p)
            if 'q from RH (over water)' not in notes: notes.append('q from RH (over water)')
        elif 'depr' in raw and np.isfinite(raw['depr'][k]).any() and np.isfinite(f3[iT, k]).any():
            f3[iQ, k] = q_from_e(es_water(f3[iT, k] - raw['depr'][k]), p)
            if 'q from dew-point depression' not in notes: notes.append('q from dew-point depression')
    fill_z_hypsometric(f3, notes)                                                             # heights missing on some levels (UK Met Office)
    if fill_below: extrapolate_below(f3, notes)
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

# ------------------------------------------------------------------ GRIB2 files without an index (Météo-France, NAVGEM)
class Stream:
    """sequential reader of a (large) HTTP object; after a dropped connection it reconnects with a byte range."""
    def __init__(self, url, tries=4, timeout=120):
        self.url, self.tries, self.timeout, self.pos, self.r, self.end = url, tries, timeout, 0, None, None
    def _open(self):
        h = {'User-Agent': 'tn-rainfall-map cyclone study'}
        if self.pos: h['Range'] = f'bytes={self.pos}-'
        self.r = urllib.request.urlopen(urllib.request.Request(self.url, headers=h), timeout=self.timeout)
        if self.pos and getattr(self.r, 'status', 206) != 206: self.close(); raise IOError('byte range not honoured')
        m = re.search(r'/(\d+)\s*$', self.r.headers.get('Content-Range') or ''); cl = self.r.headers.get('Content-Length')
        if m: self.end = int(m.group(1))
        elif cl and cl.isdigit(): self.end = self.pos + int(cl)
    def read(self, n):
        out = bytearray(); err = 0
        while len(out) < n:
            try:
                if self.r is None: self._open()
                b = self.r.read(min(n - len(out), 1 << 24))
                if not b:
                    if self.end is not None and self.pos < self.end: raise IOError(f'connection closed at byte {self.pos} of {self.end}')
                    break                                                                      # end of the object
                out += b; self.pos += len(b)
            except urllib.error.HTTPError as e:
                self.close()
                if e.code in (403, 404, 416): raise
                err += 1
                if err >= self.tries: raise
                time.sleep(3 * err)
            except Exception:
                self.close(); err += 1
                if err >= self.tries: raise
                time.sleep(3 * err)
        return bytes(out)
    def close(self):
        try:
            if self.r is not None: self.r.close()
        except Exception: pass
        self.r = None

TUNIT_H = {0: 1 / 60, 1: 1.0, 2: 24.0, 10: 3.0, 11: 6.0, 12: 12.0, 13: 1 / 3600}
def g2_head(msg):
    """identification of a GRIB2 message (its first field) from the raw sections, without decoding: discipline, parameter
    category / number, product template, type and value of the first fixed surface, forecast hour, reference time."""
    out = dict(discipline=msg[6]); pos = 16
    while pos + 5 <= len(msg) and msg[pos:pos + 4] != b'7777':
        L = int.from_bytes(msg[pos:pos + 4], 'big'); num = msg[pos + 4]
        if L < 5: break
        s = msg[pos:pos + L]
        if num == 1 and len(s) >= 19:
            try: out['ref'] = dt.datetime(int.from_bytes(s[12:14], 'big'), s[14], s[15], s[16], s[17])
            except ValueError: pass
        elif num == 4 and len(s) >= 28:
            out.update(tmpl=int.from_bytes(s[7:9], 'big'), cat=s[9], num=s[10], t1=s[22])
            out['step_h'] = int.from_bytes(s[18:22], 'big') * TUNIT_H.get(s[17], float('nan'))
            sf, sv = s[23], int.from_bytes(s[24:28], 'big')
            if sf == 255 or sv == 0xFFFFFFFF: out['lev'] = None
            else:
                sf = -(sf & 0x7F) if sf & 0x80 else sf; sv = -(sv & 0x7FFFFFFF) if sv & 0x80000000 else sv
                out['lev'] = sv * 10.0 ** (-sf)
            break                                                                              # first field only
        pos += L
    return out

def scan(src, url, want, step, t_end, max_bytes=8e9):
    """read a GRIB2 file front to back (no index needed) and keep the wanted messages at forecast hour `step` (None: any).
    want: [(key, [(discipline, category, number), ...], [surface types], [levels hPa] or None)].
    -> {(key, hPa or None): message bytes}. Stops once all are found, at time t_end or after max_bytes."""
    need = {(k, h) for k, _, _, hs in want for h in (hs or [None])}; found = {}; s = Stream(url); n = 0; steps = set(); codes = set(); t0 = time.time()
    log(src, 'reading', url)
    try:
        while len(found) < len(need) and time.time() < t_end and s.pos < max_bytes:
            h0 = s.read(16)
            if len(h0) < 16: break
            if h0[:4] != b'GRIB': log(src, 'not a GRIB message at byte', s.pos - 16, h0[:8]); break
            L = int.from_bytes(h0[8:16], 'big') if h0[7] == 2 else int.from_bytes(h0[4:7], 'big')
            msg = h0 + s.read(L - 16)
            if len(msg) < L: log(src, 'file ends inside a message at byte', s.pos); break
            n += 1
            if h0[7] != 2: continue
            hd = g2_head(msg); steps.add(round(hd.get('step_h', -1), 2))
            if step is not None and abs(hd.get('step_h', -1e9) - step) > 0.01: continue
            cd = (hd['discipline'], hd.get('cat'), hd.get('num')); codes.add(cd + (hd.get('t1'),))
            for k, cds, t1s, hs in want:
                if cd not in cds or hd.get('t1') not in t1s: continue
                if hs:
                    h = None if hd.get('lev') is None else hd['lev'] / 100.0
                    h = next((x for x in hs if h is not None and abs(x - h) < 0.01), None)
                    if h is None: continue
                else: h = None
                if (k, h) not in found: found[(k, h)] = msg
                break
    except Exception as e: log(src, 'read failed', url, repr(e)[:200])
    finally: s.close()
    log(src, 'read', n, 'messages', round(s.pos / 1e6), 'MB in', int(time.time() - t0), 's; kept', len(found), 'of', len(need),
        '; forecast hours seen', sorted(steps)[:12])
    if len(found) < len(need):
        log(src, 'missing', sorted({k for k, _ in need - set(found)}), '; codes (discipline, category, number, surface) at that hour', sorted(codes)[:60])
    return found

def put_ll(src, found, f3, f2, raw):
    """decode kept messages onto our grid: 3-D keys into f3 (or raw for 'rh'/'depr'); surface keys ps/sst/lsm/zs into f2."""
    n = 0
    for (k, h), b in found.items():
        try: v, meta = decode(b); a = sample_ll(v, meta)
        except Exception as e: log(src, 'decode failed', k, h, repr(e)[:150]); continue
        if h is not None:
            if k in raw: raw[k][LEVS.index(int(h))] = a
            else: f3[V3.index(k), LEVS.index(int(h))] = a
        elif k == 'ps': f2[0] = a
        elif k == 'sst': f2[1] = a
        elif k == 'lsm': f2[2] = a
        elif k == 'zs':
            f2[3] = a * (1.0 if code(meta) == (0, 3, 4) else G); log(src, 'terrain from code', code(meta), meta.get('shortName'))
        n += 1
    return n

def terrain_ok(src, zs, gfs_f2):
    """a surface 'height' field is the terrain only if it is ~0 over the sea (else it is e.g. a boundary-layer height)."""
    if gfs_f2 is None or not np.isfinite(zs).any(): return np.isfinite(zs).mean() > 0.9
    sea = gfs_f2[2] < 0.5; med = float(np.nanmedian(np.abs(zs[sea]))) / G if sea.any() else 0.0
    if med > 50: log(src, 'surface height field is not the terrain (median', round(med), 'm over the sea): not used')
    return med <= 50

W3 = lambda: [('temperature', [(0, 0, 0)], [100], LEVS), ('u_component_of_wind', [(0, 2, 2)], [100], LEVS),
              ('v_component_of_wind', [(0, 2, 3)], [100], LEVS), ('geopotential', [(0, 3, 4), (0, 3, 5)], [100], LEVS)]

# ------------------------------------------------------------------ Météo-France ARPEGE global 0.25 deg
MF_HOSTS = ['https://meteofrance-pnt.s3.rbx.io.cloud.ovh.net', 'https://object.data.gouv.fr/meteofrance-pnt']
MF_API = 'https://www.data.gouv.fr/api/1/datasets/paquets-arpege-resolution-0-25deg/'
def mf_url(host, r, pkg, rng='000H024H'):
    t = f'{r:%Y-%m-%dT%H:%M:%SZ}'; return f'{host}/pnt/{t}/arpege/025/{pkg}/arpege__025__{pkg}__{rng}__{t}.grib2'
class Arpege:
    """packages (no index; read front to back, stopping when complete): IP1 isobaric T, RH, U, V, Z; IP2 isobaric q (else q from
    RH); SP2 surface pressure and surface temperature; land mask / terrain from the dataset's small constants file if found."""
    def api(self):
        b = C.http(MF_API, tries=2)
        if not b: log('ARPEGE', 'data.gouv.fr API not reachable', MF_API); return []
        try: res = json.loads(b).get('resources', [])
        except Exception as e: log('ARPEGE', 'data.gouv.fr API unreadable', repr(e)[:100]); return []
        out = [(str(r.get('title') or ''), str(r.get('url') or ''), r.get('filesize')) for r in res]
        log('ARPEGE', 'data.gouv.fr resources', len(out), 'e.g.', [o[1] for o in out[:3]]); return out
    def fetch(self, run, gfs_f2):
        t0 = time.time(); t_end = t0 + MAX_S; res = self.api(); hosts = list(MF_HOSTS)
        for _, u, _ in res:
            if '/pnt/' in u and '/arpege/' in u:
                h = u.split('/pnt/')[0]
                if h not in hosts: hosts.insert(0, h); log('ARPEGE', 'storage host from data.gouv.fr', h)
        r0 = lag = host = None
        for lg in (0, 6, 12, 18):
            rr = run - dt.timedelta(hours=lg)
            for h in hosts:
                u = mf_url(h, rr, 'IP1'); ok = C.http(u, tries=2, method='HEAD') is not None
                log('ARPEGE', 'try', u, 'found' if ok else 'no')
                if ok: r0, lag, host = rr, lg, h; break
            if r0: break
        if r0 is None: log('ARPEGE', 'no run found for', f'{run:%Y%m%d%H}'); return None
        want = {'IP1': W3() + [('rh', [(0, 1, 1)], [100], LEVS)], 'IP2': [('specific_humidity', [(0, 1, 0)], [100], LEVS)],
                'SP2': [('ps', [(0, 3, 0)], [1], None), ('sst', [(0, 0, 0), (0, 0, 17)], [1], None), ('lsm', [(2, 0, 0)], [1], None),
                        ('zs', [(0, 3, 4), (0, 3, 5), (0, 3, 6), (2, 0, 7)], [1], None)]}
        maxb = float(os.environ.get('ARPEGE_MAX_GB', '6')) * 1e9
        with cf.ThreadPoolExecutor(3) as ex:
            fut = {p: ex.submit(scan, 'ARPEGE', mf_url(host, r0, p), w, lag, t_end, maxb) for p, w in want.items()}
            found = {}
            for p, f in fut.items():
                try: found.update(f.result())
                except Exception as e: log('ARPEGE', p, 'failed', repr(e)[:200])
        if not any(k == 'lsm' for k, _ in found) or not any(k == 'zs' for k, _ in found):    # the constants file listed with the packages
            for title, u, size in res:
                if not re.search(r'\.grib2?(\.bz2)?$', u) or re.search(r'__\d{3}H\d{3}H__', u) or (size and size > 1e8): continue
                log('ARPEGE', 'constants candidate', title, u, size)
                found.update({kh: b for kh, b in scan('ARPEGE', u, [w for w in want['SP2'] if w[0] in ('lsm', 'zs')], None, t_end, 2e8).items() if kh not in found})
        f3 = np.full((len(V3), len(LEVS), len(LATS), len(LONS)), np.nan, np.float32); f2 = np.full((len(V2), len(LATS), len(LONS)), np.nan, np.float32)
        raw = {'rh': np.full((len(LEVS), len(LATS), len(LONS)), np.nan, np.float32)}
        n = put_ll('ARPEGE', found, f3, f2, raw); log('ARPEGE', 'fields', n, 'in', int(time.time() - t0), 's')
        if not terrain_ok('ARPEGE', f2[3], gfs_f2): f2[3] = np.nan
        return finish('ARPEGE', run, r0, lag, f3, f2, gfs_f2, [], raw, fill_below=True)

# ------------------------------------------------------------------ UK Met Office global 10 km (AWS open data, NetCDF)
UK_B = 'https://met-office-atmospheric-model-data.s3.eu-west-2.amazonaws.com'; UK_P = 'global-deterministic-10km'
UK3 = {'temperature': 'temperature_on_pressure_levels', 'rh': 'relative_humidity_on_pressure_levels', 'geopotential': 'geopotential_height_on_pressure_levels',
       'ws': 'wind_speed_on_pressure_levels', 'wd': 'wind_direction_on_pressure_levels'}
UK2 = {'zs': ['height_of_orography', 'surface_altitude'], 'sst': ['temperature_at_surface'], 'ps': ['pressure_at_surface', 'surface_air_pressure'],
       'lsm': ['land_binary_mask', 'land_fraction', 'land_area_fraction', 'land_sea_mask']}
def s3_keys(base, prefix, pages=20):
    """object keys under prefix (S3 ListObjectsV2, anonymous)."""
    keys, tok = [], None
    for _ in range(pages):
        q = {'list-type': '2', 'prefix': prefix, 'max-keys': '1000'}
        if tok: q['continuation-token'] = tok
        b = C.http(f'{base}/?{urllib.parse.urlencode(q)}', tries=3)
        if not b: break
        t = b.decode('utf-8', 'replace'); keys += [html.unescape(k) for k in re.findall(r'<Key>(.*?)</Key>', t)]
        m = re.search(r'<NextContinuationToken>(.*?)</NextContinuationToken>', t)
        if '<IsTruncated>true</IsTruncated>' not in t or not m: break
        tok = html.unescape(m.group(1))
    return keys

def download(url, path, t_end):
    s = Stream(url); n = 0
    try:
        with open(path, 'wb') as f:
            while time.time() < t_end:
                b = s.read(1 << 23)
                if not b: break
                f.write(b); n += len(b)
    finally: s.close()
    return n

def nc_main(path):
    """the main variable of a CF NetCDF4 file (h5py) -> (dataset, attrs, lat, lon, pressure in hPa or None, file)."""
    import h5py
    f = h5py.File(path, 'r'); D = {}
    f.visititems(lambda n, o: D.__setitem__(n.rsplit('/', 1)[-1], o) if isinstance(o, h5py.Dataset) else None)
    get = lambda names: next((np.asarray(D[k][()], float) for k in names if k in D and D[k].ndim == 1), None)
    lat, lon = get(('latitude', 'lat', 'grid_latitude')), get(('longitude', 'lon', 'grid_longitude'))
    if lat is None or lon is None: raise ValueError('no latitude/longitude; datasets ' + str(sorted(D)[:30]))
    p = get(('pressure', 'air_pressure', 'pressure_level', 'level'))
    if p is not None and np.nanmax(p) > 2000: p = p / 100.0
    cand = [o for k, o in D.items() if o.ndim >= 2 and not k.endswith('_bnds') and len(lat) in o.shape and len(lon) in o.shape]
    if not cand: raise ValueError('no 2-D field; datasets ' + str(sorted(D)[:30]))
    var = max(cand, key=lambda o: o.size); at = {}
    for k, v in var.attrs.items():
        try: at[k] = v.decode() if isinstance(v, bytes) else (v.item() if getattr(v, 'size', 2) == 1 else v)
        except Exception: pass
    return var, at, lat, lon, p, f

def nc_level(var, at, lat, lon, p, hpa=None):
    """one level (or the single field) of the main variable as [lat, lon] float32 with NaN for missing."""
    sh = var.shape; ia = sh.index(len(lat)); io = len(sh) - 1 - sh[::-1].index(len(lon)); idx = [0] * len(sh)
    idx[ia] = slice(None); idx[io] = slice(None)
    if hpa is not None:
        if p is None or len(p) < 2: raise ValueError('no pressure axis')
        k = int(np.argmin(np.abs(p - hpa)))
        if abs(p[k] - hpa) > 0.5: raise ValueError(f'level {hpa} not in file')
        ip = next(i for i, n in enumerate(sh) if n == len(p) and i not in (ia, io)); idx[ip] = k
    a = np.asarray(var[tuple(idx)], np.float64)
    if ia > io: a = a.T
    for k in ('_FillValue', 'missing_value'):
        if k in at:
            try: a[a == float(at[k])] = np.nan
            except Exception: pass
    a = a * float(at.get('scale_factor', 1.0)) + float(at.get('add_offset', 0.0))
    a[np.abs(a) > 1e20] = np.nan
    return a.astype(np.float32)

def sample_1d(a, la, lo):
    """[lat, lon] field on any regular lat-lon axes -> our grid, nearest point."""
    la = np.asarray(la, float); lo = np.asarray(lo, float) % 360
    ii = np.abs(la[None, :] - LATS[:, None]).argmin(1); jj = np.abs((lo[None, :] - LONS[:, None] + 180) % 360 - 180).argmin(1)
    ok = np.abs(la[ii] - LATS) <= max(float(np.max(np.abs(np.diff(la)))) if len(la) > 1 else 1.0, 0.1) + 1e-6
    out = np.full((len(LATS), len(LONS)), np.nan, np.float32); out[ok] = a[np.ix_(ii[ok], jj)]
    return out

class Ukmo:
    """one NetCDF file per field and lead (all pressure levels inside): T, RH, geopotential height, wind speed and direction;
    terrain and surface temperature from the surface files; surface pressure from its own geopotential profile (no surface
    pressure file), land mask from GFS unless a mask file exists. Licence: CC BY-SA 4.0 (Met Office, free, unsupported)."""
    def fetch(self, run, gfs_f2):
        t0 = time.time(); t_end = t0 + MAX_S; r0 = lag = None; keys = []
        for lg in (0, 6, 12, 18):
            rr = run - dt.timedelta(hours=lg); pre = f'{UK_P}/{rr:%Y%m%dT%H%MZ}/'
            ks = s3_keys(UK_B, pre); tag = f'-PT{lg:04d}H00M-'
            hit = [k for k in ks if tag in k and k.endswith(UK3['temperature'] + '.nc')]
            if not ks:                                                                         # listing refused: try the name itself
                u = f"{UK_B}/{pre}{rr + dt.timedelta(hours=lg):%Y%m%dT%H%MZ}{tag}{UK3['temperature']}.nc"
                if C.http(u, tries=2, method='HEAD') is not None: hit = [u[len(UK_B) + 1:]]; ks = None
            log('UKMO', 'run', pre, 'objects', None if ks is None else len(ks), 'lead', lg, 'found' if hit else 'no')
            if hit: r0, lag, keys = rr, lg, ks; break
        if r0 is None: log('UKMO', 'no run found for', f'{run:%Y%m%d%H}'); return None
        tag = f'-PT{lag:04d}H00M-'; vt = r0 + dt.timedelta(hours=lag); pre = f'{UK_P}/{r0:%Y%m%dT%H%MZ}/'
        if keys: log('UKMO', 'fields at this lead', sorted({k.split(tag, 1)[1][:-3] for k in keys if tag in k})[:80])
        def key_for(field, lead=lag):
            tg = f'-PT{lead:04d}H00M-'; name = f'{pre}{r0 + dt.timedelta(hours=lead):%Y%m%dT%H%MZ}{tg}{field}.nc'
            if keys is None or name in keys: return name
            return next((k for k in keys if tg in k and k.endswith(f'-{field}.nc')), None)
        f3 = np.full((len(V3), len(LEVS), len(LATS), len(LONS)), np.nan, np.float32); f2 = np.full((len(V2), len(LATS), len(LONS)), np.nan, np.float32)
        raw = {'rh': np.full((len(LEVS), len(LATS), len(LONS)), np.nan, np.float32)}; wind = {}; notes = []; tmp = os.path.join('/tmp', 'ukmo'); os.makedirs(tmp, exist_ok=True)
        jobs = [(k, f, True) for k, f in UK3.items()] + [(k, f, False) for k, fs in UK2.items() for f in fs]
        done = set()
        def one(j):
            k, field, is3 = j
            if k in done: return False
            kk = key_for(field) or (key_for(field, 0) if not is3 else None)                   # terrain may exist at lead 0 only
            if not kk: return False
            u = f'{UK_B}/{kk}'; path = os.path.join(tmp, field + '.nc')
            try:
                nb = download(u, path, t_end); log('UKMO', 'downloaded', u, round(nb / 1e6), 'MB')
                var, at, lat, lon, p, fh = nc_main(path)
                try:
                    log('UKMO', field, 'shape', var.shape, 'units', at.get('units'), 'standard_name', at.get('standard_name'), 'levels', None if p is None else len(p))
                    if is3:
                        for i, lev in enumerate(LEVS):
                            a = sample_1d(nc_level(var, at, lat, lon, p, lev), lat, lon)
                            if k == 'rh': raw['rh'][i] = a
                            elif k in ('ws', 'wd'): wind.setdefault(k, {})[i] = a
                            else: f3[V3.index(k), i] = a
                        if k == 'wd': wind['to'] = 'to_direction' in str(at.get('standard_name', ''))
                    else:
                        a = sample_1d(nc_level(var, at, lat, lon, p if p is not None and len(p) > 1 else None), lat, lon)
                        if k == 'zs': f2[3] = a * G
                        elif k == 'sst': f2[1] = a
                        elif k == 'ps': f2[0] = a
                        elif k == 'lsm': f2[2] = a
                    done.add(k); return True
                finally: fh.close()
            except Exception as e: log('UKMO', field, 'failed', repr(e)[:200]); return False
            finally:
                try: os.remove(path)
                except Exception: pass
        n = run_jobs('UKMO', jobs, one, t0, par=3)
        if 'ws' in wind and 'wd' in wind:
            sgn = 1.0 if wind.get('to') else -1.0                                            # 'from' direction (CF wind_from_direction): minus
            for i in range(len(LEVS)):
                if i in wind['ws'] and i in wind['wd']:
                    d = np.radians(wind['wd'][i]); f3[V3.index('u_component_of_wind'), i] = sgn * wind['ws'][i] * np.sin(d)
                    f3[V3.index('v_component_of_wind'), i] = sgn * wind['ws'][i] * np.cos(d)
            notes.append('u, v from wind speed and direction (' + ('to' if wind.get('to') else 'from') + ')')
        log('UKMO', 'files', n, 'in', int(time.time() - t0), 's; fields', sorted(done))
        return finish('UKMO', run, r0, lag, f3, f2, gfs_f2, notes, raw, fill_below=True)

# ------------------------------------------------------------------ NASA GMAO GEOS-FP (OPeNDAP, GrADS Data Server)
GDS = 'https://opendap.nccs.nasa.gov/dods/GEOS-5/fp/0.25_deg'
MON = {m: i + 1 for i, m in enumerate(('jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'))}
def grads_time(s):
    m = re.search(r'(?:(\d{1,2})(?::(\d{2}))?z)?(\d{1,2})([a-z]{3})(\d{4})', str(s).lower())
    if not m or m.group(4) not in MON: return None
    return dt.datetime(int(m.group(5)), MON[m.group(4)], int(m.group(3)), int(m.group(1) or 0), int(m.group(2) or 0))
def gds_time(ds):
    """(first time, step h, number of times) of a GrADS-DODS dataset from its .das, else its .info page."""
    for suf in ('.das', '.info'):
        b = C.http(ds + suf, tries=2)
        if not b: log('GEOS', 'no', ds + suf); continue
        t = b.decode('latin-1', 'replace')
        if suf == '.das':
            blk = re.search(r'\btime\s*\{(.*?)\}', t, re.S); g = lambda k: (re.search(k + r'\s+"([^"]+)"', blk.group(1)) if blk else None)
            mn, st, nn = [(x.group(1) if x else None) for x in (g('grads_min'), g('grads_step'), g('grads_size'))]
            m = re.match(r'(\d+)\s*(mn|hr|dy)', st or '')
            h = int(m.group(1)) * {'mn': 1 / 60, 'hr': 1, 'dy': 24}[m.group(2)] if m else None
        else:
            t = re.sub(r'<[^>]+>', ' ', t); m = re.search(r'Time:\s*(\S+)\s+to\s+\S+\s+\((\d+)\s+points?,\s*avg\.\s*res\.\s*([0-9.]+)\s*days', t)
            mn, nn, h = (m.group(1), m.group(2), round(float(m.group(3)) * 24, 3)) if m else (None, None, None)
        t0 = grads_time(mn)
        if t0 and h: log('GEOS', ds.rsplit('/', 1)[-1], 'times from', t0, 'every', h, 'h, count', nn, '(' + suf + ')'); return t0, h, int(nn) if nn else None
    return None
def gds_values(txt):
    """numbers of the first array in a GrADS-DODS ASCII reply ('[i][j], v, v, ...' rows or a plain list)."""
    out = []; started = False
    for ln in txt.splitlines():
        s = ln.strip()
        if not s:
            if started: break
            continue
        if s.startswith('['): s = s.split(',', 1)[1] if ',' in s else ''
        try: vals = [float(x) for x in s.split(',') if x.strip()]
        except ValueError:
            if started: break
            continue
        out += vals; started = True
    return np.array(out, float)
class Geos:
    """inst3_3d_asm_Np (42 pressure levels, 0.25 x 0.3125 deg): T, QV, U, V, H (geopotential height), PS, PHIS; TS from
    inst3_2d_asm_Nx (sea temperature over sea); FRLAND + FRLANDICE from const_2d_asm_Nx. Subset by OPeNDAP (every 6th latitude,
    all longitudes, one level per request). Below-ground points are undefined in GEOS: extrapolated. Analysis at the
    GFS time if out, else the newest GEOS-FP forecast valid then."""
    def index(self, ds, when):
        tt = gds_time(ds)
        if not tt: return None
        t0, h, n = tt; i = (when - t0).total_seconds() / 3600.0 / h
        if abs(i - round(i)) > 1e-6 or i < 0 or (n is not None and i > n - 1): log('GEOS', ds, 'has no', f'{when:%Y%m%d%H}', '(index', round(i, 2), 'of', n, ')'); return None
        return int(round(i))
    def get(self, ds, var, ti, k=None):
        la = np.round((LATS + 90) / 0.25).astype(int); d = np.diff(la)
        lat_s = f'[{la[0]}:{d[0]}:{la[-1]}]' if len(la) > 1 and (d == d[0]).all() and d[0] > 0 else '[0:1:720]'
        url = f"{ds}.ascii?{var}[{ti}:{ti}]" + (f'[{k}:{k}]' if k is not None else '') + lat_s + '[0:1:1151]'
        b = C.http(url, tries=3)
        if not b: log('GEOS', 'no reply', url); return None
        v = gds_values(b.decode('latin-1', 'replace')); ny = len(la) if lat_s != '[0:1:720]' else 721
        if v.size != ny * 1152: log('GEOS', 'unexpected reply', url, v.size, b[:200]); return None
        v = v.reshape(ny, 1152); v[np.abs(v) > 1e14] = np.nan
        if ny == 721: v = v[la]
        jj = np.round(((LONS + 180.0) % 360.0) / 0.3125).astype(int) % 1152
        return v[:, jj].astype(np.float32)
    def fetch(self, run, gfs_f2):
        t0 = time.time(); ds3 = f'{GDS}/assim/inst3_3d_asm_Np'; ds2 = f'{GDS}/assim/inst3_2d_asm_Nx'; lag = 0; r0 = run
        ti = self.index(ds3, run)
        if ti is None:                                                                         # newest forecast valid at this time
            names = [re.sub(r'\.(das|dds|html|info|ascii)$', '', n.rstrip('/')) for n in listing(f'{GDS}/fcast/inst3_3d_asm_Np/')]   # listing entries carry a .das suffix
            log('GEOS', 'forecast datasets', len(names), names[-4:])
            for lg in (6, 12, 18, 24, 30, 36):
                rr = run - dt.timedelta(hours=lg); nm = next((n for n in names if f'{rr:%Y%m%d_%H}' in n), None)
                if not nm: continue
                ds3 = f'{GDS}/fcast/inst3_3d_asm_Np/{nm}'; ti = self.index(ds3, run)
                if ti is not None:
                    r0, lag = rr, lg; n2 = [n.rstrip('/') for n in listing(f'{GDS}/fcast/inst3_2d_asm_Nx/')]
                    m2 = next((re.sub(r'\.(das|dds|html|info|ascii)$', '', n) for n in n2 if f'{rr:%Y%m%d_%H}' in n), None); ds2 = f'{GDS}/fcast/inst3_2d_asm_Nx/{m2}' if m2 else None; break
            if ti is None: log('GEOS', 'no analysis or forecast for', f'{run:%Y%m%d%H}'); return None
        b = C.http(f'{ds3}.ascii?lev', tries=3); lev = gds_values(b.decode('latin-1', 'replace')) if b else np.array([])
        if lev.size < 13: lev = np.array([1000, 975, 950, 925, 900, 875, 850, 825, 800, 775, 750, 725, 700, 650, 600, 550, 500, 450, 400, 350, 300, 250, 200,
                                          150, 100, 70, 50, 40, 30, 20, 10, 7, 5, 4, 3, 2, 1, 0.7, 0.5, 0.4, 0.3, 0.1], float); log('GEOS', 'levels from the file specification')
        log('GEOS', 'using', ds3, 'time index', ti, 'run', f'{r0:%Y%m%d%H}+{lag}h')
        f3 = np.full((len(V3), len(LEVS), len(LATS), len(LONS)), np.nan, np.float32); f2 = np.full((len(V2), len(LATS), len(LONS)), np.nan, np.float32)
        VN = {'temperature': 't', 'specific_humidity': 'qv', 'u_component_of_wind': 'u', 'v_component_of_wind': 'v', 'geopotential': 'h'}
        jobs = [(v, i) for v in V3 for i in range(len(LEVS))] + [('ps', None), ('phis', None), ('ts', None), ('frland', None), ('frlandice', None)]
        cst = {}
        def one(j):
            v, i = j
            if i is not None:
                k = int(np.argmin(np.abs(lev - LEVS[i])))
                if abs(lev[k] - LEVS[i]) > 0.01: return False
                a = self.get(ds3, VN[v], ti, k)
                if a is None: return False
                f3[V3.index(v), i] = a * (G if v == 'geopotential' else 1.0); return True
            if v in ('ps', 'phis'):
                a = self.get(ds3, v, ti)
                if a is not None: f2[0 if v == 'ps' else 3] = a
            elif v == 'ts':
                t2 = self.index(ds2, run) if ds2 else None; a = self.get(ds2, 'ts', t2) if t2 is not None else None
                if a is not None: f2[1] = a
            else:
                for dsc in (f'{GDS}/assim/const_2d_asm_Nx', f'{GDS}/const/const_2d_asm_Nx'):
                    a = self.get(dsc, v, 0)
                    if a is not None: cst[v] = a; break
            return a is not None
        n = run_jobs('GEOS', jobs, one, t0, par=4)
        if 'frland' in cst: f2[2] = cst['frland'] + np.nan_to_num(cst.get('frlandice', 0.0))
        log('GEOS', 'fields', n, 'of', len(jobs), 'in', int(time.time() - t0), 's')
        return finish('GEOS', run, r0, lag, f3, f2, gfs_f2, [], {}, fill_below=True)

# ------------------------------------------------------------------ US Navy NAVGEM (NOAA NOMADS, GRIB2 0.5 deg, no index)
NAV = 'https://nomads.ncep.noaa.gov/pub/data/nccf/com/fnmoc/prod'
class Navgem:
    """whole file per lead (no .idx on NOMADS), read front to back; isobaric T, RH (or q), U, V, HGT; surface PRES, LAND, HGT,
    TMP. Unverified from here: whether the NOMADS files carry all 13 pressure levels (the job log lists what they hold)."""
    def fetch(self, run, gfs_f2):
        t0 = time.time(); t_end = t0 + MAX_S; url = r0 = lag = None
        for lg in (0, 6, 12, 18):
            rr = run - dt.timedelta(hours=lg); d = f'{NAV}/navgem.{rr:%Y%m%d}/'; names = listing(d, tries=2)
            cands = [f'navgem_{rr:%Y%m%d%H}f{lg:03d}.grib2', f'navgem_{rr:%Y%m%d%H}f{lg:04d}.grib2']
            hit = next((c for c in cands if c in names), None)
            if hit is None and not names:
                hit = next((c for c in cands if C.http(d + c, tries=2, method='HEAD') is not None), None)
            log('NAVGEM', 'try', d, 'files', len(names), [n for n in names if f'{rr:%Y%m%d%H}' in n][:6], 'found' if hit else 'no')
            if hit: url, r0, lag = d + hit, rr, lg; break
        if url is None: log('NAVGEM', 'no run found for', f'{run:%Y%m%d%H}'); return None
        want = W3() + [('rh', [(0, 1, 1)], [100], LEVS), ('specific_humidity', [(0, 1, 0)], [100], LEVS), ('ps', [(0, 3, 0)], [1], None),
                       ('lsm', [(2, 0, 0)], [1], None), ('zs', [(0, 3, 5), (0, 3, 4)], [1], None), ('sst', [(0, 0, 0), (10, 3, 0)], [1], None)]
        found = scan('NAVGEM', url, want, lag, t_end, 2e9)
        f3 = np.full((len(V3), len(LEVS), len(LATS), len(LONS)), np.nan, np.float32); f2 = np.full((len(V2), len(LATS), len(LONS)), np.nan, np.float32)
        raw = {'rh': np.full((len(LEVS), len(LATS), len(LONS)), np.nan, np.float32)}
        n = put_ll('NAVGEM', found, f3, f2, raw); log('NAVGEM', 'fields', n, 'in', int(time.time() - t0), 's')
        if not terrain_ok('NAVGEM', f2[3], gfs_f2): f2[3] = np.nan
        return finish('NAVGEM', run, r0, lag, f3, f2, gfs_f2, [], raw, fill_below=True)

# ------------------------------------------------------------------ entry point
def fetch_all(run, gfs_f2=None, levs=None, lats=None, lons=None, which=None):
    """fetch the centres (default all of ALL) in parallel; never raises. gfs_f2: the GFS surface fields [V2, lat, lon] for substitutes."""
    which = tuple(which or ALL)
    global LEVS, LATS, LONS
    if levs is not None and list(levs) != LEVS: LEVS = [int(x) for x in levs]
    if lats is not None: LATS = np.asarray(lats, float)
    if lons is not None: LONS = np.asarray(lons, float)
    if gfs_f2 is not None: gfs_f2 = np.asarray(gfs_f2, np.float32)
    jobs = {'ICON': lambda: Icon().fetch(run, gfs_f2), 'CMC': lambda: Cmc().fetch(run, gfs_f2), 'ARPEGE': lambda: Arpege().fetch(run, gfs_f2),
            'UKMO': lambda: Ukmo().fetch(run, gfs_f2), 'GEOS': lambda: Geos().fetch(run, gfs_f2), 'NAVGEM': lambda: Navgem().fetch(run, gfs_f2)}; res = {}
    with cf.ThreadPoolExecutor(len(which)) as ex:
        fut = {w: ex.submit(jobs[w]) for w in which}
        for w, f in fut.items():
            try: res[w] = f.result()
            except Exception as e:
                import traceback; log(w, 'FAILED', repr(e)[:300], traceback.format_exc()[-600:]); res[w] = None
    return res

if __name__ == '__main__':                                                                    # python centres_m.py [YYYYMMDDHH] [ICON CMC ARPEGE UKMO GEOS NAVGEM]
    r = dt.datetime.strptime(sys.argv[1], '%Y%m%d%H') if len(sys.argv) > 1 else C.latest_run(lambda r: C.http(C.gfs_url(r, 0) + '.idx', method='HEAD') is not None)
    print(fetch_all(r, which=tuple(sys.argv[2:]) or ALL))
