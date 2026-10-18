"""Figures for one event: track + rain, the week-before maps (low level and upper level), Hovmoller diagrams."""
import json, os, sys, datetime as dt, numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, BoundaryNorm
from scipy import ndimage as nd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
INK, INK2, MUTED, GRID, SURF = '#0b0b0b', '#52514e', '#898781', '#e1e0d9', '#fcfcfb'
BLUE = ['#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#184f95', '#0d366b']
DIV = LinearSegmentedColormap.from_list('div', ['#0d366b', '#2a78d6', '#86b6ef', '#f0efec', '#f2a3a2', '#e34948', '#8f1d1d'])
DIVR = LinearSegmentedColormap.from_list('divr', ['#8f1d1d', '#e34948', '#f2a3a2', '#f0efec', '#86b6ef', '#2a78d6', '#0d366b'])
plt.rcParams.update({'figure.facecolor': SURF, 'axes.facecolor': SURF, 'savefig.facecolor': SURF, 'text.color': INK, 'axes.labelcolor': INK2,
                     'xtick.color': MUTED, 'ytick.color': MUTED, 'axes.edgecolor': '#c3c2b7', 'font.size': 9, 'font.family': 'DejaVu Sans',
                     'axes.titlesize': 9.5, 'axes.titleweight': 'bold', 'axes.titlelocation': 'left'})
def coast(ax, box, lw=0.6, c='#52514e'):
    for ring in LAND:
        a = np.array(ring)
        if a[:, 0].max() < box[2] - 1 or a[:, 0].min() > box[3] + 1 or a[:, 1].max() < box[0] - 1 or a[:, 1].min() > box[1] + 1: continue
        ax.plot(a[:, 0], a[:, 1], color=c, lw=lw, zorder=4)
    ax.set_xlim(box[2], box[3]); ax.set_ylim(box[0], box[1]); ax.set_aspect(1 / np.cos(np.radians((box[0] + box[1]) / 2)))
    ax.tick_params(labelsize=7, length=2)
def daily(E, key, d):
    ks = [k for k, t in enumerate(E.times) if t.date() == d]
    return np.nanmean([E.f[key][k] for k in ks], 0) if ks else None
def clim_d(C, key, d):
    return C.at(key, dt.datetime(d.year, d.month, d.day, 12))
def lagname(n): return 'rain day' if n == 0 else (f'{-n} day before' if n == -1 else (f'{-n} days before' if n < 0 else f'{n} day after'))
def fig_track(E, rows, P, out, label):
    box = (0, 22, 66, 98)
    fig, ax = plt.subplots(figsize=(6.8, 5.6)); coast(ax, box)
    rain = tnsmart((E.day + dt.timedelta(days=1)).isoformat())
    if rain:
        v = np.array([[ST[k]['lon'], ST[k]['lat'], x] for k, x in rain.items() if x >= 20])
        if len(v):
            v = v[np.argsort(v[:, 2])]
            sc = ax.scatter(v[:, 0], v[:, 1], c=v[:, 2], s=5 + v[:, 2] / 10, cmap=LinearSegmentedColormap.from_list('b', BLUE), vmin=20, vmax=400, zorder=5, lw=0)
            cb = plt.colorbar(sc, ax=ax, shrink=.65, pad=.02); cb.set_label('TN SMART rain on the rain day (mm)', color=INK2); cb.ax.tick_params(labelsize=7)
    elif E.rain_days:
        d = (E.day + dt.timedelta(days=1)).isoformat()
        if d in E.rain_days:
            cf = ax.contourf(E.lon, E.lat, E.rain[E.rain_days.index(d)], levels=[20, 50, 100, 200, 400], cmap=LinearSegmentedColormap.from_list('b', BLUE[1:]), extend='max', zorder=2, alpha=.9)
            cb = plt.colorbar(cf, ax=ax, shrink=.65, pad=.02); cb.set_label('ERA5 rain on the rain day (mm)', color=INK2)
    OT = origin_track(E, P)
    if OT:
        ks = sorted(OT); x = [OT[k][1] for k in ks]; y = [OT[k][0] for k in ks]
        ax.plot(x, y, '-', color='#e34948', lw=1.8, zorder=6)
        for k in ks:
            t = E.times[k]
            ax.plot(OT[k][1], OT[k][0], 'o', color='#e34948' if t.hour == 0 else SURF, ms=5 if t.hour == 0 else 3.5, zorder=7, mec='#e34948', mew=1)
            if t.hour == 0: ax.annotate(f"{t:%d %b}", (OT[k][1], OT[k][0]), xytext=(5, 3), textcoords='offset points', fontsize=7.5, color=INK, zorder=8)
    ax.plot(P['lon'], P['lat'], '*', color=INK, ms=11, zorder=9, mec=SURF); ax.annotate('heaviest rain', (P['lon'], P['lat']), xytext=(8, 6), textcoords='offset points', fontsize=7.5, color=INK, fontweight='bold')
    ax.set_title(f'{label}: where the circulation came from\n(centre of spin at 1.5 km; filled dots 05:30 IST, open dots 17:30 IST)', fontsize=9.5)
    ax.grid(color=GRID, lw=.5); fig.savefig(out, dpi=140, bbox_inches='tight'); plt.close(fig)
