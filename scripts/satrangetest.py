"""sat-ranges branch: open the three Sat radar views in Chromium with live EUMETSAT frames, screenshot each,
and keep the frames the page fetched so an offline preview can be built."""
import base64, json, re, subprocess, time
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright
OUT = 'data/satranges'
srv = subprocess.Popen(['python', '-m', 'http.server', '8765', '-d', 'site']); time.sleep(1.5)
log, snap, latest = [], {'modes': {}}, None
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': 412, 'height': 900}, device_scale_factor=2)
    pg.on('console', lambda m: log.append(f'{m.type}: {m.text}')); pg.on('pageerror', lambda e: log.append(f'pageerror: {e}'))
    cur = {'k': None}
    def on_resp(r):
        if 'request=GetMap' in r.url and cur['k']:
            q = parse_qs(urlparse(r.url).query)
            try:
                snap['modes'].setdefault(cur['k'], {'frames': {}})['frames'][q['time'][0]] = 'data:image/png;base64,' + base64.b64encode(r.body()).decode()
            except Exception as e:
                log.append(f'body error {e}')
    pg.on('response', on_resp)
    for mode, key in (('tn', 'tn'), ('long', 'long'), ('short', 'short_Chennai')):
        cur['k'] = key; t0 = time.time()
        pg.goto(f'http://localhost:8765/satradar.html#{mode}'); pg.reload()
        pg.wait_for_function("document.getElementById('st').textContent.indexOf('Loading')<0", timeout=180000)
        log.append(f'{mode}: {time.time()-t0:.1f}s | ' + pg.inner_text('#st') + ' | ' + pg.inner_text('#cl')[:900])
        pg.screenshot(path=f'{OUT}/{mode}_page.png', full_page=True)
        pg.locator('.map').screenshot(path=f'{OUT}/{mode}_map.png')
        m = re.search(r'last picture (\d\d:\d\d)', pg.inner_text('.tl'))
    b.close()
srv.terminate()
cap = __import__('urllib.request').request.urlopen(__import__('urllib.request').request.Request('https://view.eumetsat.int/geoserver/msg_iodc/h63/ows?service=WMS&version=1.3.0&request=GetCapabilities', headers={'User-Agent': 'Mozilla/5.0'}), timeout=120).read().decode()
mm = re.search(r'<Dimension[^>]*name="time"[^>]*>([^<]*)</Dimension>', cap); snap['latest'] = mm.group(1).split('/')[1].replace('.000Z', 'Z')
open(f'{OUT}/snap.js', 'w').write('window.SATSNAP=' + json.dumps(snap) + ';')
log.append('snapshot frames: ' + json.dumps({k: len(v['frames']) for k, v in snap['modes'].items()}))
open(f'{OUT}/test.txt', 'w').write('\n'.join(log)); print('\n'.join(log))
