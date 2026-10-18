"""ERA5 case-study analysis: loading, climatology, system tracking and the diagnostics for one event."""
import json, os, glob, datetime as dt, numpy as np
from scipy import ndimage as nd
HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, 'data')
REPO = '/home/claude/tn-rainfall-map'
HIST = '/tmp/claude-0/-home-claude/2c3b34a9-cc00-53e0-8864-49737f9cdb93/scratchpad/wtdata/data/history/tnsmart/'
ST = json.load(open(f'{REPO}/data/stations.json'))
LAND = json.load(open('/tmp/claude-0/-home-claude/2c3b34a9-cc00-53e0-8864-49737f9cdb93/scratchpad/land.json'))
LEVS = (925, 850, 700, 500, 300, 200)
def unpack(Z, k):
    q = Z[k]; a = q.astype(np.float32) + 32500
    a = a * float(Z[k + '__scale']) + (float(Z[k + '__off']) - 32500 * float(Z[k + '__scale']))
    a[q == -32768] = np.nan
    return a
class Event:
    def __init__(self, name, day):
        Z = np.load(os.path.join(DATA, name + '.npz')); self.name = name; self.day = dt.date.fromisoformat(day) if isinstance(day, str) else day
        lat = Z['lat'].astype(float); flip = lat[0] > lat[-1]
        self.lat = lat[::-1] if flip else lat; self.lon = Z['lon'].astype(float)
        self.times = [dt.datetime.strptime(str(t), '%Y%m%d%H') for t in Z['times']]
        self.f = {}
        for k in Z.files:
            if k.endswith('__off') or k.endswith('__scale') or k in ('lat', 'lon', 'times', 'rain_days', 'rain'): continue
            a = unpack(Z, k); self.f[k] = a[:, ::-1] if flip else a
        for p in LEVS:                                          # relative humidity from q and T where the file lacks it
            if f'r{p}' not in self.f and f'q{p}' in self.f and f't{p}' in self.f:
                T = self.f[f't{p}']; es = 6.112 * np.exp(17.67 * (T - 273.15) / (T - 29.65)); qs = 0.622 * es / (p - 0.378 * es)
                self.f[f'r{p}'] = np.clip(100 * self.f[f'q{p}'] / 1000 / qs, 0, 110)
        self.rain_days = [str(x) for x in Z['rain_days']] if 'rain_days' in Z.files else []
        if self.rain_days:
            a = unpack(Z, 'rain'); self.rain = a[:, ::-1] if flip else a
        self.res = float(abs(self.lon[1] - self.lon[0]))
    def ti(self, t):
        return self.times.index(t) if t in self.times else None
    def ij(self, la, lo):
        return int(np.abs(self.lat - la).argmin()), int(np.abs(self.lon - lo).argmin())
    def box(self, k, it, la, lo, r=1.0, fn=np.nanmean):
        a = self.f[k][it]; m = (np.abs(self.lat - la) <= r)[:, None] & (np.abs(self.lon - lo) <= r)[None, :]
        return float(fn(a[m]))
    def dist_mask(self, la, lo, r0, r1):
        LA, LO = np.meshgrid(self.lat, self.lon, indexing='ij'); d = np.hypot(LA - la, (LO - lo) * np.cos(np.radians(la)))
        return (d >= r0) & (d <= r1)
