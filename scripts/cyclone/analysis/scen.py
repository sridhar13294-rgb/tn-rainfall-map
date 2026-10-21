"""Our scenario ensemble (no model forecast used).
Environment: today's observed analysis, relaxed (e-folding 48 h) towards the real ERA5 evolution of the closest past storms
(their own vortices removed). Track: our steering model (ERA5-trained, by intensity class) moving the storm through that
environment. Inputs varied: ridge (lat, lon, strength, timing), where/when the low forms, sea temperature, MJO, an Arabian Sea
system, the Gulf of Mannar circulation, western disturbance, NE-monsoon easterly surge, beta drift (size), shear/dry air,
forward speed.

python scen.py LIB_NPZ ANALYSIS_NPZ N          -> data/scen.json
python scen.py LIB_NPZ --hindcast              -> engine test on past storms"""
import sys, json, math, datetime as dt, numpy as np
from collections import Counter, defaultdict
from scipy import ndimage as nd
from sklearn.linear_model import Ridge
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import ourens as O
from ourens import LA, LO, segment, ORDER, SID, LIBL
from cyc import on_land
LEVS = [850, 700, 500, 200]
GLA, GLO = np.meshgrid(LA, LO, indexing='ij')
# ---------------- track model by intensity class ----------------
def train():
    D = '/tmp/claude-0/-home-claude/2c3b34a9-cc00-53e0-8864-49737f9cdb93/scratchpad/cyclone/data/'
    T = json.load(open(D + 'ibtracs_bob.json')); pos = {}
    for s in T:
        for p in s['pts']: pos[(s['sid'], p[0])] = (p[1], p[2], p[3])
    X, Y, C = [], [], []
    for r in json.load(open(D + 'steering_era5.json')):
        t0 = dt.datetime.strptime(r['t'], '%Y-%m-%dT%H'); t1 = (t0 + dt.timedelta(hours=12)).strftime('%Y-%m-%dT%H')
        if (r['sid'], t1) not in pos or (r['sid'], r['t']) not in pos: continue
        la1, lo1, _ = pos[(r['sid'], t1)]; w = pos[(r['sid'], r['t'])][2] or 20
        vy = (la1 - r['lat']) * 111.2 / 12; vx = (lo1 - r['lon']) * 111.2 * math.cos(math.radians((la1 + r['lat']) / 2)) / 12
        x = []
        for l in LEVS: x += [r['ann'][str(l)][0] * 3.6, r['ann'][str(l)][1] * 3.6]
        X.append(x + [r['lat'] - 15, r['lon'] - 88]); Y.append([vx, vy]); C.append(0 if w < 34 else (1 if w < 64 else 2))
    X, Y, C = np.array(X), np.array(Y), np.array(C); M = {}
    for c in (0, 1, 2):
        k = C == c; M[c] = [Ridge(alpha=10).fit(X[k], Y[k, j]) for j in (0, 1)]
        print('track model class', c, 'samples', int(k.sum()), 'drift east/north km/h', round(M[c][0].intercept_, 1), round(M[c][1].intercept_, 1), flush=True)
    return M
# ---------------- fields ----------------
def lib_raw(fn):
    Z = np.load(fn); T = [str(t) for t in Z['times']]; lats, lons = Z['lats'], Z['lons']
    J = [int(np.argmin(abs(lats - a))) for a in LA]; I = [int(np.argmin(abs(lons - o))) for o in LO]
    D = Z['data'][:, 1:3][:, :, :, J][:, :, :, :, I]          # time, (u,v), lev(850,700,500,200), lat, lon
    return {t: D[i] for i, t in enumerate(T)}
def ana_raw(fn, step=0):
    Z = np.load(fn); V = [str(v) for v in Z['vars']]; lats, lons = Z['lats'], Z['lons']
    J = [int(np.argmin(abs(lats - a))) for a in LA]; I = [int(np.argmin(abs(lons - o))) for o in LO]
    X = np.nanmean(Z['data'][:, list(Z['steps']).index(step)].astype(float), 0)
    out = np.zeros((2, 4, len(LA), len(LO)), np.float32)
    for li, l in enumerate(LEVS):
        for ci, c in enumerate('uv'):
            out[ci, li] = nd.uniform_filter(X[V.index(f'{c}{l}')], 3)[J][:, I]
    return out
