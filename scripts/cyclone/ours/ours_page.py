"""Build the live ensemble page: python ours_page.py ENS_JSON OUT_HTML [--site SITE_HTML]
With --site it also writes the website version (site/cyclone.html: the site's own header, tabs and dark look).
Appends this run to data/cyclone/ours/live_history.json (one row per analysis cycle)."""
import sys, os, json, datetime as dt, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SEGS = ['Sri Lanka', 'south TN', 'north TN', 'south AP', 'central AP', 'north AP', 'Odisha/WB', 'Bangladesh/Myanmar', 'no landfall']
NICE = ['Sri Lanka', 'south TN', 'north TN', 'south AP', 'central AP', 'north AP', 'Odisha/WB', 'Bangladesh/Myanmar', 'no landfall']
E = json.load(open(sys.argv[1])); t0 = dt.datetime.fromisoformat(E['run'])
H = lambda s: round((dt.datetime.fromisoformat(s) - t0).total_seconds() / 3600, 1)
ist = lambda d: (d + dt.timedelta(hours=5.5))
label = f"{t0:%HZ %-d %b} ({ist(t0):%-d %b %H:%M} IST)"
runs = []
for r in E['runs']:
    p = []
    for q in r['pts']: p += [round(q[1], 2), round(q[2], 2), round(q[3])]
    lf = r['lf']; g = r['gen']
    runs.append([SEGS.index(r['seg']), [lf['lat'], lf['lon'], H(lf['t']), lf['wind']] if lf else None, r['levels'], p,
                 [g['lat'], g['lon'], H(g['t'])] if g else None, round(r['vmax'], 1)])
land = []          # full-resolution Natural Earth 1:50m coast, clipped to 66-106E 0-30N (points outside are pulled onto the box edge)
BX = (66.0, 106.0, 0.0, 30.0)
for ring in json.load(open(os.path.join(REPO, 'data', 'cyclone', 'land.json'))):
    a = np.array(ring, float)
    if a[:, 0].max() < BX[0] or a[:, 0].min() > BX[1] or a[:, 1].min() > BX[3] or a[:, 1].max() < BX[2] or len(a) < 4: continue
    a[:, 0] = np.clip(a[:, 0], BX[0], BX[1]); a[:, 1] = np.clip(a[:, 1], BX[2], BX[3])
    out = []
    for x, y in a:
        q = [round(float(x), 2), round(float(y), 2)]
        if not out or q != out[-1]: out.append(q)
    if len(out) > 3: land.append(out)
METHOD = sys.argv[sys.argv.index('--method') + 1] if '--method' in sys.argv else 'past'
hp = os.path.join(REPO, 'data', 'cyclone', 'ours', 'live_history.json' if METHOD == 'past' else f'live_history_{METHOD}.json')
hist = json.load(open(hp)) if os.path.exists(hp) else []
c0 = E['runs'][0]; lf0 = c0['lf']
row = dict(run=E['run'], label=label, shares=E['summary']['shares'],
           control=(f"{c0['seg']} {lf0['lat']:.1f}N, {ist(dt.datetime.fromisoformat(lf0['t'])):%-d %b %H:%M} IST, {round(lf0['wind'])} kt" if lf0 else 'no landfall'))
hist = [h for h in hist if h['run'] != E['run']] + [row]; hist.sort(key=lambda h: h['run'])
json.dump(hist, open(hp, 'w'), indent=1)
obs = E['obs']
for k in ('bay', 'arabian', 'sw_bay'):
    for kk, vv in list(obs[k].items()):
        if isinstance(vv, float): obs[k][kk] = round(vv, 2)
def clean(x):
    if isinstance(x, float): return None if x != x or x in (float('inf'), float('-inf')) else x
    if isinstance(x, dict): return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [clean(v) for v in x]
    return x
E = clean(E); obs = E['obs']
D = dict(t0=E['run'], run_label=label, obs=obs, analogs=E['analogs'], factors=E['factors'], runs=runs, land=land, hist=hist)
css = open(os.path.join(HERE, 'style.css.part')).read(); body = open(os.path.join(HERE, 'body.html.part')).read()
if METHOD == 'inputs':
    i = body.index('<section>\n  <h2>How the runs are made</h2>'); body = body[:i] + open(os.path.join(HERE, 'method_inputs.html.part')).read()
    body = body.replace('<h1>Our own ensemble: where the coming Bay storm could cross the coast</h1>', '<h1>Our own ensemble, input-driven: where today’s winds, changed by the inputs, take the storm</h1>')
    body = body.replace('Each line starts at the observed seedling', 'Each line starts at the observed seedling')
if METHOD == 'bve':
    i = body.index('<section>\n  <h2>How the runs are made</h2>'); body = body[:i] + open(os.path.join(HERE, 'method_bve.html.part')).read()
    body = body.replace('<h1>Our own ensemble: where the coming Bay storm could cross the coast</h1>', '<h1>Our own ensemble, physics version: where today’s winds and the inputs alone would take the storm</h1>')
js = open(os.path.join(HERE, 'app.js.part')).read()
html = ('<title>Bay Storm Scenarios</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=Source+Sans+3:wght@400;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">\n'
        + css + body + '\n<script id="data" type="application/json">' + json.dumps(D, separators=(',', ':'), default=str).replace('</', '<\\/') + '</script>\n<script>\n' + js + '</script>\n')
open(sys.argv[2], 'w').write(html); print('page', len(html) // 1000, 'kB', label)
if '--site' in sys.argv:
    out = sys.argv[sys.argv.index('--site') + 1]
    scss = open(os.path.join(HERE, 'site_style.css.part')).read()
    head = ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="color-scheme" content="dark"><meta name="theme-color" content="#0b1522">'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><title>Tamil Nadu cyclone ensemble</title>'
            '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link href="https://fonts.googleapis.com/css2?family=Anek+Latin:wdth,wght@75..125,300..800&family=Anek+Tamil:wght@600..800&display=swap" rel="stylesheet">')
    nav = ('<header class="top"><a class="brand" href="index.html"><span class="ta" lang="ta">மழை</span><h1><b>Tamil Nadu</b> cyclone ensemble</h1></a>'
           '<nav class="tabs"><a href="index.html">Rainfall</a><a href="forecast.html">Forecast</a><a href="satradar.html">Sat radar</a><a class="on" href="cyclone.html">Cyclone</a></nav></header>'
           '<div class="warnx"><b>Experimental.</b> Our own ensemble, built from observed data and past storms without any forecast model. Updated every 6 hours. Not an official forecast: follow IMD for warnings.</div>')
    sb = body.replace('<div class="wrap">', '<div class="wrap">' + nav, 1)
    shtml = head + scss + '</head><body>' + sb + '\n<script id="data" type="application/json">' + json.dumps(D, separators=(',', ':'), default=str).replace('</', '<\\/') + '</script>\n<script>\n' + js + '</script>\n</body></html>\n'
    open(out, 'w').write(shtml); print('site page', len(shtml) // 1000, 'kB ->', out)
