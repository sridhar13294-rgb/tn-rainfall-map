"""1-D ocean mixed-layer columns under every sea grid point of the moist model (scripts/cyclone/mm/mm2.py).

Why: a storm keeps drawing energy from warm water only while the sea surface stays warm. Its winds stir up cooler water
from below (the cold wake). Over a thin warm layer (Bay of Bengal before the monsoon, or the Head Bay shelf) the surface
cools by 2-3 K and the storm weakens; over a deep warm layer (post-monsoon southern Bay, warm eddies) it hardly cools.
The old slab (cooling ~ wind squared) knew nothing about what lies below the surface; this column does.

The same functions run with numpy (local test) and jax.numpy (inside jit on the GPU): pass xp=np or xp=jnp. Only
element-wise maths, xp.where, xp.stack and python loops over the ~24 ocean levels; no in-place assignment and no
data-dependent python control flow. Arrays are [levels, X, Y], level 0 at the surface.

STATE (dict of arrays, all [N, X, Y]):  T  temperature (K)        S  salinity (psu)
                                         u, v  current (m s-1)     dz level thickness (m; levels below the sea floor are
                                                                    given dz = 1e-3 m, so a shelf column is shallow)
Default grid: 12 levels of 5 m (0-60 m), then 8, 10, 12, 14, 16, 18, 20, 24, 28, 30, 30, 30 m -> 24 levels to 300 m.

SALINITY: carried and mixed like temperature, with an optional virtual salt flux S0 (E - P) / rho0 at the top. Density is
  rho = rho0 [1 - a1 (T - 10) - a2/2 (T - 10)^2 + beta (S - 35)]   (T in deg C; a1 = 1.7e-4, a2 = 7.4e-6 K-2,
  beta = 7.6e-4 psu-1; thermal expansion 1.7e-4 at 10 C, 3.1e-4 at 29 C, close to TEOS-10).
  Why: in the Bay of Bengal the fresh river and rain water on top (barrier layer) is a large part of why post-monsoon
  cyclones cool the sea about three times less than pre-monsoon ones (Neetu et al. 2012, JGR 117 C12020: haline
  stratification ~40 % of the reduction, thermal ~60 %). A temperature-only density would overdo the October-December
  cold wakes. Without salinity data the profile is S = 35 everywhere, which reduces to temperature-only density.

ONE STEP (dt = model step, 1200-1800 s). Inputs per column: Qns non-solar net heat flux into the ocean (W m-2,
  = LW down - sigma SST^4 - sensible - latent), sw net shortwave entering the sea (W m-2), wind stress on the ocean
  (taux, tauy, N m-2), Coriolis f (s-1), optional fresh-water flux fw = E - P (kg m-2 s-1). Total Q = sw + Qns.
  rho0 = 1025 kg m-3, cp = 3990 J kg-1 K-1.

  0. existing mixed layer: levels contiguous from the top with rho_k - rho_0 < 0.01 kg m-3; depth h.
  1. surface fluxes:  T_0 += Qns dt / (rho0 cp dz_0);  S_0 += S_0 fw dt / (rho0 dz_0)
     shortwave, two-band Jerlov type I:  I(z) = 0.58 exp(-z / 0.35 m) + 0.42 exp(-z / 23 m)
       T_k += sw [I(z_top,k) - I(z_bot,k)] dt / (rho0 cp dz_k); what passes the deepest real level is put in that level
       (sea-floor absorption), so all heat stays in the column.
  2. turbulent kinetic energy budget of the mixed layer (Niiler & Kraus 1977), per unit density (m3 s-3):
       P = 2 m* u*^3 exp(-h / h_E) + h/2 [(1 + n) B - (1 - n) |B|]
       u* = sqrt(|tau| / rho0) (water-side friction velocity), m* = 0.8 (0.5-1.25 in the literature), n = 0.2 (fraction
       of convective energy used for penetrative entrainment), h_E = 0.5 u* / max(|f|, 2.5e-5) (Ekman-depth decay of
       wind-stirring energy), B = g [alpha (-(Qns + sw (1 - I(h)))) / (rho0 cp) + beta S_0 fw / rho0] the surface
       buoyancy loss (> 0 when the surface is cooled or salted: convection adds n h B; < 0 when heated: costs h |B|).
     P < 0 (calm and sunny): the layer cannot stay mixed to h; it shoals to the Monin-Obukhov depth
       h_MO = 2 m* u*^3 exp(-h/h_E) / |B|, clipped to [dz_0, h], and only that top layer is mixed (diurnal warm layer).
     P >= 0: the layer is mixed over h, and E = P dt is available for entrainment.
  3. static instability removal + TKE entrainment (one downward sweep): the next level k below the mixed layer
     (thickness h_m, buoyancy jump db = g (rho_k - rho_m) / rho0) is mixed in completely if db <= 0 (unstable), else
     costs E_full = db h_m dz_k / 2 (the potential-energy rise of mixing two slabs). With E >= E_full it joins the layer
     (E -= E_full) and the sweep goes on; otherwise both are moved a fraction r = E / E_full toward their joint mean
     (partial entrainment: smooth in time, not level-sized jumps) and the sweep stops. T, S, u, v mix alike.
  4. slab inertial current (Price-Weller-Pinkel 1986): the profile rotates by f (exact rotation, half before and half
     after the stress), du/dt = f v, dv/dt = -f u; the stress accelerates the mixed layer: du_ml = taux dt / (rho0 h);
     weak linear damping (4 days) stands in for the radiation of inertial waves.
  5. bulk Richardson number mixing (PWP): while Rb = g (rho_k - rho_m) h / (rho0 |V_m - V_k|^2) < 0.65 the next level
     joins the mixed layer. Under a cyclone the inertial current in the layer resonates with the turning wind (right of
     the track in the northern hemisphere), the shear at the base grows and this deepens the layer: the main cold-wake
     mechanism (Price 1981).
  6. gradient Richardson number mixing (PWP): at each interface where Rg = g drho dz / (rho0 |dV|^2) < 0.25 both levels
     move a fraction f = 1 - Rg / (0.25 + 0.02 (Rg - 0.25)) toward their joint mean (one downward sweep per step).
  Every mixing operation conserves sum(X dz), so the column heat content changes by exactly (Qns + sw) dt (tested).
  The new SST is T_0 (the mixed-layer temperature).

NOT INCLUDED (1-D column): Ekman upwelling under the storm and horizontal advection (both deepen the wake of slow storms,
  < 3 m/s, a few tenths of a K more); no relaxation back to the starting profile (fine for runs of a few days).

INITIAL PROFILES: profile_from_clim() takes ocean_clim.npz (WOA23 monthly climatology at 1.5 deg, made by
  scripts/cyclone/cyc_ocean.py) or ocean_live.npz (RTOFS nowcast, same layout), interpolates it to the start date, the
  model nodes and the ocean levels, and shifts its top to the model's starting SST: T(z) = T_clim(z) + dSST w(z),
  dSST = SST - T_clim(0), w = 1 down to the climatological mixed-layer depth h_c (T_clim > T_clim(0) - 0.5 K), falling
  linearly to 0 at 2 h_c. So the anomaly lives in the mixed layer and the thermocline below keeps its climatological
  temperature. Nodes without data use a generic tropical profile (50 m mixed layer, then -0.06 K/m)."""