def fig_low(E, C, P, rows, out, label, lags=(-7, -5, -3, -2, -1, 0)):
    """The week before at ~1.5 km: winds (lines, thicker = stronger) over water vapour above/below normal; red rings = strong spin."""
    fig, axs = plt.subplots(3, 2, figsize=(9.2, 11.6), gridspec_kw=dict(wspace=.08, hspace=.16)); b1 = (0, 24, 66, 98)
    for ax, n in zip(axs.ravel(), lags):
        d = E.day + dt.timedelta(days=n); pw = daily(E, 'tcwv', d)
        if pw is None: ax.set_visible(False); continue
        cf = ax.contourf(E.lon, E.lat, pw - clim_d(C, 'tcwv', d), levels=[-25, -15, -8, -3, 3, 8, 15, 25], cmap=DIVR, extend='both', zorder=1)
        u, v = daily(E, 'u850', d), daily(E, 'v850', d); sp = np.hypot(u, v)
        ax.streamplot(E.lon, E.lat, u, v, color=INK, linewidth=0.3 + sp / 22, density=1.1, arrowsize=.6, zorder=3)
        vo = nd.gaussian_filter(np.nan_to_num(daily(E, 'vo850', d)), 2); ax.contour(E.lon, E.lat, vo, levels=[5, 10, 20], colors='#e34948', linewidths=[1, 1.6, 2.2], zorder=4)
        coast(ax, b1); ax.plot(P['lon'], P['lat'], '*', color='#eda100', ms=13, zorder=9, mec=INK, mew=.6)
        ax.set_title(f"{d:%a %d %b} · {lagname(n)}", fontsize=10)
        if ax not in axs[:, 0]: ax.set_yticklabels([])
        if ax not in axs[-1]: ax.set_xticklabels([])
    cb = fig.colorbar(cf, ax=axs, orientation='horizontal', fraction=.025, pad=.04, aspect=45)
    cb.set_label('water vapour in the air column vs normal (mm): blue = wetter.  Red rings: spin at 1.5 km.  Star: heaviest rain', color=INK2, fontsize=9)
    fig.suptitle(f'{label}: winds at 1.5 km and moisture, the week before', x=.125, y=.915, ha='left', fontsize=11.5, fontweight='bold')
    fig.savefig(out, dpi=125, bbox_inches='tight'); plt.close(fig)
def fig_up(E, C, P, rows, out, label, lags=(-7, -5, -3, -2, -1, 0)):
    """The week before at 5.8 km (500 hPa heights vs normal: troughs blue, ridges red) with the 12 km jet (violet)."""
    fig, axs = plt.subplots(3, 2, figsize=(9.2, 9.6), gridspec_kw=dict(wspace=.06, hspace=.2)); b2 = (0, 40, 50, 110)
    for ax, n in zip(axs.ravel(), lags):
        d = E.day + dt.timedelta(days=n); z = daily(E, 'z500', d)
        if z is None: ax.set_visible(False); continue
        cf = ax.contourf(E.lon, E.lat, z - clim_d(C, 'z500', d), levels=[-120, -80, -50, -25, -10, 10, 25, 50, 80, 120], cmap=DIV, extend='both', zorder=1)
        cs = ax.contour(E.lon, E.lat, z / 10, levels=np.arange(560, 600, 2), colors=INK2, linewidths=.45, zorder=2); ax.clabel(cs, fontsize=6, fmt='%d')
        jet = np.hypot(daily(E, 'u200', d), daily(E, 'v200', d)); ax.contour(E.lon, E.lat, jet, levels=[35, 50, 65], colors='#6250d6', linewidths=[.9, 1.6, 2.4], zorder=3)
        coast(ax, b2, lw=.45); ax.plot(P['lon'], P['lat'], '*', color='#eda100', ms=12, zorder=9, mec=INK, mew=.6)
        ax.set_title(f"{d:%a %d %b} · {lagname(n)}", fontsize=10)
        if ax not in axs[:, 0]: ax.set_yticklabels([])
        if ax not in axs[-1]: ax.set_xticklabels([])
    cb = fig.colorbar(cf, ax=axs, orientation='horizontal', fraction=.03, pad=.05, aspect=45)
    cb.set_label('5.8 km height vs normal (m): blue = trough (western disturbance), red = ridge.  Violet: jet stream at 12 km, 35/50/65 m/s', color=INK2, fontsize=9)
    fig.suptitle(f'{label}: the upper air, the week before', x=.125, y=.93, ha='left', fontsize=11.5, fontweight='bold')
    fig.savefig(out, dpi=125, bbox_inches='tight'); plt.close(fig)
