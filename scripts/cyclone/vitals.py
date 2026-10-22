"""Latest North Indian Ocean storm vitals (position, strength, size) from open, machine-readable sources, for the storm
insertion of the moist model. Called from ours_fetch_m.py (RUN word "oursm"): save(run) -> data/cyclone/vitals_<run>.json.
Sources, all tried every time (an empty list means none of them had an active Arabian Sea / Bay of Bengal system):
 1. 'NCEP tcvitals' - the tcvitals of the GFS cycle (every agency's storms; JTWC's Indian Ocean ones have ids like 03B / 91A):
      https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.YYYYMMDD/HH/atmos/gfs.tHHz.syndata.tcvitals.tm00   (AWS copy of NCEP's
      directory, the GFS source the fetch already uses), then the same path on nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod
      and ftp.ncep.noaa.gov/data/nccf/com/gfs/prod (gdas.tHHz... as a last try). Empty file = no storm anywhere.
 2. 'JTWC b-deck' - JTWC's working best track (ATCF b-deck, basin IO) from NCAR/RAL's open mirror, re-synced a few times a day:
      https://hurricanes.ral.ucar.edu/repository/data/bdecks_open/YYYY/bioNNYYYY.dat
 3. IMD RSMC New Delhi: bulletins and TCAC advisories are PDF files with hashed names (rsmcnewdelhi.imd.gov.in/uploads/archive/..):
    not machine-readable, not used.
 NHC's https://ftp.nhc.noaa.gov/atcf/com/tcvitals holds only Atlantic / east and central Pacific storms (not used).
Each record: source, id, name, time (UTC ISO), lat, lon (deg E), vmax_kt (1-min), pmin_hPa, rmw_km, r34_km [NE, SE, SW, NW] or None,
roci_km (radius of the outermost closed isobar), penv_hPa, motion_deg, motion_kt, depth, basin ('A' Arabian Sea / 'B' Bay of
Bengal), age_h (run time minus record time). Missing values are null.
pick(path_or_list, t0) -> dict(lat, lon, vmax_kt[, rmw_km, R_out]) for mm2.Model.init(storm=...), or None.
python vitals.py [YYYYMMDDHH]"""
import os, re, sys, json, math, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ROOT = os.path.dirname(os.path.dirname(HERE)); OUTD = os.path.join(ROOT, 'data', 'cyclone')
KT = 1.943844; NM = 1.852
TCV = ['https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{d}/{h}/atmos/{m}.t{h}z.syndata.tcvitals.tm00',
       'https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/gfs.{d}/{h}/atmos/{m}.t{h}z.syndata.tcvitals.tm00',
       'https://ftp.ncep.noaa.gov/data/nccf/com/gfs/prod/gfs.{d}/{h}/atmos/{m}.t{h}z.syndata.tcvitals.tm00']
RAL = 'https://hurricanes.ral.ucar.edu/repository/data/bdecks_open/{y}/'

def _log(*a):
    try:
        import centres_m; centres_m.log('VITALS', *a)                                       # data/cyclone/fetch_status.json
    except Exception: print('VITALS', *a, flush=True)

def _http(url):
    try:
        import cyc_fetch as C; return C.http(url, tries=3)
    except ImportError:
        import urllib.request
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'tn-rainfall-map cyclone study'}), timeout=60) as r: return r.read()
        except Exception: return None

def _num(x, scale=1.0, bad=(-9, -99, -999, -9999)):
    try: v = float(x)
    except (TypeError, ValueError): return None
    return None if v in bad or v < 0 else round(v * scale, 2)

def in_nio(lat, lon): return 0 <= lat <= 32 and 40 <= lon <= 101

# ------------------------------------------------------------------ parsers (no network)
TCV_RE = re.compile(r'^(\S{1,4})\s+(\d\d[A-Z])\s+(.*?)\s+(\d{8})\s+(\d{4})\s+(\d{2,3})([NS])\s+(\d{3,4})([EW])\s+(.*)$')
def parse_tcvitals(txt, src='NCEP tcvitals'):
    """tcvitals records (EMC format: lat/lon tenths, motion dm/s, pressures hPa, radii km, vmax m/s) -> list of dicts."""
    out = []
    for line in txt.splitlines():
        m = TCV_RE.match(line.strip())
        if not m: continue
        cen, sid, name, d, hm, la, ns, lo, ew, rest = m.groups(); t = rest.split()
        lat = int(la) / 10.0 * (1 if ns == 'N' else -1); lon = (int(lo) / 10.0 * (1 if ew == 'E' else -1)) % 360
        g = lambda i, s=1.0: _num(t[i], s) if len(t) > i else None
        r34 = [g(i) for i in (7, 8, 9, 10)]
        out.append(dict(source=src, agency=cen, id=sid, name=name.strip() or None, time=dt.datetime.strptime(d + hm, '%Y%m%d%H%M').isoformat(),
                        lat=round(lat, 2), lon=round(lon, 2), motion_deg=g(0), motion_kt=g(1, 0.1 * KT), pmin_hPa=g(2), penv_hPa=g(3), roci_km=g(4),
                        vmax_kt=g(5, KT), rmw_km=g(6), r34_km=r34 if any(x is not None for x in r34) else None,
                        depth=(t[11] if len(t) > 11 and t[11] in 'SMDX' else None), basin=sid[-1]))
    return out