import math
import numpy as np

RHO0, CPW, GRAV = 1025.0, 3990.0, 9.81
JERLOV_I = (0.58, 0.35, 23.0)
DZ_DEFAULT = np.array([5.0] * 12 + [8, 10, 12, 14, 16, 18, 20, 24, 28, 30, 30, 30], np.float32)   # 24 levels, 300 m
PRM = dict(mstar=0.8, ncv=0.2, rb_crit=0.65, rg_crit=0.25, rcon=0.02, tau_u=4 * 86400.0, drho_ml=0.01, hE_coef=0.5,
           f_min=2.5e-5, dz_real=0.5, jerlov=JERLOV_I)
A1, A2, BETA = 1.7e-4, 7.4e-6, 7.6e-4


def density(T, S):
    """kg m-3; T in K, S in psu."""
    t = T - 283.15
    return RHO0 * (1.0 - A1 * t - 0.5 * A2 * t * t + BETA * (S - 35.0))


def alpha(T):
    return A1 + A2 * (T - 283.15)


def sw_frac(z, xp=np, jer=JERLOV_I):
    """fraction of the surface shortwave reaching depth z (m)."""
    R, z1, z2 = jer
    return R * xp.exp(-z / z1) + (1.0 - R) * xp.exp(-z / z2)


