"""Stage 2, step A: currents and upwelling for the 1-D ocean columns of the moist model (scripts/cyclone/mm/ocean.py).

Why: the columns know only what happens straight below each grid point. Three things the real ocean does sideways are
missing: (1) wind-driven (Ekman) transport in the top tens of metres, whose divergence lifts cold water from below
(Somali and Oman coasts in the south-west monsoon, the Sri Lanka dome, the south-west coast of India, the equator under
easterlies, the centre of a slow cyclone); (2) the return flow beneath it, which brings that cold water to the coast;
(3) carriage of warm or cold water by currents (heat transport). This module moves the column temperature and salinity
with a three-dimensional velocity field built every step from the wind stress and the columns' own density.

Pure functions, numpy or jax.numpy (xp=np / xp=jnp, as ocean.py): element-wise maths, xp.roll and python loops over the
~24 ocean levels; no in-place assignment, no data-dependent python control flow. Arrays [levels, X, Y] (X = longitude,
Y = latitude, as on the model nodes, level 0 at the surface); 2-D fields [X, Y].

VELOCITY (at the cell faces, one value per level and face, as a volume transport per unit face length q = u dz, m2 s-1)
 1. Ekman transport of the stress tau (N m-2), with a friction rate r so that it stays finite at the equator
    (Zebiak & Cane 1987 surface layer; r = 1 / 2 days):
        Mx = (r taux + f tauy) / (rho0 (r^2 + f^2)),   My = (r tauy - f taux) / (rho0 (r^2 + f^2))       (m2 s-1)
    far from the equator this is the classical tau x k / (rho0 f) (90 degrees to the right of the wind in the north);
    at the equator it goes with the wind; within ~3 degrees it turns, so that easterlies give poleward transport on both
    sides and upwelling on the equator.
    The transport fills the Ekman layer (depth h_E = 40 m, at most half the water depth) evenly.
 2. Return flow: the same transport, opposite sign, spread evenly from h_E to the bottom of the column (300 m or the sea
    floor). So the depth-integrated transport through every face is zero (no sea-level change, no exchange with the deep
    ocean below 300 m). The upwelling velocity at the base of the Ekman layer is then exactly the divergence of the Ekman
    transport, w_E = div(M) = curl(tau / f) / rho0 away from the equator, and at a coast the offshore transport is fed
    from below (coastal upwelling, spread over one grid cell). In water shallower than 2 h_E the transport is reduced in
    proportion (surface and bottom Ekman layers overlap on shelves).
 3. Baroclinic geostrophic current (optional, geo = 1): hydrostatic pressure from the columns' density, p/rho0 = g
    sum(rho - rho0) dz / rho0, u = -(1/f) dp/dy, v = (1/f) dp/dx, with 1/f replaced by f / (f^2 + f_eq^2) (f_eq = f at
    2.5 degrees; no geostrophy on the equator), its depth mean removed per face (level of no net motion, consistent with
    2.). This carries the warm/cold water along density fronts (East India Coastal Current, Somali Current, the dome).
 4. Analysis currents (optional, u_ext / v_ext [levels, X, Y], e.g. RTOFS or Copernicus): added as given; their depth
    mean is removed too unless closure='open', in which case water may enter or leave through the bottom of the column
    with the temperature of the deepest real level.
    mode='slab': instead of 1., use the columns' own mixed-layer currents (st['u'], st['v'], the damped inertial slab of
    ocean.py: Ekman drift plus inertial oscillations; under a slow cyclone their divergence gives inertial pumping).
 A face is closed where either side is land or the level is below the sea floor (face thickness = the thinner side).
 Speed limiter: on each face the whole profile is scaled down if any level would move more than 0.3 of a cell per step
 (keeps the explicit scheme stable near the poles; does not change the zero-net closure).

ADVECTION (finite volume, first-order upwind, explicit): vertical velocity at every level interface from continuity
 (rigid lid, w = 0 at the surface), then for each level
    d(T dz)/dt = -(sum of upwind face fluxes out) / area + w_below T_from_below - w_above T_from_above.
 Conserves sum(T dz area) exactly with the zero-net closure; a uniform field stays uniform; no new extremes (CFL < 1).
 Salinity alike. The columns' u, v are not advected (they are the local inertial slab).
"""
import math, os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'cyclone', 'mm'))
from ocean import density, RHO0, GRAV                                       # same equation of state as the columns