def parse_bdeck(txt, src='JTWC b-deck'):
    """ATCF b-deck (kt, hPa, nautical miles) -> the latest record of the storm as a dict (radii in km), or None."""
    rows = [[x.strip() for x in l.split(',')] for l in txt.splitlines() if l.count(',') >= 8]
    rows = [r for r in rows if re.match(r'^\d{10}$', r[2]) and re.match(r'^\d+[NS]$', r[6]) and re.match(r'^\d+[EW]$', r[7])]
    if not rows: return None
    tl = max(r[2] for r in rows); cur = [r for r in rows if r[2] == tl]; r = cur[0]
    lat = int(r[6][:-1]) / 10.0 * (1 if r[6][-1] == 'N' else -1); lon = (int(r[7][:-1]) / 10.0 * (1 if r[7][-1] == 'E' else -1)) % 360
    f = lambda row, i, s=1.0: _num(row[i], s) if len(row) > i and row[i] != '' else None
    z = lambda row, i, s=1.0: _num(row[i], s, bad=(0, -9, -99, -999, -9999)) if len(row) > i and row[i] != '' else None   # 0 = not given
    r34 = None
    for x in cur:
        if len(x) > 16 and x[11] == '34':
            q = [f(x, i, NM) for i in (13, 14, 15, 16)]
            r34 = [q[0]] * 4 if x[12] == 'AAA' else q
    sub = r[22] if len(r) > 22 and r[22] in ('A', 'B') else ('A' if lon < 78 else 'B')
    prev = sorted({x[2] for x in rows if x[2] < tl})
    mkt = z(r, 26); mdeg = f(r, 25) if mkt else None                                          # 0/0 = not filled in
    if mkt is None and prev:                                                 # motion from the previous fix
        p = next(x for x in rows if x[2] == prev[-1]); la0 = int(p[6][:-1]) / 10.0 * (1 if p[6][-1] == 'N' else -1)
        lo0 = (int(p[7][:-1]) / 10.0 * (1 if p[7][-1] == 'E' else -1)) % 360
        hrs = (dt.datetime.strptime(tl, '%Y%m%d%H') - dt.datetime.strptime(prev[-1], '%Y%m%d%H')).total_seconds() / 3600
        if 0 < hrs <= 12:
            dy = (lat - la0) * 60; dx = ((lon - lo0 + 180) % 360 - 180) * 60 * math.cos(math.radians(lat))
            mdeg = round(math.degrees(math.atan2(dx, dy)) % 360, 0); mkt = round(math.hypot(dx, dy) / hrs, 1)
    name = r[27] if len(r) > 27 and r[27] else None
    return dict(source=src, agency='JTWC', id=f'{int(r[1]):02d}{sub}', name=name, time=dt.datetime.strptime(tl, '%Y%m%d%H').isoformat(),
                lat=round(lat, 2), lon=round(lon, 2), vmax_kt=f(r, 8), pmin_hPa=z(r, 9), rmw_km=z(r, 19, NM), r34_km=r34,
                roci_km=z(r, 18, NM), penv_hPa=z(r, 17), motion_deg=mdeg, motion_kt=mkt, depth=(r[28] if len(r) > 28 and r[28] else None),
                basin=sub, intensity_class=r[10] or None)

# ------------------------------------------------------------------ fetch
def from_tcvitals(run):
    for m in ('gfs', 'gdas'):
        for u in TCV:
            url = u.format(d=f'{run:%Y%m%d}', h=f'{run:%H}', m=m); b = _http(url)
            if b is None: continue
            recs = parse_tcvitals(b.decode('utf-8', 'replace')); nio = [r for r in recs if r['basin'] in ('A', 'B') or in_nio(r['lat'], r['lon'])]
            _log('tcvitals', url, 'records', len(recs), 'North Indian Ocean', len(nio)); return nio, url
    _log('tcvitals: none of the URLs answered for', f'{run:%Y%m%d%H}'); return [], None

