"""Two maps for the doc: our model's tracks on every ensemble member, and the best analogue storms."""
import json, sys, os, datetime as dt, numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
sys.path.insert(0, '.')
LAND = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'data', 'cyclone', 'land.json')))
O = json.load(open('data/ours.json')); T = json.load(open('data/tracks.json')); C = json.load(open('data/consensus.json')); C['central'] = [c for c in C['central'] if c['h'] <= 120]; A = json.load(open('data/analogs.json'))
EXT = (76, 99, 5, 25)
LABELS = [('TAMIL\nNADU', 78.3, 11.0), ('ANDHRA\nPRADESH', 79.0, 16.2), ('ODISHA', 84.0, 20.6), ('WEST\nBENGAL', 87.4, 23.6), ('BANGLADESH', 90.1, 24.2),
          ('MYANMAR', 95.6, 21.5), ('SRI\nLANKA', 80.7, 7.6), ('Andaman\nIslands', 93.9, 11.0)]
def base(title):
    fig, ax = plt.subplots(figsize=(7.2, 6.6), dpi=150)
    ax.set_facecolor('#e8f1f8')
    for r in LAND:
        a = np.array(r)
        if a[:, 0].max() < EXT[0] - 5 or a[:, 0].min() > EXT[1] + 5 or a[:, 1].max() < EXT[2] - 5 or a[:, 1].min() > EXT[3] + 5: continue
        ax.add_patch(Polygon(a, closed=True, fc='#f3efe6', ec='#9a9486', lw=0.6, zorder=1))
    for t, x, y in LABELS:
        ax.text(x, y, t, fontsize=7.5, color='#6b665c', ha='center', va='center', zorder=2, fontweight='bold' if t.isupper() else 'normal')
    ax.plot(80.27, 13.08, 'o', ms=3.5, color='#444', zorder=6); ax.text(80.45, 13.08, 'Chennai', fontsize=7.5, va='center', color='#333', zorder=6)
    ax.set_xlim(EXT[0], EXT[1]); ax.set_ylim(EXT[2], EXT[3]); ax.set_aspect(1 / np.cos(np.radians(15)))
    ax.set_xticks(range(78, 100, 4)); ax.set_yticks(range(6, 26, 4))
    ax.set_xticklabels([f'{x}°E' for x in range(78, 100, 4)], fontsize=7.5); ax.set_yticklabels([f'{y}°N' for y in range(6, 26, 4)], fontsize=7.5)
    ax.grid(color='white', lw=0.6, zorder=0); ax.set_title(title, fontsize=10.5, loc='left', fontweight='bold')
    return fig, ax
def xy(pts): return [p['lon'] for p in pts], [p['lat'] for p in pts]
# ---- map 1: our forecast
fig, ax = base('Our track model on the 73 forecast members that form the storm')
for src, col in (('ENS', '#2f6db3'), ('GEFS', '#d9822b')):
    for r in O[src]:
        if not r: continue
        x, y = xy(r['pts']); ax.plot(x, y, color=col, lw=0.7, alpha=0.35, zorder=3)
        if r['lf']: ax.plot(r['lf']['lon'], r['lf']['lat'], 'o', ms=2.6, color=col, alpha=0.8, zorder=4)
for src, col, lab in (('HRES', '#1a7f4b', 'ECMWF main run (its own storm, not our model)'), ('GFS', '#b8323a', 'GFS main run (its own storm, not our model)')):
    t = [x for x in T[src]['tracks'] if x][0]; x, y = xy(t['pts']); ax.plot(x, y, '--', color=col, lw=1.6, zorder=5, label=lab)
cen = C['central']; x, y = xy(cen)
ax.plot(x, y, '-', color='black', lw=2.6, zorder=6, label='Our model, middle track (to 29 Oct)')
for c in cen:
    if c['h'] % 24 == 0:
        ax.plot(c['lon'], c['lat'], 'o', ms=5, mfc='white', mec='black', zorder=7)
        d = dt.datetime.fromisoformat(c['t'])
        if c['h'] <= 144: ax.text(c['lon'] + 0.35, c['lat'] - 0.15, d.strftime('%-d Oct'), fontsize=7.5, zorder=8, color='black')
g = C['genesis']; ax.plot(g['lon'], g['lat'], '*', ms=13, color='#ffd400', mec='black', zorder=8, label='Middle forming point (24 Oct)')
ax.plot([], [], color='#2f6db3', lw=1.2, label='Our model on each ECMWF ensemble member'); ax.plot([], [], color='#d9822b', lw=1.2, label='Our model on each GFS (GEFS) member')
ax.plot([], [], 'o', ms=3, color='grey', label='Dot = where that member hits the coast')
ax.legend(loc='lower right', fontsize=7, framealpha=0.92)
fig.tight_layout(); fig.savefig('data/map_ours.png'); plt.close(fig)
# ---- map 2: analogues
fig, ax = base('Closest past storms (1980–2025) and our middle track')
COL = ['#c0392b', '#8e44ad', '#2471a3', '#17a589', '#d68910', '#7f8c8d']
for r, col in zip(A['top'][:6], COL):
    t0 = dt.datetime.strptime(r['t0'], '%d %b %Y') if isinstance(r['t0'], str) else None
    P = [p for p in r['path']]
    k = next((i for i, p in enumerate(P) if (p[3] or 0) >= 17), 0)
    P = P[max(0, k - 2):]
    x = [p[2] for p in P]; y = [p[1] for p in P]
    name = r['name'].split(':')[0]; name = 'Unnamed' if name.lower() == 'unnamed' else name
    lab = f"{name} {r['season']} ({r['t0'][:6]}) → {r['land']}"
    ax.plot(x, y, '-', color=col, lw=1.9, zorder=4, label=lab)
    ax.plot(x[0], y[0], 'o', ms=4, color=col, zorder=5)
    if r['lf']: ax.plot(r['lf'][1], r['lf'][0], 's', ms=5, color=col, mec='black', mew=0.5, zorder=5)
x, y = xy(C['central']); ax.plot(x, y, '-', color='black', lw=2.8, zorder=6, label='This system: our middle track')
ax.plot(C['genesis']['lon'], C['genesis']['lat'], '*', ms=13, color='#ffd400', mec='black', zorder=7)
ax.plot([], [], 's', ms=5, color='white', mec='black', label='Square = landfall')
ax.legend(loc='lower right', fontsize=7, framealpha=0.92)
fig.tight_layout(); fig.savefig('data/map_analogs.png'); plt.close(fig)
print('ok')
