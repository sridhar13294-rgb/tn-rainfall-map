"""Probe 3 (sat-radar branch): can a web page read EUMETView frames directly (CORS), and how fresh are they?"""
import datetime as dt, re, urllib.request
OUT = 'data/satradar/probe3_report.txt'; log = []
def say(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); log.append(s)
W = 'https://view.eumetsat.int/geoserver/ows'
q = W + '?service=WMS&version=1.3.0&request=GetMap&layers=msg_iodc:h63&styles=&crs=EPSG:4326&bbox=7,75.5,14.5,81.5&width=240&height=300&format=image/png&transparent=true'
for origin in ('https://sridhar13294-rgb.github.io', None):
    h = {'User-Agent': 'Mozilla/5.0'}
    if origin: h['Origin'] = origin
    try:
        with urllib.request.urlopen(urllib.request.Request(q, headers=h), timeout=60) as r:
            say('origin', origin, 'status', r.status, {k: v for k, v in r.headers.items() if k.lower().startswith(('access-control', 'cache', 'content-type', 'last-mod', 'expires'))})
    except Exception as e:
        say('origin', origin, 'ERROR', e)
# preflight-less OPTIONS check
try:
    req = urllib.request.Request(q, method='OPTIONS', headers={'Origin': 'https://sridhar13294-rgb.github.io', 'Access-Control-Request-Method': 'GET'})
    with urllib.request.urlopen(req, timeout=60) as r:
        say('OPTIONS', r.status, dict(r.headers))
except Exception as e:
    say('OPTIONS ERROR', e)
cap = urllib.request.urlopen(urllib.request.Request(W + '?service=WMS&version=1.3.0&request=GetCapabilities', headers={'User-Agent': 'Mozilla/5.0'}), timeout=180).read().decode('utf8', 'replace')
for lay in ('msg_iodc:h63', 'msg_iodc:ir108'):
    i = cap.find('<Name>' + lay + '</Name>'); d = re.search(r'<Dimension[^>]*name="time"[^>]*>([^<]*)</Dimension>', cap[i:i + 6000])
    last = d.group(1).split('/')[1] if d else '?'
    say(lay, 'latest frame', last, 'checked at', dt.datetime.now(dt.timezone.utc).isoformat()[:19])
open(OUT, 'w').write('\n'.join(log))
