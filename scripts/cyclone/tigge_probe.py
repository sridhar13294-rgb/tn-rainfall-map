"""Probe the TIGGE cyclone-track archive layout (OSDF mirror of NCAR d330003); writes data/cyclone/tigge_probe.txt."""
import urllib.request, re
out = open('data/cyclone/tigge_probe.txt', 'w'); B = 'https://osdf-director.osg-htc.org/ncar/rda/d330003/'
def ls(u):
    try: t = urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'}), timeout=90).read().decode('utf-8', 'replace')
    except Exception as e: return ['ERR ' + repr(e)[:200]]
    return re.findall(r'<a href="([^"]+)"', t)
for sub in ['', 'ecmf/', 'kwbc/']:
    L = ls(B + sub); print('==', sub, len(L), L[:40], file=out)
L = ls(B + 'ecmf/'); print('ecmf entries', L[-10:], file=out)
for y in ('2018', '2023'):
    for c in ('ecmf', 'kwbc'):
        L = ls(B + f'{c}/{y}/'); print('==', c, y, len(L), L[:15], L[-5:], file=out)
        if L and not L[0].startswith('ERR'):
            d = [x for x in L if '1112' in x or '1111' in x][:2] or L[:2]
            for x in d:
                L2 = ls(B + f'{c}/{y}/' + x.rstrip('/').split('/')[-1] + '/'); print('   ', x, len(L2), L2[:12], file=out)
out.close()
