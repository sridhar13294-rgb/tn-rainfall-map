"""Probe the two new data accounts from GitHub Actions (no secrets printed): EUMETSAT Data Store (sea winds, satellite
cloud-motion winds) and NASA Earthdata (GPM IMERG rain). python obs_probe2.py -> data/cyclone/obs_probe2.txt"""
import os, json, base64, datetime as dt, urllib.request, urllib.parse, http.cookiejar, netrc
OUT = []; log = lambda *a: (OUT.append(' '.join(str(x) for x in a)), print(*a, flush=True))
def get(url, headers=None, data=None, opener=None, timeout=60):
    req = urllib.request.Request(url, data=data, headers=dict({'User-Agent': 'megam-obs/1.0'}, **(headers or {})))
    with (opener or urllib.request.build_opener()).open(req, timeout=timeout) as r: return r.status, r.read(), r.geturl()
# ---------------------------------------------------------------- EUMETSAT
k, s = os.environ.get('EUMETSAT_KEY', ''), os.environ.get('EUMETSAT_SECRET', '')
log('EUMETSAT key present:', bool(k), 'secret present:', bool(s))
if k and s:
    try:
        st, b, _ = get('https://api.eumetsat.int/token', {'Authorization': 'Basic ' + base64.b64encode(f'{k}:{s}'.encode()).decode(), 'Content-Type': 'application/x-www-form-urlencoded'}, b'grant_type=client_credentials')
        tok = json.loads(b)['access_token']; log('EUMETSAT token: OK')
        H = {'Authorization': 'Bearer ' + tok}
        st, b, _ = get('https://api.eumetsat.int/data/browse/collections?format=json', H)
        cols = json.loads(b); items = cols.get('links') or cols.get('collections') or []
        log('collections listed:', len(items))
        for c in items:
            t = (c.get('title') or '') + ' ' + (c.get('href') or c.get('id') or '')
            if any(w in t.lower() for w in ('wind', 'ascat', 'amv', 'scatter', 'iodc', 'atmospheric motion')): log('  ', t[:200])
        now = dt.datetime.utcnow(); t0 = (now - dt.timedelta(hours=9)).strftime('%Y-%m-%dT%H:%M:%SZ'); t1 = now.strftime('%Y-%m-%dT%H:%M:%SZ')
        for cid in ('EO:EUM:DAT:METOP:OSI-104', 'EO:EUM:DAT:METOP:ASCSZR1B', 'EO:EUM:DAT:MSG:AMV-IODC', 'EO:EUM:DAT:MSG:AMV', 'EO:EUM:DAT:0398'):
            try:
                q = urllib.parse.urlencode({'format': 'json', 'pi': cid, 'dtstart': t0, 'dtend': t1, 'c': 5})
                st, b, _ = get('https://api.eumetsat.int/data/search-products/1.0.0/os?' + q, H)
                j = json.loads(b); n = j.get('totalResults', len(j.get('features', [])))
                log('search', cid, 'last 9 h products:', n, [f.get('id', '')[:80] for f in j.get('features', [])[:2]])
            except Exception as e: log('search', cid, 'failed', repr(e)[:150])
    except Exception as e: log('EUMETSAT failed:', repr(e)[:300])
# ---------------------------------------------------------------- NASA Earthdata (GES DISC IMERG)
u, p = os.environ.get('EARTHDATA_USER', ''), os.environ.get('EARTHDATA_PASSWORD', '')
log('Earthdata user present:', bool(u), 'password present:', bool(p))
if u and p:
    try:
        with open(os.path.expanduser('~/.netrc'), 'w') as f: f.write(f'machine urs.earthdata.nasa.gov login {u} password {p}\n')
        os.chmod(os.path.expanduser('~/.netrc'), 0o600)
        pm = urllib.request.HTTPPasswordMgrWithDefaultRealm(); pm.add_password(None, 'https://urs.earthdata.nasa.gov', u, p)
        op = urllib.request.build_opener(urllib.request.HTTPBasicAuthHandler(pm), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        day = dt.datetime.utcnow() - dt.timedelta(hours=8)
        base = f'https://gpm1.gesdisc.eosdis.nasa.gov/data/GPM_L3/GPM_3IMERGHHE.07/{day:%Y}/{day.timetuple().tm_yday:03d}/'
        st, b, _ = get(base, opener=op); names = sorted(set(x.split('"')[0] for x in b.decode(errors='ignore').split('href="')[1:] if x.split('"')[0].endswith('.HDF5')))
        log('IMERG Early half-hourly files today:', len(names), names[-1][:90] if names else '')
        if names:
            st, b, url = get(base + names[-1], opener=op, timeout=120); log('IMERG download:', st, len(b) // 1024, 'KB', 'HDF5' if b[:4] == b'\x89HDF' else 'NOT HDF5 (login/authorisation problem?)')
        st, b, _ = get('https://cmr.earthdata.nasa.gov/search/collections.json?keyword=ASCAT%20wind&page_size=5')
        log('PO.DAAC ASCAT collections (search):', [e.get('short_name') for e in json.loads(b)['feed']['entry']])
    except Exception as e: log('Earthdata failed:', repr(e)[:300])
open('data/cyclone/obs_probe2.txt', 'w').write('\n'.join(OUT) + '\n')