def from_bdeck(run, max_age_h=72):
    out = []; years = sorted({run.year, (run - dt.timedelta(days=20)).year})
    for y in years:
        url = RAL.format(y=y); b = _http(url)
        if b is None: _log('b-deck folder not reachable', url); continue
        names = sorted(set(re.findall(rf'href="(bio\d\d{y}\.dat)"', b.decode('utf-8', 'replace'))))
        for n in names:
            t = _http(url + n)
            if not t: continue
            try: r = parse_bdeck(t.decode('utf-8', 'replace'))
            except Exception as e: _log('b-deck parse', n, repr(e)[:120]); continue
            if r and abs((run - dt.datetime.fromisoformat(r['time'])).total_seconds()) / 3600 <= max_age_h: r['file'] = url + n; out.append(r)
        _log('b-deck', url, 'files', len(names), 'recent storms', len([r for r in out if str(y) in r.get('file', '')]))
    return out

def fetch(run):
    recs = []
    for name, f in (('tcvitals', lambda: from_tcvitals(run)[0]), ('b-deck', lambda: from_bdeck(run))):
        try: recs += f()
        except Exception as e: _log(name, 'FAILED', repr(e)[:200])
    for r in recs: r['age_h'] = round((run - dt.datetime.fromisoformat(r['time'])).total_seconds() / 3600, 1)
    return sorted(recs, key=lambda r: (r['source'], r['id'], r['time']))

def save(run):
    recs = fetch(run); os.makedirs(OUTD, exist_ok=True); fn = os.path.join(OUTD, f'vitals_{run:%Y%m%d%H}.json')
    json.dump(recs, open(fn, 'w'), indent=1)
    _log('saved', fn, len(recs), 'records:', '; '.join(f"{r['source']} {r['id']} {r['name']} {r['time']} {r['lat']}N {r['lon']}E {r['vmax_kt']}kt {r['pmin_hPa']}hPa" for r in recs) or 'no active North Indian Ocean system')
    _log('IMD RSMC New Delhi: not machine-readable (PDF bulletins), not used')
    return fn

# ------------------------------------------------------------------ use in the model
def pick(vit, t0, basin=None, prefer=('NCEP tcvitals', 'JTWC b-deck'), max_age_h=12.0, min_kt=15.0, box=(5, 25, 77, 100)):
    """The strongest system in the box (lat0, lat1, lon0, lon1; default the Bay of Bengal) at t0 from the first source that has
    one (basin 'A'/'B' to also require JTWC's sub-basin letter) -> storm dict for mm2.Model.init(storm=...): lat, lon (moved on with the reported motion to t0), vmax_kt, and rmw_km /
    R_out (outer radius from the outermost closed isobar) when reported. None if no usable record."""
    if isinstance(vit, str):
        if not os.path.exists(vit): return None
        vit = json.load(open(vit))
    if isinstance(t0, str): t0 = dt.datetime.fromisoformat(t0)
    for src in prefer:
        c = []
        for r in vit:
            if r.get('source') != src or r.get('lat') is None or r.get('vmax_kt') is None: continue
            age = (t0 - dt.datetime.fromisoformat(r['time'])).total_seconds() / 3600
            if abs(age) > max_age_h or r['vmax_kt'] < min_kt: continue
            lat, lon = r['lat'], r['lon']
            if age and r.get('motion_deg') is not None and r.get('motion_kt'):
                d = r['motion_kt'] * age / 60.0; lat += d * math.cos(math.radians(r['motion_deg']))
                lon += d * math.sin(math.radians(r['motion_deg'])) / max(0.2, math.cos(math.radians(lat)))
            if box[0] <= lat <= box[1] and box[2] <= lon <= box[3] and (basin is None or r.get('basin') in (basin, None)):
                c.append((r['vmax_kt'], dict(lat=round(lat, 2), lon=round(lon, 2), vmax_kt=float(r['vmax_kt'])), r))
        if c:
            _, s, r = max(c, key=lambda x: x[0])
            if r.get('rmw_km') and 10 <= r['rmw_km'] <= 300: s['rmw_km'] = float(r['rmw_km'])
            if r.get('roci_km') and r['roci_km'] >= 150: s['R_out'] = float(min(900.0, max(300.0, r['roci_km'])))
            return s
    return None

if __name__ == '__main__':
    if len(sys.argv) > 1: R = dt.datetime.strptime(sys.argv[1], '%Y%m%d%H')
    else: n = dt.datetime.utcnow(); R = n.replace(hour=n.hour // 6 * 6, minute=0, second=0, microsecond=0) - dt.timedelta(hours=6)
    print(save(R))
