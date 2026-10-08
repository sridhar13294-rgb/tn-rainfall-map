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
            keys = [(re.search(r'<Key>([^<]+)</Key>', c).group(1), (re.search(r'<Size>(\d+)</Size>', c) or re.search('()', c)).group(1)) for c in re.findall(r'<Contents>(.*?)</Contents>', r.get('body', ''))]
            out[f'{sub}_{d}{hh}_raw'] = r.get('body', '')[:600]
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
try:
    import netCDF4
    for nm, u in [('pr', 'https://psl.noaa.gov/thredds/dodsC/Datasets/cpc_global_precip/precip.day.ltm.1991-2020.nc'),
                  ('tx', 'https://psl.noaa.gov/thredds/dodsC/Datasets/cpc_global_temp/tmax.day.ltm.1991-2020.nc')]:
        try:
            ds = netCDF4.Dataset(u); v = list(ds.variables)
            la = ds['lat'][:]; lo = ds['lon'][:]
            vn = 'precip' if nm == 'pr' else 'tmax'
            j = [i for i, x in enumerate(la) if 8 <= x <= 13.5]; i2 = [i for i, x in enumerate(lo) if 76 <= x <= 80.5]
            a = ds[vn][280, j[0]:j[-1] + 1, i2[0]:i2[-1] + 1]
            out['dap_' + nm] = dict(vars=v, shape=list(ds[vn].shape), lat=[float(la[0]), float(la[1])], lon=[float(lo[0]), float(lo[1])],
                                    time_units=ds['time'].units, sample=[[None if x is None else float(x) for x in row] for row in a.filled(-1).tolist()][:3])
        except Exception as e:
            out['dap_' + nm] = str(e)
except Exception as e:
    out['dap'] = str(e)
json.dump(out, open('data/probe.json', 'w'), indent=1)
print(json.dumps(out)[:3000])
