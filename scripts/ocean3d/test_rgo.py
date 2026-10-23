"""CPU tests of the reduced-gravity layer (rgo.py) and its coupling to the columns. Run: python3 scripts/ocean3d/test_rgo.py
1. volume conservation (no relaxation, closed basin with islands, random wind)
2. equatorial Kelvin wave: a thermocline bump on the equator moves east at c = sqrt(g' H)
3. Ekman pumping: under a uniform wind curl the interior thermocline moves at -curl(tau/f)/rho0 in the first days
4. coastal upwelling with the columns: alongshore wind lifts the thermocline at the coast and cools the SST there"""
import math, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'cyclone', 'mm'))
import rgo, currents as cu, ocean as oc
from test_currents import tropical_profile, grid


def test_volume():
    rs = np.random.default_rng(0); LA, LO = grid(-20, 30, 40, 100, 1.0); X, Y = LA.shape
    sea = np.ones((X, Y), bool); sea[0] = sea[-1] = False; sea[:, 0] = sea[:, -1] = False; sea[20:25, 30:40] = False
    g = rgo.make_geom(LA, LO, sea, periodic=False); st = rgo.init_state(g, 100 + 20 * rs.random((X, Y)))
    V0 = (st['h'] * g['area'])[sea].sum()
    for i in range(500):
        st = rgo.step(st, rs.normal(0, 0.1, (X, Y)), rs.normal(0, 0.1, (X, Y)), g, 3600.0, prm=dict(tau_h=1e30, h_min=0.0))
    e = abs((st['h'] * g['area'])[sea].sum() - V0) / V0
    print('1. volume change after 500 one-hour steps: %.1e (relative); max |u| %.2f m/s' % (e, np.abs(st['u']).max()))
    assert e < 1e-12 and np.isfinite(st['h']).all()


def test_kelvin():
    LA, LO = grid(-20, 20, 0, 359, 1.0); X, Y = LA.shape; sea = np.ones((X, Y), bool)
    g = rgo.make_geom(LA, LO, sea); H = 100.0
    h0 = H + 10 * np.exp(-((LO - 60) / 6) ** 2 - (LA / 4) ** 2)
    st = rgo.init_state(g, h0, geostrophic=False); st['h_ref'] = np.full_like(h0, H)
    dt = 3600.0; days = 10; prm = dict(r=0.0, A=2e3, tau_h=1e30)
    j0 = np.argmin(abs(LA[0]))
    for i in range(int(days * 86400 / dt)): st = rgo.step(st, 0 * h0, 0 * h0, g, dt, prm=prm)
    a = st['h'][:, j0] - H; east = (LO[:, 0] > 60) & (LO[:, 0] < 300); x_pk = LO[east, 0][np.argmax(a[east])]
    c = (x_pk - 60) * math.pi / 180 * rgo.R / (days * 86400); c0 = math.sqrt(rgo.PRM['gp'] * H)
    print('2. equatorial Kelvin wave: speed %.2f m/s (theory sqrt(g\'H) = %.2f m/s)' % (c, c0))
    assert abs(c - c0) / c0 < 0.15


def test_pumping():
    LA, LO = grid(5, 40, 40, 100, 1.0); X, Y = LA.shape
    sea = np.ones((X, Y), bool); sea[:2] = sea[-2:] = False; sea[:, :2] = sea[:, -2:] = False
    g = rgo.make_geom(LA, LO, sea, periodic=False); cg = cu.make_geom(LA, LO, np.ones((24, X, Y)) * 12.5, sea, periodic=False)
    tx = -0.1 * np.cos(math.pi * (LA - 5) / 35.0); ty = 0 * tx
    st = rgo.init_state(g, np.full((X, Y), 150.0), geostrophic=False); dt = 3600.0; days = 3
    for i in range(int(days * 86400 / dt)): st = rgo.step(st, tx, ty, g, dt)
    wE = cu.ekman_pumping(tx, ty, cg['f'], cg, prm=dict(r_ek=0.0, h_ek=1.0))
    m = sea & (LA > 15) & (LA < 33) & (LO > 55) & (LO < 85)
    dh = -(st['h'] - 150.0)[m] / (days * 86400); w = wE[m]
    ratio = np.median(dh / w)
    print('3. Ekman pumping: interior thermocline rise / curl(tau/f)/rho0 after 3 days = %.2f (median), correlation %.2f'
          % (ratio, np.corrcoef(dh, w)[0, 1]))
    assert 0.7 < ratio < 1.3 and np.corrcoef(dh, w)[0, 1] > 0.9


def test_coast_columns():
    LA, LO = grid(5, 25, 50, 70, 0.5); X, Y = LA.shape; sea = LO > 52.0
    col = tropical_profile((X, Y), h=25.0); cg = cu.make_geom(LA, LO, col['dz'], sea, periodic=False)
    g = rgo.make_geom(LA, LO, sea, periodic=False)
    st = rgo.init_state(g, rgo.d20(col['T'], col['dz']), geostrophic=False)
    ty = 0.15 * np.ones((X, Y)); z = 0 * ty; dt = 1800.0; f = cg['f']; T0 = col['T'][0].copy(); h0 = st['h'].copy()
    for i in range(int(10 * 86400 / dt)):
        col, _ = oc.step(col, z, z, z, ty, f, dt, mask=sea)
        st = rgo.step(st, z, ty, g, dt)
        q = rgo.column_transports(st, g, cg, z, ty, f)
        col = cu.step(col, z, ty, f, cg, dt, q=q)
    j = np.argmin(abs(LA[0] - 12)); ic = np.where(sea[:, j])[0][0]
    print('4. coastal upwelling, 10 days, layer + columns: thermocline at the coast %+.0f m, 6 deg offshore %+.0f m; '
          'SST coast %+.2f K, offshore %+.2f K' % ((st['h'] - h0)[ic, j], (st['h'] - h0)[ic + 12, j], (col['T'][0] - T0)[ic, j], (col['T'][0] - T0)[ic + 12, j]))
    assert (st['h'] - h0)[ic, j] < -20 and (col['T'][0] - T0)[ic, j] < (col['T'][0] - T0)[ic + 12, j] - 1.0


if __name__ == '__main__':
    test_volume(); test_kelvin(); test_pumping(); test_coast_columns(); print('all ok')
