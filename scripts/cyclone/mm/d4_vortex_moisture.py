"""D4 offline check (A-B4, vortex moisture). At each storm's start: where is the moist core after the bogus step?
mm2.bogus removes the analysis' own vortex from T, ps, u, v (fill within 3-4 deg) but NOT from q, then raises q toward
0.9 qs within 2.5 rmw of the observed centre (p >= 400 hPa, never lowers it). If the analysis' moist core sits away from
the observed centre and is already > 0.9 RH, it stays as a second (moister) convective focus -> two centres compete.
Measure: separation observed centre <-> analysis low (min ps), and <-> max of 850-500 hPa mean RH within 400 km,
before and after the bogus moisture step (numpy copy of the mm2 lines; warm-core T change ignored: it raises qs, so
the bogus RH target is reached with more q and the conclusion does not depend on it).
python d4_vortex_moisture.py LIBM_NPZ"""
import sys, os, math, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'analysis'))
import ourens as O
Z = np.load(sys.argv[1]); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
LA, LO = np.meshgrid(Z['lats'], Z['lons'], indexing='ij'); levs = Z['levs']
def qs(T, p): es = 611.2 * np.exp(17.67 * (T - 273.15) / (T - 29.65)); return 0.622 * es / (p * 100.0 - 0.378 * es)
def at(P0, t):
    for a, b in zip(P0, P0[1:]):
        if a[0] <= t <= b[0]:
            f = (t - a[0]).total_seconds() / max(1, (b[0] - a[0]).total_seconds()); return tuple(a[i] + f * (b[i] - a[i]) for i in (1, 2))
mid = [i for i, p in enumerate(levs) if 500 <= p <= 850]
out = []
for s in O.LIBL:
    if s['name'] not in ('Sidr', 'Titli', 'Phailin', 'Giri', 'Hamoon', 'Nivar'): continue
    g = O.gen_time(s); key = g.strftime('%Y-%m-%dT%H')
    if key not in TT: continue
    k = TT.index(key); lat, lon = at(O.path_of(s), g)
    T = Z['f3'][k, V3.index('temperature')]; q = Z['f3'][k, V3.index('specific_humidity')]; ps = Z['f2'][k, V2.index('surface_pressure')]
    cosl = math.cos(math.radians(lat)); d = np.hypot(LA - lat, ((LO - lon + 180) % 360 - 180) * cosl) * 111.2
    near = d <= 400
    def rhmid(Q): return np.mean([Q[i] / qs(T[i], levs[i]) for i in mid], 0)
    ia = np.unravel_index(np.argmin(np.where(d <= 350, ps, 1e9)), ps.shape); da = d[ia]
    R0 = rhmid(q); i0 = np.unravel_index(np.argmax(np.where(near, R0, -1)), R0.shape)
    vmax = s.get('vmax_kt') or 25.0; rm = max(150.0 if vmax < 34 else 100.0, 1.3 * 111.2 * 180 / 256)
    q2 = q.copy(); core = np.clip(1 - d / (2.5 * rm), 0, 1)
    for i, p in enumerate(levs):
        if p >= 400: q2[i] = q[i] + core * np.maximum(0.9 * qs(T[i], p) - q[i], 0)
    R2 = rhmid(q2); i2 = np.unravel_index(np.argmax(np.where(near, R2, -1)), R2.shape)
    at_c = float(R2[np.unravel_index(np.argmin(d), d.shape)])
    out.append((s['name'], round(da), round(d[i0]), round(float(R0[i0]), 3), round(d[i2]), round(float(R2[i2]), 3), round(at_c, 3)))
    print(f"{s['name']:8s} analysis low {da:4.0f} km from obs centre | moist-core max before {d[i0]:4.0f} km (RH {R0[i0]:.2f}) | after bogus {d[i2]:4.0f} km (RH {R2[i2]:.2f}); RH at obs centre after {at_c:.2f}")
sep = [o[4] for o in out]; print('mean distance obs centre -> moist-core max after bogus:', round(float(np.mean(sep))), 'km;', sum(1 for x in sep if x > 100), 'of', len(sep), 'storms > 100 km')

if len(sys.argv) > 2:      # does the model storm drift toward the left-over moist core? (control tracks, e.g. tn-quick6-ctl-d1/q6.json)
    import json
    R = {r['name']: r for r in json.load(open(sys.argv[2])) if 'trk' in r}
    print('error vector (model - observed) at 12/24 h vs direction to the left-over moist core (cosine; >0.5 = toward it)')
    for s in O.LIBL:
        n = s['name']
        if n not in R: continue
        g = O.gen_time(s); key = g.strftime('%Y-%m-%dT%H'); k = TT.index(key); lat, lon = at(O.path_of(s), g)
        T = Z['f3'][k, V3.index('temperature')]; q = Z['f3'][k, V3.index('specific_humidity')]
        cosl = math.cos(math.radians(lat)); d = np.hypot(LA - lat, ((LO - lon + 180) % 360 - 180) * cosl) * 111.2
        R0 = np.mean([q[i] / qs(T[i], levs[i]) for i in mid], 0); i0 = np.unravel_index(np.argmax(np.where(d <= 400, R0, -1)), R0.shape)
        bx, by = ((LO[i0] - lon + 180) % 360 - 180) * cosl, LA[i0] - lat
        cs = []
        for h in (12, 24):
            x = [t for t in R[n]['trk'] if t[0] == h][0]; tr = [p for p in R[n]['real']]
            tt = next(((a[1] + (h - a[0]) / (b[0] - a[0]) * (b[1] - a[1]), a[2] + (h - a[0]) / (b[0] - a[0]) * (b[2] - a[2])) for a, b in zip(tr, tr[1:]) if a[0] <= h <= b[0]), None)
            ex, ey = (x[2] - tt[1]) * cosl, x[1] - tt[0]
            cs.append((h, round((ex * bx + ey * by) / max(1e-9, math.hypot(ex, ey) * math.hypot(bx, by)), 2), round(111.2 * math.hypot(ex, ey))))
        print(f'{n:8s} core at ({by*111:+.0f} km N, {bx*111:+.0f} km E): ' + ', '.join(f'{h} h cos {c} (error {e} km)' for h, c, e in cs))
