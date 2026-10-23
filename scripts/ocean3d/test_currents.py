"""CPU tests of the column-ocean currents and upwelling (currents.py). Run: python3 scripts/ocean3d/test_currents.py
1. conservation of sum(T dz area) and salt, no new extremes, uniform field stays uniform (land, shelf, random wind)
2. Ekman pumping on the grid equals curl(tau/f)/rho0 for a smooth wind away from the equator
3. coastal upwelling: alongshore wind with the coast on the left (northern hemisphere) cools the coastal cell; reversed
   wind gives downwelling (no cooling)
4. equatorial easterlies: upwelling and cooling on the equator, none at 8 degrees
5. numpy and jax.numpy give the same answer (skipped when jax is missing)."""
import math, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'cyclone', 'mm'))
import currents as cu
import ocean as oc

DZ = oc.DZ_DEFAULT.astype(float); N = len(DZ); ZC = np.cumsum(DZ) - DZ / 2; K0 = 273.15


def tropical_profile(shape, sst=29.0, h=30.0):
    T = np.where(ZC <= h, sst, np.maximum(sst - 0.08 * (ZC - h), 12.0)) + K0
    T = np.broadcast_to(T.reshape((-1,) + (1,) * len(shape)), (N,) + shape).copy()
    S = np.broadcast_to(np.where(ZC < 30, 34.0, 35.0).reshape((-1,) + (1,) * len(shape)), (N,) + shape).copy()
    return dict(T=T, S=S, u=np.zeros_like(T), v=np.zeros_like(T), dz=np.broadcast_to(DZ.reshape((-1, 1, 1)), (N,) + shape).copy())


def grid(lat0, lat1, lon0, lon1, d):
    la = np.arange(lat0, lat1 + 1e-6, d); lo = np.arange(lon0, lon1 + 1e-6, d)
    LO, LA = np.meshgrid(lo, la, indexing='ij'); return LA, LO


def test_conservation():
    rs = np.random.default_rng(0); LA, LO = grid(-6, 20, 60, 80, 1.0); X, Y = LA.shape
    st = tropical_profile((X, Y)); st['T'] = st['T'] + rs.normal(0, 0.5, st['T'].shape); st['S'] = st['S'] + rs.normal(0, 0.3, st['S'].shape)
    sea = np.ones((X, Y), bool); sea[:4, 10:] = False; sea[10:13, 5:8] = False                    # a coast and an island
    dz = st['dz'].copy(); dz[10:, 4:7, 10:14] = 1e-3; st['dz'] = dz                              # a 50 m shelf
    g = cu.make_geom(LA, LO, st['dz'], sea)
    A = g['area']; vol = lambda s, k: (s[k] * g['dzR'] * A).sum()
    H0, S0 = vol(st, 'T'), vol(st, 'S'); lo_, hi_ = st['T'][g['real']].min(), st['T'][g['real']].max()
    f = g['f']; dt = 1800.0
    for i in range(200):
        tx = rs.normal(0, 0.3, (X, Y)); ty = rs.normal(0, 0.3, (X, Y))
        st = cu.step(st, tx, ty, f, g, dt)
    eT = abs(vol(st, 'T') - H0) / H0; eS = abs(vol(st, 'S') - S0) / S0
    Tr = st['T'][g['real']]
    print('1. conservation over 200 steps with random winds, coast, island, shelf: relative heat error %.1e, salt %.1e; '
          'range %.2f..%.2f K inside the start range %.2f..%.2f' % (eT, eS, Tr.min(), Tr.max(), lo_, hi_))
    assert eT < 1e-12 and eS < 1e-12 and Tr.min() >= lo_ - 1e-9 and Tr.max() <= hi_ + 1e-9
    u = tropical_profile((X, Y)); u['T'][:] = 300.0; u['S'][:] = 35.0; u['dz'] = dz
    u2 = cu.step(u, rs.normal(0, 0.5, (X, Y)), rs.normal(0, 0.5, (X, Y)), f, g, dt, prm=dict(geo=0))
    assert np.abs(u2['T'][g['real']] - 300.0).max() < 1e-9
    print('   uniform field stays uniform: ok')


def test_pumping():
    LA, LO = grid(10, 30, 60, 90, 0.5); X, Y = LA.shape
    st = tropical_profile((X, Y)); g = cu.make_geom(LA, LO, st['dz'])
    y = np.radians(LA); x = np.radians(LO); R = cu.REARTH
    tx = -0.1 * np.cos(2 * np.pi * (LA - 10) / 20.0); ty = 0.05 * np.sin(2 * np.pi * (LO - 60) / 30.0)
    f = g['f']
    w = cu.ekman_pumping(tx, ty, f, g, prm=dict(r_ek=0.0))
    # analytic curl(tau / f) / rho0 on the sphere
    a, b = tx / f, ty / f
    dbdx = np.gradient(b, x[:, 0], axis=0) / (R * np.cos(y)); dacos = np.gradient(a * np.cos(y), y[0], axis=1) / (R * np.cos(y))
    wa = (dbdx - dacos) / cu.RHO0
    inner = (slice(3, -3), slice(3, -3)); err = np.abs(w - wa)[inner].max() / np.abs(wa[inner]).max()
    print('2. Ekman pumping vs analytic curl(tau/f)/rho0: max |w| %.2f m/day, max error %.1f %% of max' % (np.abs(wa[inner]).max() * 86400, 100 * err))
    assert err < 0.05


