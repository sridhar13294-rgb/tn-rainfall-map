"""Build the live ensemble page: python ours_page.py ENS_JSON OUT_HTML
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
land = []
for ring in json.load(open(os.path.join(REPO, 'data', 'cyclone', 'land.json'))):
    a = np.array(ring)
    if a[:, 0].max() < 70 or a[:, 0].min() > 100 or a[:, 1].min() > 27 or a[:, 1].max() < 3 or len(a) < 4: continue
    st = max(1, len(a) // 400); land.append([[round(x, 2), round(y, 2)] for x, y in a[::st]])
hp = os.path.join(REPO, 'data', 'cyclone', 'ours', 'live_history.json')
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
D = dict(t0=E['run'], run_label=label, obs=obs, analogs=E['analogs'], factors=E['factors'], runs=runs, land=land, hist=hist)
css = open(os.path.join(HERE, 'style.css.part')).read(); body = open(os.path.join(HERE, 'body.html.part')).read(); js = open(os.path.join(HERE, 'app.js.part')).read()
html = ('<title>Bay Storm Scenarios</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=Source+Sans+3:wght@400;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">\n'
        + css + body + '\n<script id="data" type="application/json">' + json.dumps(D, separators=(',', ':'), default=str).replace('</', '<\\/') + '</script>\n<script>\n' + js + '</script>\n')
open(sys.argv[2], 'w').write(html); print('page', len(html) // 1000, 'kB', label)
