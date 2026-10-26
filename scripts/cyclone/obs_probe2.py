"""Probe the two new data accounts from GitHub Actions (no secrets printed): EUMETSAT Data Store (sea winds, satellite
cloud-motion winds) and NASA Earthdata (GPM IMERG rain). python obs_probe2.py -> data/cyclone/obs_probe2.txt"""
import os, json, base64, socket, datetime as dt, urllib.request, urllib.parse, http.cookiejar, netrc
_gai = socket.getaddrinfo
socket.getaddrinfo = lambda h, *a, **k: [x for x in _gai(h, *a, **k) if x[0] == socket.AF_INET] or _gai(h, *a, **k)   # GitHub runners have no IPv6
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
        allc = []
        for c in items:
            cid = urllib.parse.unquote((c.get('href') or c.get('id') or '').split('/collections/')[-1].split('?')[0]); allc.append(cid)
            t = (c.get('title') or '') + ' ' + cid
            if any(w in t.lower() for w in ('wind', 'ascat', 'amv', 'scatter', 'iodc', 'motion', 'mpef', 'bufr')): log('  ', t[:200])
        open('data/cyclone/eumetsat_collections.txt', 'w').write('\n'.join(allc) + '\n')
        for cid in ([] if os.environ.get('PROBE_FAST', '1') == '1' else allc):                    # titles: look for motion winds
            try:
                st, b, _ = get('https://api.eumetsat.int/data/browse/1.0.0/collections/' + urllib.parse.quote(cid) + '?format=json', H, timeout=20)
                j = json.loads(b); t = (j.get('title') or j.get('properties', {}).get('title') or '')
                if any(w in t.lower() for w in ('wind', 'motion', 'amv')): log('  title:', cid, '|', t[:150])
            except Exception: pass
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
# ---------------------------------------------------------------- NOAA GTS gateway (synop/ship/temp): why empty?
for url in ('https://tgftp.nws.noaa.gov/SL.us008001/DF.an/DC.sflnd/DS.synop/', 'https://tgftp.nws.noaa.gov/SL.us008001/DF.an/DC.sflnd/DS.synop/sn.0000',
            'https://tgftp.nws.noaa.gov/SL.us008001/DF.an/', 'https://tgftp.nws.noaa.gov/data/nsd_bbsss.txt'):
    try:
        st, b, u = get(url, timeout=60)
        if url.endswith('DS.synop/'):
            import re as _re; t = b.decode('latin-1', 'replace'); hs = _re.findall(r'href="([^"]+)"', t); log('GTS hrefs', len(hs), hs[:8], hs[-5:])
            i = t.find(hs[6]) if len(hs) > 6 else 0; log('GTS row sample:', t[max(0, i - 80):i + 220].replace('\n', ' | '))
        log('GTS', url[-40:], 'status', st, 'bytes', len(b), 'final', u[-50:], '|', b[:160].decode('latin-1', 'replace').replace('\n', ' '))
    except Exception as e: log('GTS', url[-40:], 'failed', repr(e)[:200])
open('data/cyclone/obs_probe2.txt', 'w').write('\n'.join(OUT) + '\n')
# ---------------------------------------------------------------- MOSDAC (ISRO): login from GitHub + dataset search
mu, mp = os.environ.get('MOSDAC_USER', ''), os.environ.get('MOSDAC_PASSWORD', '')
log('MOSDAC user present:', bool(mu), 'password present:', bool(mp))
try:
    import zipfile as _zf, io as _io, re as _re
    st, b, _ = get('https://www.mosdac.gov.in/software/mdapi.zip', timeout=60)
    z = _zf.ZipFile(_io.BytesIO(b)); src = z.read([n for n in z.namelist() if n.endswith('mdapi.py')][0]).decode('utf-8', 'replace')
    urls = sorted(set(_re.findall(r'https?://[^\s\'"]+', src))); log('mdapi urls:', urls[:12])
    open('data/cyclone/mosdac_mdapi_src.txt', 'w').write(src[:20000])
    tok_url = next((u for u in urls if 'token' in u.lower()), None)
    if mu and mp and tok_url:
        st, b, _ = get(tok_url, {'Content-Type': 'application/json'}, json.dumps({'username': mu, 'password': mp}).encode(), timeout=60)
        j = json.loads(b); log('MOSDAC token: OK' if any(k in j for k in ('access_token', 'token')) else 'MOSDAC token reply keys: ' + str(list(j)[:6]))
except Exception as e: log('MOSDAC failed:', repr(e)[:300])
open('data/cyclone/obs_probe2.txt', 'w').write('\n'.join(OUT) + '\n')
