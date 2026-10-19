"""Analogue search over every Bay of Bengal storm since 1980 (IBTrACS): timing, genesis place, track, intensity, MJO, IOD,
El Nino.  score(target) ranks them; lower is closer."""
import json, os, sys, math, datetime as dt, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'case_analysis'))
import indices
from cyc import km, on_land
HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.abspath('data')
CATS = [(17, 'D'), (28, 'DD'), (34, 'CS'), (48, 'SCS'), (64, 'VSCS'), (90, 'ESCS'), (120, 'SuCS')]
NAMES = dict(D='depression', DD='deep depression', CS='cyclonic storm', SCS='severe cyclonic storm', VSCS='very severe cyclonic storm',
             ESCS='extremely severe cyclonic storm', SuCS='super cyclonic storm')
def cat(w):
    c = None
    for lim, n in CATS:
        if w is not None and w >= lim: c = n
    return c
def cat_idx(c): return [n for _, n in CATS].index(c) if c else -1
def region(la, lo):
    if lo >= 92.3 or (lo >= 91.5 and la < 21.0): return 'Myanmar'
    if lo >= 89.0 and la >= 21.0: return 'Bangladesh'
    if lo >= 87.0 and la >= 21.4: return 'West Bengal'
    if la >= 19.1: return 'Odisha'
    if la >= 13.6: return 'Andhra Pradesh'
    if la < 10.0 and lo > 79.6: return 'Sri Lanka'
    return 'Tamil Nadu'
def storms():
    out = []
    for s in json.load(open(os.path.join(D, 'ibtracs_bob.json'))):
        pts = [p for p in s['pts'] if p[1] is not None]
        g = next((p for p in pts if (p[3] or 0) >= 17), None)
        if g is None: continue
        t0 = dt.datetime.strptime(g[0], '%Y-%m-%dT%H')
        P = [(dt.datetime.strptime(p[0], '%Y-%m-%dT%H'), p[1], p[2], p[3], p[4], p[6]) for p in pts]
        def at(h):
            t = t0 + dt.timedelta(hours=h)
            for a, b in zip(P, P[1:]):
                if a[0] <= t <= b[0]:
                    f = (t - a[0]).total_seconds() / max(1, (b[0] - a[0]).total_seconds()); return (a[1] + f * (b[1] - a[1]), a[2] + f * (b[2] - a[2]))
            return None
        inbay = next((p[0] for p in P if p[0] >= t0 and p[2] <= 96.5), None)            # landfall on the Bay rim only after the storm is in the Bay
        lf = next(((p[1], p[2], p[0]) for p in P if inbay and p[0] >= inbay and p[5] is not None and p[5] == 0), None)
        pk = max((p[3] or 0) for p in P); pmin = min((p[4] for p in P if p[4]), default=None)
        d = t0.date(); m = indices.mjo(d); ph, amp = (m['rmm_phase'], m['rmm_amp']) if m['rmm_phase'] else (m['omi_phase'], m['omi_amp'])
        out.append(dict(sid=s['sid'], name=s['name'].title() if s['name'] not in ('NOT_NAMED', '') else 'unnamed', season=s['season'], t0=t0, gen=(g[1], g[2]),
                        track={h: at(h) for h in (0, 24, 48, 72, 96, 120)}, landfall=lf, land_region=region(lf[0], lf[1]) if lf else 'no landfall',
                        peak=pk, cat=cat(pk), pmin=pmin, mjo=(ph, amp), oni=indices.enso(d), dmi=indices.iod(d),
                        path=[(p[0].isoformat(), p[1], p[2], p[3]) for p in P]))
    return out
def phase_gap(a, b):
    if a is None or b is None: return 4
    d = abs(a - b) % 8; return min(d, 8 - d)
def score(S, T, w=None):
    """T: dict(t0, gen, track{h: (lat,lon)}, cat, mjo=(phase, amp), oni, dmi)."""
    w = w or dict(time=1, gen=1, track=2, inten=0.5, mjo=0.5, iod=0.5, enso=0.5)
    out = []
    for s in S:
        doy = lambda t: (t - dt.datetime(t.year, 1, 1)).days
        c = {}
        c['time'] = min(3, abs(doy(s['t0']) - doy(T['t0'])) / 20)
        c['gen'] = km(s['gen'], T['gen']) / 400
        ds = [km(s['track'][h], T['track'][h]) for h in (24, 48, 72, 96, 120) if T['track'].get(h) and s['track'].get(h)]
        miss = sum(1 for h in (24, 48, 72, 96, 120) if T['track'].get(h) and not s['track'].get(h))
        c['track'] = (np.mean(ds) / 400 if ds else 3) + 0.3 * miss
        c['inten'] = abs(cat_idx(s['cat']) - cat_idx(T['cat'])) / 2
        c['mjo'] = phase_gap(s['mjo'][0], T['mjo'][0]) / 2 + (0.5 if (s['mjo'][1] or 0) < 0.8 else 0)
        c['iod'] = abs((s['dmi'] or 0) - T['dmi']) / 0.6
        c['enso'] = abs((s['oni'] or 0) - T['oni']) / 1.2
        phys = sum(w[k] * c[k] for k in ('time', 'gen', 'track', 'inten')); bg = sum(w[k] * c[k] for k in ('mjo', 'iod', 'enso'))
        out.append(dict(s=s, c=c, phys=phys, bg=bg, total=phys + bg))
    return sorted(out, key=lambda r: r['total'])
