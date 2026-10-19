"""Run our track model on each forecast run: start where that run forms the Bay system, then move it every step with the
model's motion from that run's own winds around the storm."""
import math, numpy as np, pickle, os, datetime as dt
from cyc import on_land
HERE = os.path.dirname(os.path.abspath(__file__))
M = pickle.load(open(os.path.join('data', 'steer_model_h.pkl'), 'rb'))     # winds + its own previous 12 h motion
LEVS = ['850', '700', '500', '200']
def ring(F, m, s, la, lo, r0=2, r1=6):
    d = np.hypot(F.LA - la, (F.LO - lo) * np.cos(np.radians(la))); msk = (d >= r0) & (d <= r1); w = np.cos(np.radians(F.LA[msk]))
    x = []
    for l in LEVS:
        u, v = F.f(m, s, 'u' + l), F.f(m, s, 'v' + l)
        if u is None or not np.isfinite(u[msk]).all(): return None
        x += [float((u[msk] * w).sum() / w.sum()) * 3.6, float((v[msk] * w).sum() / w.sum()) * 3.6]
    return x + [la - 15, lo - 88]
def motion(x, prev):
    X = np.array([x + list(prev)]); return float(M[0].predict(X)[0]), float(M[1].predict(X)[0])          # km/h east, north
def run(F, m, start_s, la, lo, prev=(0.0, 0.0), max_inland_h=24):
    pts = [dict(t=F.times[start_s], lat=la, lon=lo)]; inland = 0; prev = list(prev)
    for s in range(start_s, len(F.times) - 1):
        h = (F.times[s + 1] - F.times[s]).total_seconds() / 3600
        x = ring(F, m, s, la, lo)
        if x is None: break
        u, v = motion(x, prev)
        la2 = la + v * h / 2 / 111.2; lo2 = lo + u * h / 2 / (111.2 * math.cos(math.radians(la)))        # half step, then re-evaluate
        x2 = ring(F, m, s + 1, la2, lo2) or x
        u2, v2 = motion(x2, prev); u, v = (u + u2) / 2, (v + v2) / 2; prev = [u, v]
        la += v * h / 111.2; lo += u * h / (111.2 * math.cos(math.radians(la)))
        pts.append(dict(t=F.times[s + 1], lat=la, lon=lo, u=u, v=v))
        if on_land(lo, la):
            inland += h
            if inland > max_inland_h: break
        if not (0 < la < 29 and 71 < lo < 104): break
    return pts
