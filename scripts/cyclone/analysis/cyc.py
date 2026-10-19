"""Cyclone study helpers: load forecast fields, find and follow the Bay low in every run, land mask, distances."""
import json, os, glob, math, datetime as dt, numpy as np
from matplotlib.path import Path
from scipy import ndimage as nd
HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.abspath('data'); os.makedirs(DATA, exist_ok=True)
LAND = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'data', 'cyclone', 'land.json')))
def _area(r):
    a = np.array(r); x, y = a[:, 0], a[:, 1]; return 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))
_PATHS = [Path(np.array(r)) for r in LAND if len(r) > 10 and _area(r) > 3.0]      # mainland and Sri Lanka; small islands count as sea
def on_land(lo, la):
    return any(p.contains_point((lo, la)) for p in _PATHS)
def km(a, b):
    """distance in km between (lat, lon) points."""
    return 6371 * math.acos(min(1, max(-1, math.sin(math.radians(a[0])) * math.sin(math.radians(b[0])) + math.cos(math.radians(a[0])) * math.cos(math.radians(b[0])) * math.cos(math.radians(a[1] - b[1])))))
class Fc:
    def __init__(self, fn):
        Z = np.load(fn); self.src = os.path.basename(fn).split('_')[1]; self.run = dt.datetime.strptime(str(Z['run']), '%Y%m%d%H')
        self.data = Z['data'].astype(np.float32); self.vars = [str(v) for v in Z['vars']]; self.lats = Z['lats']; self.lons = Z['lons']
        self.steps = [int(s) for s in Z['steps']]; self.members = [int(m) for m in Z['members']]
        self.times = [self.run + dt.timedelta(hours=s) for s in self.steps]
        self.res = float(self.lats[1] - self.lats[0])
        LA, LO = np.meshgrid(self.lats, self.lons, indexing='ij'); self.LA, self.LO = LA, LO
        self.sea = ~np.array([[on_land(lo, la) for lo in self.lons] for la in self.lats]) if not os.path.exists(os.path.join(DATA, 'seamask.npy')) else np.load(os.path.join(DATA, 'seamask.npy'))
        np.save(os.path.join(DATA, 'seamask.npy'), self.sea)
    def f(self, m, s, v):
        return self.data[m, s, self.vars.index(v)] if v in self.vars else None
    def vort850(self, m, s):
        u, v = self.f(m, s, 'u850'), self.f(m, s, 'v850')
        if u is None or not np.isfinite(u).any(): return None
        dy = self.res * 111e3; dx = dy * np.cos(np.radians(self.LA))
        return (np.gradient(v, axis=1) / dx - np.gradient(u, axis=0) / dy) * 1e5
BOX = (4, 23.5, 79.5, 99.5)                       # Bay of Bengal and Andaman Sea, where a track may start
def find_lows(F, m, s):
    """Closed lows: smoothed sea-level pressure minimum at least 1.5 hPa below its 2.5-4 deg ring, with cyclonic spin."""
    p = F.f(m, s, 'msl')
    if p is None or not np.isfinite(p).all(): return []
    g = nd.gaussian_filter(p, 1.0); vo = F.vort850(m, s); vo = nd.gaussian_filter(np.nan_to_num(vo), 1.5) if vo is not None else None
    mn = nd.minimum_filter(g, size=5); out = []
    for j, i in np.argwhere(g <= mn + 1e-6):
        la, lo = F.lats[j], F.lons[i]
        if la < 2 or la > 28: continue
        d = np.hypot(F.LA - la, (F.LO - lo) * np.cos(np.radians(la))); ring = g[(d >= 2.5) & (d <= 4)]
        depth = float(ring.mean() - g[j, i])
        if depth < 1.5: continue
        z = float(vo[j, i]) if vo is not None else 0
        out.append(dict(lat=float(la), lon=float(lo), p=float(p[j, i]), depth=depth, vo=z, sea=bool(F.sea[j, i])))
    return out
def track_member(F, m):
    """Follow the Bay system in one run: start = first sea low in the Bay box with depth >= 2 hPa and spin >= 3;
    continue to the nearest low within 2 deg per 6 h of a first-guess position; end after 24 h lost."""
    tracks = []; active = []
    for s, t in enumerate(F.times):
        lows = find_lows(F, m, s); used = set()
        hrs = (F.times[s] - F.times[s - 1]).total_seconds() / 3600 if s else 6
        for tr in active:
            last = tr['pts'][-1]; vx = vy = 0.0
            if len(tr['pts']) >= 2:
                a, b = tr['pts'][-2], tr['pts'][-1]; h0 = max(1, (b['t'] - a['t']).total_seconds() / 3600)
                vx, vy = (b['lon'] - a['lon']) / h0, (b['lat'] - a['lat']) / h0
            g = (last['lat'] + vy * hrs, last['lon'] + vx * hrs)
            best = None
            for q, L in enumerate(lows):
                if q in used: continue
                d = math.hypot(L['lat'] - g[0], (L['lon'] - g[1]) * math.cos(math.radians(g[0])))
                if d <= 1.0 + 1.5 * hrs / 6 and (best is None or d < best[0]): best = (d, q)
            if best:
                used.add(best[1]); L = dict(lows[best[1]]); L['t'] = t; L['s'] = s; tr['pts'].append(L); tr['miss'] = 0
            else:
                tr['miss'] = tr.get('miss', 0) + hrs
        for tr in active:
            if tr.get('miss', 0) > 24: tracks.append(tr)
        active = [tr for tr in active if tr.get('miss', 0) <= 24]
        for q, L in enumerate(lows):
            if q in used: continue
            if L['sea'] and L['depth'] >= 2.0 and L['vo'] >= 3 and BOX[0] <= L['lat'] <= BOX[1] and BOX[2] <= L['lon'] <= BOX[3]:
                L = dict(L); L['t'] = t; L['s'] = s; active.append(dict(pts=[L]))
    tracks += active
    good = [tr for tr in tracks if len(tr['pts']) >= 4 and max(p['depth'] for p in tr['pts']) >= 3]
    return good
def landfall(pts):
    """first point on land after being at sea: (time, lat, lon) interpolated half way."""
    for a, b in zip(pts, pts[1:]):
        if not on_land(a['lon'], a['lat']) and on_land(b['lon'], b['lat']):
            return dict(t=a['t'] + (b['t'] - a['t']) / 2, lat=(a['lat'] + b['lat']) / 2, lon=(a['lon'] + b['lon']) / 2)
    return None
