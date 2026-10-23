"""Stage 2, step B (prototype): a 3-D ocean of our own in JAX/numpy - a nonlinear 1.5-layer reduced-gravity ocean
(upper layer of thickness h above a deep, motionless lower layer) on the model's own grid, carrying the 24-level
temperature/salinity columns of ocean.py with it.

Why this and not a full ocean model first: see docs/stage2_ocean.md (Veros timings). For forecasts of days to weeks in
the tropics, what the SST needs from ocean dynamics is (a) the wind-driven currents and their heat transport, (b) the
up-and-down movement of the thermocline (Ekman pumping, coastal upwelling, and the Kelvin and Rossby waves that carry
thermocline changes along the equator and around the Bay of Bengal rim within days to weeks) and (c) the mixed layer.
A 1.5-layer model (the first baroclinic mode; Zebiak & Cane 1987, McCreary et al. 1993 for the Indian Ocean) gives
(a)-(b) at almost no cost; the columns give (c) and the vertical structure. Deep circulation, the Indonesian
throughflow and anything slower than a season are not represented.

GRID: Arakawa B-grid on the model nodes (good when the grid is coarser than the Rossby radius, as at T85/T170 outside the
deep tropics): h at the cell centres [X, Y]; u, v at the corners (i+1/2, j+1/2), stored at [i, j]. Corners are wet when
all four surrounding cells are sea and |lat| < lat_max (60 deg; poleward of it the layer is frozen at rest).

EQUATIONS (dt up to 1-2 h; forward-backward):
  dh/dt = -div(h u)                      (centred fluxes on the cell faces; h kept >= h_min by entrainment;
                                          weak relaxation of h towards its start, tau_h = 1 year)
  du/dt - f v = -g' dh/dx + taux / (rho0 max(h, h_tau)) - r u + A lap(u)
  dv/dt + f u = -g' dh/dy + tauy / (rho0 max(h, h_tau)) - r v + A lap(v)
  Coriolis and friction implicit (Crank-Nicolson rotation, exact per corner on the B-grid); no momentum advection.
  g' = 0.035 m s-2, r = 1/(60 days), A = 2e4 m2 s-1 (Munk layer ~100 km), h_min = 25 m, h_tau = 50 m.
  The whole wind stress acts on the layer: its transport h u contains the Ekman transport plus the geostrophic flow.

COUPLING TO THE COLUMNS (column_transports): at every face, the layer velocity u fills the column levels down to the
  face's h; on top of it the Ekman shear (Ekman transport M in the top h_ek = 40 m, -M spread over the rest of the layer)
  puts the drift where it belongs. These transports are handed to currents.step(..., q=...), which works out the
  vertical velocity from continuity (so the levels at the thermocline move up and down with h) and advects T and S;
  below the layer water enters/leaves the 300 m column through its bottom (the deep lower layer of the model).

INITIAL STATE: h = depth of the 20 C isotherm of the start profiles (WOA23 or RTOFS, via ocean.profile_from_clim;
  clipped to 40-300 m; 300 m where the water is colder than 20 C), currents in geostrophic balance with it (1/f
  regularised near the equator), then optionally a spin-up with climatological winds (skill_rgo.py)."""
import math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import currents as cu

OMEGA, R = 7.292e-5, 6.371e6
PRM = dict(gp=0.035, r=1.0 / (60 * 86400.0), A=2e4, h_min=25.0, h_tau=50.0, tau_h=365 * 86400.0, lat_max=60.0,
           h_ek=40.0, r_ek=1.0 / (2 * 86400.0), f_eq=2 * OMEGA * math.sin(math.radians(2.5)), rho0=1025.0)


