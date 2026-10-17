"""Probe round 3: how far back TN SMART goes, NOAA GEFSv12 reforecasts (2000-2019) and IMD gridded rain (imdlib)."""
import json, os, sys, urllib.request, urllib.parse, subprocess, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
out = {}
def head(u):
    r = urllib.request.urlopen(urllib.request.Request(u, method='HEAD', headers={'User-Agent': 'tn-rainfall-map probe'}), timeout=60)
    return dict(status=r.status, size=r.headers.get('Content-Length'))
import update as U
geo = U.load(U.P('data/geo.json'), None); res = {}
for d in ['2018-11-16', '2017-11-30', '2016-12-12', '2015-12-01', '2015-11-16', '2012-10-31', '2010-11-15', '2008-11-26', '2005-10-27', '2000-11-30']:
    try:
        page = U.fetch_date(d); date, rows = U.parse_page(page, geo['d'] + list(U.ALIASES))
        top = sorted([(r['rain'], r.get('name') or r.get('station')) for r in rows if r['rain'] is not None], key=lambda x: -x[0])[:2]
        res[d] = dict(page_date=date, gauges=sum(r['rain'] is not None for r in rows), top=top)
    except Exception as e:
        res[d] = 'ERR ' + str(e)[:150]
out['tnsmart_old'] = res
g = {}
base = 'https://noaa-gefs-retrospective.s3.amazonaws.com/GEFSv12/reforecast'
for y, d in [(2000, '2000100100'), (2010, '2010110100'), (2019, '2019120100'), (2020, '2020110100')]:
    for path in [f'{base}/{y}/{d}/c00/Days:1-10/apcp_sfc_{d}_c00.grib2', f'{base}/{y}/{d}/c00/Days%3A1-10/apcp_sfc_{d}_c00.grib2']:
        try: g[path[len(base):]] = head(path)
        except Exception as e: g[path[len(base):]] = 'ERR ' + str(e)[:120]
try:
    lst = urllib.request.urlopen('https://noaa-gefs-retrospective.s3.amazonaws.com/?list-type=2&prefix=GEFSv12/reforecast/2010/2010110100/c00/&max-keys=40', timeout=60).read().decode()
    import re; g['listing'] = re.findall(r'<Key>([^<]+)</Key><LastModified>[^<]+</LastModified><ETag>[^<]+</ETag><Size>(\d+)</Size>', lst)[:40]
except Exception as e:
    g['listing'] = 'ERR ' + str(e)[:200]
out['gefs_reforecast'] = g
try:
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'imdlib'], check=True, timeout=300)
    import imdlib as imd
    t0 = time.time(); os.makedirs('/tmp/imd', exist_ok=True)
    data = imd.get_data('rain', 2015, 2015, fn_format='yearwise', file_dir='/tmp/imd')
    ds = data.get_xarray(); r = ds['rain'].sel(lat=13.0, lon=80.25, method='nearest').sel(time='2015-12-01')
    out['imd_gridded'] = dict(ok=True, seconds=round(time.time() - t0), shape=str(ds['rain'].shape), chennai_2015_12_01=float(r.values), files=os.listdir('/tmp/imd'))
    for y in (2000, 2024, 2025):
        try:
            imd.get_data('rain', y, y, fn_format='yearwise', file_dir='/tmp/imd'); out['imd_gridded'][f'year_{y}'] = 'ok'
        except Exception as e:
            out['imd_gridded'][f'year_{y}'] = 'ERR ' + str(e)[:120]
except Exception as e:
    out['imd_gridded'] = 'ERR ' + str(e)[:300]
os.makedirs('data', exist_ok=True); json.dump(out, open('data/probe_train.json', 'w'), indent=1); print(json.dumps(out, indent=1)[:5000])