class ClimDaily:
    """1990-2019 day-of-year climatology (WeatherBench2), regridded to the event grid; units as in the event files."""
    UNIT = {'z': 1 / 9.80665, 'q': 1000.0, 'msl': 0.01, 'r': 100.0}
    def __init__(self, lat, lon):
        from scipy.interpolate import RegularGridInterpolator
        Z = np.load(os.path.join(DATA, 'era5_clim_daily.npz')); la = Z['lat'].astype(float); lo = Z['lon'].astype(float)
        o = np.argsort(la); self._la = la[o]; self._lo = lo; self._o = o; self.doy = Z['doy']
        self.raw = {}
        for k in Z.files:
            if k in ('lat', 'lon', 'doy'): continue
            a = Z[k]; self.raw[k] = np.swapaxes(a, 1, 2) if a.shape[1] == len(lo) and a.shape[2] == len(la) else a   # stored (doy, lon, lat)
        self.lat, self.lon = lat, lon; self._c = {}
        LA, LO = np.meshgrid(lat, lon, indexing='ij'); self._pts = np.stack([LA.ravel(), LO.ravel()], -1); self._RGI = RegularGridInterpolator
    def at(self, k, t):
        src = {'ivtu': None, 'ivtv': None, 'ivt': None}.get(k, k)          # WB2's vapour-transport climatology is not in kg/m/s
        if src not in self.raw: return None
        d = t.date() if isinstance(t, dt.datetime) else t; doy = d.timetuple().tm_yday; key = (src, doy)
        if key not in self._c:
            a = self.raw[src][int(np.abs(self.doy - doy).argmin())][self._o].astype(float)
            if np.isnan(a).any():                                  # fill land holes (sea temperature) from the nearest sea value
                idx = nd.distance_transform_edt(np.isnan(a), return_distances=False, return_indices=True); a = a[tuple(idx)]
            base = ''.join(c for c in src if not c.isdigit()); a = a * self.UNIT.get(base, 1.0)
            if src == 'sst': a = a - 273.15
            f = self._RGI((self._la, self._lo), a, bounds_error=False, fill_value=None)
            self._c[key] = f(self._pts).reshape(len(self.lat), len(self.lon))
        return self._c[key]
class Clim:
    def __init__(self):
        Z = np.load(os.path.join(DATA, 'era5_clim_1991_2020.npz')); lat = Z['lat'].astype(float); flip = lat[0] > lat[-1]
        self.lat = lat[::-1] if flip else lat; self.lon = Z['lon'].astype(float)
        self.f = {k: (Z[k][:, ::-1] if flip else Z[k]) for k in Z.files if k not in ('lat', 'lon')}
    def at(self, k, t):
        """Monthly means interpolated to the day (mid-month anchors)."""
        if k not in self.f: return None
        d = t.date() if isinstance(t, dt.datetime) else t
        mid = dt.date(d.year, d.month, 15)
        if d >= mid:
            m2 = d.month % 12 + 1; nxt = dt.date(d.year + (d.month == 12), m2, 15); w = (d - mid).days / (nxt - mid).days
            return (1 - w) * self.f[k][d.month - 1] + w * self.f[k][m2 - 1]
        m0 = (d.month - 2) % 12 + 1; prv = dt.date(d.year - (d.month == 1), m0, 15); w = (mid - d).days / (mid - prv).days
        return (1 - w) * self.f[k][d.month - 1] + w * self.f[k][m0 - 1]
def tnsmart(day):
    fn = HIST + day + '.json'
    if not os.path.exists(fn): return {}
    return {k: v for k, v in json.load(open(fn)).items() if v is not None and k in ST}
def target(day_file):
    """Heaviest-rain centre for a TN SMART report: rain-weighted centre of the gauges with >= half the day's top."""
    d = tnsmart(day_file)
    if not d: return None
    mx = max(d.values()); g = [(v, ST[k]) for k, v in d.items() if v >= 0.5 * mx]
    w = np.array([v for v, _ in g]); la = float(np.sum(w * [s['lat'] for _, s in g]) / w.sum()); lo = float(np.sum(w * [s['lon'] for _, s in g]) / w.sum())
    top = max(d, key=d.get)
    return dict(lat=la, lon=lo, max=mx, top=ST[top]['name'], dist=ST[top]['district'], n100=sum(v >= 100 for v in d.values()), n=len(d))
