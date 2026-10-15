"""sat-ranges branch: is the satellite radar's direction of movement right? Measure how rain moved on IMD's Chennai
radar between two scans 20-40 min apart, then compute the movement from the satellite pictures of the same two moments
with the same method the page uses, and compare (median direction/speed over the area both see, plus per-region)."""
import datetime as dt, json, math, os, time
import numpy as np
import radarcheck as rc
OUT = 'data/dircheck'; os.makedirs(OUT, exist_ok=True)
NX, NY, DX = rc.NX, rc.NY, (rc.LON1 - rc.LON0) / rc.NX
KMX, KMY = DX * 111.32 * math.cos(math.radians(11)), DX * 110.6
def blur(a, r=2):
    from numpy.lib.stride_tricks import sliding_window_view as sw
    p = np.pad(a, r, mode='edge'); return sw(p, (2 * r + 1, 2 * r + 1)).mean(axis=(-1, -2))
def motion(A, B, BS=30, ST=15, R=12, need=40):
    """Same block matching as the page: per block, shift of the older map that best matches the newer one."""
    A, B = blur(A), blur(B); out = []
    for y0 in range(0, NY - BS, ST):
        for x0 in range(0, NX - BS, ST):
            a = A[y0:y0 + BS:2, x0:x0 + BS:2]
            if a.sum() < need: continue
            best = None
            for dv in range(-R, R + 1):
                for du in range(-R, R + 1):
                    ys, xs = y0 + dv, x0 + du
                    if ys < 0 or xs < 0 or ys + BS > NY or xs + BS > NX: continue
                    s = np.abs(a - B[ys:ys + BS:2, xs:xs + BS:2]).sum() + 0.02 * (du * du + dv * dv)
                    if best is None or s < best[0]: best = (s, du, dv)
            if best: out.append((x0 + BS / 2, y0 + BS / 2, best[1], best[2], float(a.sum())))
    return out
