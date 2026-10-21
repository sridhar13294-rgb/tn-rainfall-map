"""ECMWF and NCEP ensemble storm tracks for our past storms, from the TIGGE cyclone-track archive (CXML; NCAR d330003 via its
OSDF mirror). For each storm's start time (from 2006 on): the ECMWF run at that time (or the 00/12Z run up to 6 h before,
leads shifted) and the GEFS/GFS run at that time. For each member, the disturbance whose first position is nearest the
storm's real position (within 300 km). Output: data/cyclone/tigge_tracks.json
{storm key: {centre: {members: {name: [[hour_from_our_start, lat, lon, pmin_hPa, vmax_ms], ...]}}}}"""
import os, sys, json, math, re, datetime as dt, urllib.request, xml.etree.ElementTree as ET, concurrent.futures as cf
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'analysis'))
import ourens as O
B = 'https://osdf-director.osg-htc.org/ncar/rda/d330003/'
def get(u):
    for _ in range(3):
        try: return urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'}), timeout=120).read()
        except Exception as e: err = e
    return None
def listing(u):
    t = get(u); return re.findall(r'<a href="([^"]+)"', t.decode('utf-8', 'replace')) if t else []
def num(x):
    try: return float(x.text)
    except Exception: return None
def parse(xml):
    """-> {member: [ [ (hour, lat, lon, p, v), ...] per disturbance ]}"""
    root = ET.fromstring(xml); out = {}
    for d in root.iter('data'):
        typ = d.get('type'); mem = d.get('member') or '0'
        if typ not in ('forecast', 'ensembleForecast'): continue
        name = ('det' if typ == 'forecast' else 'm') + mem
        for dist in d.iter('disturbance'):
            fx = []
            for f in dist.iter('fix'):
                h = f.get('hour'); la = f.find('latitude'); lo = f.find('longitude')
                if h is None or la is None or lo is None: continue
                lat = num(la); lon = num(lo)
                if lat is None or lon is None: continue
                if (la.get('units') or '').lower().endswith('s'): lat = -lat
                if (lo.get('units') or '').lower().endswith('w'): lon = -lon
                p = f.find('.//minimumPressure/pressure'); v = f.find('.//maximumWind/speed')
                vv = num(v) if v is not None else None
                if vv is not None and v.get('units', '').lower().startswith('kt'): vv *= 0.5144
                fx.append((float(h), lat, lon % 360, num(p) if p is not None else None, vv))
            if fx: out.setdefault(name, []).append(sorted(fx))
    return out
def real_at(P0, t):
    for a, b in zip(P0, P0[1:]):
        if a[0] <= t <= b[0]:
            f = (t - a[0]).total_seconds() / max(1, (b[0] - a[0]).total_seconds()); return (a[1] + f * (b[1] - a[1]), a[2] + f * (b[2] - a[2]))
    return None
def km(a, b): return math.hypot(a[0] - b[0], (a[1] - b[1]) * math.cos(math.radians(a[0]))) * 111.2
def one(s):
    g = O.gen_time(s)
    if g < dt.datetime(2006, 10, 1): return None
    P0 = O.path_of(s); res = {}
    for centre, pat, step in (('ECMWF', 'ecmf', 12), ('GEFS', 'kwbc', 6)):
        init = g.replace(hour=g.hour // step * step); lag = (g - init).total_seconds() / 3600
        files = listing(B + f'{pat}/{init:%Y}/{init:%Y%m%d}/')
        tag = f'{init:%Y%m%d%H}0000'
        want = [f for f in files if tag in f and (pat == 'ecmf' or '_GEFS_' in f or '_GFS_' in f)]
        mem = {}
        for f in want:
            x = get('https://osdf-director.osg-htc.org' + f if f.startswith('/') else f)
            if not x: continue
            try: P = parse(x)
            except Exception as e: print(s['name'], centre, 'parse failed', repr(e)[:100], flush=True); continue
            for name, dists in P.items():
                key = ('GFS-' if '_GFS_' in f else '') + name
                r0 = real_at(P0, init + dt.timedelta(hours=lag)) or real_at(P0, g)
                best = None
                for fx in dists:
                    first = min(fx, key=lambda q: abs(q[0] - lag))
                    if abs(first[0] - lag) > 6: continue
                    dk = km((first[1], first[2]), r0)
                    if dk <= 300 and (best is None or dk < best[0]): best = (dk, fx)
                if best: mem[key] = [[round(q[0] - lag, 1), round(q[1], 2), round(q[2], 2), q[3], None if q[4] is None else round(q[4], 1)] for q in best[1] if q[0] >= lag - 0.1]
        res[centre] = dict(init=f'{init:%Y-%m-%dT%H}', lag=lag, files=len(want), members=mem)
        print(s['name'], s['season'], centre, init, 'files', len(want), 'members matched', len(mem), flush=True)
    return f"{s['name']}|{s['season']}|{g:%Y-%m-%dT%H}", res
out = {}
with cf.ThreadPoolExecutor(8) as ex:
    for r in ex.map(one, O.LIBL):
        if r: out[r[0]] = r[1]
json.dump(out, open('data/cyclone/tigge_tracks.json', 'w'))
print('storms', len(out), 'with ECMWF members', sum(1 for v in out.values() if v.get('ECMWF', {}).get('members')), 'with GEFS', sum(1 for v in out.values() if v.get('GEFS', {}).get('members')))