def remove_vortex(F, la, lo, R=4.5):
    """fill a disc of radius R deg around (la, lo) by smooth diffusion from outside: the environment without that vortex."""
    d = np.hypot(GLA - la, (GLO - lo) * math.cos(math.radians(la))); m = d <= R
    if not m.any(): return F
    F = F.copy()
    for idx in np.ndindex(F.shape[:-2]):
        f = F[idx]; f[m] = np.nanmean(f[(d > R) & (d <= R + 2)])
        for _ in range(40): f[m] = nd.uniform_filter(f, 3, mode='nearest')[m]
        F[idx] = f
    return F
def vort_max(F, li, box):
    u, v = F[0, li], F[1, li]; z = O.vort(u, v); z = nd.uniform_filter(z, 3)
    k = (GLA >= box[0]) & (GLA <= box[1]) & (GLO >= box[2]) & (GLO <= box[3]); j = np.argmax(np.where(k, z, -1e9))
    return float(GLA.flat[j]), float(GLO.flat[j]), float(z.flat[j])
def pos_at(s, t):
    P = O.path_of(s)
    for a, b in zip(P, P[1:]):
        if a[0] <= t <= b[0]:
            f = (t - a[0]).total_seconds() / max(1, (b[0] - a[0]).total_seconds()); return (a[1] + f * (b[1] - a[1]), a[2] + f * (b[2] - a[2]))
    return None
TAU = list(range(0, 241, 12))
def composite(ranked, RAW, K=12):
    top = ranked[:K]; d = np.array([r[0] for r in top]); w = np.exp(-(d - d.min()) / max(0.02, d.std())); w /= w.sum()
    C = np.zeros((len(TAU), 2, 4, len(LA), len(LO))); W = np.zeros(len(TAU))
    for (dd, sid, lag), ww in zip(top, w):
        s = SID[sid]; g = O.gen_time(s); last = None
        for k, tau in enumerate(TAU):
            t = g + dt.timedelta(hours=lag + tau); key = t.strftime('%Y-%m-%dT%H')
            if key in RAW:
                F = RAW[key].astype(float); p = pos_at(s, t)
                if p: F = remove_vortex(F, *p)
                last = F
            if last is not None: C[k] += ww * last; W[k] += ww
    return C / W[:, None, None, None, None], [(SID[r[1]]['name'], SID[r[1]]['season'], r[2], round(float(x), 3)) for r, x in zip(top, w)]
def base_env(now_raw, C, efold=48.0):
    A = now_raw - C[0]
    return np.stack([C[k] + math.exp(-tau / efold) * A for k, tau in enumerate(TAU)])
# ---------------- perturbations ----------------
def vortex(la0, lo0, vmax, rmw_km, outer=1800):
    dy = (GLA - la0) * 111.2; dx = (GLO - lo0) * 111.2 * math.cos(math.radians(la0)); r = np.hypot(dx, dy) + 1e-6
    rm = rmw_km; V = np.where(r < rm, vmax * r / rm, vmax * (rm / r) ** 0.6) * np.exp(-(r / outer) ** 2)
    return -V * dy / r, V * dx / r                                    # counter-clockwise
def lerp_track(pts, t):
    """pts [(datetime, lat, lon)] -> position at t (held at the ends) or None before start."""
    if t < pts[0][0]: return None
    for a, b in zip(pts, pts[1:]):
        if a[0] <= t <= b[0]:
            f = (t - a[0]).total_seconds() / max(1, (b[0] - a[0]).total_seconds()); return a[1] + f * (b[1] - a[1]), a[2] + f * (b[2] - a[2])
    return None
