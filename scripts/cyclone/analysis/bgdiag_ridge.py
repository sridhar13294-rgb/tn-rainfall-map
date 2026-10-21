# copy of the background diagnostics used by the cyclone study (ridge, highs, steering)
"""Steering-background diagnostics that need only winds, so ERA5 and the forecasts are measured the same way.
ridge(u, lats, lons): latitude where the wind turns from easterly (south) to westerly (north) - the subtropical
ridge axis - averaged over 82-92E.  anticyclone(u, v): centre of the clockwise circulation on that axis (v changes
from southerly to northerly going east).  trough: 500 hPa relative vorticity over 22-30N, 66-80E (positive =
westerly trough / western disturbance over NW India).  sw: mean v500 over 18-26N, 84-92E (positive = southerly flow
ahead of a trough, which turns storms north).  steer: deep-layer (850/500/200 weighted 0.4/0.4/0.2) wind in a
2-6 deg ring around the storm, km/h east and north."""
import numpy as np
from scipy import ndimage as nd
def _sub(lats, lons, la0, la1, lo0, lo1):
    return (lats >= la0) & (lats <= la1), (lons >= lo0) & (lons <= lo1)
def ridge(u, lats, lons, lo0=82, lo1=92, la0=6, la1=30):
    us = nd.uniform_filter(np.nan_to_num(u), 3)
    J, I = _sub(lats, lons, la0, la1, lo0, lo1); la = lats[J]; out = []
    for i in np.where(I)[0]:
        col = us[J, i]
        for k in range(len(col) - 1):
            if col[k] < 0 <= col[k + 1]:
                f = -col[k] / (col[k + 1] - col[k]); out.append(la[k] + f * (la[k + 1] - la[k])); break
    return float(np.median(out)) if out else None
def anticyclone(u, v, lats, lons, lo0=72, lo1=104, la0=6, la1=30):
    """lon/lat of the ridge-axis point where v turns from + (west) to - (east), searching west to east;
    returns the strongest such sign change (largest v drop)."""
    us = nd.uniform_filter(np.nan_to_num(u), 3); vs = nd.uniform_filter(np.nan_to_num(v), 3)
    J, I = _sub(lats, lons, la0, la1, lo0, lo1); la = lats[J]
    axis = []
    for i in np.where(I)[0]:
        col = us[J, i]; jj = None
        for k in range(len(col) - 1):
            if col[k] < 0 <= col[k + 1]: jj = np.where(J)[0][k]; break
        axis.append((lons[i], jj, vs[jj, i] if jj is not None else np.nan))
    best = None
    for a, b in zip(axis, axis[1:]):
        if np.isfinite(a[2]) and np.isfinite(b[2]) and a[2] > 0 >= b[2]:
            drop = a[2] - b[2]
            if best is None or drop > best[0]: best = (drop, (a[0] + b[0]) / 2, lats[a[1]])
    return (float(best[1]), float(best[2])) if best else None
def vort(u, v, lats, lons):
    dy = (lats[1] - lats[0]) * 111e3; dx = dy * np.cos(np.radians(lats))[:, None]
    return (np.gradient(v, axis=1) / dx - np.gradient(u, axis=0) / dy) * 1e5
def box(x, lats, lons, la0, la1, lo0, lo1):
    J, I = _sub(lats, lons, la0, la1, lo0, lo1); return float(np.nanmean(x[np.ix_(J, I)]))
def trough(u5, v5, lats, lons):
    return box(nd.uniform_filter(np.nan_to_num(vort(u5, v5, lats, lons)), 3), lats, lons, 22, 30, 66, 80)
def sw(v5, lats, lons):
    return box(v5, lats, lons, 18, 26, 84, 92)
def steer(U, V, lats, lons, la, lo):
    """U, V: dict level -> 2-D field (m/s). Returns (east, north) km/h."""
    LA, LO = np.meshgrid(lats, lons, indexing='ij')
    d = np.hypot(LA - la, (LO - lo) * np.cos(np.radians(la))); m = (d >= 2) & (d <= 6)
    if not m.any(): return None
    w = {850: 0.4, 500: 0.4, 200: 0.2}
    e = sum(w[l] * np.nanmean(U[l][m]) for l in w) * 3.6; n = sum(w[l] * np.nanmean(V[l][m]) for l in w) * 3.6
    return float(e), float(n)
def high_from_wind(u, v, lats, lons, la0=12, la1=29, lo0=72, lo1=104):
    """Centre of the mid-level high from winds alone: the slackest wind where the flow turns clockwise
    (negative relative vorticity), searched over 12-29N, 72-104E. Fields should already be smoothed."""
    z = vort(u, v, lats, lons); sp = np.hypot(u, v)
    J, I = _sub(lats, lons, la0, la1, lo0, lo1)
    m = np.zeros_like(sp, bool); m[np.ix_(J, I)] = True; m &= nd.uniform_filter(z, 5) < 0
    if not m.any(): return None
    s = np.where(m, sp, np.inf); j, i = np.unravel_index(np.argmin(s), s.shape)
    return float(lons[i]), float(lats[j])
def ridge_z(z, lats, lons, lo0, lo1, la0=8, la1=30):
    """Ridge-axis latitude from heights: latitude of the highest 500 hPa height at each longitude, median over the band."""
    zs = nd.uniform_filter(z, 3); J, I = _sub(lats, lons, la0, la1, lo0, lo1); la = lats[J]
    return float(np.median([la[np.argmax(zs[J, i])] for i in np.where(I)[0]]))
def highs(z, lats, lons, la0=8, la1=31, lo0=64, lo1=106, size=5):
    """Closed highs: local maxima of smoothed height inside the box (not on its edge). [(lon, lat, height)]"""
    zs = nd.uniform_filter(z, 3); mx = nd.maximum_filter(zs, size=size); out = []
    for j, i in np.argwhere((zs >= mx - 1e-6)):
        if la0 < lats[j] < la1 and lo0 < lons[i] < lo1 and 0 < j < len(lats) - 1 and 0 < i < len(lons) - 1:
            out.append((float(lons[i]), float(lats[j]), float(zs[j, i])))
    return sorted(out)
def wd(v5, lats, lons):
    """Westerly-trough index: southerly minus northerly flow either side of 77E at 24-30N (m/s). Positive = a trough
    near 75-80E (western disturbance) with southerlies ahead of it."""
    return box(v5, lats, lons, 24, 30, 79, 89) - box(v5, lats, lons, 24, 30, 66, 76)