def fig_hov(E, C, P, out, label):
    days = sorted({t.date() for t in E.times}); T = [t for t in E.times]
    fig, axs = plt.subplots(1, 3, figsize=(13, 5.6), gridspec_kw=dict(wspace=.42))
    yt = np.arange(len(T)); ylab = [t.strftime('%d %b') if t.hour == 0 else '' for t in T]
    def setup(ax, title, xl):
        ax.set_yticks(yt[::4]); ax.set_yticklabels([l for l in ylab[::4]], fontsize=7); ax.invert_yaxis(); ax.set_title(title, fontsize=9); ax.set_xlabel(xl, fontsize=8)
        k0 = [k for k, t in enumerate(T) if t.date() == E.day and t.hour == 0]
        if k0: ax.axhline(k0[0], color=INK, lw=.8, ls='--')
    # (a) low-level spin moving along the band of the rain centre
    la0, la1 = max(1.0, P['lat'] - 8), P['lat'] + 4; js = (E.lon >= 70) & (E.lon <= 105); band = (E.lat >= la0) & (E.lat <= la1)
    H = np.array([np.nanmax(nd.gaussian_filter(np.nan_to_num(E.f['vo850'][k]), 1)[band][:, js], 0) for k in range(len(T))])
    cf = axs[0].contourf(E.lon[js], yt, H, levels=[0, 3, 6, 10, 15, 25, 40], cmap=LinearSegmentedColormap.from_list('r', ['#fcfcfb', '#f2a3a2', '#e34948', '#8f1d1d']), extend='max')
    axs[0].axvline(P['lon'], color=INK, lw=.8); setup(axs[0], f'Spin at 1.5 km\n({la0:.0f}–{la1:.0f}°N)', 'longitude °E')
    plt.colorbar(cf, ax=axs[0], shrink=.8, pad=.02).set_label('x1e-5 per second', color=INK2)
    # (b) western disturbances: 500 hPa height anomaly 27.5-35N
    js2 = (E.lon >= 50) & (E.lon <= 105); band2 = (E.lat >= 27.5) & (E.lat <= 35)
    H2 = np.array([np.nanmean((E.f['z500'][k] - C.at('z500', T[k]))[band2][:, js2], 0) for k in range(len(T))])
    cf2 = axs[1].contourf(E.lon[js2], yt, H2, levels=[-120, -80, -50, -25, -10, 10, 25, 50, 80, 120], cmap=DIV, extend='both')
    axs[1].axvline(P['lon'], color=INK, lw=.8); setup(axs[1], 'Western disturbances\n(5.8 km heights vs normal, 27–35°N)', 'longitude °E')
    plt.colorbar(cf2, ax=axs[1], shrink=.8, pad=.02).set_label('m (blue = trough)', color=INK2)
    # (c) moisture and rising air near the rain centre: PW anomaly along latitude of the rain
    js3 = (E.lon >= 70) & (E.lon <= 100); band3 = (E.lat >= P['lat'] - 1.5) & (E.lat <= P['lat'] + 1.5)
    H3 = np.array([np.nanmean((E.f['tcwv'][k] - C.at('tcwv', T[k]))[band3][:, js3], 0) for k in range(len(T))])
    cf3 = axs[2].contourf(E.lon[js3], yt, H3, levels=[-25, -15, -8, -3, 3, 8, 15, 25], cmap=DIVR, extend='both')
    axs[2].axvline(P['lon'], color=INK, lw=.8); setup(axs[2], f'Water vapour vs normal\n({P["lat"] - 1.5:.0f}–{P["lat"] + 1.5:.0f}°N)', 'longitude °E')
    plt.colorbar(cf3, ax=axs[2], shrink=.8, pad=.02).set_label('mm above normal', color=INK2)
    fig.suptitle(f'{label}: how things travelled. Time runs down; dashed line = rain day; solid line = where the rain fell', x=.1, y=1.02, ha='left', fontsize=10.5, fontweight='bold')
    fig.savefig(out, dpi=125, bbox_inches='tight'); plt.close(fig)
