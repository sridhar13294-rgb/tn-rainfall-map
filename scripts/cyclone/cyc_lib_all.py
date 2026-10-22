"""Storm list for testing the model over the whole Indian Ocean, 1980-2025 (IBTrACS v04r01 best tracks).
Basins: BB = Bay of Bengal, AS = Arabian Sea (North Indian Ocean, all months), SI = South Indian Ocean west of 100E.
A storm enters at its first 6-hourly fix with >= 25 kt (depression / tropical depression); t0 is that time.
Writes data/cyclone/lib_all.json: [{sid, name, season, basin, t0, gen [lat, lon], vmax, lf [lat, lon] or None,
path [[iso time, lat, lon, wind kt]]}], sorted by t0."""
import json, os, csv, io, time, urllib.request, datetime as dt
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = 'https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/'
WIND = {'NI': ('NEWDELHI_WIND', 'WMO_WIND', 'USA_WIND'), 'SI': ('REUNION_WIND', 'BOM_WIND', 'WMO_WIND', 'USA_WIND')}
def num(x):
    try: return float(x)
    except Exception: return None
def get(url):
    for k in range(5):
        try: return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'tn-rainfall-map'}), timeout=600).read().decode('utf-8', 'replace')
        except Exception as e: print('retry', k, url, e, flush=True); time.sleep(20)
    raise RuntimeError('download failed ' + url)
storms = {}
for basin in ('NI', 'SI'):
    rows = list(csv.reader(io.StringIO(get(BASE + f'ibtracs.{basin}.list.v04r01.csv')))); H = {h: i for i, h in enumerate(rows[0])}
    for r in rows[2:]:
        season = int(r[H['SEASON']])
        if season < 1980 or r[H['BASIN']] != basin: continue
        t = r[H['ISO_TIME']]
        if t[11:13] not in ('00', '06', '12', '18') or t[14:16] != '00': continue
        la, lo = num(r[H['LAT']]), num(r[H['LON']])
        if la is None or lo is None: continue
        w = next((num(r[H[c]]) for c in WIND[basin] if c in H and num(r[H[c]]) is not None), None)
        sub = r[H['SUBBASIN']] if basin == 'NI' else 'SI'
        s = storms.setdefault(r[H['SID']], dict(sid=r[H['SID']], name=r[H['NAME']].title(), season=season, basin=sub, pts=[]))
        s['pts'].append((t[:13].replace(' ', 'T'), la, lo, w, num(r[H['DIST2LAND']])))
out = []
for s in storms.values():
    P = s['pts']; k0 = next((i for i, p in enumerate(P) if p[3] is not None and p[3] >= 25), None)
    if k0 is None: continue
    t0, la0, lo0 = P[k0][0], P[k0][1], P[k0][2]
    if s['basin'] == 'SI' and not (30 <= lo0 <= 100): continue
    if s['basin'] != 'SI': s['basin'] = 'BB' if lo0 >= 77.5 else 'AS'                          # North Indian Ocean: by where it formed
    if int(t0[:4]) > 2025: continue
    lf = None
    for a, b in zip(P[k0:], P[k0 + 1:]):
        if (a[4] or 0) > 0 and b[4] is not None and b[4] <= 0: lf = [b[1], b[2]]; break
    out.append(dict(sid=s['sid'], name=s['name'], season=s['season'], basin=s['basin'], t0=t0, gen=[la0, lo0],
                    vmax=max([p[3] for p in P if p[3] is not None] or [None]), lf=lf,
                    path=[[p[0] + ':00:00', p[1], p[2], p[3]] for p in P]))
out.sort(key=lambda s: s['t0'])
json.dump(out, open(os.path.join(ROOT, 'data', 'cyclone', 'lib_all.json'), 'w'), separators=(',', ':'))
from collections import Counter
print('storms', len(out), Counter(s['basin'] for s in out), Counter(s['t0'][:3] + '0s' for s in out), flush=True)