def smooth(a, s): return nd.gaussian_filter(np.nan_to_num(a), s)
def track(E, P, lo_lim=(68, 100), la_lim=(0, 24)):
    """Follow the centre of low-level spin (850 and 700 hPa vorticity, smoothed ~1.5 deg) backward and forward from the
    rain day.  Each step picks the strongest spin near the last position, with a penalty for jumping (1e-5/s per 100 km)."""
    s = 1.5 / E.res; V = {k: smooth(0.6 * E.f['vo850'][k] + 0.4 * E.f['vo700'][k], s) for k in range(len(E.times))}
    LA, LO = np.meshgrid(E.lat, E.lon, indexing='ij'); inside = (LA >= la_lim[0]) & (LA <= la_lim[1]) & (LO >= lo_lim[0]) & (LO <= lo_lim[1])
    def best(k, la, lo, r_km, pen):
        d = np.hypot((LA - la) * 110.6, (LO - lo) * 111.3 * np.cos(np.radians(la))); m = inside & (d <= r_km)
        if not m.any(): return None
        sc = np.where(m, V[k] - pen * d / 100, -np.inf); i, j = np.unravel_index(np.argmax(sc), sc.shape); return float(E.lat[i]), float(E.lon[j]), float(V[k][i, j])
    ks = [k for k, t in enumerate(E.times) if dt.datetime(E.day.year, E.day.month, E.day.day) <= t <= dt.datetime(E.day.year, E.day.month, E.day.day, 18)]
    cand = [(best(k, P['lat'], P['lon'], 800, 0.3), k) for k in ks]; cand = [(c, k) for c, k in cand if c]
    (la0, lo0, v0), k0 = max(cand, key=lambda x: x[0][2])
    path = {k0: (la0, lo0, v0)}
    for direction in (-1, 1):
        la, lo = la0, lo0; k = k0 + direction
        while 0 <= k < len(E.times):
            hrs = abs((E.times[k] - E.times[k - direction]).total_seconds()) / 3600
            b = best(k, la, lo, 40 * hrs + 60, 1.0)
            if not b or b[2] < 2.0: break                              # lost (spin below 2e-5/s)
            la, lo, v = b; path[k] = b; k += direction
    return dict(sorted(path.items())), k0
def origin_track(E, P, step_h=12, r_km=450, sig=1.5, vmin=2.0):
    """Where did the circulation come from?  12-hourly, from the rain day back to 8 days before: strongest broad spin at
    850 hPa (smoothed ~1.5 deg) within 450 km of the next position; stops when the spin fades below 2e-5/s."""
    s = sig / E.res; LA, LO = np.meshgrid(E.lat, E.lon, indexing='ij'); box = (LA >= 0) & (LA <= 24) & (LO >= 66) & (LO <= 102)
    ks = [k for k, t in enumerate(E.times) if t.hour % step_h == 0]
    def best(k, la, lo, r):
        V = smooth(E.f['vo850'][k], s); d = np.hypot((LA - la) * 110.6, (LO - lo) * 111.3 * np.cos(np.radians(la))); m = box & (d <= r)
        if not m.any(): return None
        v = np.where(m, V - 0.2 * d / 100, -np.inf); i, j = np.unravel_index(np.argmax(v), v.shape); return float(E.lat[i]), float(E.lon[j]), float(V[i, j])
    k0 = [k for k in ks if E.times[k].date() == E.day and E.times[k].hour == 0][0]
    b = best(k0, P['lat'], P['lon'], 800)
    out = {k0: b}; la, lo = b[0], b[1]
    for k in [k for k in ks if k < k0][::-1]:
        b = best(k, la, lo, r_km)
        if not b or b[2] < vmin: break
        out[k] = b; la, lo = b[0], b[1]
    la, lo = out[k0][0], out[k0][1]
    for k in [k for k in ks if k > k0]:
        b = best(k, la, lo, r_km)
        if not b or b[2] < vmin: break
        out[k] = b; la, lo = b[0], b[1]
    return dict(sorted(out.items()))
def layer_wind(E, k, la, lo, levs, r0=2, r1=5):
    m = E.dist_mask(la, lo, r0, r1); us = [np.nanmean(E.f[f'u{p}'][k][m]) for p in levs]; vs = [np.nanmean(E.f[f'v{p}'][k][m]) for p in levs]
    return float(np.mean(us)), float(np.mean(vs))
def kmh_dir(u, v):                                            # speed km/h and direction the wind blows TOWARD (deg)
    return float(np.hypot(u, v) * 3.6), float(np.degrees(np.arctan2(u, v)) % 360)
