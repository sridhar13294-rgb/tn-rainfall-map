"""Latest GFS, GEFS, ECMWF HRES and ECMWF ENS forecasts over the Bay of Bengal for cyclone tracking and our track model.
Fields: sea-level pressure, 10 m wind, and wind at 850/700/500/300/250/200 hPa where the source has them.
Region 0-30N 70-105E on a 0.5 deg grid; 6-hourly to 240 h then 12-hourly to 360 h (ensembles 12-hourly throughout).
Writes /tmp/cyc_out/fc_<SOURCE>_<RUN>.npz (uploaded to the era5-cases release) and data/cyclone/fetch_status.json."""
import json, os, sys, time, datetime as dt, urllib.request, urllib.error, concurrent.futures as cf, threading, random
import numpy as np, pygrib
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, 'data', 'cyclone'); os.makedirs(OUT, exist_ok=True); TMP = '/tmp/cyc_out'; os.makedirs(TMP, exist_ok=True)
LA0, LA1, LO0, LO1, RES = 0.0, 30.0, 70.0, 105.0, 0.5
LATS = np.arange(LA0, LA1 + 1e-6, RES); LONS = np.arange(LO0, LO1 + 1e-6, RES)
LEVS = [850, 700, 500, 300, 250, 200]
VARS = ['msl', 'u10', 'v10'] + [f'{c}{p}' for p in LEVS for c in 'uv']
LOG = {}; LK = threading.Lock()
def log(src, *a):
    m = ' '.join(str(x) for x in a); print(src, m, flush=True)
    with LK:
        LOG.setdefault(src, []).append(m[:500]); json.dump(LOG, open(os.path.join(OUT, 'fetch_status.json'), 'w'), indent=1)
def http(url, rng=None, tries=5, method='GET'):
    for i in range(tries):
        h = {'User-Agent': 'tn-rainfall-map cyclone study'}
        if rng: h['Range'] = f'bytes={rng[0]}-' + ('' if rng[1] is None else str(rng[1]))
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h, method=method), timeout=90) as r:
                return r.read() if method == 'GET' else b''
        except urllib.error.HTTPError as e:
            if e.code in (403, 404): return None
            time.sleep(2 * (i + 1) + random.random())
        except Exception:
            time.sleep(2 * (i + 1) + random.random())
    return None
def subset(buf):
    """GRIB message bytes -> field on our 0.5 deg grid (nearest point, any regular lat-lon source grid)."""
    m = pygrib.fromstring(buf); v = m.values; v = np.where(np.ma.getmaskarray(v), np.nan, np.ma.getdata(v)).astype(np.float32)
    la0 = m['latitudeOfFirstGridPointInDegrees']; lo0 = m['longitudeOfFirstGridPointInDegrees']
    dla = m['jDirectionIncrementInDegrees'] * (1 if m['jScansPositively'] else -1); dlo = m['iDirectionIncrementInDegrees']
    ii = np.round((LATS - la0) / dla).astype(int); jj = np.round(((LONS - lo0) % 360) / dlo).astype(int)
    return v[np.ix_(ii, jj)]
def steps_for(kind, last=360):
    if kind == 'ens': return list(range(0, last + 1, 12))
    return list(range(0, 241, 6)) + list(range(252, last + 1, 12))
# ------------------------------------------------------------------ NOAA (GFS 0.25, GEFS 0.5)
GFS = 'https://noaa-gfs-bdp-pds.s3.amazonaws.com'; GEFS = 'https://noaa-gefs-pds.s3.amazonaws.com'
def gfs_url(run, step): return f"{GFS}/gfs.{run:%Y%m%d}/{run:%H}/atmos/gfs.t{run:%H}z.pgrb2.0p25.f{step:03d}"
def gefs_url(run, mem, step):
    name = 'gec00' if mem == 0 else f'gep{mem:02d}'
    return f"{GEFS}/gefs.{run:%Y%m%d}/{run:%H}/atmos/pgrb2ap5/{name}.t{run:%H}z.pgrb2a.0p50.f{step:03d}"
def parse_idx(txt):
    L = [l.split(':') for l in txt.strip().splitlines()]; out = []
    for i, p in enumerate(L):
        start = int(p[1]); end = int(L[i + 1][1]) - 1 if i + 1 < len(L) else None
        out.append(dict(var=p[3], level=p[4], start=start, end=end))
    return out
def noaa_key(r):
    if r['var'] == 'PRMSL' and r['level'] == 'mean sea level': return 'msl'
    if r['var'] in ('UGRD', 'VGRD'):
        c = 'u' if r['var'] == 'UGRD' else 'v'
        if r['level'] == '10 m above ground': return c + '10'
        if r['level'].endswith(' mb'):
            p = int(r['level'].split()[0])
            if p in LEVS: return f'{c}{p}'
    return None
def latest_run(test, cycles=(0, 6, 12, 18)):
    now = dt.datetime.utcnow()
    for h in range(0, 48):
        run = (now - dt.timedelta(hours=h)).replace(minute=0, second=0, microsecond=0)
        if run.hour in cycles and test(run): return run
    return None