OMEGA, REARTH = 7.292e-5, 6.371e6
PRM = dict(r_ek=1.0 / (2 * 86400.0), h_ek=40.0, geo=1.0, f_eq=2 * OMEGA * math.sin(math.radians(2.5)), cfl=0.3,
           dz_real=0.5, ugeo_max=1.5, mode='ekman', closure='zero_net')


# ------------------------------------------------------------------------------------------------------------- geometry
def make_geom(lat2d, lon2d, dz, sea=None, periodic=None, R=REARTH):
    """grid metrics on the model nodes (numpy, once). lat2d, lon2d [X, Y] (degrees; X = longitude, uniform spacing;
    Y = latitude, any monotonic spacing, e.g. Gaussian); dz [N, X, Y] the columns' level thickness (levels below the sea
    floor ~1e-3 m, as profile_from_clim makes them); sea [X, Y] bool. periodic: longitudes wrap around (default: when
    they cover 360 degrees)."""
    LA = np.asarray(lat2d, float); LO = np.asarray(lon2d, float); dz = np.asarray(dz, float); N, X, Y = dz.shape
    lat = LA[0]; lon = LO[:, 0]; dlon = np.radians(abs(lon[1] - lon[0])) if X > 1 else 1.0
    if periodic is None: periodic = X > 2 and abs(abs(lon[1] - lon[0]) * X - 360.0) < 1e-3
    sea = np.ones((X, Y), bool) if sea is None else np.asarray(sea, bool)
    # latitude edges: midpoints; the outer ones at the poles for a global grid, else half a spacing beyond
    phi = np.radians(lat); mid = 0.5 * (phi[1:] + phi[:-1])
    lo_e = phi[0] - (mid[0] - phi[0]) if Y > 1 else phi[0] - 0.01; hi_e = phi[-1] + (phi[-1] - mid[-1]) if Y > 1 else phi[-1] + 0.01
    edges = np.clip(np.concatenate([[lo_e], mid, [hi_e]]), -math.pi / 2, math.pi / 2)
    area1 = R * R * dlon * np.abs(np.sin(edges[1:]) - np.sin(edges[:-1]))         # [Y]
    dyc = R * np.abs(np.diff(edges))                                               # meridional size of a cell [Y]
    LE = np.broadcast_to(dyc, (X, Y)).copy()                                       # length of the east face of each cell
    LN = np.broadcast_to(R * np.cos(edges[1:Y + 1]) * dlon, (X, Y)).copy()        # length of the face to the j+1 neighbour
    dxE = np.broadcast_to(R * np.cos(phi) * dlon, (X, Y)).copy()                  # centre-to-centre distance in x
    dyN = np.broadcast_to(R * np.abs(np.append(np.diff(phi), 1.0)), (X, Y)).copy()  # centre-to-centre in y (to j+1)
    sy = np.sign(lat[-1] - lat[0]) if Y > 1 else 1.0                               # +1 if j+1 is to the north
    real = (dz >= PRM['dz_real']) & sea[None]
    dzR = np.where(real, dz, 0.0)
    nb = lambda a, ax: np.roll(a, -1, axis=ax)
    dzE = np.minimum(dzR, nb(dzR, 1)); dzN = np.minimum(dzR, nb(dzR, 2))
    if not periodic: dzE[:, -1, :] = 0.0
    dzN[:, :, -1] = 0.0
    LN[:, -1] = 0.0
    zc = np.cumsum(dz, 0) - dz / 2
    return dict(area=np.broadcast_to(area1, (X, Y)).copy(), LE=LE, LN=LN, dxE=dxE, dyN=dyN, sy=float(sy), dzE=dzE, dzN=dzN,
                dzR=dzR, real=real, H=dzR.sum(0), HE=dzE.sum(0), HN=dzN.sum(0), sea=sea, zc=zc, periodic=bool(periodic),
                lat=LA, lon=LO, f=2 * OMEGA * np.sin(np.radians(LA)))


def _overlap(zt, zb, a, b, xp):
    """thickness of [zt, zb] inside [a, b] (all >= 0, depth positive down)."""
    return xp.maximum(xp.minimum(zb, b) - xp.maximum(zt, a), 0.0)


