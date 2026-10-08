"""One-off probe: current daily OLR observation sources."""
import json, urllib.request, re
UA = {'User-Agent': 'tn-rainfall-map probe'}
out = {}
def get(url, n=200000):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
            return dict(status=r.status, body=r.read(n).decode('utf-8', 'replace'))
    except Exception as e:
        return dict(error=str(e)[:200])
r = get('https://downloads.psl.noaa.gov/Datasets/')
out['psl_dirs'] = [x for x in re.findall(r'href="([^"]+)"', r.get('body', '')) if 'olr' in x.lower() or 'cbo' in x.lower() or 'cpc' in x.lower()]
for d in out['psl_dirs'][:8]:
    u = 'https://downloads.psl.noaa.gov/Datasets/' + d.lstrip('/')
    r = get(u)
    out[u] = re.findall(r'href="([^"?]+\.nc)"[^<]*</a>\s*([^<\n]*)', r.get('body', ''))[:40] or r.get('error')
for u in ['https://www.ncei.noaa.gov/data/outgoing-longwave-radiation-daily/access/',
          'https://www.ncei.noaa.gov/data/outgoing-longwave-radiation-daily/access/preliminary/',
          'https://ftp.cpc.ncep.noaa.gov/precip/CBO_V1/', 'https://ftp.cpc.ncep.noaa.gov/precip/CBO_V1/READ_ME/CBO_V1_Readme.txt']:
    r = get(u)
    body = r.get('body', '')
    out[u] = (re.findall(r'href="([^"?]+)"', body)[-30:] if '<html' in body.lower() or 'href' in body else body[:3000]) or r.get('error')
json.dump(out, open('data/probe.json', 'w'), indent=1)
