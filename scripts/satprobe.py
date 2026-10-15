"""Feasibility probe for a satellite 'radar' (sat-radar branch only): which free rain sources GitHub can read, how late."""
import datetime as dt, json, os, re, sys, time, urllib.request, xml.etree.ElementTree as ET

UA = {'User-Agent': 'tn-rainfall-map satellite probe (non-commercial)'}
OUT = 'data/satradar'
os.makedirs(OUT, exist_ok=True)
log = []
def say(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); log.append(s)

def get(url, timeout=60, rng=None):
    h = dict(UA)
    if rng: h['Range'] = 'bytes=%d-%d' % rng
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
        return r.read(), dict(r.headers)

NS = '{http://s3.amazonaws.com/doc/2006-03-01/}'
def s3_list(bucket, prefix='', delim='/', token=None):
    u = f'https://{bucket}.s3.amazonaws.com/?list-type=2&delimiter={delim}&prefix={prefix}' + (f'&continuation-token={urllib.parse.quote(token)}' if token else '')
    x = ET.fromstring(get(u)[0])
    pre = [p.find(NS + 'Prefix').text for p in x.findall(NS + 'CommonPrefixes')]
    keys = [(c.find(NS + 'Key').text, c.find(NS + 'LastModified').text, int(c.find(NS + 'Size').text)) for c in x.findall(NS + 'Contents')]
    nt = x.find(NS + 'NextContinuationToken')
    return pre, keys, (nt.text if nt is not None else None)

import urllib.parse
def s3_walk(bucket, depth=7):
    say(f'\n== S3 {bucket}')
    prefix = ''
    for lvl in range(depth):
        pre, keys, tok = s3_list(bucket, prefix)
        while tok and not keys and len(pre) < 5000:
            p2, k2, tok = s3_list(bucket, prefix, token=tok); pre += p2; keys += k2
        say(f'  level {lvl} prefix={prefix!r}: {len(pre)} folders, {len(keys)} files; folders: {pre[:6]} ... {pre[-6:]}')
        if keys:
            keys.sort(key=lambda k: k[1])
            for k in keys[-8:]:
                say('   ', k)
            return keys
        if not pre:
            return []
        prefix = sorted(pre)[-1]
    return []

now = dt.datetime.now(dt.timezone.utc)
say('probe at', now.isoformat())
found = {}
for b in ('noaa-enterprise-rainrate-pds', 'noaa-ghe-pds'):
    try:
        ks = s3_walk(b)
        if ks:
            k, lm, size = ks[-1]
            age = now - dt.datetime.fromisoformat(lm.replace('Z', '+00:00'))
            say(f'  newest file {k} size {size} uploaded {lm} -> {age.total_seconds()/60:.0f} min ago')
            found[b] = ks
            # download the newest small-ish file to inspect its format
            if size < 80e6:
                t0 = time.time(); buf, hd = get(f'https://{b}.s3.amazonaws.com/{k}', timeout=180)
                say(f'  downloaded {len(buf)/1e6:.1f} MB in {time.time()-t0:.0f}s; magic {buf[:8]!r}')
                fn = os.path.join(OUT, 'sample_' + b + '_' + os.path.basename(k))
                open(fn, 'wb').write(buf)
    except Exception as e:
        say('  ERROR', b, e)

# EUMETSAT public map service (no account): layer list
say('\n== EUMETView WMS capabilities')
try:
    cap = get('https://view.eumetsat.int/geoserver/ows?service=WMS&request=GetCapabilities', timeout=120)[0].decode('utf8', 'replace')
    names = re.findall(r'<Layer[^>]*>\s*<Name>([^<]+)</Name>\s*<Title>([^<]*)</Title>', cap)
    say(f'  {len(names)} layers')
    for n, t in names:
        if re.search(r'iodc|indian|mpe|precip|rain|msg_?iodc|m8|m9|crr|rdt', n + ' ' + t, re.I):
            say('   ', n, '|', t)
    open(os.path.join(OUT, 'eumetview_layers.txt'), 'w').write('\n'.join(f'{n} | {t}' for n, t in names))
except Exception as e:
    say('  ERROR', e)

# IMD radar images: reference only (scan time is printed in UTC on the image)
say('\n== IMD radar images')
for site in ('cni', 'kkl', 'plk', 'shr'):
    for prod in ('caz', 'ppz', 'ppi'):
        u = f'https://mausam.imd.gov.in/Radar/{prod}_{site}.gif'
        try:
            buf, hd = get(u, timeout=60)
            m = re.search(rb'\d{2}:\d{2}[^\x00]{0,40}', buf[:4000])
            say(f'  {prod}_{site}: {len(buf)} bytes, Last-Modified {hd.get("Last-Modified")}')
            open(os.path.join(OUT, f'imd_{prod}_{site}.gif'), 'wb').write(buf)
        except Exception as e:
            say(f'  {prod}_{site}: ERROR {e}')
open(os.path.join(OUT, 'probe_report.txt'), 'w').write('\n'.join(log))