class Env:
    def __init__(self, E, t0, P):
        self.E, self.t0, self.P = E, t0, P
    def at(self, t):
        P = self.P; tau = (t - self.t0).total_seconds() / 3600 - P['ridge_dt']       # ridge timing: the whole pattern early/late
        k = min(max(tau, 0), TAU[-1]) / 12; k0 = int(k); k1 = min(k0 + 1, len(TAU) - 1); f = k - k0
        F = (1 - f) * self.E[k0] + f * self.E[k1]
        if P['ridge_dlat'] or P['ridge_dlon']:
            F = nd.shift(F, (0, 0, P['ridge_dlat'] / 1.5, P['ridge_dlon'] / 1.5), order=1, mode='nearest')
        U, V = F[0].copy(), F[1].copy()
        south = (GLA < 20)
        for li in (0, 1, 2):                                            # ridge strength: easterlies on its south side
            U[li] = np.where(south & (U[li] < 0), U[li] * P['ridge_str'], U[li])
        day = (t - self.t0).total_seconds() / 86400
        # MJO: low-level westerly anomaly over the south Bay
        mw = P['mjo_u'] * np.clip((14 - GLA) / 6, 0, 1) * (GLA > 2)
        U[0] += mw; U[1] += 0.7 * mw
        # NE-monsoon easterly surge over 10-18N after its start day
        if day >= P['surge_day']:
            sm = P['surge_u'] * ((GLA >= 9) & (GLA <= 19)) * min(1, day - P['surge_day'] + 0.5)
            U[0] += sm; U[1] += 0.7 * sm
        # western disturbance: trough axis moving east at 8 deg/day, reaching 80E on wd_day; southerlies ahead
        if P['wd_amp']:
            x = 80 + 8 * (day - P['wd_day']); wl = np.clip((GLA - 15) / 9, 0, 1); dl = GLO - x
            vv = P['wd_amp'] * wl * np.sin(np.pi * dl / 12) * (abs(dl) < 12)
            for li, fac in ((1, 0.3), (2, 0.6), (3, 1.0)): V[li] += fac * vv
        # Arabian Sea system and Gulf of Mannar circulation (vortices with their outer flow)
        for key, vmax, rmw in (('as_track', 12, 150), ('gom_track', 7, 150)):
            tr = P.get(key)
            if not tr: continue
            p = lerp_track(tr, t)
            if p is None: continue
            vm = vmax * p[2] if len(p) > 2 else vmax
            u1, v1 = vortex(p[0], p[1], vmax, rmw)
            for li, fac in ((0, 1.0), (1, 1.0), (2, 0.5)): U[li] += fac * u1; V[li] += fac * v1
        return U, V
def ring(U, V, la, lo, r0=2, r1=6):
    d = np.hypot(GLA - la, (GLO - lo) * math.cos(math.radians(la))); m = (d >= r0) & (d <= r1); w = np.cos(np.radians(GLA[m]))
    if m.sum() < 8: return None
    x = []
    for li in range(4): x += [float((U[li][m] * w).sum() / w.sum()) * 3.6, float((V[li][m] * w).sum() / w.sum()) * 3.6]
    return x + [la - 15, lo - 88]
def peak_class(P):
    I = 0.9 * (P['sst'] - 0.8) + P['mjo_i'] + P['shear_i']
    return 0 if I < 0 else (1 if I < 0.8 else 2)
import pickle, intens as IN
IM = None
SHEAR_SCALE = {'low shear, moist': 0.75, 'moderate': 1.0, 'high shear or dry air': 1.35}
def run_track(M, env, P, hours=240, dt_h=6):
    """track + intensity (kt) from the seedling to dissipation. pts: (t, lat, lon, wind_kt)."""
    global IM
    if IM is None: IM = pickle.load(open('data/intens_model.pkl', 'rb'))
    t = P.get('start_t', P['gen_t']); la, lo = P.get('start_lat', P['gen_lat']), P.get('start_lon', P['gen_lon'])
    v = 12.0 if 'start_t' in P else 17.0; dvp = 0.0; pts = [(t, la, lo, v)]; lf = None; land_h = 0.0; v_lf = None; acc = 0.0
    off = 1.5 * (P['sst'] - 0.3) + {0.4: 1.0, 0.2: 0.0, -0.2: -1.0}.get(P['mjo_i'], 0.0)
    shs = SHEAR_SCALE.get(P.get('shear'), 1.0)
    while (t - P['gen_t']).total_seconds() / 3600 < hours:
        age = (t - P['gen_t']).total_seconds() / 3600
        c = 0 if v < 34 else (1 if v < 64 else 2)
        U, V = env.at(t); x = ring(U, V, la, lo)
        if x is None: break
        m = M[c]; u = m[0].predict([x])[0]; w = m[1].predict([x])[0]
        u += (P['beta'] - 1) * m[0].intercept_; w += (P['beta'] - 1) * m[1].intercept_
        u *= P['speed']; w *= P['speed']
        la2 = la + w * dt_h / 111.2; lo2 = lo + u * dt_h / (111.2 * math.cos(math.radians(la)))
        land_now = on_land(lo, la)
        # intensity
        if land_now:
            land_h += dt_h; v = IN.inland(v_lf or v, land_h)
        elif age < 0:
            v = min(16.5, v + 0.6 * dt_h / 6)
        else:
            if age < dt_h: v = max(v, 17.0)
            sh = IN.shear_at(U, V, la, lo) or 10.0
            dv = float(IM.predict([IN.feats(v, sh * shs, la, dvp, age)])[0]) + off
            v = min(140.0, max(10.0, v + dv * dt_h / 12)); acc += dv * dt_h / 12
            if int(age) % 12 == 0: dvp = acc; acc = 0.0
        t2 = t + dt.timedelta(hours=dt_h)
        if lf is None and not land_now and on_land(lo2, la2):
            lf = dict(t=t + dt.timedelta(hours=dt_h / 2), lat=(la + la2) / 2, lon=(lo + lo2) / 2, cls=c, wind=round(v, 1)); v_lf = v; land_h = 0.0
        la, lo, t = la2, lo2, t2; pts.append((t, la, lo, round(v, 1)))
        if on_land(lo, la) and v < 12: break                                      # remnant low has filled
        if not (2 < la < 29 and 71 < lo < 104.5): break
    return pts, lf