def _face_profile(M, dzF, HF, h_ek, xp):
    """transport per level (m2 s-1) on faces with total Ekman transport M [X, Y] and level thicknesses dzF [N, X, Y]:
    M spread over the top h (h = min(h_ek, HF/2)), -M over the rest; reduced by HF / (2 h_ek) in shallow water."""
    h = xp.minimum(h_ek, 0.5 * HF); M = M * xp.clip(HF / (2.0 * h_ek), 0.0, 1.0)
    out = []; zt = xp.zeros_like(HF)
    for k in range(dzF.shape[0]):
        zb = zt + dzF[k]
        e = _overlap(zt, zb, 0.0, h, xp) / xp.maximum(h, 1e-6)
        r = _overlap(zt, zb, h, HF, xp) / xp.maximum(HF - h, 1e-6)
        out.append(M * (e - r)); zt = zb
    return out


def _remove_mean(q, dzF, HF, xp):
    """q per level (velocity x dz); subtract the depth mean velocity so that sum(q) = 0 on every face."""
    tot = sum(q); ubar = tot / xp.maximum(HF, 1e-6)
    return [qk - ubar * d for qk, d in zip(q, dzF)]


def _inv_f(f, prm, xp):
    return f / (f * f + prm['f_eq'] ** 2)


def ekman_transport(taux, tauy, f, prm=None, xp=np):
    """(Mx, My) m2 s-1 at the cell centres (friction-regularised, finite at the equator)."""
    P = dict(PRM); P.update(prm or {}); r = P['r_ek']; d = RHO0 * (r * r + f * f)
    return (r * taux + f * tauy) / d, (r * tauy - f * taux) / d


