"""sat-radar branch: cross-check our satellite radar against IMD's Chennai and Karaikal radars.
Grabs the latest IMD PPI pictures (lowest scan, closest to rain at the ground), waits for the satellite picture
taken at the same time (it appears ~55 min later), turns both into mm/h on the same 0.025 degree grid and compares
them within 200 km of each radar. Results are appended to data/satradar/radarcheck.jsonl (one line per check)."""
import datetime as dt, io, json, math, os, re, time, urllib.request
import numpy as np
from PIL import Image
UA = {'User-Agent': 'Mozilla/5.0 (tn-rainfall-map satellite radar check)'}
OUT = 'data/satradar'; os.makedirs(OUT, exist_ok=True)
LON0, LON1, LAT0, LAT1, NX, NY = 75.5, 81.5, 7.0, 14.5, 240, 300
CAL = 0.3
UTC = dt.timezone.utc
def get(u, t=90):
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t) as r:
        return r.read()
# ---------- radar pictures: position on the map and colour -> dBZ
CHN = dict(url='https://mausam.imd.gov.in/Radar/ppz_cni.gif', name='Chennai', centre=(80.29, 13.08),
           xy=lambda lo, la: (378 + (lo - 80) * 72.3, 404 + (13 - la) * 74), panel=(0, 0, 800, 800))
def kk_xy(lo, la, C=(79.84, 10.92), cx=360, cy=358, s=0.72):
    dx = (lo - C[0]) * 111.32 * np.cos(np.radians((la + C[1]) / 2)); dy = (la - C[1]) * 110.6
    return (cx + dx * s, cy - dy * s)
KKL = dict(url='https://mausam.imd.gov.in/Radar/ppz_kkl.gif', name='Karaikal', centre=(79.84, 10.92), xy=kk_xy, panel=(0, 0, 718, 720))
# Chennai uses web-safe colours; the sea is drawn with (102,204,255)/(153,204,255)/(102,153,255)/(153,153,255)/(102,153,204),
# so those shades are left out and only unmistakable rain colours are read.
CHN_LUT = {(0, 0, 153): 21.25, (0, 0, 204): 23.75, (0, 51, 255): 26.25, (0, 102, 255): 28.75, (0, 153, 255): 31.25, (51, 153, 255): 31.25,
           (51, 204, 255): 33.75, (102, 255, 255): 36.25, (153, 255, 255): 36.25, (255, 255, 255): 38.75, (255, 255, 153): 41.25,
           (255, 255, 204): 41.25, (255, 255, 0): 43.75, (255, 204, 0): 46.25, (255, 153, 0): 46.25, (255, 102, 0): 48.75,
           (255, 51, 0): 51.25, (204, 0, 0): 53.75, (153, 0, 0): 56.25, (153, 0, 51): 58.75, (102, 0, 51): 61.0}
def kk_lut(img):
    """Karaikal: continuous colour bar at x=789, y 383 (60 dBZ) to 607 (20 dBZ)."""
    a = np.asarray(img.convert('RGB')).astype(int); lut = {}
    for y in range(383, 608):
        c = tuple(a[y, 789]); lut.setdefault(c, 60 - (y - 383) * 40 / (607 - 383))
    return lut
def scan_time(buf):
    m = re.search(rb'(20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d)', buf[:3000])
    return dt.datetime.fromisoformat(m.group(1).decode()).replace(tzinfo=dt.timezone(dt.timedelta(hours=5, minutes=30))).astimezone(UTC) if m else None