ENS_VARS = {'msl', 'u850', 'v850', 'u700', 'v700', 'u500', 'v500', 'u200', 'v200'}     # ensembles: lighter set
def fetch_noaa(src, members, url_fn, kind, par=24):
    run = latest_run(lambda r: http(url_fn(r, members[-1], 360) + '.idx', method='HEAD') is not None)
    if run is None: log(src, 'no complete run'); return
    steps = steps_for(kind); log(src, 'run', run, 'members', len(members), 'steps', len(steps))
    A = np.full((len(members), len(steps), len(VARS), len(LATS), len(LONS)), np.nan, np.float32)
    def job(mi, si):
        mem, st = members[mi], steps[si]; txt = http(url_fn(run, mem, st) + '.idx')
        if not txt: return 0
        n = 0
        for r in parse_idx(txt.decode()):
            k = noaa_key(r)
            if k is None or (kind == 'ens' and k not in ENS_VARS): continue
            b = http(url_fn(run, mem, st), (r['start'], r['end']))
            if b:
                try: A[mi, si, VARS.index(k)] = subset(b); n += 1
                except Exception as e: log(src, 'decode', mem, st, k, repr(e)[:100])
        return n
    t0 = time.time()
    with cf.ThreadPoolExecutor(par) as ex:
        tot = sum(ex.map(lambda a: job(*a), [(mi, si) for mi in range(len(members)) for si in range(len(steps))]))
    if 'msl' in VARS: A[:, :, VARS.index('msl')] /= 100.0
    save(src, run, members, steps, A, tot, t0)
# ------------------------------------------------------------------ ECMWF open data (HRES oper, ENS enfo)
EC = ['https://ecmwf-forecasts.s3.eu-central-1.amazonaws.com', 'https://data.ecmwf.int/forecasts']
def ec_url(base, run, step, kind):
    if kind == 'ens': return f"{base}/{run:%Y%m%d}/{run:%H}z/ifs/0p25/enfo/{run:%Y%m%d%H}0000-{step}h-enfo-ef"
    return f"{base}/{run:%Y%m%d}/{run:%H}z/ifs/0p25/oper/{run:%Y%m%d%H}0000-{step}h-oper-fc"
def ec_key(r):
    p = r.get('param'); lt = r.get('levtype')
    if lt == 'sfc':
        return {'msl': 'msl', '10u': 'u10', '10v': 'v10'}.get(p)
    if lt == 'pl' and p in ('u', 'v') and int(r.get('levelist', 0)) in LEVS: return f"{p}{int(r['levelist'])}"
    return None
def fetch_ec(src, kind, par=24):
    base = EC[0]
    run = latest_run(lambda r: http(ec_url(base, r, 360 if kind == 'ens' else 240, kind) + '.index', method='HEAD') is not None, cycles=(0, 12))
    if run is None: log(src, 'no complete run'); return
    members = list(range(51)) if kind == 'ens' else [0]
    steps = steps_for(kind); log(src, 'run', run, 'steps', len(steps))
    A = np.full((len(members), len(steps), len(VARS), len(LATS), len(LONS)), np.nan, np.float32)
    tasks = []
    def idx(si):
        st = steps[si]; txt = http(ec_url(base, run, st, kind) + '.index')
        if not txt: return []
        out = []
        for l in txt.decode().splitlines():
            if not l.strip(): continue
            r = json.loads(l); k = ec_key(r)
            if k is None or (kind == 'ens' and k not in ENS_VARS): continue
            mem = int(r.get('number', 0)) if r.get('type') == 'pf' else 0
            if kind == 'oper' and r.get('type') not in (None, 'fc'): continue
            out.append((si, mem, k, r['_offset'], r['_offset'] + r['_length'] - 1))
        return out
    with cf.ThreadPoolExecutor(16) as ex:
        for o in ex.map(idx, range(len(steps))): tasks += o
    log(src, 'fields to fetch', len(tasks))
    def job(t):
        si, mem, k, a, b = t
        for k2 in range(3):
            buf = http(ec_url(EC[(mem + si + k2) % len(EC)], run, steps[si], kind) + '.grib2', (a, b))
            if buf:
                try: A[members.index(mem), si, VARS.index(k)] = subset(buf); return 1
                except Exception as e: log(src, 'decode', mem, steps[si], k, repr(e)[:100]); return 0
        return 0
    t0 = time.time()
    with cf.ThreadPoolExecutor(par) as ex: tot = sum(ex.map(job, tasks))
    A[:, :, VARS.index('msl')] /= 100.0
    save(src, run, members, steps, A, tot, t0)
def save(src, run, members, steps, A, tot, t0):
    have = {v: float(np.isfinite(A[:, :, i]).mean()) for i, v in enumerate(VARS)}
    log(src, 'fields ok', tot, 'in', int(time.time() - t0), 's; coverage', {k: round(x, 2) for k, x in have.items()})
    keep = [i for i, v in enumerate(VARS) if have[v] > 0.05]
    fn = os.path.join(TMP, f'fc_{src}_{run:%Y%m%d%H}.npz')
    np.savez_compressed(fn, data=A[:, :, keep].astype(np.float16), vars=np.array([VARS[i] for i in keep]), lats=LATS, lons=LONS,
                        steps=np.array(steps), members=np.array(members), run=run.strftime('%Y%m%d%H'))
    log(src, 'saved', fn, os.path.getsize(fn) // 1000, 'kB')
if __name__ == '__main__':
    which = sys.argv[1:] or ['GFS', 'HRES', 'GEFS', 'ENS']
    jobs = {'GFS': lambda: fetch_noaa('GFS', [0], lambda r, m, s: gfs_url(r, s), 'det'),
            'GEFS': lambda: fetch_noaa('GEFS', list(range(31)), gefs_url, 'ens'),
            'HRES': lambda: fetch_ec('HRES', 'oper'), 'ENS': lambda: fetch_ec('ENS', 'ens', par=32)}
    with cf.ThreadPoolExecutor(len(which)) as ex:
        for w, f in [(w, ex.submit(jobs[w])) for w in which]:
            try: f.result()
            except Exception as e:
                import traceback; log(w, 'FAILED', repr(e)[:300], traceback.format_exc()[-600:])
