"""sat-radar branch test: satellite rain over Tamil Nadu added up over one TN SMART day, from
(a) EUMETSAT H SAF H63 rain rate (EUMETView WMS, 15 min, colour-coded PNG decoded with the legend) and
(b) NOAA Enterprise Rain Rate global blend (AWS open data, 10 min, netCDF; sampled every 30 min).
Grids: 75.5-81.5E, 7-14.5N at 0.05 deg (120 x 150), rain in mm."""
import datetime as dt, io, json, os, re, sys, time, urllib.request, urllib.parse, xml.etree.ElementTree as ET
import concurrent.futures as cf
import numpy as np
from PIL import Image
UA = {'User-Agent': 'tn-rainfall-map satellite test (non-commercial)'}
OUT = 'data/satradar'; os.makedirs(OUT, exist_ok=True)
LON0, LON1, LAT0, LAT1, STEP = 75.5, 81.5, 7.0, 14.5, 0.05
NX, NY = int(round((LON1 - LON0) / STEP)), int(round((LAT1 - LAT0) / STEP))
def get(url, timeout=120, tries=4):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception as e:
            last = e; time.sleep(3 * (k + 1))
    raise last
# legend of H SAF H60B/H63 on EUMETView: (mm/h, colour) stops
STOPS = [(0.0, (255, 255, 204)), (0.2, (227, 244, 192)), (1.05, (198, 232, 179)), (2.0, (162, 218, 183)), (3.0, (126, 204, 186)),
         (5.0, (96, 194, 191)), (7.0, (65, 183, 196)), (10.0, (47, 164, 194)), (15.0, (29, 145, 191)), (20.0, (32, 120, 180)),
         (30.0, (34, 94, 168)), (49.2, (12, 44, 133)), (60.0, (8, 30, 100))]
def decode(rgba):
    """colour image -> mm/h (nearest point on the legend's colour ramp; transparent = 0)."""
    a = rgba[..., 3] > 0; rgb = rgba[..., :3].astype(float)
    best = np.full(a.shape, 1e9); val = np.zeros(a.shape)
    for (v0, c0), (v1, c1) in zip(STOPS, STOPS[1:]):
        c0, c1 = np.array(c0, float), np.array(c1, float); d = c1 - c0
        t = np.clip(((rgb - c0) @ d) / max(d @ d, 1e-9), 0, 1)
        dist = np.linalg.norm(rgb - (c0 + t[..., None] * d), axis=-1)
        m = dist < best; best[m] = dist[m]; val[m] = (v0 + t * (v1 - v0))[m]
    val[~a] = 0; val[a & (best > 60)] = 0     # anything far from the ramp (borders/text) is not rain
    return val
def h63(t):
    bbox = f'{LAT0},{LON0},{LAT1},{LON1}'
    q = (f'https://view.eumetsat.int/geoserver/ows?service=WMS&version=1.3.0&request=GetMap&layers=msg_iodc:h63&styles=&crs=EPSG:4326'
         f'&bbox={bbox}&width={NX*2}&height={NY*2}&format=image/png&transparent=true&time={t:%Y-%m-%dT%H:%M:00Z}')
    im = np.asarray(Image.open(io.BytesIO(get(q))).convert('RGBA'))
    r = decode(im)[::-1]                         # row 0 = south
    return r.reshape(NY, 2, NX, 2).mean(axis=(1, 3))
# ---- NOAA blend
NS = '{http://s3.amazonaws.com/doc/2006-03-01/}'
B = 'https://noaa-enterprise-rainrate-pds.s3.amazonaws.com'
def blend_keys(hour):
    p = f'BLEND/RainRate-Blend-INST/{hour:%Y/%m/%d/%H}/'
    x = ET.fromstring(get(f'{B}/?list-type=2&prefix={p}'))
    return sorted(c.find(NS + 'Key').text for c in x.findall(NS + 'Contents'))
