"""Observing network for the OSSE (synthetic observations at plausible places), in obs_fetch.py's record format.

Real positions where we have them: the 306 Indian SYNOP stations, 465 METAR airports (30-120E, 40S-40N) and 16 Indian
radiosonde stations from obs_fetch's 22 Oct 2026 12Z run (stations_obs2026102212.json). Elsewhere a plausible global
network on the model's land-sea mask (fixed random seed, so every cycle uses the same stations):
  land surface stations  ~2.5-deg candidates, kept with probability 0.8 (20-70N), 0.55 (tropics), 0.45 (south),
                         0.15 (Antarctica); not within 250 km of a real station; ps, t (2 m), q (2 m), u, v (10 m)
  radiosondes            ~6.5-deg land/coast candidates, probability 0.75 north / 0.45 elsewhere (~300 + 16 real);
                         full set at 00/12Z, 15 % at 06/18Z; levels 1000-100 hPa (11), t, u, v (+ q up to 300 hPa)
  buoys and ships        ~6-deg sea candidates, probability 0.35; ps, plus u, v for a third (ships)
  scatterometer          10-m u, v on a 2-deg grid inside 10 random polar-orbit swaths per 6 h (two satellites),
                         |lat| <= 70, sea only (ASCAT-like, ~25-30 % of the ocean per cycle)
Aircraft and satellite radiances are not simulated (we do not have them in real time either)."""
import os, json, math, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
SONDE_LEVS = (1000, 925, 850, 700, 500, 400, 300, 250, 200, 150, 100)

def _bilin(F, lon, lat, olat, olon):
    import obsop
    return obsop.Geometry(lon, lat, olat, olon).apply(np.asarray(F, np.float32))

def _near(la1, lo1, la2, lo2, km):
    """[n1] bool: any point of set 2 within km."""
    if len(la2) == 0: return np.zeros(len(la1), bool)
    from scipy.spatial import cKDTree
    import letkf
    t = cKDTree(letkf.unit_xyz(la2, lo2)); d, _ = t.query(letkf.unit_xyz(la1, lo1), k=1)
    return letkf.great_circle_km(d) < km

def build(lon, lat, land, zs, seed=7, stations=os.path.join(HERE, 'stations_obs2026102212.json')):
    """static station list: dict(kind -> dict(lat, lon, z, sid)). land, zs [X, Y] on the model grid (lon, lat axes)."""
    rs = np.random.default_rng(seed); R = json.load(open(stations)) if stations and os.path.exists(stations) else {}
    real_sfc = [r for k in ('synop', 'metar') for r in R.get(k, [])]
    rla = np.array([r[1] for r in real_sfc], float); rlo = np.array([r[2] for r in real_sfc], float)
    def cand(step, jitter):
        la = np.arange(-88.75, 89, step); lo = np.arange(0, 360, step); LA, LO = np.meshgrid(la, lo, indexing='ij')
        LA = np.clip(LA + rs.uniform(-jitter, jitter, LA.shape), -89, 89); LO = (LO + rs.uniform(-jitter, jitter, LO.shape)) % 360
        lf = _bilin(land, lon, lat, LA.ravel(), LO.ravel()); return LA.ravel(), LO.ravel(), lf
    out = {}
    # land surface stations
    la, lo, lf = cand(2.5, 1.0)
    p = np.where(la < -60, 0.15, np.where(la < -20, 0.45, np.where(la < 20, 0.55, np.where(la < 70, 0.8, 0.4))))
    m = (lf > 0.5) & (rs.uniform(size=la.size) < p) & ~_near(la, lo, rla, rlo, 250.0)
    z = _bilin(zs, lon, lat, la[m], lo[m]) + rs.normal(0, 60.0, m.sum())                    # station vs model terrain: +-60 m
    out['synop'] = dict(lat=np.concatenate([la[m], rla]), lon=np.concatenate([lo[m], rlo]),
                        z=np.concatenate([np.maximum(z, 0), np.array([np.nan if r[3] is None else r[3] for r in real_sfc], float)]),
                        sid=np.array(['s%05d' % i for i in range(m.sum())] + [r[0] for r in real_sfc]))
    # radiosondes
    la, lo, lf = cand(6.5, 2.0); p = np.where(la > 20, 0.75, 0.45)
    m = (lf > 0.3) & (rs.uniform(size=la.size) < p)
    rt = R.get('temp', []); tla = np.array([r[1] for r in rt], float); tlo = np.array([r[2] for r in rt], float)
    m &= ~_near(la, lo, tla, tlo, 500.0)
    out['temp'] = dict(lat=np.concatenate([la[m], tla]), lon=np.concatenate([lo[m], tlo]), sid=np.array(['t%04d' % i for i in range(m.sum())] + [r[0] for r in rt]))
    out['temp']['synoptic_only'] = rs.uniform(size=len(out['temp']['lat'])) > 0.15        # True: no 06/18Z ascent
    # buoys / ships
    la, lo, lf = cand(6.0, 2.5); m = (lf < 0.05) & (rs.uniform(size=la.size) < 0.35) & (np.abs(la) < 75)
    out['marine'] = dict(lat=la[m], lon=lo[m], sid=np.array(['b%04d' % i for i in range(m.sum())]), ship=rs.uniform(size=m.sum()) < 1 / 3)
    return out