def run_coast(sign, days=10, mix=True, off=False):
    LA, LO = grid(5, 25, 50, 65, 0.5); X, Y = LA.shape
    sea = LO > 52.0                                                                               # land to the west (Somalia-like)
    st = tropical_profile((X, Y), h=25.0); g = cu.make_geom(LA, LO, st['dz'], sea)
    ty = sign * 0.15 * np.ones((X, Y))                                                            # south-westerly monsoon: northward stress
    T0 = st['T'][0].copy(); dt = 1800.0
    z = np.zeros_like(ty)
    for i in range(int(days * 86400 / dt)):
        if mix: st, _ = oc.step(st, z, z, z, ty, g['f'], dt, mask=sea)                         # column mixing, no heat flux
        if not off: st, d = cu.step(st, z, ty, g['f'], g, dt, diag=True)
        else: d = dict(wE=np.zeros_like(ty))
    j = np.argmin(abs(LA[0] - 12)); ic = np.where(sea[:, j])[0][0]
    return (st['T'][0] - T0)[ic, j], (st['T'][0] - T0)[ic + 12, j], d['wE'][ic, j] * 86400, (st['T'][6] - T0)[ic, j]


def test_coastal():
    dc, do, w, d30 = run_coast(+1); dc2, do2, w2, _ = run_coast(-1); dn, don, _, dn30 = run_coast(+1, mix=False)
    print('3. coastal upwelling, 10 days of 0.15 N/m2 alongshore stress at 12N, columns mixing as in the model: coastal cell '
          'SST %+.2f K (w at 40 m %+.1f m/day), 6 deg offshore %+.2f K (wind mixing only); reversed wind: coast %+.2f K '
          '(w %+.1f m/day); currents off (column only): coast %+.2f K' % (dc, w, do, dc2, w2, run_coast(+1, mix=True, off=True)[0]))
    print('   advection alone (no column mixing): coast SST %+.2f K, 32 m %+.2f K' % (dn, dn30))
    assert dc < -1.0 and w > 0 and dc < do - 1.0 and dc2 > do2 - 0.3 and w2 < 0


def test_equator():
    LA, LO = grid(-12, 12, 60, 70, 1.0); X, Y = LA.shape
    st = tropical_profile((X, Y), h=30.0); g = cu.make_geom(LA, LO, st['dz'])
    tx = -0.05 * np.ones((X, Y)); T0 = st['T'][0].copy(); dt = 1800.0
    z = np.zeros_like(tx)
    for i in range(int(10 * 86400 / dt)):
        st, _ = oc.step(st, z, z, tx, z, g['f'], dt)                                             # column mixing, no heat flux
        st, d = cu.step(st, tx, z, g['f'], g, dt, diag=True, prm=dict(geo=0))
    j0 = np.argmin(abs(LA[0])); j8 = np.argmin(abs(LA[0] - 8)); i = X // 2
    print('4. equatorial easterlies 0.05 N/m2, 10 days: w at 40 m on the equator %+.2f m/day, at 8N %+.2f m/day; SST change %+.2f K '
          'on the equator, %+.2f K at 8N (both with wind mixing)' % (d['wE'][i, j0] * 86400, d['wE'][i, j8] * 86400, (st['T'][0] - T0)[i, j0], (st['T'][0] - T0)[i, j8]))
    assert d['wE'][i, j0] > 0 and (st['T'][0] - T0)[i, j0] < -0.3 and (st['T'][0] - T0)[i, j8] > (st['T'][0] - T0)[i, j0] + 0.3


def test_jax():
    try:
        import jax, jax.numpy as jnp
    except Exception:
        print('5. jax not installed here: skipped'); return
    jax.config.update('jax_enable_x64', True)
    rs = np.random.default_rng(3); LA, LO = grid(0, 20, 60, 80, 1.0); X, Y = LA.shape
    st = tropical_profile((X, Y)); sea = np.ones((X, Y), bool); sea[:3] = False; g = cu.make_geom(LA, LO, st['dz'], sea)
    tx, ty = rs.normal(0, 0.2, (X, Y)), rs.normal(0, 0.2, (X, Y))
    a = cu.step(st, tx, ty, g['f'], g, 1800.0)
    fj = jax.jit(lambda s, x, y: cu.step(s, x, y, g['f'], g, 1800.0, xp=jnp))
    b = fj({k: jnp.asarray(v) for k, v in st.items()}, jnp.asarray(tx), jnp.asarray(ty))
    e = float(np.abs(np.asarray(b['T']) - a['T']).max()); print('5. jax vs numpy max difference %.1e K' % e); assert e < 1e-9


if __name__ == '__main__':
    test_conservation(); test_pumping(); test_coastal(); test_equator(); test_jax(); print('all ok')
