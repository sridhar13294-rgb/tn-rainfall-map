"""Probe the TIGGE cyclone-track archive (NCAR GDEX/RDA d330003) layout from a GitHub runner; writes data/cyclone/tigge_probe.txt."""
import urllib.request, ssl, re
out = open('data/cyclone/tigge_probe.txt', 'w')
def get(u, n=3000):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'}), timeout=60); b = r.read(); return r.status, r.geturl(), b[:n].decode('utf-8', 'replace'), b
    except Exception as e: return None, u, repr(e)[:300], b''
for u in ['https://data.rda.ucar.edu/d330003/', 'https://data.rda.ucar.edu/ds330.3/', 'https://data.gdex.ucar.edu/d330003/', 'https://osdf-director.osg-htc.org/ncar/rda/d330003/',
          'https://data.rda.ucar.edu/d330003/ecmf/', 'https://data.rda.ucar.edu/d330003/ecmf/2023/', 'https://data.gdex.ucar.edu/d330003/ecmf/2023/',
          'https://gdex.ucar.edu/datasets/d330003/filelist/', 'https://rda.ucar.edu/datasets/ds330.3/filelist/']:
    s, fu, txt, _ = get(u); print('==', u, s, fu, file=out); print(re.sub(r'\s+', ' ', txt)[:1500], file=out)
out.close()