# ---------------- scenario sampling ----------------
def lhs(n, k, rng):
    return np.stack([(rng.permutation(n) + rng.random(n)) / n for _ in range(k)], 1)
AS_OPTS = {'none': None,
           'stalls off Kerala/Karnataka': [(0, 11.0, 73.5), (6, 12.0, 73.0)],
           'moves NW toward Oman': [(0, 11.0, 73.5), (2, 12.5, 70.0), (6, 16.0, 62.0)],
           'moves N toward Gujarat': [(0, 11.0, 73.5), (3, 15.5, 72.0), (6, 20.5, 70.5)]}
GOM_OPTS = {'fades in a day': [(0, 10.5, 81.5), (1, 10.6, 81.2)],
            'moves into TN and dies': [(0, 10.5, 81.5), (1.5, 10.9, 79.6)],
            'lingers off the coast': [(0, 10.5, 81.5), (2, 11.5, 81.3), (4, 12.5, 81.2)]}
MJO_OPTS = {'active, phase 3 (Indian Ocean)': (1.5, 0.4, -12), 'moves on to phase 4-5': (0.8, 0.2, 0), 'weak / fades': (0.0, -0.2, 12)}
SHEAR_OPTS = {'low shear, moist': 0.3, 'moderate': -0.1, 'high shear or dry air': -0.7}
def sample(n, t0, seed=1):
    rng = np.random.default_rng(seed); X = lhs(n, 13, rng); out = []
    for i in range(n):
        x = X[i]
        while True:
            gl, go = 8 + 6 * x[0], 85 + 9 * x[1]
            if not on_land(go, gl) and not (91.8 <= go <= 93.2 and 10.5 <= gl <= 13.8): break      # skip Andaman Islands
            x[1] = rng.random()
        mjo = list(MJO_OPTS)[i % 3]; asn = list(AS_OPTS)[(i // 3) % 4]; gom = list(GOM_OPTS)[(i // 12) % 3]; sh = list(SHEAR_OPTS)[rng.integers(3)]
        mu, mi, mdt = MJO_OPTS[mjo]
        gen_t = t0 + dt.timedelta(hours=24 + 96 * x[2] + mdt)
        wd_amp = [0, 4, 8][int(x[3] * 3)]
        P = dict(gen_lat=round(gl, 2), gen_lon=round(go, 2), gen_t=gen_t,
                 ridge_dlat=round(-2 + 4 * x[4], 2), ridge_dlon=round(-3 + 6 * x[5], 2), ridge_str=round(0.7 + 0.6 * x[6], 2), ridge_dt=round(-24 + 48 * x[7], 1),
                 sst=round(0.8 + 1.0 * x[8], 2), mjo=mjo, mjo_u=mu, mjo_i=mi, shear=sh, shear_i=SHEAR_OPTS[sh],
                 wd_amp=wd_amp, wd_day=round(4 + 4 * x[9], 1), surge_u=round(-4 * x[10], 2), surge_day=round(2 + 5 * rng.random(), 1),
                 beta=round(0.6 + 0.8 * x[11], 2), speed=round(0.8 + 0.4 * x[12], 2), as_sys=asn, gom=gom)
        P['as_track'] = [(t0 + dt.timedelta(days=d), a, b) for d, a, b in AS_OPTS[asn]] if AS_OPTS[asn] else None
        P['gom_track'] = [(t0 + dt.timedelta(days=d), a, b) for d, a, b in GOM_OPTS[gom]]
        out.append(P)
    return out
def sample_likely(n, t0, seed, sd):
    """Inputs narrowed to what today's observations support: every run starts from the observed seedling and moves with it."""
    rng = np.random.default_rng(seed); out = []
    for i in range(n):
        u = rng.random
        mjo = rng.choice(list(MJO_OPTS), p=[0.6, 0.3, 0.1]); mu, mi, mdt = MJO_OPTS[mjo]
        asn = rng.choice(list(AS_OPTS), p=[0.7, 0.1, 0.1, 0.1]); gom = rng.choice(list(GOM_OPTS)); sh = rng.choice(list(SHEAR_OPTS), p=[0.3, 0.5, 0.2])
        P = dict(start_t=t0, start_lat=round(sd[0] + rng.normal(0, 0.4), 2), start_lon=round(sd[1] + rng.normal(0, 0.4), 2),
                 gen_t=t0 + dt.timedelta(hours=36 + 48 * u() + mdt / 2), gen_lat=None, gen_lon=None,
                 ridge_dlat=round(rng.normal(0, 0.5), 2), ridge_dlon=round(rng.normal(0, 1.0), 2), ridge_str=round(1 + rng.normal(0, 0.07), 2), ridge_dt=round(rng.normal(0, 8), 1),
                 sst=round(1.4 + rng.normal(0, 0.15), 2), mjo=str(mjo), mjo_u=mu, mjo_i=mi, shear=str(sh), shear_i=SHEAR_OPTS[sh],
                 wd_amp=[0, 4][int(u() * 2)], wd_day=round(4 + 4 * u(), 1), surge_u=round(-2 * u(), 2), surge_day=round(2 + 5 * u(), 1),
                 beta=round(1 + rng.normal(0, 0.12), 2), speed=round(1 + rng.normal(0, 0.06), 2), as_sys=str(asn), gom=str(gom))
        P['as_track'] = [(t0 + dt.timedelta(days=d), a, b) for d, a, b in AS_OPTS[asn]] if AS_OPTS[asn] else None
        P['gom_track'] = [(t0 + dt.timedelta(days=d), a, b) for d, a, b in GOM_OPTS[gom]]
        out.append(P)
    return out
FACT51 = [  # (key, title, three settings low / as observed / high)
    ('gen', 'When the low forms', ['22 Oct evening', '23 Oct', '24 Oct evening']),
    ('start', 'Seedling position / early path', ['0.8 deg south-west', 'as observed', '0.8 deg north-east']),
    ('rlat', 'Ridge north-south', ['1 deg south', 'as now', '1 deg north']),
    ('rlon', 'Ridge east-west', ['1.5 deg west', 'as now', '1.5 deg east']),
    ('rstr', 'Ridge strength', ['15% weaker', 'as now', '15% stronger']),
    ('rdt', 'Ridge timing', ['12 h earlier', 'as now', '12 h later']),
    ('sst', 'Bay sea temperature', ['+1.2 C', '+1.4 C (observed)', '+1.6 C']),
    ('mjo', 'MJO', ['weak / fades', 'moves on to phase 4-5', 'active, phase 3 (Indian Ocean)']),
    ('shear', 'Wind shear / dry air', ['high shear or dry air', 'moderate', 'low shear, moist']),
    ('wd', 'Western disturbance', ['none', 'moderate', 'deep']),
    ('surge', 'NE-monsoon easterly surge', ['none', 'moderate', 'strong']),
    ('as', 'Arabian Sea system', ['none', 'stalls off Kerala/Karnataka', 'moves N toward Gujarat']),
    ('size', 'Storm size (beta drift)', ['smaller', 'typical', 'bigger'])]
def design51():
    """member 0 = control (every factor as observed); 1-27 = L27 orthogonal array (every pair of settings of any two
    factors together exactly 3 times); 28-50 = a second, shifted L27 block for more mixing."""
    combos = [(1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0), (1, 2, 0), (1, 0, 1), (1, 0, 2), (0, 1, 1), (0, 1, 2), (1, 1, 1), (1, 1, 2), (1, 2, 1), (1, 2, 2)]
    L = [[(a * x + b * y + c * z) % 3 for (x, y, z) in combos] for a in range(3) for b in range(3) for c in range(3)]
    rows = [[1] * 13] + L
    seen = {tuple(r) for r in rows}
    for r in L:
        r2 = [(v + 1 + (j % 2)) % 3 for j, v in enumerate(r[5:] + r[:5])]
        if tuple(r2) not in seen and len(rows) < 51: rows.append(r2); seen.add(tuple(r2))
    return rows
def sample51(t0, sd):
    out = []
    for m, lv in enumerate(design51()):
        f = {k: lv[i] for i, (k, _, _) in enumerate(FACT51)}
        mjo = ['weak / fades', 'moves on to phase 4-5', 'active, phase 3 (Indian Ocean)'][f['mjo']]; mu, mi, mdt = MJO_OPTS[mjo]
        sh = ['high shear or dry air', 'moderate', 'low shear, moist'][f['shear']]
        asn = ['none', 'stalls off Kerala/Karnataka', 'moves N toward Gujarat'][f['as']]
        off = (f['start'] - 1) * 0.8 / math.sqrt(2)
        P = dict(member=m, levels=lv, start_t=t0, start_lat=round(sd[0] + off, 2), start_lon=round(sd[1] + off, 2),
                 gen_t=t0 + dt.timedelta(hours=[36, 48, 84][f['gen']]), gen_lat=None, gen_lon=None,
                 ridge_dlat=[-1, 0, 1][f['rlat']], ridge_dlon=[-1.5, 0, 1.5][f['rlon']], ridge_str=[0.85, 1, 1.15][f['rstr']], ridge_dt=[-12, 0, 12][f['rdt']],
                 sst=[1.2, 1.4, 1.6][f['sst']], mjo=mjo, mjo_u=mu, mjo_i=mi, shear=sh, shear_i=SHEAR_OPTS[sh],
                 wd_amp=[0, 4, 8][f['wd']], wd_day=5.5, surge_u=[0, -2, -4][f['surge']], surge_day=3.0,
                 beta=[0.8, 1.0, 1.2][f['size']], speed=1.0, as_sys=asn, gom='fades in a day')
        P['as_track'] = [(t0 + dt.timedelta(days=d), a, b) for d, a, b in AS_OPTS[asn]] if AS_OPTS[asn] else None
        P['gom_track'] = [(t0 + dt.timedelta(days=d), a, b) for d, a, b in GOM_OPTS['fades in a day']]
        out.append(P)
    return out
def scen_summary(R):
    c = Counter(r['seg'] for r in R); n = len(R)
    return {k: round(100 * c[k] / n, 1) for k in ORDER if c[k]}
if __name__ == '__main__':
    M = train()
    S = O.lib_states(sys.argv[1]); sc = O.scales(S); RAW = lib_raw(sys.argv[1])
    if sys.argv[2] == '--hindcast':
        rows = []
        for s in LIBL:
            if (s['sid'], -24) not in S or not s['lf']: continue
            R = O.match(S[(s['sid'], -24)], S, sc, exclude_season=s['season'])
            C, top = composite(R, RAW)
            g = O.gen_time(s); now = RAW[(g - dt.timedelta(hours=24)).strftime('%Y-%m-%dT%H')].astype(float)
            E = base_env(now, C); P0 = O.path_of(s)
            pk = 0 if (max(p[3] or 0 for p in P0) < 34) else (1 if max(p[3] or 0 for p in P0) < 64 else 2)
            P = dict(gen_lat=P0[0][1], gen_lon=P0[0][2], gen_t=P0[0][0], ridge_dlat=0, ridge_dlon=0, ridge_str=1, ridge_dt=0, mjo_u=0, surge_u=0, surge_day=99,
                     wd_amp=0, beta=1, speed=1, sst=0.8 + 0.8 * pk, mjo_i=0, shear_i=0.0)
            env = Env(E, g - dt.timedelta(hours=24), P); pts, lf = run_track(M, env, P)
            # perfect-environment check: the storm's own ERA5 (vortex removed) as the environment
            own = []
            for tau in TAU:
                t = g - dt.timedelta(hours=24) + dt.timedelta(hours=tau); key = t.strftime('%Y-%m-%dT%H')
                if key in RAW:
                    F = RAW[key].astype(float); p = pos_at(s, t); own.append(remove_vortex(F, *p) if p else F)
                else: own.append(own[-1])
            pts2, lf2 = run_track(M, Env(np.stack(own), g - dt.timedelta(hours=24), P), P)
            truth = s['lf']
            e = lambda L: (abs(L['lat'] - truth[0]) if truth[1] < 89 else None) if L else None
            rows.append(dict(name=s['name'], season=s['season'], truth=segment(*truth), ours=segment(lf['lat'], lf['lon']) if lf else 'no landfall',
                             own=segment(lf2['lat'], lf2['lon']) if lf2 else 'no landfall', e=e(lf), e_own=e(lf2), top=top[:3]))
            print(f"{s['name'][:10]:10s} {s['season']} truth {rows[-1]['truth']:18s} ours {rows[-1]['ours']:18s} perfect-env {rows[-1]['own']:18s} err {e(lf)} / {e(lf2)}", flush=True)
        json.dump(rows, open('data/scen_hindcast.json', 'w'), default=str)
        for k, lab in (('ours', 'composite environment'), ('own', 'perfect environment')):
            hit = np.mean([r[k] == r['truth'] for r in rows]); E = [r['e' if k == 'ours' else 'e_own'] for r in rows]; E = [x for x in E if x is not None]
            print(f"{lab}: right coast stretch {hit:.0%} of {len(rows)} | median landfall-lat error {np.median(E):.1f} deg (n={len(E)})")
        sys.exit()
    now = ana_raw(sys.argv[2]); t0 = dt.datetime.strptime(str(np.load(sys.argv[2])['run']), '%Y%m%d%H')
    st = O.analysis_state(sys.argv[2])[1]; R = O.match(st, S, sc); C, top = composite(R, RAW)
    sd = vort_max(now, 1, (5, 15, 86, 98)); gm = vort_max(now, 0, (8, 13.5, 79, 84.5))
    print('seedling 700 hPa', sd, '| Gulf of Mannar 850 hPa', gm)
    now = remove_vortex(remove_vortex(now, sd[0], sd[1]), gm[0], gm[1], R=3.5)
    E = base_env(now, C)
    N = int(sys.argv[3]); PS = sample51(t0, sd) if len(sys.argv) > 4 and sys.argv[4] == '51' else (sample_likely(N, t0, 7, sd) if len(sys.argv) > 4 and sys.argv[4] == 'likely' else sample(N, t0)); RES = []
    for i, P in enumerate(PS):
        pts, lf = run_track(M, Env(E, t0, P), P)
        if P.get('gen_pos'): P['gen_lat'], P['gen_lon'] = round(P['gen_pos'][0], 2), round(P['gen_pos'][1], 2)
        r = {k: (v.isoformat() if isinstance(v, dt.datetime) else v) for k, v in P.items() if k not in ('as_track', 'gom_track', 'gen_pos')}
        r.update(peak=peak_class(P), vmax=max(p[3] for p in pts), seg=segment(lf['lat'], lf['lon']) if lf else 'no landfall',
                 lf=dict(t=lf['t'].isoformat(), lat=round(lf['lat'], 2), lon=round(lf['lon'], 2), cls=lf['cls'], wind=lf.get('wind')) if lf else None,
                 pts=[(p[0].isoformat(), round(p[1], 2), round(p[2], 2), p[3]) for p in (pts if len(sys.argv) > 4 and sys.argv[4] == '51' else pts[::2])])
        RES.append(r)
        if i % 200 == 0: print(i, scen_summary(RES), flush=True)
    json.dump(dict(t0=t0.isoformat(), analogs=top, seedling=sd, gom=gm, runs=RES), open(('data/scen_%s.json' % sys.argv[4]) if len(sys.argv) > 4 else 'data/scen.json', 'w'))
    print('ALL', len(RES), scen_summary(RES))