def face_transports(st, taux, tauy, f, geom, prm=None, xp=np, u_ext=None, v_ext=None):
    """lists (per level) of transports per unit face length through the east faces (qE, towards i+1) and the j+1 faces
    (qN, towards j+1), m2 s-1."""
    P = dict(PRM); P.update(prm or {}); g = geom
    nbx = lambda a: xp.roll(a, -1, axis=-2); nby = lambda a: xp.roll(a, -1, axis=-1)
    dzE, dzN = g['dzE'], g['dzN']; N = dzE.shape[0]
    openE = g['HE'] > 0; openN = g['HN'] > 0
    zero = [xp.zeros_like(g['HE'])] * N
    if P['mode'] == 'slab':                                                           # the columns' own currents
        U, V = st['u'], st['v']
        qE = [0.5 * (U[k] + nbx(U[k])) * dzE[k] for k in range(N)]
        qN = [g['sy'] * 0.5 * (V[k] + nby(V[k])) * dzN[k] for k in range(N)]
        qE = _remove_mean(qE, dzE, g['HE'], xp); qN = _remove_mean(qN, dzN, g['HN'], xp)
    else:
        Mx, My = ekman_transport(taux, tauy, f, P, xp)
        sea = g['sea']; Mx = xp.where(sea, Mx, 0.0); My = xp.where(sea, My, 0.0)
        MxE = xp.where(openE, 0.5 * (Mx + nbx(Mx)), 0.0); MyN = xp.where(openN, g['sy'] * 0.5 * (My + nby(My)), 0.0)
        qE = _face_profile(MxE, dzE, g['HE'], P['h_ek'], xp); qN = _face_profile(MyN, dzN, g['HN'], P['h_ek'], xp)
    if P['geo']:
        T, S = st['T'], st['S']; real = g['real']; acc = 0.0; p = []
        for k in range(N):                                                            # pressure / rho0 at level centres
            b = GRAV * (density(T[k], S[k]) - RHO0) / RHO0
            b = xp.where(real[k], b, 0.0); d = g['dzR'][k]
            p.append(acc + b * 0.5 * d); acc = acc + b * d
        fi = _inv_f(f, P, xp)
        ue, vn = [], []
        for k in range(N):
            rk = real[k]; pk = p[k]
            # centred differences using only wet neighbours (one-sided at coasts, zero when both are dry)
            pE, pW = nbx(pk), xp.roll(pk, 1, axis=-2); wE, wW = nbx(rk), xp.roll(rk, 1, axis=-2)
            pNn, pS = nby(pk), xp.roll(pk, 1, axis=-1); wN, wS = nby(rk), xp.roll(rk, 1, axis=-1)
            if not g['periodic']:
                wE = xp.where(xp.arange(rk.shape[0])[:, None] == rk.shape[0] - 1, False, wE)
                wW = xp.where(xp.arange(rk.shape[0])[:, None] == 0, False, wW)
            wN = xp.where(xp.arange(rk.shape[1])[None, :] == rk.shape[1] - 1, False, wN)
            wS = xp.where(xp.arange(rk.shape[1])[None, :] == 0, False, wS)
            nxw = wE.astype(pk.dtype) + wW.astype(pk.dtype); nyw = wN.astype(pk.dtype) + wS.astype(pk.dtype)
            dpdx = (xp.where(wE, pE - pk, 0.0) + xp.where(wW, pk - pW, 0.0)) / xp.maximum(nxw, 1.0) / g['dxE']
            dyS = xp.roll(g['dyN'], 1, axis=-1)
            dpdy = (xp.where(wN, (pNn - pk) / g['dyN'], 0.0) + xp.where(wS, (pk - pS) / dyS, 0.0)) / xp.maximum(nyw, 1.0) * g['sy']
            ug = xp.clip(-fi * dpdy, -P['ugeo_max'], P['ugeo_max']); vg = xp.clip(fi * dpdx, -P['ugeo_max'], P['ugeo_max'])
            ug = xp.where(rk, ug, 0.0); vg = xp.where(rk, vg, 0.0)
            ue.append(0.5 * (ug + nbx(ug)) * dzE[k]); vn.append(g['sy'] * 0.5 * (vg + nby(vg)) * dzN[k])
        ue = _remove_mean(ue, dzE, g['HE'], xp); vn = _remove_mean(vn, dzN, g['HN'], xp)
        qE = [a + P['geo'] * b for a, b in zip(qE, ue)]; qN = [a + P['geo'] * b for a, b in zip(qN, vn)]
    if u_ext is not None:
        ue = [0.5 * (u_ext[k] + nbx(u_ext[k])) * dzE[k] for k in range(N)]
        vn = [g['sy'] * 0.5 * (v_ext[k] + nby(v_ext[k])) * dzN[k] for k in range(N)]
        if P['closure'] != 'open': ue = _remove_mean(ue, dzE, g['HE'], xp); vn = _remove_mean(vn, dzN, g['HN'], xp)
        qE = [a + b for a, b in zip(qE, ue)]; qN = [a + b for a, b in zip(qN, vn)]
    return qE, qN


def _limit(q, dzF, dist, dt, cfl, xp):
    """scale each face's profile so that no level moves more than cfl x (centre distance) per step."""
    umax = None
    for qk, d in zip(q, dzF):
        u = xp.abs(qk) / xp.maximum(d, 1e-6); u = xp.where(d > 0, u, 0.0)
        umax = u if umax is None else xp.maximum(umax, u)
    s = xp.minimum(1.0, cfl * dist / dt / xp.maximum(umax, 1e-12))
    return [qk * s for qk in q]