_idx = {}
def blend(key, info):
    import netCDF4
    ds = netCDF4.Dataset('x.nc', memory=get(f'{B}/{key}', 300))
    if not info:
        info['vars'] = {k: (v.dimensions, v.shape, getattr(v, 'units', ''), getattr(v, 'long_name', '')) for k, v in ds.variables.items()}
        info['attrs'] = {k: str(getattr(ds, k))[:200] for k in ds.ncattrs()}
    var = next((k for k in ds.variables if k.upper() in ('RRQPE', 'RRQPE_BLEND', 'RAINRATE', 'RR')), None) or \
          next(k for k, v in ds.variables.items() if v.ndim == 2 and v.shape[0] > 500)
    v = ds.variables[var]
    lat = next((ds.variables[k][:] for k in ('lat', 'latitude', 'Latitude') if k in ds.variables), None)
    lon = next((ds.variables[k][:] for k in ('lon', 'longitude', 'Longitude') if k in ds.variables), None)
    if lat is None or lon is None:            # regular global grid described only by attributes
        A = {k: getattr(ds, k) for k in ds.ncattrs()}
        info['geo_attrs'] = {k: str(v) for k, v in A.items() if 'geospatial' in k or 'resolution' in k}
        ny, nx = v.shape
        la_max = float(A.get('geospatial_lat_max', 65)); la_min = float(A.get('geospatial_lat_min', -65))
        lo_min = float(A.get('geospatial_lon_min', -180)); lo_max = float(A.get('geospatial_lon_max', 180))
        dla = (la_max - la_min) / (ny - 1); dlo = (lo_max - lo_min) / nx
        lat = la_max - dla * np.arange(ny); lon = lo_min + dlo * (np.arange(nx) + .5)
    if 'sel' not in _idx:
        la = np.asarray(lat); lo = np.asarray(lon) % 360
        tl = LAT0 + STEP * (np.arange(NY) + .5); tn = LON0 + STEP * (np.arange(NX) + .5)
        _idx['sel'] = (np.abs(la[:, None] - tl[None]).argmin(0), np.abs(lo[:, None] - tn[None]).argmin(0))
        info['var'] = var; info['lat_range'] = [float(la.min()), float(la.max())]; info['lon_range'] = [float(lo.min()), float(lo.max())]
    j, i = _idx['sel']
    a = np.asarray(v[j.min():j.max() + 1, i.min():i.max() + 1], float)[np.ix_(j - j.min(), i - i.min())] if j[0] <= j[-1] else \
        np.asarray(v[j.max():j.min() + 1, i.min():i.max() + 1], float)[np.ix_(j - j.max(), i - i.min())]
    a[~np.isfinite(a)] = np.nan
    ds.close()
    return a
def main():
    day = dt.date.fromisoformat(sys.argv[1] if len(sys.argv) > 1 else '2026-10-15')
    t0 = dt.datetime(day.year, day.month, day.day, 3, tzinfo=dt.timezone.utc) - dt.timedelta(days=1)
    out = dict(day=day.isoformat(), window=[t0.isoformat(), (t0 + dt.timedelta(days=1)).isoformat()],
               grid=dict(lon0=LON0, lat0=LAT0, step=STEP, nx=NX, ny=NY))
    # H63: 96 frames of 15 min
    times = [t0 + dt.timedelta(minutes=15 * k) for k in range(96)]
    acc = np.zeros((NY, NX)); ok = 0; mx = np.zeros((NY, NX))
    with cf.ThreadPoolExecutor(6) as ex:
        for t, r in zip(times, ex.map(lambda t: (lambda: h63(t))() if True else None, times)):
            acc += r * 0.25; mx = np.maximum(mx, r); ok += 1
    out['h63'] = dict(frames=ok, acc=np.round(acc, 1).tolist(), max_rate=np.round(mx, 1).tolist())
    print('h63 frames', ok, 'TN-box mean', acc.mean(), 'max', acc.max(), flush=True)
    # NOAA blend: every 30 min (rate x 0.5 h)
    info = {}; bacc = np.zeros((NY, NX)); n = 0; miss = 0
    for k in range(48):
        t = t0 + dt.timedelta(minutes=30 * k)
        try:
            keys = [x for x in blend_keys(t) if f's{t:%Y%m%d%H%M}' in x]
            if not keys:
                miss += 1; continue
            a = blend(keys[0], info)
            bacc += np.nan_to_num(a) * 0.5; n += 1
        except Exception as e:
            miss += 1; info.setdefault('errors', []).append(f'{t}: {e}'[:200])
    out['blend'] = dict(frames=n, missing=miss, info={k: (v if k != 'vars' else {a: str(b) for a, b in v.items()}) for k, v in info.items()},
                        acc=np.round(bacc, 1).tolist())
    print('errors', info.get('errors', [])[:5]); print('blend frames', n, 'missing', miss, 'mean', bacc.mean(), 'max', bacc.max(), json.dumps(info, default=str)[:1500], flush=True)
    json.dump(out, open(f'{OUT}/acc_{day}.json', 'w'), separators=(',', ':'))
if __name__ == '__main__':
    main()