def make_geom(lat2d, lon2d, sea, periodic=None, lat_max=60.0):
    """B-grid metrics (numpy, once). lat2d, lon2d [X, Y] as on the model nodes."""
    LA = np.asarray(lat2d, float); LO = np.asarray(lon2d, float); X, Y = LA.shape
    lat = LA[0]; lon = LO[:, 0]; dl = np.radians(abs(lon[1] - lon[0]))
    if periodic is None: periodic = abs(abs(lon[1] - lon[0]) * X - 360.0) < 1e-3
    phi = np.radians(lat); mid = 0.5 * (phi[1:] + phi[:-1])
    edges = np.clip(np.concatenate([[phi[0] - (mid[0] - phi[0])], mid, [phi[-1] + (phi[-1] - mid[-1])]]), -math.pi / 2, math.pi / 2)
    area = np.broadcast_to(R * R * dl * np.abs(np.sin(edges[1:]) - np.sin(edges[:-1])), (X, Y)).copy()
    sy = float(np.sign(lat[-1] - lat[0]))
    phc = np.append(mid, mid[-1])                                                     # corner latitude (j + 1/2)
    dxc = np.broadcast_to(R * np.cos(phc) * dl, (X, Y)).copy()
    dyc = np.broadcast_to(R * np.abs(np.append(np.diff(phi), np.diff(phi)[-1])), (X, Y)).copy()
    LE = np.broadcast_to(R * np.abs(np.diff(edges)), (X, Y)).copy()                 # east face length
    LN = np.broadcast_to(R * np.cos(edges[1:Y + 1]) * dl, (X, Y)).copy()            # face to j+1
    sea = np.asarray(sea, bool) & (np.abs(LA) < lat_max + 5)
    nb = lambda a, s, ax: np.roll(a, -s, axis=ax)
    wet = sea & nb(sea, 1, 0) & nb(sea, 1, 1) & nb(nb(sea, 1, 0), 1, 1) & (np.abs(np.degrees(np.broadcast_to(phc, (X, Y)))) < lat_max)
    wet[:, -1] = False
    if not periodic: wet[-1, :] = False
    openE = sea & nb(sea, 1, 0); openN = sea & nb(sea, 1, 1); openN[:, -1] = False
    if not periodic: openE[-1, :] = False
    fc = 2 * OMEGA * np.sin(np.broadcast_to(phc, (X, Y)))
    return dict(area=area, dxc=dxc, dyc=dyc, LE=LE, LN=LN, sy=sy, sea=sea, wet=wet, openE=openE, openN=openN, fc=fc,
                periodic=bool(periodic), lat=LA, lon=LO)


def _c2corner(a, xp):
    """cell-centre field -> corners (mean of the four cells)."""
    b = a + xp.roll(a, -1, axis=0); return 0.25 * (b + xp.roll(b, -1, axis=1))


def face_velocities(st, g, xp=np):
    """normal velocity on the east faces (towards i+1) and on the j+1 faces (towards j+1) of every cell."""
    u, v = st['u'], st['v']
    uE = 0.5 * (u + xp.roll(u, 1, axis=1)); vN = g['sy'] * 0.5 * (v + xp.roll(v, 1, axis=0))
    return xp.where(g['openE'], uE, 0.0), xp.where(g['openN'], vN, 0.0)


def step(st, taux, tauy, g, dt, prm=None, xp=np):
    """one forward-backward step. st = dict(h [X, Y] m, u, v [X, Y] m s-1 at the corners, h_ref [X, Y]); taux, tauy at
    the cell centres (N m-2)."""
    P = dict(PRM); P.update(prm or {})
    h, u, v = st['h'], st['u'], st['v']; sea, wet = g['sea'], g['wet']
    # continuity
    uE, vN = face_velocities(st, g, xp)
    hE = 0.5 * (h + xp.roll(h, -1, axis=0)); hN = 0.5 * (h + xp.roll(h, -1, axis=1))
    FE = uE * hE * g['LE']; FN = vN * hN * g['LN']
    div = (FE - xp.roll(FE, 1, axis=0) + FN - xp.roll(FN, 1, axis=1)) / g['area']
    hn = h - dt * div + dt * (st['h_ref'] - h) / P['tau_h']
    hn = xp.where(sea, xp.maximum(hn, P['h_min']), h)
    # momentum at the corners
    hip = xp.roll(hn, -1, axis=0); hjp = xp.roll(hn, -1, axis=1); hpp = xp.roll(hip, -1, axis=1)
    dhdx = 0.5 * ((hip - hn) + (hpp - hjp)) / g['dxc']; dhdy = g['sy'] * 0.5 * ((hjp - hn) + (hpp - hip)) / g['dyc']
    hc = 0.25 * (hn + hip + hjp + hpp)
    tx, ty = _c2corner(xp.where(sea, taux, 0.0), xp), _c2corner(xp.where(sea, tauy, 0.0), xp)
    lap = lambda a: ((xp.roll(a, -1, axis=0) - 2 * a + xp.roll(a, 1, axis=0)) / g['dxc'] ** 2
                     + (xp.roll(a, -1, axis=1) - 2 * a + xp.roll(a, 1, axis=1)) / g['dyc'] ** 2)
    us = u + dt * (-P['gp'] * dhdx + tx / (P['rho0'] * xp.maximum(hc, P['h_tau'])) + P['A'] * lap(u))
    vs = v + dt * (-P['gp'] * dhdy + ty / (P['rho0'] * xp.maximum(hc, P['h_tau'])) + P['A'] * lap(v))
    a = 0.5 * g['fc'] * dt; b = 1.0 + P['r'] * dt
    ru, rv = us + a * v, vs - a * u                                                     # Crank-Nicolson Coriolis
    det = b * b + a * a
    un = (b * ru + a * rv) / det; vn = (b * rv - a * ru) / det
    return dict(st, h=hn, u=xp.where(wet, un, 0.0), v=xp.where(wet, vn, 0.0))