def summary(vecs, minutes):
    if not vecs: return None
    u = np.array([v[2] for v in vecs]) * KMX / minutes * 60; w = np.array([v[3] for v in vecs]) * KMY / minutes * 60
    wt = np.array([v[4] for v in vecs]); mu, mv = np.average(u, weights=wt), np.average(w, weights=wt)
    ang = (math.degrees(math.atan2(mv, mu)) + 360) % 360       # 0 = moving east, 90 = moving north
    names = ['east', 'north-east', 'north', 'north-west', 'west', 'south-west', 'south', 'south-east']
    return dict(blocks=len(vecs), toward=names[int((ang + 22.5) // 45) % 8], angle_deg=round(ang), kmh=round(math.hypot(mu, mv), 1),
                spread_deg=round(float(np.degrees(np.std(np.unwrap(np.arctan2(w, u))))), 0))
def grab():
    buf = rc.get(rc.CHN['url']); return buf, rc.scan_time(buf)
b1, t1 = grab(); print('radar scan 1', t1, flush=True)
deadline = time.time() + 75 * 60; b2, t2 = None, None
while time.time() < deadline:
    time.sleep(120); b, t = grab()
    if t and (t - t1).total_seconds() >= 40 * 60:
        b2, t2 = b, t; break
print('radar scan 2', t2, flush=True)
res = dict(radar=[t1.isoformat(), t2.isoformat() if t2 else None])
if b2:
    R1 = np.nan_to_num(rc.radar_grid(rc.CHN, b1)); R2 = np.nan_to_num(rc.radar_grid(rc.CHN, b2))
    mins = (t2 - t1).total_seconds() / 60
    rv = motion(R1, R2, need=8); res['radar_motion'] = summary(rv, mins); print('radar', res['radar_motion'], flush=True)
    # cell tracking on the radar: match each rain cell to the nearest cell in the later scan (within 40 km, similar size)
    from scipy import ndimage
    def cells(F):
        lab, n = ndimage.label(F >= 1); out = []
        for k in range(1, n + 1):
            yy, xx = np.nonzero(lab == k)
            if len(yy) >= 8: out.append((xx.mean(), yy.mean(), len(yy)))
        return out
    c1, c2 = cells(R1), cells(R2); tr = []
    for x, y, n in c1:
        best = None
        for X2, Y2, n2 in c2:
            d = math.hypot((X2 - x) * KMX, (Y2 - y) * KMY)
            if d <= 40 and 0.33 <= n2 / n <= 3 and (best is None or d < best[0]): best = (d, X2 - x, Y2 - y, n)
        if best: tr.append((x, y, best[1], best[2], best[3]))
    res['radar_cells'] = summary(tr, mins); res['radar_cells_n'] = [len(c1), len(c2), len(tr)]; print('radar cells', res['radar_cells'], flush=True)
    try:
        S = json.load(open('site/steer.json')); import bisect
        ts = [dt.datetime.fromisoformat(x.replace('Z', '+00:00')) for x in S['times']]; k = min(range(len(ts)), key=lambda i: abs((ts[i] - t1).total_seconds()))
        us, vs = [], []
        for j in range(S['ny']):
            for i in range(S['nx']):
                lo, la = S['lon0'] + i * S['step'], S['lat0'] + j * S['step']
                if 78.5 <= lo <= 81.5 and 11.5 <= la <= 14.5: us.append(S['u'][k][j * S['nx'] + i]); vs.append(S['v'][k][j * S['nx'] + i])
        mu, mv = sum(us) / len(us), sum(vs) / len(vs); ang = (math.degrees(math.atan2(mv, mu)) + 360) % 360
        names = ['east', 'north-east', 'north', 'north-west', 'west', 'south-west', 'south', 'south-east']
        res['steering_wind'] = dict(time=S['times'][k], toward=names[int((ang + 22.5) // 45) % 8], angle_deg=round(ang), kmh=round(math.hypot(mu, mv) * 3.6, 1))
    except Exception as e:
        res['steering_wind'] = str(e)
    s1, s2 = rc.sat_time_for(t1), rc.sat_time_for(t2)
    while time.time() < deadline + 70 * 60:
        if rc.sat_latest() >= s2: break
        time.sleep(120)
    S1 = rc.sat_frame(s1) * 0.3; S2 = rc.sat_frame(s2) * 0.3
    mask = ~np.isnan(rc.radar_grid(rc.CHN, b1))                  # compare over the radar's area only
    sv = motion(np.where(mask, S1, 0), np.where(mask, S2, 0), need=40); sm = (s2 - s1).total_seconds() / 60
    res['sat_frames'] = [s1.isoformat(), s2.isoformat()]; res['sat_motion'] = summary(sv, sm); print('satellite', res['sat_motion'], flush=True)
    # picture: radar at both times with movement arrows, satellite with its arrows
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    G = json.load(open('data/geo.json')); ext = [rc.LON0, rc.LON1, rc.LAT0, rc.LAT1]
    fig, ax = plt.subplots(1, 2, figsize=(11, 6), dpi=100)
    for a_, F1, F2, V, ti, m in ((ax[0], R1, R2, rv, f'IMD Chennai radar {mins:.0f} min apart', mins), (ax[1], np.where(mask, S1, 0), np.where(mask, S2, 0), sv, f'Our satellite radar {sm:.0f} min apart', sm)):
        a_.set_facecolor('#eef2f4')
        a_.contourf(np.linspace(*ext[:2], NX), np.linspace(*ext[2:], NY), F1, [1, 1e9], colors=['#9ecae1'], alpha=.8)
        a_.contour(np.linspace(*ext[:2], NX), np.linspace(*ext[2:], NY), F2, [1], colors=['#08519c'], linewidths=1)
        for x, y, du, dv, w in V:
            lo, la = rc.LON0 + x * DX, rc.LAT0 + y * DX
            a_.arrow(lo, la, du * DX * 60 / m, dv * DX * 60 / m, head_width=.06, color='#c0392b', length_includes_head=True)
        for r in G['tn']:
            r = np.array(r); a_.plot(r[:, 0], r[:, 1], color='#555', lw=.5)
        a_.set_xlim(78.2, 82.3); a_.set_ylim(11.2, 14.9); a_.set_aspect(1 / math.cos(math.radians(13))); a_.set_title(ti, fontsize=10)
    fig.suptitle(f'Light blue = first picture, dark outline = second; red arrows = movement in 1 hour', fontsize=10)
    fig.savefig(f'{OUT}/direction_{t1:%Y%m%d%H%M}.png', bbox_inches='tight')
json.dump(res, open(f'{OUT}/direction_{t1:%Y%m%d%H%M}.json', 'w'), indent=1); print(json.dumps(res, indent=1))
