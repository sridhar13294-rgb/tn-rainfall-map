"""Probe 2 (rerun): radar images for each IMD radar near Tamil Nadu, their scan time (GIF comment) vs when they appear online."""
import datetime as dt, json, os, re, time, urllib.request
OUT = 'data/radar_probe'; os.makedirs(OUT, exist_ok=True)
UA = 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Mobile Safari/537.36'
IDS = ['Chennai', 'Pallikaranai', 'Karaikal', 'Sriharikota', 'Kochi', 'Thiruvananthapuram']
def get(url):
    r = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA, 'Referer': 'https://mausam.imd.gov.in/'}), timeout=60)
    return r.read(), r.headers.get('Last-Modified')
def comment(b):
    m = re.search(rb'\x21\xfe(.)', b[:4000])
    if not m: return None
    n = b[m.end() - 1]; return b[m.end():m.end() + n].decode('latin1')
log = {'rounds': []}; imgs = {}
for rid in IDS:
    try:
        h, _ = get('https://mausam.imd.gov.in/chennai/index_radar.php?id=' + rid)
        imgs[rid] = sorted(set(re.findall(r'Radar/[A-Za-z0-9_]+\.(?:gif|png|jpg)', h.decode('utf-8', 'replace'))))
    except Exception as e:
        imgs[rid] = 'ERR ' + str(e)[:200]
log['images'] = imgs
for rnd in range(7):
    now = dt.datetime.now(dt.timezone.utc).strftime('%H:%M:%S'); row = {'fetched_utc': now}
    for rid, L in imgs.items():
        if not isinstance(L, list): continue
        for path in L:
            try:
                b, lm = get('https://mausam.imd.gov.in/' + path)
                row[path] = dict(scan=comment(b), modified=lm, len=len(b))
                if rnd == 0:
                    open(os.path.join(OUT, path.split('/')[-1]), 'wb').write(b)
            except Exception as e:
                row[path] = 'ERR ' + str(e)[:120]
    log['rounds'].append(row)
    json.dump(log, open(os.path.join(OUT, 'probe2.json'), 'w'), indent=1)
    if rnd < 6: time.sleep(300)
print(json.dumps(log['images'], indent=1))
