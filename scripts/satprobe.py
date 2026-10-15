"""Feasibility probe 2 (sat-radar branch only): EUMETView H SAF h63 rain rate over Tamil Nadu + NOAA BLEND/GHE folders."""
import datetime as dt, json, os, re, time, urllib.request, urllib.parse, xml.etree.ElementTree as ET
UA = {'User-Agent': 'tn-rainfall-map satellite probe (non-commercial)'}
OUT = 'data/satradar'; os.makedirs(OUT, exist_ok=True)
log = []
def say(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); log.append(s)
def get(url, timeout=90):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read(), dict(r.headers)
now = dt.datetime.now(dt.timezone.utc); say('probe 2 at', now.isoformat())
W = 'https://view.eumetsat.int/geoserver'
# 1) capabilities detail for the layers we care about (time dimension = how far back, how often)
try:
    cap = get(W + '/ows?service=WMS&version=1.3.0&request=GetCapabilities', 180)[0].decode('utf8', 'replace')
    for lay in ('msg_iodc:h63', 'msg_iodc:ir108', 'msg_iodc:rgb_convection', 'msg_iodc:cth'):
        i = cap.find('<Name>' + lay + '</Name>')
        blk = cap[i:i + 6000]
        dim = re.search(r'<Dimension[^>]*name="time"[^>]*>([^<]*)</Dimension>', blk)
        sty = re.findall(r'<Style>\s*<Name>([^<]+)</Name>', blk)
        leg = re.search(r'<LegendURL.*?xlink:href="([^"]+)"', blk, re.S)
        d = dim.group(1) if dim else ''
        say(f'\n{lay}: styles {sty[:4]} legend {leg.group(1) if leg else None}')
        say('  time dim:', (d[:300] + ' ... ' + d[-300:]) if len(d) > 600 else d)
except Exception as e:
    say('caps ERROR', e)
# 2) WCS (raw numbers)?
for u in (W + '/msg_iodc/ows?service=WCS&version=2.0.1&request=GetCapabilities', W + '/ows?service=WCS&version=2.0.1&request=GetCapabilities'):
    try:
        t = get(u, 120)[0].decode('utf8', 'replace')
        ids = re.findall(r'<wcs:CoverageId>([^<]+)</wcs:CoverageId>', t)
        say(f'\nWCS {u}: {len(ids)} coverages; h63-like: {[x for x in ids if "h63" in x or "iodc" in x][:20]}')
    except Exception as e:
        say('\nWCS', u, 'ERROR', e)
# 3) GetMap over Tamil Nadu (latest, and a few past times), plus legend
bbox = '7.0,75.5,14.5,81.5'   # WMS 1.3.0 EPSG:4326 = lat,lon order
def gm(layer, t=None, fmt='image/png', w=480, h=600, extra=''):
    q = f'{W}/ows?service=WMS&version=1.3.0&request=GetMap&layers={layer}&styles=&crs=EPSG:4326&bbox={bbox}&width={w}&height={h}&format={urllib.parse.quote(fmt)}&transparent=true' + (f'&time={t}' if t else '') + extra
    return get(q, 120)
for lay in ('msg_iodc:h63', 'msg_iodc:ir108', 'msg_iodc:rgb_convection'):
    try:
        buf, hd = gm(lay); fn = f'{OUT}/now_{lay.split(":")[1]}.png'; open(fn, 'wb').write(buf)
        say(f'\nGetMap {lay}: {len(buf)} bytes, type {hd.get("Content-Type")}')
    except Exception as e:
        say('\nGetMap', lay, 'ERROR', e)
try:
    buf, hd = get(f'{W}/ows?service=WMS&version=1.3.0&request=GetLegendGraphic&layer=msg_iodc:h63&format=image/png', 60)
    open(f'{OUT}/legend_h63.png', 'wb').write(buf); say('legend h63', len(buf))
except Exception as e:
    say('legend ERROR', e)
# GetFeatureInfo: does it return the rain-rate number at a point?
try:
    q = f'{W}/ows?service=WMS&version=1.3.0&request=GetFeatureInfo&layers=msg_iodc:h63&query_layers=msg_iodc:h63&crs=EPSG:4326&bbox={bbox}&width=480&height=600&i=300&j=300&info_format=application/json'
    say('featureinfo:', get(q, 60)[0][:600])
except Exception as e:
    say('featureinfo ERROR', e)
# past frames for 15 Oct heavy-rain night (to compare with TN SMART / radar): 2026-10-14 18Z .. 15 00Z
for t in ('2026-10-14T18:00:00Z', '2026-10-14T21:00:00Z', '2026-10-15T00:00:00Z', '2026-10-15T09:00:00Z'):
    try:
        buf, hd = gm('msg_iodc:h63', t); open(f'{OUT}/h63_{t[:13]}.png', 'wb').write(buf)
        say(f'past h63 {t}: {len(buf)} bytes {hd.get("Content-Type")}')
    except Exception as e:
        say(f'past h63 {t}: ERROR {e}')
# 4) NOAA BLEND / GHE: do they still update and cover India?
NS = '{http://s3.amazonaws.com/doc/2006-03-01/}'
def lst(b, p):
    x = ET.fromstring(get(f'https://{b}.s3.amazonaws.com/?list-type=2&delimiter=/&prefix={p}')[0])
    return [c.find(NS + 'Prefix').text for c in x.findall(NS + 'CommonPrefixes')], [(c.find(NS + 'Key').text, c.find(NS + 'LastModified').text, c.find(NS + 'Size').text) for c in x.findall(NS + 'Contents')]
for b, p in (('noaa-enterprise-rainrate-pds', 'BLEND/'), ('noaa-ghe-pds', 'rain_rate/')):
    try:
        for _ in range(6):
            pre, ks = lst(b, p)
            say(f'{b} {p}: {len(pre)} folders {pre[-4:]} | {len(ks)} files {ks[-3:]}')
            if not pre: break
            p = sorted(pre)[-1]
    except Exception as e:
        say(b, 'ERROR', e)
open(f'{OUT}/probe2_report.txt', 'w').write('\n'.join(log))
