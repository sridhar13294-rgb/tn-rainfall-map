"""Read IMD's lightning maps (INSAT-3DS/3DR + national lightning network) every 15 minutes and turn the strike marks
into positions, storm clusters, their trend and their movement. Used only as a background reference for the Sat radar
page; IMD's images are never shown on the site.

IMD publishes three maps with the same map time: strikes 0-10 min (red stars), 10-20 min (green diamonds) and
20-30 min (purple circles) before it. Markers are shrunk to their centres, put on a 0.1-degree grid, and movement is
found by matching the 20-30 min strikes to the 0-10 min strikes (20 minutes apart), block by block.

Usage: python scripts/lightning.py <out_dir>   (writes lightning.json and hist.jsonl there)
"""
import os, sys, io, json, datetime as dt, urllib.request, email.utils
import numpy as np
from PIL import Image
from scipy import ndimage as nd

BASE = 'https://internal.imd.gov.in/section/satmet/lightning/'
IMGS = {'b10': ('Last10_BT.png', 3), 'b20': ('Last20_BT.png', 4), 'b30': ('Last30_BT.png', 4)}   # file, marker half-size (px)
# georeference of the 875x656 plot, checked against the coast (Kanyakumari, Chennai, Point Calimere) to ~0.1 deg
X80, PX_LON, Y5, PX_LAT = 369.9, 14.067, 586.0, 14.11
LON0, LON1, LAT0, LAT1, STEP = 62.0, 96.0, -2.0, 25.0, 0.1
NX, NY = int(round((LON1 - LON0) / STEP)), int(round((LAT1 - LAT0) / STEP))
UTC = dt.timezone.utc


def get(name):
    r = urllib.request.urlopen(urllib.request.Request(BASE + name, headers={'User-Agent': 'Mozilla/5.0 (tn-rainfall-map)'}), timeout=60)
    lm = r.headers.get('Last-Modified')
    return r.read(), (email.utils.parsedate_to_datetime(lm) if lm else None)


def strikes(buf, half):
    """Strike markers -> boolean 0.1-degree grid of marker centres (row 0 = LAT0)."""
    a = np.asarray(Image.open(io.BytesIO(buf)).convert('RGB')).astype(int)
    if a.shape[:2] != (656, 875):
        raise ValueError(f'unexpected image size {a.shape}')
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    yellow = (np.abs(r - g) < 60) & (r > 80) & (b < 140)                      # state borders (and their edges)
    m = ((a.max(2) - a.min(2)) > 80) & ~yellow
    m[:150, :] = False; m[:, 640:] = False                                    # title, legend, colour bar
    m = nd.binary_erosion(m, np.ones((2 * half - 1, 2 * half - 1)))          # markers -> their centres
    ys, xs = np.nonzero(m)
    lon = 80 + (xs - X80) / PX_LON
    lat = 5 + (Y5 - ys) / PX_LAT
    G = np.zeros((NY, NX), bool)
    i = np.floor((lon - LON0) / STEP).astype(int); j = np.floor((lat - LAT0) / STEP).astype(int)
    ok = (i >= 0) & (i < NX) & (j >= 0) & (j < NY)
    G[j[ok], i[ok]] = True
    fp = sorted({(round(LON0 + (int((x - LON0) / FS) + .5) * FS, 3), round(LAT0 + (int((y - LAT0) / FS) + .5) * FS, 3)) for x, y in zip(lon[ok], lat[ok])})
    return G, fp


FS = 0.05                                                              # fine grid for movement
FNX, FNY = int(round((LON1 - LON0) / FS)), int(round((LAT1 - LAT0) / FS))


def fine(pts):
    G = np.zeros((FNY, FNX))
    for lo, la in pts:
        i, j = int((lo - LON0) / FS), int((la - LAT0) / FS)
        if 0 <= i < FNX and 0 <= j < FNY:
            G[j, i] = 1
    return G


