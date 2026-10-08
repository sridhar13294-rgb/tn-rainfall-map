"""One-off probe: NOAA CFSv2 files on AWS and CPC climatologies on PSL."""
import json, urllib.request, re, datetime as dt
out = {}
def get(url, rng=None, n=4000):
    try:
        r = urllib.request.Request(url, headers={'User-Agent': 'tn-rainfall-map probe'})
        if rng: r.add_header('Range', rng)
        with urllib.request.urlopen(r, timeout=60) as f:
            b = f.read(n); return {'status': f.status, 'len': f.headers.get('Content-Length'), 'body': b.decode('latin1')}
    except Exception as e:
        return {'error': str(e)}
def head(url):
    try:
        r = urllib.request.Request(url, method='HEAD', headers={'User-Agent': 'tn-rainfall-map probe'})
        with urllib.request.urlopen(r, timeout=60) as f:
            return {'status': f.status, 'len': f.headers.get('Content-Length'), 'mod': f.headers.get('Last-Modified')}
    except Exception as e:
        return {'error': str(e)}
B = 'https://noaa-cfs-pds.s3.amazonaws.com'
today = dt.datetime.utcnow().date()
for back in range(0, 3):
    d = (today - dt.timedelta(days=back)).strftime('%Y%m%d')
    r = get(f'{B}/?list-type=2&prefix=cfs.{d}/&delimiter=/', n=20000)
    out[f'list_{d}'] = re.findall(r'<Prefix>([^<]+)</Prefix>', r.get('body', '')) or r
for back in (1,):
    d = (today - dt.timedelta(days=back)).strftime('%Y%m%d')
    for hh in ('00', '18'):
        r = get(f'{B}/?list-type=2&prefix=cfs.{d}/{hh}/&delimiter=/', n=20000)
        out[f'sub_{d}{hh}'] = re.findall(r'<Prefix>([^<]+)</Prefix>', r.get('body', ''))
        for sub in ('time_grib_01', 'time_grib_02', '6hrly_grib_01'):
            r = get(f'{B}/?list-type=2&prefix=cfs.{d}/{hh}/{sub}/&max-keys=1000', n=400000)
            keys = re.findall(r'<Key>([^<]+)</Key><LastModified>[^<]+</LastModified><ETag>[^<]+</ETag><Size>(\d+)</Size>', r.get('body', ''))
            out[f'{sub}_{d}{hh}_n'] = len(keys)
            out[f'{sub}_{d}{hh}_keys'] = [k for k in keys if re.search(r'(prate|tmax|tmin|tmp2m)', k[0])][:16] if 'time' in sub else keys[:6] + keys[-4:]
    tk = [k for k in out.get(f'time_grib_02_{d}00_keys', []) if 'prate' in k[0] and k[0].endswith('.idx')]
    if tk:
        r = get(f'{B}/{tk[0][0]}', n=3000); out['prate_idx_head'] = r.get('body', '')[:2500]
        r = get(f'{B}/{tk[0][0]}', n=10 ** 7); b = r.get('body', '').strip().split('\n'); out['prate_idx_tail'] = b[-5:]; out['prate_idx_lines'] = len(b)
PSL = 'https://downloads.psl.noaa.gov/Datasets'
for u in ['cpc_global_precip/precip.day.ltm.1991-2020.nc', 'cpc_global_temp/tmax.day.ltm.1991-2020.nc', 'cpc_global_temp/tmin.day.ltm.1991-2020.nc',
          'cpc_global_precip/precip.2026.nc', 'cpc_global_temp/tmax.2026.nc']:
    out[u] = head(f'{PSL}/{u}')
json.dump(out, open('data/probe.json', 'w'), indent=1)
print(json.dumps(out)[:3000])
