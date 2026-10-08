"""One-off probe: can IMD's Chennai/Karaikal radar pages and images be read automatically from outside India?"""
import json, os, re, time, urllib.request, urllib.parse, hashlib
OUT = 'data/radar_probe'; os.makedirs(OUT, exist_ok=True)
UA = 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Mobile Safari/537.36'
log = {}
def get(url, n=None):
    t = time.time()
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA, 'Referer': 'https://mausam.imd.gov.in/'}), timeout=60)
        b = r.read()
        return dict(status=r.status, type=r.headers.get('Content-Type'), len=len(b), modified=r.headers.get('Last-Modified'),
                    server=r.headers.get('Server'), secs=round(time.time() - t, 1)), b
    except Exception as e:
        return dict(error=str(e)[:300], secs=round(time.time() - t, 1)), b''
ip, _ = get('https://api.ipify.org?format=json'); 
try: log['runner_ip'] = json.loads(_.decode())
except Exception: log['runner_ip'] = ip
pages = ['https://mausam.imd.gov.in/chennai/index_radar.php', 'https://mausam.imd.gov.in/imd_latest/contents/index_radar.php',
         'https://mausam.imd.gov.in/responsive/radar.php']
imgs = set()
for u in pages:
    meta, b = get(u); log[u] = meta
    if b:
        h = b.decode('utf-8', 'replace'); open(os.path.join(OUT, re.sub(r'\W+', '_', u)[-60:] + '.html'), 'w').write(h)
        for m in re.findall(r'''(?:src|href|data-src)\s*=\s*["']([^"']+\.(?:gif|png|jpe?g)[^"']*)["']''', h, re.I):
            full = urllib.parse.urljoin(u, m)
            if re.search(r'radar|dwr|ppi|caz|maxz|sri|chn|kkl|karaikal|chennai', full, re.I):
                imgs.add(full)
        for m in re.findall(r'''["']([^"']*(?:radar|dwr|DWR)[^"']*\.(?:gif|png|jpe?g))["']''', h):
            imgs.add(urllib.parse.urljoin(u, m))
log['images_found'] = sorted(imgs)
for i, u in enumerate(sorted(imgs)[:40]):
    meta, b = get(u); meta['sha'] = hashlib.md5(b).hexdigest()[:10] if b else None; log['img:' + u] = meta
    if b and len(b) > 2000:
        ext = os.path.splitext(urllib.parse.urlparse(u).path)[1] or '.img'
        open(os.path.join(OUT, f'img{i:02d}{ext}'), 'wb').write(b)
# second look 12 minutes later: do the images change?
time.sleep(720)
for u in sorted(imgs)[:40]:
    meta, b = get(u); log['img2:' + u] = dict(modified=meta.get('modified'), sha=hashlib.md5(b).hexdigest()[:10] if b else None, err=meta.get('error'))
json.dump(log, open(os.path.join(OUT, 'probe.json'), 'w'), indent=1)
print(json.dumps(log, indent=1)[:5000])