def _mix_to(Xs, members, dz, xp):
    """replace the member levels of each column by their thickness-weighted mean (conservative)."""
    num = sum(xp.where(m, x * d, 0.0) for x, m, d in zip(Xs, members, dz))
    den = sum(xp.where(m, d, 0.0) for m, d in zip(members, dz))
    mean = num / xp.maximum(den, 1e-12)
    return [xp.where(m, mean, x) for x, m in zip(Xs, members)], mean, den


def ml_depth(st, xp=np, drho=0.03):
    """diagnostic mixed-layer depth (m): levels contiguous from the top within drho (kg m-3) of the surface density."""
    T, S, dz = st['T'], st['S'], st['dz']; r0 = density(T[0], S[0]); inml = None; h = 0.0
    for k in range(T.shape[0]):
        ok = (density(T[k], S[k]) - r0 < drho) if k else (r0 == r0)
        inml = ok if inml is None else (inml & ok)
        h = h + xp.where(inml, dz[k], 0.0)
    return h


def heat_content(st, xp=np):
    """column heat content (J m-2) relative to 0 K."""
    return (RHO0 * CPW * st['T'] * st['dz']).sum(0)


def step(st, Qns, sw, taux, tauy, f, dt, mask=None, fw=None, prm=None, xp=np):
    """advance every ocean column by dt seconds. Returns (new state, SST in K). Columns where mask is False (land, sea ice,
    no SST) come back unchanged; their SST is returned as the input surface temperature."""
    P = dict(PRM); P.update(prm or {}); g = GRAV
    T0, S0, U0, V0, DZ0 = st['T'], st['S'], st['u'], st['v'], st['dz']; N = T0.shape[0]
    if mask is None: mask = xp.isfinite(T0[0]) & (T0[0] > 0)
    cl = lambda a, v: xp.where(mask & xp.isfinite(a), a, v)
    Qns, sw, taux, tauy = cl(Qns * 1.0, 0.0), cl(sw * 1.0, 0.0), cl(taux * 1.0, 0.0), cl(tauy * 1.0, 0.0)
    fw = xp.zeros_like(Qns) if fw is None else cl(fw * 1.0, 0.0)
    f = xp.zeros_like(Qns) + f; true = xp.ones(Qns.shape, dtype=bool)
    m3 = mask[None] & xp.isfinite(T0) & xp.isfinite(S0)
    T = [x for x in xp.where(m3, T0, 300.0)]; S = [x for x in xp.where(m3, S0, 35.0)]
    U = [x for x in xp.where(m3, U0, 0.0)]; V = [x for x in xp.where(m3, V0, 0.0)]
    dz = [x for x in xp.where(mask[None] & (DZ0 > 0), DZ0, 1.0)]
    zb, zt, acc = [], [], xp.zeros_like(dz[0])
    for k in range(N): zt.append(acc); acc = acc + dz[k]; zb.append(acc)
    real = [d >= P['dz_real'] for d in dz]
    # ---- 0. existing mixed layer
    rho = [density(T[k], S[k]) for k in range(N)]
    inml, run, h = [], None, 0.0
    for k in range(N):
        ok = (rho[k] - rho[0] < P['drho_ml']) if k else true
        run = ok if run is None else (run & ok); inml.append(run); h = h + xp.where(run, dz[k], 0.0)
    # ---- 1. surface fluxes and penetrating shortwave
    ab = [xp.where(real[k], sw * (sw_frac(zt[k], xp, P['jerlov']) - sw_frac(zb[k], xp, P['jerlov'])), 0.0) for k in range(N)]
    rem = sw - sum(ab)
    last = [real[k] & (~real[k + 1]) if k < N - 1 else real[k] for k in range(N)]
    ab = [a + xp.where(l_, rem, 0.0) for a, l_ in zip(ab, last)]
    T = [T[k] + ab[k] * dt / (RHO0 * CPW * dz[k]) for k in range(N)]
    T[0] = T[0] + Qns * dt / (RHO0 * CPW * dz[0])
    Ssurf = S[0]; S[0] = S[0] + Ssurf * fw * dt / (RHO0 * dz[0])
    # ---- 2. TKE budget
    tau = xp.sqrt(taux ** 2 + tauy ** 2); ust = xp.sqrt(tau / RHO0)
    B = g * (alpha(T[0]) * (-(Qns + sw * (1.0 - sw_frac(h, xp, P['jerlov'])))) / (RHO0 * CPW) + BETA * Ssurf * fw / RHO0)
    hE = xp.maximum(P['hE_coef'] * ust / xp.maximum(xp.abs(f), P['f_min']), 1e-6)
    Ew = 2.0 * P['mstar'] * ust ** 3 * xp.exp(-h / hE)
    n = P['ncv']; Pw = Ew + 0.5 * h * ((1 + n) * B - (1 - n) * xp.abs(B))
    heat = Pw < 0
    hmo = Ew / xp.maximum(-B, 1e-15)
    hmix = xp.where(heat, xp.minimum(xp.maximum(hmo, dz[0]), h), h)
    E = xp.where(heat, 0.0, Pw * dt)
    in1 = [(zt[k] + 0.5 * dz[k] < hmix) & inml[k] if k else true for k in range(N)]
    (T, S, U, V) = [_mix_to(X, in1, dz, xp)[0] for X in (T, S, U, V)]
    # ---- 3. static instability + TKE entrainment
    Tm, Sm, Um, Vm = T[0], S[0], U[0], V[0]; hm = dz[0]; active = true; mem = [in1[0]]
    for k in range(1, N):
        isin = in1[k] & active
        hm = hm + xp.where(isin, dz[k], 0.0)
        below = (~in1[k]) & active
        db = g * (density(T[k], S[k]) - density(Tm, Sm)) / RHO0
        Ef = xp.maximum(db, 0.0) * hm * dz[k] / 2.0
        r = xp.where(db <= 0, 1.0, xp.minimum(1.0, E / xp.maximum(Ef, 1e-30)))
        r = xp.where(below, xp.maximum(r, 0.0), 0.0)
        w = dz[k] / (hm + dz[k])
        new = []
        for X, Xm in ((T, Tm), (S, Sm), (U, Um), (V, Vm)):
            mean = Xm + w * (X[k] - Xm)
            new.append((Xm + r * (mean - Xm), X[k] + r * (mean - X[k])))
        (Tm, Tk), (Sm, Sk), (Um, Uk), (Vm, Vk) = new
        T[k], S[k], U[k], V[k] = Tk, Sk, Uk, Vk
        joined = below & (r >= 1.0)
        E = xp.where(below, xp.maximum(E - r * Ef, 0.0), E)
        hm = hm + xp.where(joined, dz[k], 0.0)
        mem.append(isin | joined)
        active = active & (isin | joined)
    T = [xp.where(m, Tm, x) for m, x in zip(mem, T)]; S = [xp.where(m, Sm, x) for m, x in zip(mem, S)]
    U = [xp.where(m, Um, x) for m, x in zip(mem, U)]; V = [xp.where(m, Vm, x) for m, x in zip(mem, V)]
    # ---- 4. inertial rotation + wind stress into the mixed layer + damping
    c, s_ = xp.cos(0.5 * f * dt), xp.sin(0.5 * f * dt)
    rot = lambda U, V: ([u * c + v * s_ for u, v in zip(U, V)], [-u * s_ + v * c for u, v in zip(U, V)])
    U, V = rot(U, V)
    hml = sum(xp.where(m, d, 0.0) for m, d in zip(mem, dz))
    U = [u + xp.where(m, taux * dt / (RHO0 * hml), 0.0) for u, m in zip(U, mem)]
    V = [v + xp.where(m, tauy * dt / (RHO0 * hml), 0.0) for v, m in zip(V, mem)]
    U, V = rot(U, V)
    damp = math.exp(-dt / P['tau_u']) if P['tau_u'] else 1.0
    U = [u * damp for u in U]; V = [v * damp for v in V]
    # ---- 5. bulk Richardson number deepening
    Tm, Sm, Um, Vm = T[0], S[0], U[0], V[0]; hm = dz[0]; active = true; mem2 = [mem[0]]
    for k in range(1, N):
        isin = mem[k] & active
        hm = hm + xp.where(isin, dz[k], 0.0)
        below = (~mem[k]) & active
        dV2 = (Um - U[k]) ** 2 + (Vm - V[k]) ** 2
        Rb = g * (density(T[k], S[k]) - density(Tm, Sm)) / RHO0 * hm / xp.maximum(dV2, 1e-10)
        mix = below & (Rb < P['rb_crit'])
        w = dz[k] / (hm + dz[k])
        Tm, Sm, Um, Vm = [xp.where(mix, Xm + w * (X[k] - Xm), Xm) for X, Xm in ((T, Tm), (S, Sm), (U, Um), (V, Vm))]
        hm = hm + xp.where(mix, dz[k], 0.0)
        mem2.append(isin | mix); active = active & (isin | mix)
    T = [xp.where(m, Tm, x) for m, x in zip(mem2, T)]; S = [xp.where(m, Sm, x) for m, x in zip(mem2, S)]
    U = [xp.where(m, Um, x) for m, x in zip(mem2, U)]; V = [xp.where(m, Vm, x) for m, x in zip(mem2, V)]
    # ---- 6. gradient Richardson number mixing (one sweep)
    rg, rc = P['rg_crit'], P['rcon']
    for j in range(N - 1):
        dV2 = (U[j] - U[j + 1]) ** 2 + (V[j] - V[j + 1]) ** 2
        Rg = g * (density(T[j + 1], S[j + 1]) - density(T[j], S[j])) / RHO0 * 0.5 * (dz[j] + dz[j + 1]) / xp.maximum(dV2, 1e-10)
        fr = xp.where(Rg <= 0, 1.0, xp.clip(1.0 - Rg / xp.maximum(rg + rc * (Rg - rg), 1e-6), 0.0, 1.0))
        fr = xp.where(Rg < rg, fr, 0.0)
        wa = dz[j + 1] / (dz[j] + dz[j + 1])
        for X in (T, S, U, V):
            mean = X[j] + wa * (X[j + 1] - X[j])
            X[j], X[j + 1] = X[j] + fr * (mean - X[j]), X[j + 1] + fr * (mean - X[j + 1])
    out = dict(T=xp.where(m3, xp.stack(T), T0), S=xp.where(m3, xp.stack(S), S0), u=xp.where(m3, xp.stack(U), U0),
               v=xp.where(m3, xp.stack(V), V0), dz=DZ0)
    for k_ in st:
        if k_ not in out: out[k_] = st[k_]
    return out, xp.where(mask, out['T'][0], T0[0])


