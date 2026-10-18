"""Average picture of the NE-monsoon events at 7, 5, 3, 1 days before and on the rain day (anomalies from normal), and the
lag profile of the key measures across all events."""
import json, os, sys, datetime as dt, numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
import figs
from figs import coast, DIV, DIVR, INK, INK2, SURF
HERE = os.path.dirname(os.path.abspath(__file__))
from run import DAYS
EV = [(a, dt.date.fromisoformat(b)) for a, b in DAYS.items() if dt.date.fromisoformat(b).month in (10, 11, 12)]
LAGS = (-7, -5, -3, -1, 0)
acc = {n: {k: [] for k in ('pw', 'u850', 'v850', 'z500', 'u200', 'v200', 'jet', 'vo850', 'msl')} for n in LAGS}
C = None
for name, D in EV:
    E = Event(name, D)
    if C is None: C = ClimDaily(E.lat, E.lon)
    for n in LAGS:
        d = D + dt.timedelta(days=n); t = dt.datetime(d.year, d.month, d.day, 12)
        g = lambda k: figs.daily(E, k, d)
        acc[n]['pw'].append(g('tcwv') - C.at('tcwv', t)); acc[n]['z500'].append(g('z500') - C.at('z500', t)); acc[n]['msl'].append(g('msl') - C.at('msl', t))
        acc[n]['u850'].append(g('u850') - C.at('u850', t)); acc[n]['v850'].append(g('v850') - C.at('v850', t))
        acc[n]['u200'].append(g('u200')); acc[n]['v200'].append(g('v200')); acc[n]['jet'].append(np.hypot(g('u200'), g('v200')))
        acc[n]['vo850'].append(g('vo850'))
    print(name, flush=True)
lat, lon = E.lat, E.lon
M = {n: {k: np.nanmean(v, 0) for k, v in acc[n].items()} for n in LAGS}
# share of events with water vapour above normal at each point (agreement)
AG = {n: np.mean(np.array(acc[n]['pw']) > 3, 0) for n in LAGS}
np.savez_compressed(os.path.join(HERE, 'composite.npz'), lat=lat, lon=lon, **{f'{k}_{n}': M[n][k] for n in LAGS for k in M[n]}, **{f'agree_{n}': AG[n] for n in LAGS})
TN = (11.0, 79.5)
fig, axs = plt.subplots(len(LAGS), 2, figsize=(9.4, 15.5), gridspec_kw=dict(wspace=.12, hspace=.22))
for r_, n in enumerate(LAGS):
    ax = axs[r_, 0]
    cf = ax.contourf(lon, lat, M[n]['pw'], levels=[-12, -8, -5, -2, 2, 5, 8, 12], cmap=DIVR, extend='both')
    ax.quiver(lon[::4], lat[::4], M[n]['u850'][::4, ::4], M[n]['v850'][::4, ::4], scale=60, width=.004, color=INK)
    ax.contour(lon, lat, AG[n], levels=[.75], colors='#6250d6', linewidths=1.4)
    coast(ax, (0, 24, 66, 98)); ax.set_title(('Rain day' if n == 0 else ('1 day before' if n == -1 else f'{-n} days before')) + ' · low level', fontsize=10)
    ax = axs[r_, 1]
    cf2 = ax.contourf(lon, lat, M[n]['z500'], levels=[-60, -40, -25, -15, -5, 5, 15, 25, 40, 60], cmap=DIV, extend='both')
    ax.contour(lon, lat, M[n]['jet'], levels=[35, 45], colors='#6250d6', linewidths=[1, 2])
    ax.contour(lon, lat, M[n]['u200'], levels=[0], colors=INK, linewidths=1.2, linestyles='--')
    coast(ax, (0, 40, 50, 110), lw=.45); ax.set_title(('Rain day' if n == 0 else ('1 day before' if n == -1 else f'{-n} days before')) + ' · upper air', fontsize=10)
    for a in axs[r_]: a.plot(80.2, 13.0, 'o', color='#eda100', ms=5, mec=INK, mew=.5); a.plot(78.1, 8.8, 'o', color='#eda100', ms=5, mec=INK, mew=.5)
fig.colorbar(cf, ax=axs[:, 0], orientation='horizontal', fraction=.015, pad=.03, aspect=30).set_label('Left: water vapour vs normal (mm).\nArrows: 1.5 km wind vs normal.\nViolet line: 3 in 4 events wetter than normal.', fontsize=8, color=INK2)
fig.colorbar(cf2, ax=axs[:, 1], orientation='horizontal', fraction=.015, pad=.03, aspect=30).set_label('Right: 5.8 km height vs normal (m): red = ridge.\nViolet: jet stream 35/45 m/s.\nDashed: where 12 km winds turn westerly.', fontsize=8, color=INK2)
fig.suptitle(f'The average big-rain event ({len(EV)} Oct–Dec events, 2000–2025)', x=.125, y=.91, ha='left', fontsize=12, fontweight='bold')
fig.savefig(os.path.join(HERE, 'out', 'composite.png'), dpi=115, bbox_inches='tight'); plt.close(fig)
print('saved')