def step(st, taux, tauy, f, geom, dt, prm=None, xp=np, u_ext=None, v_ext=None, diag=False):
    """advect the columns' T and S by dt seconds. st: ocean.py state (T, S, u, v, dz [N, X, Y]); taux, tauy (N m-2) and
    f (s-1) [X, Y]; geom from make_geom() (numpy arrays are fine inside jit: they become constants).
    Returns the new state (and with diag=True also dict(w = vertical velocity at the level bottoms [N, X, Y] m s-1,
    wE = w at the Ekman-layer base [X, Y], qE, qN))."""
    P = dict(PRM); P.update(prm or {}); g = geom
    N = st['T'].shape[0]; A = g['area']
    f = xp.zeros_like(st['T'][0]) + f
    sea = g['sea']; taux = xp.where(sea & xp.isfinite(taux), taux, 0.0); tauy = xp.where(sea & xp.isfinite(tauy), tauy, 0.0)
    qE, qN = face_transports(st, taux, tauy, f, g, P, xp, u_ext, v_ext)
    qE = _limit(qE, g['dzE'], g['dxE'], dt, P['cfl'], xp); qN = _limit(qN, g['dzN'], g['dyN'], dt, P['cfl'], xp)
    VE = [q * g['LE'] for q in qE]; VN = [q * g['LN'] for q in qN]                     # m3 s-1
    pvx = lambda a: xp.roll(a, 1, axis=-2); pvy = lambda a: xp.roll(a, 1, axis=-1)
    real = g['real']; dz = g['dzR']
    T0, S0 = st['T'], st['S']
    Tc = [xp.where(real[k], T0[k], 0.0) for k in range(N)]; Sc = [xp.where(real[k], S0[k], 0.0) for k in range(N)]
    # vertical velocity at level bottoms from continuity (rigid lid)
    w_top = xp.zeros_like(A); W = []
    for k in range(N):
        D = (VE[k] - pvx(VE[k]) + VN[k] - pvy(VN[k])) / A
        w_bot = xp.where(real[k], w_top + D, 0.0); W.append(w_bot); w_top = w_bot
    out = {}
    for name, C in (('T', Tc), ('S', Sc)):
        new = []
        for k in range(N):
            c, cE, cN = C[k], xp.roll(C[k], -1, axis=-2), xp.roll(C[k], -1, axis=-1)
            FE = VE[k] * xp.where(VE[k] > 0, c, cE); FN = VN[k] * xp.where(VN[k] > 0, c, cN)
            hdiv = (FE - pvx(FE) + FN - pvy(FN)) / A
            wt = W[k - 1] if k else xp.zeros_like(A)                                    # upward velocity at the top face
            above = C[k - 1] if k else c
            Ftop = wt * xp.where(wt > 0, c, above)
            wb = W[k]; below = C[k + 1] if k < N - 1 else c
            below = xp.where(real[k + 1], below, c) if k < N - 1 else c                # deepest real level: zero gradient
            Fbot = wb * xp.where(wb > 0, below, c)
            ck = c + dt * (-hdiv + Fbot - Ftop) / xp.maximum(dz[k], 1e-6)
            new.append(xp.where(real[k], ck, (T0 if name == 'T' else S0)[k]))
        out[name] = xp.stack(new)
    res = dict(st); res['T'] = out['T']; res['S'] = out['S']
    if not diag: return res
    # w at the Ekman-layer base: interpolate the interface values to depth h_ek
    zb = xp.cumsum(dz, 0) if xp is np else xp.cumsum(xp.asarray(dz), 0)
    wE = xp.zeros_like(A); zt = xp.zeros_like(A); wt = xp.zeros_like(A)
    for k in range(N):
        zbk = zb[k]; inside = (zt < P['h_ek']) & (zbk >= P['h_ek']) & real[k]
        fr = (P['h_ek'] - zt) / xp.maximum(zbk - zt, 1e-6)
        wE = xp.where(inside, wt + fr * (W[k] - wt), wE); zt = zbk; wt = W[k]
    return res, dict(w=xp.stack(W), wE=wE, qE=qE, qN=qN)


def ekman_pumping(taux, tauy, f, geom, prm=None, xp=np):
    """the divergence of the (regularised) Ekman transport on the model grid, m s-1 (> 0 upwelling): what step()
    produces at the Ekman-layer base in deep water. For maps and tests."""
    P = dict(PRM); P.update(prm or {}); g = geom
    Mx, My = ekman_transport(taux, tauy, f, P, xp)
    Mx = xp.where(g['sea'], Mx, 0.0); My = xp.where(g['sea'], My, 0.0)
    nbx = lambda a: xp.roll(a, -1, axis=-2); nby = lambda a: xp.roll(a, -1, axis=-1)
    VE = xp.where(g['HE'] > 0, 0.5 * (Mx + nbx(Mx)), 0.0) * g['LE'] * xp.clip(g['HE'] / (2 * P['h_ek']), 0, 1)
    VN = xp.where(g['HN'] > 0, g['sy'] * 0.5 * (My + nby(My)), 0.0) * g['LN'] * xp.clip(g['HN'] / (2 * P['h_ek']), 0, 1)
    return (VE - xp.roll(VE, 1, axis=-2) + VN - xp.roll(VN, 1, axis=-1)) / g['area']