COMPASS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
def compass(deg): return COMPASS[int((deg + 11.25) % 360 // 22.5)]
def sea_point(E, P):
    """Nearest open-sea point (has SST) east or south of the rain centre, for the sea temperature nearby."""
    s = E.f['sst'][0]; best = None
    for i, la in enumerate(E.lat):
        for j, lo in enumerate(E.lon):
            if np.isfinite(s[i, j]) and abs(la - P['lat']) <= 3 and abs(lo - P['lon']) <= 3:
                d = np.hypot(la - P['lat'], lo - P['lon'])
                if d >= 0.75 and (best is None or d < best[0]): best = (d, la, lo)
    return best[1], best[2]
def diagnose(E, C, P):
    path, k0 = track(E, P); rows = []; prev = None; sp = sea_point(E, P)
    for k, t in enumerate(E.times):
        r = dict(t=t.strftime('%Y-%m-%d %H'), lag_h=(t - dt.datetime(E.day.year, E.day.month, E.day.day, 12)).total_seconds() / 3600)
        ca = lambda key: C.at(key, t)
        def anom(key, la, lo, rr=1.0):
            v = E.box(key, k, la, lo, rr); c = ca(key)
            if c is None: return v, None
            m = (np.abs(C.lat - la) <= rr)[:, None] & (np.abs(C.lon - lo) <= rr)[None, :]; return v, v - float(np.nanmean(c[m]))
        # at the rain centre
        for key, out in (('tcwv', 'pw'), ('cape', 'cape'), ('ttr', 'olr'), ('r700', 'rh700'), ('w500', 'w500'), ('q850', 'q850')):
            v, a = anom(key, P['lat'], P['lon']); r[out] = v; r[out + '_anom'] = a
        ivu, ivv = E.box('ivtu', k, P['lat'], P['lon']), E.box('ivtv', k, P['lat'], P['lon']); r['ivt'] = float(np.hypot(ivu, ivv)); r['ivt_dir'] = float(np.degrees(np.arctan2(ivu, ivv)) % 360)
        cu, cv = ca('ivtu'), ca('ivtv'); civ = ca('ivt')
        if civ is not None:
            m = (np.abs(C.lat - P['lat']) <= 1)[:, None] & (np.abs(C.lon - P['lon']) <= 1)[None, :]; r['ivt_anom'] = r['ivt'] - float(np.nanmean(civ[m]))
        elif cu is not None:
            m = (np.abs(C.lat - P['lat']) <= 1)[:, None] & (np.abs(C.lon - P['lon']) <= 1)[None, :]; r['ivt_anom'] = r['ivt'] - float(np.hypot(np.nanmean(cu[m]), np.nanmean(cv[m])))
        for p in (925, 850):
            u, v = E.box(f'u{p}', k, P['lat'], P['lon']), E.box(f'v{p}', k, P['lat'], P['lon']); r[f'wind{p}_kmh'], r[f'wind{p}_to'] = kmh_dir(u, v)
        r['conv925'] = -E.box('d925', k, P['lat'], P['lon']); r['conv850'] = -E.box('d850', k, P['lat'], P['lon']); r['div200'] = E.box('d200', k, P['lat'], P['lon'])
        r['shear_kmh'] = kmh_dir(E.box('u200', k, P['lat'], P['lon'], 2) - E.box('u850', k, P['lat'], P['lon'], 2), E.box('v200', k, P['lat'], P['lon'], 2) - E.box('v850', k, P['lat'], P['lon'], 2))[0]
        r['sst'], r['sst_anom'] = anom('sst', sp[0], sp[1], 0.5)
        # NE monsoon flow over the SW Bay and the upper easterlies over the south
        r['u850_swbay'] = E.box('u850', k, 11, 83.5, 2.5); r['v850_swbay'] = E.box('v850', k, 11, 83.5, 2.5)
        c = ca('u850'); r['u850_swbay_anom'] = r['u850_swbay'] - float(np.nanmean(c[(np.abs(C.lat - 11) <= 2.5)[:, None] & (np.abs(C.lon - 83.5) <= 2.5)[None, :]])) if c is not None else None
        r['u200_south'] = E.box('u200', k, 9, 79, 3)
        # subtropical ridge: where the 500 hPa wind turns from easterly to westerly, 76-86E
        for p in (500, 200):                                        # southern edge of the mid-latitude westerlies, 76-86E
            um = np.nanmean(E.f[f'u{p}'][k][:, (E.lon >= 76) & (E.lon <= 86)], 1); idx = [i for i in np.where((E.lat >= 0) & (E.lat <= 35))[0]][::-1]
            lat_w = None
            for i in idx:                                           # walk south from 35N while the wind stays westerly
                if um[i] > 0: lat_w = float(E.lat[i])
                else: break
            r[f'westerly_edge{p}'] = lat_w
        # western disturbance: 500 hPa trough in 27.5-35N, 55-100E (heights minus their zonal mean in the band)
        band = (E.lat >= 27.5) & (E.lat <= 35); js = (E.lon >= 55) & (E.lon <= 100)
        zb = np.nanmean(E.f['z500'][k][band][:, js], 0); za = zb - zb.mean(); jt = int(np.argmin(za)); r['wd_lon'] = float(E.lon[js][jt]); r['wd_depth'] = float(-za[jt])
        cz = ca('z500')
        if cz is not None:
            zc = np.nanmean(cz[band][:, js], 0); r['wd_anom_min'] = float(np.min(zb - zc)); r['wd_anom_lon'] = float(E.lon[js][int(np.argmin(zb - zc))])
        sb = (E.lat >= 20) & (E.lat <= 40); u2 = E.f['u200'][k][sb][:, js]; i, j = np.unravel_index(np.nanargmax(u2), u2.shape)
        r['jet_max'] = float(u2[i, j]); r['jet_lat'] = float(E.lat[sb][i]); r['jet_lon'] = float(E.lon[js][j])
        # trough reach: southernmost latitude with a 500 hPa height anomaly below -20 m between 70-90E
        if cz is not None:
            an = (E.f['z500'][k] - cz)[:, (E.lon >= 70) & (E.lon <= 90)]; low = [float(E.lat[i]) for i in range(len(E.lat)) if np.nanmin(an[i]) < -20 and E.lat[i] >= 10]
            r['trough_south_lat'] = min(low) if low else None
        # the system
        if k in path:
            la, lo, v = path[k]; r.update(sys_lat=la, sys_lon=lo, vo850=v)
            r['vo700'] = float(smooth(E.f['vo700'][k], 1 / E.res)[E.ij(la, lo)]); r['vo500'] = float(smooth(E.f['vo500'][k], 1 / E.res)[E.ij(la, lo)])
            i, j = E.ij(la, lo); w = E.f['msl'][k][max(0, i - 4):i + 5, max(0, j - 4):j + 5]; r['msl_min'] = float(np.nanmin(w))
            r['msl_deficit'] = float(np.nanmean(E.f['msl'][k][E.dist_mask(la, lo, 4, 6)]) - r['msl_min'])
            r['wind10_max_kmh'] = float(np.nanmax(np.hypot(E.f['u10'][k], E.f['v10'][k])[E.dist_mask(la, lo, 0, 3)]) * 3.6)
            for nm, lv in (('steer', (850, 700, 500, 300, 200)), ('steer_low', (925, 850)), ('steer_mid', (700, 500)), ('steer_up', (300, 200))):
                r[nm + '_kmh'], r[nm + '_to'] = kmh_dir(*layer_wind(E, k, la, lo, lv))
            r['dist_km'] = float(np.hypot((la - P['lat']) * 110.6, (lo - P['lon']) * 111.3 * np.cos(np.radians(la))))
            if prev is not None and prev[0] == k - 1:
                hrs = (t - E.times[prev[0]]).total_seconds() / 3600; dy = (la - prev[1]) * 110.6; dx = (lo - prev[2]) * 111.3 * np.cos(np.radians(la))
                r['move_kmh'] = float(np.hypot(dx, dy) / hrs); r['move_to'] = float(np.degrees(np.arctan2(dx, dy)) % 360)
            prev = (k, la, lo)
        rows.append(r)
    return rows, path, k0, sp
def kind_of_system(r):
    if 'vo850' not in r: return 'no organised circulation'
    if r['msl_deficit'] >= 4 and r['wind10_max_kmh'] >= 55: return 'depression or cyclone'
    if r['msl_deficit'] >= 1.5: return 'low-pressure area'
    return 'upper-air circulation (no surface low)'