# ---------------------------------------------------------------------------------------------------- starting profiles
def generic_profile(sst_k, dz=DZ_DEFAULT, h=50.0, grad=0.06, tmin=277.15):
    """T [N, ...] (K): mixed layer h (m) at the SST, then cooling by grad K/m down to tmin."""
    zc = np.cumsum(dz) - dz / 2; zc = zc.reshape((-1,) + (1,) * np.ndim(sst_k))
    return np.maximum(sst_k - grad * np.maximum(zc - h, 0.0), np.minimum(tmin, sst_k))


def _month_weights(when, nt):
    if nt == 1 or when is None: return [(0, 1.0)]
    doy = when.timetuple().tm_yday - 1 + when.hour / 24.0; m = doy / 365.25 * 12 - 0.5     # 0 = mid January
    i0 = int(math.floor(m)) % 12; w1 = m - math.floor(m); return [(i0, 1 - w1), ((i0 + 1) % 12, w1)]


def _nearest_fill(A):
    """fill NaNs of a 2-D [lat, lon] field from the nearest valid cell."""
    from scipy import ndimage as ndi
    bad = ~np.isfinite(A)
    if bad.all() or not bad.any(): return A
    _, idx = ndi.distance_transform_edt(bad, return_indices=True); return A[tuple(idx)]