def radar_grid(R, buf):
    img = Image.open(io.BytesIO(buf)); a = np.asarray(img.convert('RGB')).astype(int)
    lut = CHN_LUT if R is CHN else kk_lut(img)
    keys = np.array(list(lut)); vals = np.array([lut[tuple(k)] for k in keys])
    lon = LON0 + (np.arange(NX) + .5) * (LON1 - LON0) / NX; lat = LAT0 + (np.arange(NY) + .5) * (LAT1 - LAT0) / NY
    LO, LA = np.meshgrid(lon, lat)
    X, Y = R['xy'](LO, LA); X = np.round(X).astype(int); Y = np.round(Y).astype(int)
    rng = np.hypot((LO - R['centre'][0]) * 111.32 * np.cos(np.radians(LA)), (LA - R['centre'][1]) * 110.6)
    x0, y0, x1, y1 = R['panel']; inside = (X >= x0 + 1) & (X < x1 - 1) & (Y >= y0 + 1) & (Y < y1 - 1) & (rng <= 200) & (rng >= 8)
    rate = np.zeros((NY, NX))
    for dy in (-1, 0, 1):                      # 3x3 pixel average (the pictures are dithered)
        for dx in (-1, 0, 1):
            px = a[np.clip(Y + dy, 0, a.shape[0] - 1), np.clip(X + dx, 0, a.shape[1] - 1)]
            d = np.abs(px[..., None, :] - keys[None, None]).sum(-1)
            k = d.argmin(-1); ok = d.min(-1) <= (0 if R is CHN else 12)
            dbz = np.where(ok, vals[k], 0)
            r = np.where(dbz >= 20, (10 ** (dbz / 10) / 200) ** (1 / 1.6), 0)   # Marshall-Palmer Z = 200 R^1.6
            rate += r / 9
    rate[~inside] = np.nan
    return rate
# ---------- satellite (same decoding as the page)
STOPS = [(0.0, (255, 255, 204)), (0.2, (227, 244, 192)), (1.05, (198, 232, 179)), (2.0, (162, 218, 183)), (3.0, (126, 204, 186)), (5.0, (96, 194, 191)),
         (7.0, (65, 183, 196)), (10.0, (47, 164, 194)), (15.0, (29, 145, 191)), (20.0, (32, 120, 180)), (30.0, (34, 94, 168)), (49.2, (12, 44, 133)), (60.0, (8, 30, 100))]
def sat_decode(rgba):
    a = rgba[..., 3] > 0; rgb = rgba[..., :3].astype(float); best = np.full(a.shape, 1e9); val = np.zeros(a.shape)
    for (v0, c0), (v1, c1) in zip(STOPS, STOPS[1:]):
        c0, c1 = np.array(c0, float), np.array(c1, float); d = c1 - c0
        t = np.clip(((rgb - c0) @ d) / (d @ d), 0, 1); dist = np.linalg.norm(rgb - (c0 + t[..., None] * d), axis=-1)
        m = dist < best; best[m] = dist[m]; val[m] = (v0 + t * (v1 - v0))[m]
    val[~a] = 0; val[a & (best > 60)] = 0
    return val[::-1]
W = 'https://view.eumetsat.int/geoserver'
def sat_latest():
    cap = get(W + '/msg_iodc/h63/ows?service=WMS&version=1.3.0&request=GetCapabilities').decode()
    m = re.search(r'<Dimension[^>]*name="time"[^>]*>([^<]*)</Dimension>', cap)
    return dt.datetime.fromisoformat(m.group(1).split('/')[1].replace('.000Z', '+00:00'))
def sat_frame(t):
    u = (f'{W}/ows?service=WMS&version=1.3.0&request=GetMap&layers=msg_iodc:h63&styles=&crs=EPSG:4326&bbox={LAT0},{LON0},{LAT1},{LON1}'
         f'&width={NX}&height={NY}&format=image/png&transparent=true&time={t:%Y-%m-%dT%H:%M:00Z}')
    return sat_decode(np.asarray(Image.open(io.BytesIO(get(u))).convert('RGBA')))
# ---------- compare
def stats(sat, rad):
    m = ~np.isnan(rad); s = sat[m]; r = rad[m]
    def pod_far(th):
        h = ((s >= th) & (r >= th)).sum(); mi = ((s < th) & (r >= th)).sum(); f = ((s >= th) & (r < th)).sum()
        return dict(hit=int(h), miss=int(mi), false=int(f), pod=round(h / max(1, h + mi), 2), far=round(f / max(1, h + f), 2))
    both = (s >= 1) & (r >= 1)
    return dict(cells=int(m.sum()), radar_rain_share=round(float((r >= 1).mean()), 3), sat_rain_share=round(float((s >= 1).mean()), 3),
                radar_mean=round(float(r.mean()), 2), sat_mean=round(float(s.mean()), 2),
                ratio_where_both=round(float(s[both].sum() / max(r[both].sum(), 1e-6)), 2) if both.any() else None,
                radar_p90=round(float(np.percentile(r[r >= 1], 90)), 1) if (r >= 1).any() else 0, sat_p90=round(float(np.percentile(s[s >= 1], 90)), 1) if (s >= 1).any() else 0,
                at1=pod_far(1), at5=pod_far(5))
