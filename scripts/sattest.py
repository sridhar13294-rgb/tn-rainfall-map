"""sat-radar branch: open site/satradar.html in Chromium (live EUMETSAT frames), screenshot it, and save a frame snapshot."""
import base64, datetime as dt, json, re, subprocess, time, urllib.request
from playwright.sync_api import sync_playwright
OUT = 'data/satradar'
srv = subprocess.Popen(['python', '-m', 'http.server', '8765', '-d', 'site'])
time.sleep(1.5)
logs = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': 412, 'height': 900}, device_scale_factor=2)
    pg.on('console', lambda m: logs.append(f'{m.type}: {m.text}'))
    pg.on('pageerror', lambda e: logs.append(f'pageerror: {e}'))
    t0 = time.time(); pg.goto('http://localhost:8765/satradar.html')
    pg.wait_for_function("document.getElementById('st').textContent.indexOf('Loading')<0", timeout=120000)
    logs.append(f'loaded in {time.time()-t0:.1f}s: ' + pg.inner_text('#st'))
    pg.screenshot(path=f'{OUT}/live_now.png', full_page=False)
    n = int(pg.get_attribute('#sl', 'max') or 0)
    for k in (0, 8, n):
        pg.evaluate(f"(()=>{{const s=document.getElementById('sl');s.value={k};s.dispatchEvent(new Event('input'))}})()")
        pg.locator('.map').screenshot(path=f'{OUT}/live_frame{k}.png')
    b.close()
srv.terminate()
# snapshot of the same frames (for an offline preview)
cap = urllib.request.urlopen(urllib.request.Request('https://view.eumetsat.int/geoserver/msg_iodc/h63/ows?service=WMS&version=1.3.0&request=GetCapabilities', headers={'User-Agent': 'Mozilla/5.0'}), timeout=120).read().decode()
logs.append(f'layer capabilities size {len(cap)}')
m = re.search(r'<Dimension[^>]*name="time"[^>]*>([^<]*)</Dimension>', cap)
last = dt.datetime.fromisoformat(m.group(1).split('/')[1].replace('Z', '+00:00').replace('.000', ''))
fr = {}
for k in range(9):
    t = last - dt.timedelta(minutes=15 * k); key = t.strftime('%Y-%m-%dT%H:%M:00Z')
    u = f'https://view.eumetsat.int/geoserver/ows?service=WMS&version=1.3.0&request=GetMap&layers=msg_iodc:h63&styles=&crs=EPSG:4326&bbox=7,75.5,14.5,81.5&width=240&height=300&format=image/png&transparent=true&time={key}'
    fr[key] = 'data:image/png;base64,' + base64.b64encode(urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'}), timeout=60).read()).decode()
open(f'{OUT}/snap.js', 'w').write('window.SATSNAP=' + json.dumps(dict(latest=last.strftime('%Y-%m-%dT%H:%M:00Z'), frames=fr)) + ';')
open(f'{OUT}/live_test.txt', 'w').write('\n'.join(logs)); print('\n'.join(logs))