def motion(A, B, minutes, BS=24, ST=8, R=6):
    """Block matching of smoothed strike density A (older) -> B (newer) on the 0.05-degree grid, with sub-cell refinement.
    Returns [lon, lat, u_ms, v_ms, n] per block (n = strike cells in the block)."""
    A = nd.gaussian_filter(A, 1.5); B = nd.gaussian_filter(B, 1.5); out = []
    for y0 in range(R, FNY - BS - R, ST):
        for x0 in range(R, FNX - BS - R, ST):
            a = A[y0:y0 + BS, x0:x0 + BS]
            if a.sum() < 4 or B[y0 - R:y0 + BS + R, x0 - R:x0 + BS + R].sum() < 4:
                continue
            sc = np.empty((2 * R + 1, 2 * R + 1))
            for dv in range(-R, R + 1):
                for du in range(-R, R + 1):
                    sc[dv + R, du + R] = ((a - B[y0 + dv:y0 + dv + BS, x0 + du:x0 + du + BS]) ** 2).sum()
            j, i = np.unravel_index(sc.argmin(), sc.shape)
            if i in (0, 2 * R) or j in (0, 2 * R):
                continue                                               # best match at the edge of the search: not trusted
            sub = lambda m, c, p: 0.0 if (m - 2 * c + p) <= 0 else 0.5 * (m - p) / (m - 2 * c + p)
            du = i - R + sub(sc[j, i - 1], sc[j, i], sc[j, i + 1]); dv = j - R + sub(sc[j - 1, i], sc[j, i], sc[j + 1, i])
            lat = LAT0 + (y0 + BS / 2) * FS
            dx = du * FS * 111.32 * np.cos(np.radians(lat)); dy = dv * FS * 110.57
            u, v = dx * 1000 / (minutes * 60), dy * 1000 / (minutes * 60)
            if np.hypot(u, v) * 3.6 <= 60:
                out.append([round(LON0 + (x0 + BS / 2) * FS, 2), round(lat, 2), round(float(u), 2), round(float(v), 2), int((a > 0.05).sum())])
    return out


def clusters(G10, G20, G30, vecs):
    """Groups of strikes (gaps up to ~10 km bridged): position, size, trend and movement."""
    U = G10 | G20 | G30
    lab, n = nd.label(nd.binary_dilation(U, np.ones((3, 3))), np.ones((3, 3)))
    res = []
    for k in range(1, n + 1):
        sel = (lab == k)
        n10, n20, n30 = int((G10 & sel).sum()), int((G20 & sel).sum()), int((G30 & sel).sum())
        if n10 + n20 + n30 < 2:
            continue
        js, is_ = np.nonzero(sel & U)
        lon = float(LON0 + (is_.mean() + .5) * STEP); lat = float(LAT0 + (js.mean() + .5) * STEP)
        c = dict(lon=round(lon, 2), lat=round(lat, 2), n10=n10, n20=n20, n30=n30,
                 w=round(float((is_.max() - is_.min() + 1) * STEP), 1), h=round(float((js.max() - js.min() + 1) * STEP), 1))
        older = (n20 + n30) / 2
        c['trend'] = ('new' if n10 >= 2 and n20 + n30 == 0 else
                      'growing' if n10 >= 3 and n10 >= 1.5 * max(1, older) else
                      'fading' if n10 <= 0.5 * older else 'steady')
        vs = [v for v in vecs if abs(v[0] - lon) <= max(0.6, c['w'] / 2) and abs(v[1] - lat) <= max(0.6, c['h'] / 2)]
        if vs:
            wt = np.array([v[4] for v in vs], float)
            u = float((np.array([v[2] for v in vs]) * wt).sum() / wt.sum()); v_ = float((np.array([v[3] for v in vs]) * wt).sum() / wt.sum())
            c.update(u_ms=round(u, 2), v_ms=round(v_, 2), kmh=round(float(np.hypot(u, v_) * 3.6), 1))
        res.append(c)
    res.sort(key=lambda c: -(c['n10'] * 2 + c['n20'] + c['n30']))
    return res


