"""One-off probe: which MJO pattern (EOF) sources are reachable from GitHub's servers."""
import json, urllib.request, re
UA = {'User-Agent': 'tn-rainfall-map probe'}
out = {}
def get(url, method='GET', n=4000):
    try:
        req = urllib.request.Request(url, headers=UA, method=method)
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read(n) if method == 'GET' else b''
            return dict(status=r.status, length=r.headers.get('Content-Length'), type=r.headers.get('Content-Type'), body=body.decode('utf-8', 'replace'))
    except Exception as e:
        return dict(error=str(e)[:300])
r = get('https://api.github.com/repos/dtcenter/METplus/releases?per_page=6', n=4_000_000)
try:
    rel = json.loads(r['body'])
    out['metplus_assets'] = [(x['tag_name'], a['name'], a['size'], a['browser_download_url']) for x in rel for a in x['assets'] if 'mjo' in a['name'].lower() or 's2s' in a['name'].lower()]
except Exception as e:
    out['metplus_assets'] = r
for v in ('v6.1', 'v6.0', 'v5.1', 'v5.0', 'develop'):
    for name in ('sample_data-s2s_mjo.tgz', 'sample_data-s2s_mjo-%s.tgz' % v):
        u = f'https://dtcenter.ucar.edu/dfiles/code/METplus/METplus_Data/{v}/{name}'
        out[u] = get(u, 'HEAD')
for u in ['https://psl.noaa.gov/mjo/mjoindex/', 'https://psl.noaa.gov/mjo/mjoindex/omi_eofs/', 'https://psl.noaa.gov/mjo/mjoindex/eofs/',
          'https://psl.noaa.gov/mjo/mjoindex/eof1/eof001.txt', 'https://iridl.ldeo.columbia.edu/SOURCES/.BoM/.MJO/',
          'https://iridl.ldeo.columbia.edu/SOURCES/.BoM/.MJO/.RMM/', 'https://www.bom.gov.au/climate/mjo/']:
    r = get(u, n=20000)
    if 'body' in r:
        r['links'] = sorted(set(re.findall(r'href="([^"#?]+)"', r.pop('body'))))[:80]
    out[u] = r
json.dump(out, open('data/probe.json', 'w'), indent=1)
print(json.dumps(out, indent=1)[:3000])
