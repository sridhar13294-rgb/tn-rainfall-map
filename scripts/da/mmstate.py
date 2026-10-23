"""mm2 model state <-> the nodal fields the LETKF analyses, and verification fields. Needs jax + dinosaur (GPU job).

nodal(M, st)            -> dict t [L, X, Y] K, q kg/kg, u, v m/s, ps [X, Y] Pa  (as wx_prof.py / mm2.run_wx read them)
update(M, st, Fb, Fa)   -> state with the analysis increments added: T and ln ps through the spectral transform,
                           (u, v) increments -> (vorticity, divergence) increments, q (nodal tracer) replaced, >= 0.
                           Increments finer than the T85 truncation are filtered out by the transform.
verif(M, st)            -> t850 (K), z500 (m), u850, v850 (m/s), ps (Pa) on the model grid [X, Y], computed as mm2.run_wx."""
import numpy as np, jax, jax.numpy as jnp
from dinosaur import spherical_harmonic, primitive_equations
G, RD = 9.80616, 287.04
_cache = {}

def _nodal(M, st):
    hor = M.coords.horizontal
    T = (hor.to_nodal(st.temperature_variation) + M.ref_t[:, None, None]) / M.K
    u, v = spherical_harmonic.vor_div_to_uv_nodal(hor, st.vorticity, st.divergence)
    ps = jnp.exp(hor.to_nodal(st.log_surface_pressure))[0] / M.PA
    return dict(t=T, q=st.tracers['specific_humidity'], u=u / M.MPS, v=v / M.MPS, ps=ps)

def _update(M, st, Fb, Fa):
    hor = M.coords.horizontal
    dvo, ddv = spherical_harmonic.uv_nodal_to_vor_div_modal(hor, (Fa['u'] - Fb['u']) * M.MPS, (Fa['v'] - Fb['v']) * M.MPS)
    dT = hor.to_modal((Fa['t'] - Fb['t']) * M.K)
    dlp = hor.to_modal(jnp.log(Fa['ps'] / Fb['ps'])[None])
    return st.replace(vorticity=st.vorticity + dvo, divergence=st.divergence + ddv,
                      temperature_variation=st.temperature_variation + dT, log_surface_pressure=st.log_surface_pressure + dlp,
                      tracers={'specific_humidity': jnp.maximum(Fa['q'], 0.0).astype(st.tracers['specific_humidity'].dtype)})

def _to_p(F, lp, P):
    lt = jnp.log(P); idx = jnp.sum(lp < lt, axis=0); k1 = jnp.clip(idx, 1, F.shape[0] - 1); k0 = k1 - 1
    g = lambda X, k: jnp.take_along_axis(X, k[None], 0)[0]
    w = jnp.clip((lt - g(lp, k0)) / (g(lp, k1) - g(lp, k0)), 0.0, 1.0); return g(F, k0) + w * (g(F, k1) - g(F, k0))

def _verif(M, st):
    F = _nodal(M, st); zs = jnp.asarray(M.zs)
    phi = primitive_equations.get_geopotential_on_sigma(F['t'] * (1 + 0.608 * F['q']) * M.K, nodal_orography=zs[None] * M.M, sigma=M.coords.vertical,
                                                        gravity_acceleration=M.ps.gravity_acceleration, ideal_gas_constant=M.ps.ideal_gas_constant) / (M.M ** 2 / M.SEC ** 2)
    lp = jnp.log(jnp.asarray(M.sig)[:, None, None] * F['ps'][None])
    T = F['t']; t850 = _to_p(T, lp, 85000.0)
    t850 = jnp.where(jnp.log(85000.0) > lp[-1], T[-1] * (85000.0 / jnp.exp(lp[-1])) ** (RD * 0.0065 / G), t850)   # below ground as run_wx
    return dict(t850=t850, z500=_to_p(phi, lp, 50000.0) / G, u850=_to_p(F['u'], lp, 85000.0), v850=_to_p(F['v'], lp, 85000.0), ps=F['ps'])

def _jit(M, name, f):
    key = (id(M), name)
    if key not in _cache: _cache[key] = jax.jit(lambda *a: f(M, *a))
    return _cache[key]
def nodal(M, st): return _jit(M, 'nodal', _nodal)(st)
def update(M, st, Fb, Fa): return _jit(M, 'update', _update)(st, Fb, Fa)
def verif(M, st): return _jit(M, 'verif', _verif)(st)

def stack(Fs):
    return {k: jnp.stack([F[k] for F in Fs]) for k in Fs[0]}
def member(F, k):
    return {v: a[k] for v, a in F.items()}

def combine(st, sa, sb, beta):
    """st + beta (sa - sb) for the prognostic fields (start perturbations); q kept >= 0."""
    f = lambda a, x, y: a + beta * (x - y)
    return st.replace(vorticity=f(st.vorticity, sa.vorticity, sb.vorticity), divergence=f(st.divergence, sa.divergence, sb.divergence),
                      temperature_variation=f(st.temperature_variation, sa.temperature_variation, sb.temperature_variation),
                      log_surface_pressure=f(st.log_surface_pressure, sa.log_surface_pressure, sb.log_surface_pressure),
                      tracers={'specific_humidity': jnp.maximum(f(st.tracers['specific_humidity'], sa.tracers['specific_humidity'], sb.tracers['specific_humidity']), 0.0)})

def mean_state(sts):
    n = len(sts); m = lambda get: sum(get(s) for s in sts) / n
    s0 = sts[0]
    return s0.replace(vorticity=m(lambda s: s.vorticity), divergence=m(lambda s: s.divergence), temperature_variation=m(lambda s: s.temperature_variation),
                      log_surface_pressure=m(lambda s: s.log_surface_pressure), tracers={'specific_humidity': m(lambda s: s.tracers['specific_humidity'])})