def scat_points(lon, lat, land, cycle, seed=11):
    """scatterometer superobs for one 6-h cycle: 2-deg cells inside 10 swaths (each ~1100 km wide, polar orbit)."""
    rs = np.random.default_rng(seed + 1000 * cycle)
    la = np.arange(-69, 70, 2.0); lo = np.arange(0, 360, 2.0); LA, LO = np.meshgrid(la, lo, indexing='ij'); LA = LA.ravel(); LO = LO.ravel()
    inside = np.zeros(LA.size, bool)
    for _ in range(10):
        l0 = rs.uniform(0, 360); tilt = rs.uniform(-0.25, 0.25)                             # near-polar track, slight slope
        track = (l0 + tilt * LA * 4) % 360; dx = (LO - track + 180) % 360 - 180
        inside |= np.abs(dx * np.cos(np.radians(LA))) * 111.2 < 550.0
    lf = _bilin(land, lon, lat, LA, LO); m = inside & (lf < 0.01)
    return LA[m], LO[m]

def records(net, hour, lon, lat, land, cycle):
    """observation records (no values yet) for one analysis time: dict of arrays type, sid, lat, lon, p (hPa or NaN), z, var."""
    rows = {k: [] for k in ('type', 'sid', 'lat', 'lon', 'p', 'z', 'var')}
    def add(t, s, la, lo, p, z, v):
        n = len(la); rows['type'].append(np.full(n, t)); rows['sid'].append(np.asarray(s)); rows['lat'].append(np.asarray(la, float))
        rows['lon'].append(np.asarray(lo, float)); rows['p'].append(np.full(n, p, float)); rows['z'].append(np.asarray(z, float) * np.ones(n)); rows['var'].append(np.full(n, v))
    S = net['synop']
    for v in ('ps', 't', 'q', 'u', 'v'): add('synop', S['sid'], S['lat'], S['lon'], np.nan, S['z'], v)
    T = net['temp']; sel = np.ones(len(T['lat']), bool) if hour % 12 == 0 else ~T['synoptic_only']
    for P in SONDE_LEVS:
        for v in ('t', 'u', 'v') + (('q',) if P >= 300 else ()):
            add('temp', T['sid'][sel], T['lat'][sel], T['lon'][sel], float(P), np.nan, v)
    B = net['marine']
    add('buoy', B['sid'][~B['ship']], B['lat'][~B['ship']], B['lon'][~B['ship']], np.nan, 0.0, 'ps')
    for v in ('ps', 'u', 'v'): add('ship', B['sid'][B['ship']], B['lat'][B['ship']], B['lon'][B['ship']], np.nan, 0.0, v)
    la, lo = scat_points(lon, lat, land, cycle); sid = np.array(['c%05d' % i for i in range(len(la))])
    for v in ('u', 'v'): add('scat', sid, la, lo, np.nan, 0.0, v)
    return {k: np.concatenate(v) for k, v in rows.items()}