def main(out):
    os.makedirs(out, exist_ok=True)
    now = dt.datetime.now(UTC)
    status = dict(run_utc=now.isoformat())
    try:
        got = {k: get(v[0]) for k, v in IMGS.items()}
    except Exception as e:
        status['error'] = f'download failed: {e}'; print(json.dumps(status)); return
    t_img = got['b10'][1] or now
    t_end = (t_img - dt.timedelta(minutes=9)).replace(second=0, microsecond=0)   # the map is drawn ~9 min after its time
    try:
        prev = json.load(open(f'{out}/lightning.json'))
        if prev.get('t_img') == t_img.isoformat():
            print('no new lightning map since', t_img); return
    except Exception:
        pass
    try:
        SG = {k: strikes(got[k][0], IMGS[k][1]) for k in IMGS}
    except Exception as e:
        status['error'] = f'decode failed: {e}'; print(json.dumps(status)); return
    G = {k: v[0] for k, v in SG.items()}; FP = {k: v[1] for k, v in SG.items()}
    # movement: strikes of the last 20 min against those of the map 30 min earlier (kept in recent.json); without it,
    # the 20-30 min strikes against the 0-10 min ones (20 min apart)
    recent, rf = [], f'{out}/recent.json'
    try:
        recent = [r for r in json.load(open(rf)) if (t_end - dt.datetime.fromisoformat(r['t_end'])).total_seconds() < 2 * 3600]
    except Exception:
        pass
    cur = FP['b10'] + FP['b20']
    old = min((r for r in recent if 25 <= (t_end - dt.datetime.fromisoformat(r['t_end'])).total_seconds() / 60 <= 40),
              key=lambda r: abs((t_end - dt.datetime.fromisoformat(r['t_end'])).total_seconds() / 60 - 30), default=None)
    if old:
        gap = (t_end - dt.datetime.fromisoformat(old['t_end'])).total_seconds() / 60
        vecs = motion(fine(old['pts']), fine(cur), gap); how = f'{gap:.0f} min (map against the one 30 min earlier)'
    else:
        vecs = motion(fine(FP['b30']), fine(FP['b10']), 20); how = '20 min (20-30 min strikes against 0-10 min strikes)'
    recent.append(dict(t_end=t_end.isoformat(), pts=[list(p) for p in cur]))
    json.dump(recent, open(rf, 'w'), separators=(',', ':'))
    cl = clusters(G['b10'], G['b20'], G['b30'], vecs)
    pts = lambda M: [[round(LON0 + (i + .5) * STEP, 2), round(LAT0 + (j + .5) * STEP, 2)] for j, i in zip(*np.nonzero(M))]
    rec = dict(t_end=t_end.isoformat(), t_img=t_img.isoformat(), source='IMD lightning (INSAT-3DS/3DR, national lightning network)',
               note='Strike positions read from IMD lightning maps to about 0.1 deg; reference only, IMD images are not shown on the site.',
               step=STEP, motion_from=how, s10=pts(G['b10']), s20=pts(G['b20']), s30=pts(G['b30']), vectors=vecs, clusters=cl)
    json.dump(rec, open(f'{out}/lightning.json', 'w'), separators=(',', ':'))
    hist, hf = [], f'{out}/hist.jsonl'                                 # 3 days, for scoring directions against the radars
    if os.path.exists(hf):
        for line in open(hf):
            try:
                if (now - dt.datetime.fromisoformat(json.loads(line)['t_end'])).total_seconds() < 3 * 86400:
                    hist.append(line.strip())
            except Exception:
                pass
    hist.append(json.dumps(dict(t_end=rec['t_end'], vectors=vecs), separators=(',', ':')))
    open(hf, 'w').write('\n'.join(hist) + '\n')
    tn = [c for c in cl if 76 <= c['lon'] <= 81 and 8 <= c['lat'] <= 13.6]
    print(json.dumps(dict(t_end=rec['t_end'], strikes10=len(rec['s10']), clusters=len(cl), vectors=len(vecs), tn=tn[:6])))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'data/lightning')