def profile_from_clim(clim, when, lat2d, lon2d, sst_k, sea, dz=DZ_DEFAULT, min_depth=15.0, dT_ml=0.5):
    """starting state for step(): clim = dict or path of ocean_clim.npz / ocean_live.npz (keys T, S [time, depth, lat, lon]
    in deg C / psu, depth, lat, lon); when = datetime of the start (month interpolation; ignored for a single snapshot);
    lat2d, lon2d, sst_k (K), sea (bool) on the model nodes [X, Y]. numpy only (run once at the start)."""
    if isinstance(clim, str): clim = dict(np.load(clim))
    dz = np.asarray(dz, np.float32); N = len(dz); zc = np.cumsum(dz) - dz / 2; shp = np.shape(sst_k)
    depth = np.asarray(clim['depth'], float); la = np.asarray(clim['lat'], float); lo = np.asarray(clim['lon'], float) % 360
    Tc = sum(w * np.asarray(clim['T'][i], float) for i, w in _month_weights(when, clim['T'].shape[0]))
    Sc = sum(w * np.asarray(clim['S'][i], float) for i, w in _month_weights(when, clim['S'].shape[0])) if 'S' in clim else None
    # sea-floor depth of each climatology cell: deepest valid level (+ half the spacing), nearest-filled onto coasts
    valid = np.isfinite(Tc); nd = valid.sum(0)
    half = np.append(np.diff(depth) / 2, np.diff(depth)[-1] / 2)
    bot = np.where(nd > 0, depth[np.maximum(nd - 1, 0)] + half[np.maximum(nd - 1, 0)], np.nan)
    bot = np.where(nd == len(depth), 1e4, bot); bot = _nearest_fill(bot)
    Tc = np.stack([_nearest_fill(x) for x in Tc]); Sc = None if Sc is None else np.stack([_nearest_fill(x) for x in Sc])
    for k in range(1, len(depth)):                                                   # below the floor: copy the level above
        Tc[k] = np.where(np.isfinite(Tc[k]), Tc[k], Tc[k - 1])
        if Sc is not None: Sc[k] = np.where(np.isfinite(Sc[k]), Sc[k], Sc[k - 1])
    # bilinear onto the nodes (inside the climatology box only)
    LA = np.asarray(lat2d, float); LO = np.asarray(lon2d, float) % 360
    fy = (LA - la[0]) / (la[1] - la[0]); fx = ((LO - lo[0]) % 360) / (lo[1] - lo[0])
    inside = (fy >= 0) & (fy <= len(la) - 1) & (fx >= 0) & (fx <= len(lo) - 1)
    y0 = np.clip(np.floor(fy).astype(int), 0, len(la) - 2); x0 = np.clip(np.floor(fx).astype(int), 0, len(lo) - 2)
    wy = np.clip(fy - y0, 0, 1); wx = np.clip(fx - x0, 0, 1)
    def bil(A):
        return ((1 - wy) * (1 - wx) * A[..., y0, x0] + (1 - wy) * wx * A[..., y0, x0 + 1] + wy * (1 - wx) * A[..., y0 + 1, x0] + wy * wx * A[..., y0 + 1, x0 + 1])
    Tn, botn = bil(Tc), bil(bot); Sn = None if Sc is None else bil(Sc)
    # onto the ocean levels
    ii = np.clip(np.searchsorted(depth, zc) - 1, 0, len(depth) - 2); wz = np.clip((zc - depth[ii]) / (depth[ii + 1] - depth[ii]), 0, 1)
    vz = lambda A: ((1 - wz).reshape((-1,) + (1,) * len(shp)) * A[ii] + wz.reshape((-1,) + (1,) * len(shp)) * A[ii + 1])
    Tz = vz(Tn) + 273.15; Sz = np.full((N,) + shp, 35.0) if Sn is None else vz(Sn)
    ok = inside & np.isfinite(Tz).all(0) & sea
    # shift the top to the model SST: anomaly uniform over the climatological mixed layer, fading to 0 at twice its depth
    hc = np.full(shp, zc[-1])
    for k in range(N - 1, 0, -1): hc = np.where(Tz[k] < Tz[0] - dT_ml, zc[k], hc)
    wgt = np.clip(2.0 - zc.reshape((-1,) + (1,) * len(shp)) / np.maximum(hc, dz[0]), 0.0, 1.0)
    T = np.where(ok, Tz + (sst_k - Tz[0]) * wgt, generic_profile(sst_k, dz))
    S = np.where(ok & np.isfinite(Sz), Sz, 35.0)
    # sea floor: levels below it get a negligible thickness
    bott = np.where(ok, np.maximum(botn, min_depth), 1e4); ztop = (np.cumsum(dz) - dz).reshape((-1,) + (1,) * len(shp))
    DZ = np.where(ztop < bott, dz.reshape((-1,) + (1,) * len(shp)) * np.ones(shp), 1e-3)
    T = np.where(sea, T, 273.15); S = np.where(sea, S, 35.0)
    z = np.zeros((N,) + shp, np.float32)
    return dict(T=T.astype(np.float32), S=S.astype(np.float32), u=z, v=z.copy(), dz=DZ.astype(np.float32))