def picture(name, t, sat, rad, latest=False):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    from matplotlib.colors import BoundaryNorm, ListedColormap
    G = json.load(open('data/geo.json'))
    cols = ['#a6dcf0', '#4fb8e8', '#1f72d6', '#2bb24c', '#f5c400', '#f06b00', '#c4001a']; b = [0.5, 1, 2.5, 5, 10, 20, 40, 500]
    cm = ListedColormap(cols); cm.set_under((0, 0, 0, 0)); nm = BoundaryNorm(b, cm.N)
    fig, ax = plt.subplots(1, 2, figsize=(10, 6), dpi=100)
    m = np.isnan(rad)
    for a_, f, ti in ((ax[0], rad, f'IMD {name} radar (lowest scan)'), (ax[1], np.where(m, np.nan, sat), 'Our satellite radar (x0.3)')):
        a_.set_facecolor('#e8edf0'); a_.imshow(np.ma.masked_less(f, .5), origin='lower', extent=[LON0, LON1, LAT0, LAT1], cmap=cm, norm=nm, interpolation='nearest')
        for r in G['tn']:
            r = np.array(r); a_.plot(r[:, 0], r[:, 1], color='#555', lw=.5)
        a_.contour(np.linspace(LON0, LON1, NX), np.linspace(LAT0, LAT1, NY), (~m).astype(float), [.5], colors='k', linewidths=.6)
        a_.set_title(ti, fontsize=10); a_.set_aspect(1 / np.cos(np.radians(11)))
        c = (CHN if name == 'Chennai' else KKL)['centre']; a_.set_xlim(c[0] - 2.1, c[0] + 2.1); a_.set_ylim(c[1] - 1.9, c[1] + 1.9)
    fig.suptitle(f'{name}: {(t + dt.timedelta(hours=5, minutes=30)):%d %b %H:%M} IST, rain rate mm/h', fontsize=11)
    fig.colorbar(plt.cm.ScalarMappable(norm=nm, cmap=cm), ax=ax, orientation='horizontal', fraction=.05, pad=.06, ticks=b[:-1])
    fig.savefig(f'{OUT}/check_{name.lower()}_' + ('latest' if latest else f'{t:%Y%m%d%H%M}') + '.png', bbox_inches='tight'); plt.close(fig)