def init_state(g, h0, geostrophic=True, prm=None):
    """h0 [X, Y] (m) -> state at rest or in geostrophic balance (numpy)."""
    P = dict(PRM); P.update(prm or {}); h = np.where(g['sea'], h0, P['h_min'])
    st = dict(h=h.astype(float), u=np.zeros_like(h, float), v=np.zeros_like(h, float), h_ref=h.astype(float))
    if geostrophic:
        hip = np.roll(h, -1, 0); hjp = np.roll(h, -1, 1); hpp = np.roll(hip, -1, 1)
        dhdx = 0.5 * ((hip - h) + (hpp - hjp)) / g['dxc']; dhdy = g['sy'] * 0.5 * ((hjp - h) + (hpp - hip)) / g['dyc']
        fi = g['fc'] / (g['fc'] ** 2 + P['f_eq'] ** 2)
        st['u'] = np.where(g['wet'], np.clip(-P['gp'] * fi * dhdy, -1.5, 1.5), 0.0); st['v'] = np.where(g['wet'], np.clip(P['gp'] * fi * dhdx, -1.5, 1.5), 0.0)
    return st


def d20(T_k, dz, iso=293.15, hmin=40.0, hmax=300.0):
    """depth (m) of the 20 C isotherm in column profiles T [N, X, Y] (K) with level thickness dz [N, X, Y]."""
    zc = np.cumsum(dz, 0) - dz / 2; N = T_k.shape[0]; out = np.full(T_k.shape[1:], hmax)
    for k in range(N - 1, 0, -1):
        a, b = T_k[k - 1], T_k[k]; cross = (a >= iso) & (b < iso) & (dz[k] > 0.5)
        zz = zc[k - 1] + (a - iso) / np.maximum(a - b, 1e-6) * (zc[k] - zc[k - 1]); out = np.where(cross, zz, out)
    out = np.where(T_k[0] < iso, hmin, out)
    return np.clip(out, hmin, hmax)


def column_transports(rg, g, cg, taux, tauy, f, prm=None, xp=np):
    """face transports per column level (lists of [X, Y], m2 s-1) for currents.step(q=...): the layer velocity over
    the top h_face of the column plus the Ekman shear (M over h_ek, -M over the rest of the layer). g = rgo geometry,
    cg = currents.make_geom on the same grid."""
    P = dict(PRM); P.update(prm or {})
    uE, vN = face_velocities(rg, g, xp)
    h = rg['h']; hE = 0.5 * (h + xp.roll(h, -1, axis=0)); hN = 0.5 * (h + xp.roll(h, -1, axis=1))
    Mx, My = cu.ekman_transport(taux, tauy, f, dict(r_ek=P['r_ek']), xp)
    Mx = xp.where(g['sea'], Mx, 0.0); My = xp.where(g['sea'], My, 0.0)
    ME = xp.where(g['openE'], 0.5 * (Mx + xp.roll(Mx, -1, axis=0)), 0.0); MN = xp.where(g['openN'], g['sy'] * 0.5 * (My + xp.roll(My, -1, axis=1)), 0.0)
    out = []
    for vel, M, hF, dzF in ((uE, ME, hE, cg['dzE']), (vN, MN, hN, cg['dzN'])):
        he = xp.minimum(P['h_ek'], 0.5 * hF); q = []; zt = xp.zeros_like(hF)
        for k in range(dzF.shape[0]):
            zb = zt + dzF[k]
            inl = cu._overlap(zt, zb, 0.0, hF, xp)
            e = cu._overlap(zt, zb, 0.0, he, xp) / xp.maximum(he, 1e-6); r_ = cu._overlap(zt, zb, he, hF, xp) / xp.maximum(hF - he, 1e-6)
            q.append(vel * inl + M * (e - r_)); zt = zb
        out.append(q)
    return out[0], out[1]