def process(R, buf, tt, ts):
    raw = sat_frame(ts); rad = radar_grid(R, buf); sat = raw * CAL
    st = stats(sat, rad)
    rec = dict(radar=R['name'], radar_utc=tt.isoformat(), sat_utc=ts.isoformat(), corrected=st, raw_ratio=stats(raw, rad)['ratio_where_both'])
    print(json.dumps(rec), flush=True)
    open(f'{OUT}/radarcheck.jsonl', 'a').write(json.dumps(rec) + '\n')
    os.makedirs(f'{OUT}/pairs', exist_ok=True)
    half = lambda g: np.nanmean(g.reshape(NY // 2, 2, NX // 2, 2), axis=(1, 3))      # 0.05 degree, keeps files small
    np.savez_compressed(f'{OUT}/pairs/{R["name"].lower()}_{tt:%Y%m%d%H%M}.npz', sat_raw=half(raw).astype(np.float16), radar=half(rad).astype(np.float16))
    picture(R['name'], tt, sat, rad, latest=os.environ.get('CRON') == '1')
def sat_time_for(tt):
    c = [(tt - dt.timedelta(minutes=8)).replace(minute=0, second=0, microsecond=0) + dt.timedelta(minutes=15 * k) for k in range(0, 5)]
    return min(c, key=lambda x: abs((x + dt.timedelta(minutes=8)) - tt))
def main():
    hours = float(os.environ.get('CHECK_HOURS', '0'))
    stop_grab = time.time() + hours * 3600; queue = []; seen = set()
    while True:
        for R in (CHN, KKL):
            try:
                buf = get(R['url']); tt = scan_time(buf)
                if tt and (R['name'], tt) not in seen:
                    seen.add((R['name'], tt)); queue.append((R, buf, tt, sat_time_for(tt))); print(R['name'], 'radar scan', tt, flush=True)
            except Exception as e:
                print(R['name'], 'radar ERROR', e, flush=True)
        try:
            L = sat_latest()
        except Exception as e:
            L = None; print('sat latest ERROR', e)
        for item in [q for q in queue if L and q[3] <= L]:
            queue.remove(item)
            try:
                process(*item)
            except Exception as e:
                print(item[0]['name'], 'compare ERROR', e, flush=True)
        if time.time() > stop_grab and not queue:
            break
        if time.time() > stop_grab + 80 * 60:
            break
        time.sleep(30 * 60 if time.time() < stop_grab else 120)
    fit()
def fit():
    """Best cut-off T (raw mm/h below T = no rain) and scale a (rate = a * raw) so the satellite matches the radar:
    same share of area raining at 1 mm/h, same total rain where it rains. Scored by critical success index at 1 mm/h."""
    import glob
    S, Rr = [], []
    for f in sorted(glob.glob(f'{OUT}/pairs/*.npz')):
        z = np.load(f); m = ~np.isnan(z['radar']); S.append(z['sat_raw'][m]); Rr.append(z['radar'][m])
    if not S:
        return None
    s = np.concatenate(S); r = np.concatenate(Rr); res = []
    for T in (0, 1, 2, 3, 5, 7, 10, 15, 20, 30):
        for a in (0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.6, 0.8, 1.0):
            c = np.where(s >= T, s * a, 0)
            h = ((c >= 1) & (r >= 1)).sum(); mi = ((c < 1) & (r >= 1)).sum(); fa = ((c >= 1) & (r < 1)).sum()
            csi = h / max(1, h + mi + fa); bias = (c >= 1).sum() / max(1, (r >= 1).sum())
            res.append(dict(T=T, a=a, csi=round(float(csi), 3), area_bias=round(float(bias), 2), mean_ratio=round(float(c.mean() / max(r.mean(), 1e-6)), 2),
                            pod=round(h / max(1, h + mi), 2), far=round(fa / max(1, h + fa), 2)))
    res.sort(key=lambda d: (-d['csi']))
    out = dict(pairs=len(S), cells=int(len(r)), radar_rain_share=round(float((r >= 1).mean()), 3), best=res[:10],
               current=[d for d in res if d['T'] == 0 and d['a'] == 0.3])
    json.dump(out, open(f'{OUT}/fit.json', 'w'), indent=1); print(json.dumps(out, indent=1))
    return out if len(S) >= 6 else None
def fit_quantiles(min_pairs=6):
    """Quantile matching: (1) cut-off so the satellite rains over the same share of the area as the radar (1 mm/h or
    more), (2) above the cut-off, map the satellite's rate distribution onto the radar's (light to light, heavy to heavy),
    so heavy cores stay heavy. Uses every saved pair (last 14 days). Returns None until there are enough pairs."""
    import glob
    S, Rr = [], []
    for f in sorted(glob.glob(f'{OUT}/pairs/*.npz')):
        z = np.load(f); r = np.asarray(z['radar'], float); s_ = np.asarray(z['sat_raw'], float); m = ~np.isnan(r)
        if s_.shape != r.shape: continue
        S.append(s_[m]); Rr.append(r[m])
    if len(S) < min_pairs: return None
    s = np.concatenate(S); r = np.concatenate(Rr)
    share = float((r >= 1).mean())
    if share <= 0: return None
    cut = float(np.quantile(s, 1 - share))                    # same raining share as the radar
    cut = max(cut, 0.2)
    rs, ss = np.sort(r[r >= 1]), np.sort(s[s >= cut])
    if len(rs) < 50 or len(ss) < 50: return None
    qs = [0, .1, .2, .3, .4, .5, .6, .7, .8, .9, .95, .98, .995, 1]
    lut = []
    for q in qs:
        a_, b_ = float(np.quantile(ss, q)), float(np.quantile(rs, q))
        if not lut or a_ > lut[-1][0] + 1e-3: lut.append([round(a_, 2), round(max(b_, lut[-1][1] if lut else 0), 2)])
    corr = np.where(s >= cut, np.interp(s, [p[0] for p in lut], [p[1] for p in lut]), 0)
    h = ((corr >= 1) & (r >= 1)).sum(); mi = ((corr < 1) & (r >= 1)).sum(); fa = ((corr >= 1) & (r < 1)).sum()
    # single multiplier for older page versions: least-squares slope of the mapping (keeps heavy cores far better than the median ratio)
    med = sum(p[0] * p[1] for p in lut) / max(sum(p[0] * p[0] for p in lut), 1e-6)
    return dict(cut=round(cut, 2), lut=lut, scale=round(med, 3), pairs=len(S), csi=round(h / max(1, h + mi + fa), 3),
                area_bias=round(float((corr >= 1).sum() / max(1, (r >= 1).sum())), 2), radar_p90=round(float(np.quantile(rs, .9)), 1))
def radar_ok(buf, tt, now):
    """A radar counts as working only if its picture is fresh (scan within 2 hours; IMD pictures often lag 1 hour) and decodes."""
    if tt is None or len(buf) < 20000:
        return False, 'no scan time or picture too small'
    age = (now - tt).total_seconds() / 60
    if age > 120:
        return False, f'picture is {age:.0f} min old (radar probably not working)'
    try:
        Image.open(io.BytesIO(buf)).convert('RGB')
    except Exception as e:
        return False, f'picture does not open: {e}'
    return True, ''
def cron():
    """One pass, run every 30 min by a timed job: save fresh radar pictures, compare any whose satellite picture
    is now available, prune old pairs, refit the correction and write data/satradar/satcal.json."""
    import glob
    now = dt.datetime.now(UTC); P = f'{OUT}/pending'; os.makedirs(P, exist_ok=True)
    status = dict(run_utc=now.isoformat(), radars={})
    for R in (CHN, KKL):
        try:
            buf = get(R['url']); tt = scan_time(buf); ok, why = radar_ok(buf, tt, now)
        except Exception as e:
            ok, why, tt = False, f'download failed: {e}', None
        status['radars'][R['name']] = dict(working=ok, scan_utc=tt.isoformat() if tt else None, note=why)
        if ok:
            fn = f'{P}/{R["name"].lower()}_{tt:%Y%m%d%H%M%S}.gif'
            if not os.path.exists(fn):
                open(fn, 'wb').write(buf)
    try:
        L = sat_latest()
    except Exception as e:
        L = None; status['satellite_error'] = str(e)
    status['satellite_latest'] = L.isoformat() if L else None
    done = 0
    for fn in sorted(glob.glob(f'{P}/*.gif')):
        name, stamp = os.path.basename(fn)[:-4].split('_')
        tt = dt.datetime.strptime(stamp, '%Y%m%d%H%M%S').replace(tzinfo=UTC); ts = sat_time_for(tt)
        R = CHN if name == 'chennai' else KKL
        if L and ts <= L:
            try:
                process(R, open(fn, 'rb').read(), tt, ts); done += 1
            except Exception as e:
                print(name, 'compare ERROR', e, flush=True)
            os.remove(fn)
        elif (now - tt).total_seconds() > 6 * 3600:
            os.remove(fn)
    status['compared_this_run'] = done
    for f in glob.glob(f'{OUT}/pairs/*.npz'):            # keep two weeks of pairs
        try:
            t = dt.datetime.strptime(os.path.basename(f)[:-4].split('_')[1], '%Y%m%d%H%M').replace(tzinfo=UTC)
            if (now - t).days > 14:
                os.remove(f)
        except Exception:
            pass
    out = fit(); q = fit_quantiles()
    if q:
        json.dump(dict(updated=now.isoformat(), method='quantile', cut_mm_h=q['cut'], scale=q['scale'], lut=q['lut'], pairs=q['pairs'],
                       csi=q['csi'], area_bias=q['area_bias'], radar_p90=q['radar_p90'], radars=status['radars']), open(f'{OUT}/satcal.json', 'w'), indent=1)
    elif out and out.get('best'):
        b = out['best'][0]
        json.dump(dict(updated=now.isoformat(), cut_mm_h=b['T'], scale=b['a'], pairs=out['pairs'], csi=b['csi'], area_bias=b['area_bias'],
                       radars=status['radars']), open(f'{OUT}/satcal.json', 'w'), indent=1)
    json.dump(status, open(f'{OUT}/cron_status.json', 'w'), indent=1); print(json.dumps(status))
if __name__ == '__main__':
    import sys
    fit() if 'fit' in sys.argv else cron() if 'cron' in sys.argv else main()
