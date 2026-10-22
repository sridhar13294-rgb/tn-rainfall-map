"""Local numpy tests of the ocean mixed-layer columns (ocean.py). Run: python scripts/cyclone/mm/test_ocean.py
1. heat conservation to round-off (random fluxes, shelf columns, many steps)
2. a moving cyclone over a Bay of Bengal October profile (thin warm layer) and over a deep warm layer: cold wake
3. a calm sunny day: the surface warms slightly by day and gives most of it back at night."""
import math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocean as oc

DZ = oc.DZ_DEFAULT.astype(float); N = len(DZ); ZC = np.cumsum(DZ) - DZ / 2; K0 = 273.15


def column(sst_c, h, t_at_100=22.0, grad_below=None, S=None, ncol=1):
    """T profile: mixed layer h (m) at sst_c, linear thermocline (gradient of 29.5 -> 22 C over 30 -> 100 m, 0.107 K/m),
    then 22 -> 15 C between that depth and 300 m."""
    g1 = (29.5 - t_at_100) / 70.0 if grad_below is None else grad_below
    zt = h + (sst_c - 22.0) / g1                                    # depth where 22 C is reached
    T = np.where(ZC <= h, sst_c, np.where(ZC <= zt, sst_c - g1 * (ZC - h), 22.0 - 7.0 * (ZC - zt) / max(300 - zt, 1)))
    T = np.repeat((T + K0)[:, None, None], ncol, 1)
    Sa = np.full_like(T, 34.0) if S is None else np.repeat(np.asarray(S, float)[:, None, None], ncol, 1)
    return dict(T=T, S=Sa, u=np.zeros_like(T), v=np.zeros_like(T), dz=np.repeat(DZ[:, None, None], ncol, 1))


def test_conservation():
    rs = np.random.default_rng(1); X = 40
    st = column(29.0, 30.0, ncol=X)
    st['T'] = st['T'] + rs.normal(0, 0.3, st['T'].shape)                   # include unstable bits
    st['S'] = st['S'] + rs.normal(0, 0.2, st['S'].shape)
    dz = st['dz'].copy(); dz[8:, :5] = 1e-3; st['dz'] = dz                  # 5 shelf columns 40 m deep
    f = 2 * 7.292e-5 * np.sin(np.radians(rs.uniform(-30, 30, (X, 1))))
    H0 = oc.heat_content(st); S0 = (st['S'] * st['dz']).sum(0); Fin = 0.0; Fs = 0.0; dt = 1200.0; worst = 0.0
    for i in range(500):
        Qns = rs.uniform(-900, 200, (X, 1)); sw = np.maximum(rs.uniform(-300, 1000, (X, 1)), 0)
        tx, ty = rs.normal(0, 1.5, (X, 1)), rs.normal(0, 1.5, (X, 1)); fw = rs.normal(0, 2e-4, (X, 1))
        Ssurf = st['S'][0]
        st, sst = oc.step(st, Qns, sw, tx, ty, f, dt, fw=fw)
        Fin = Fin + (Qns + sw) * dt; Fs = Fs + Ssurf * fw * dt / oc.RHO0
        err = np.abs(oc.heat_content(st) - H0 - Fin).max(); worst = max(worst, err)
    Serr = np.abs((st['S'] * st['dz']).sum(0) - S0 - Fs).max()
    hc = oc.heat_content(st)
    print('1. conservation: 500 steps, 40 columns; worst |heat change - flux*dt| = %.3g J m-2 (column heat %.3g J m-2, '
          'relative %.1e; = %.2g W m-2 over the run); salt error %.2g psu m' % (worst, hc.max(), worst / hc.max(), worst / (500 * dt), Serr))
    assert worst / hc.max() < 1e-12 and Serr < 1e-9
    assert np.isfinite(st['T']).all()
    # land / no-SST points pass through unchanged
    st2 = column(29.0, 30.0, ncol=3); st2['T'][:, 1] = np.nan; mask = np.array([[True], [False], [True]])
    out, sst = oc.step(st2, np.full((3, 1), -500.0), np.zeros((3, 1)), np.full((3, 1), 2.0), np.zeros((3, 1)), 4e-5, 1200.0, mask=mask)
    assert np.isnan(out['T'][:, 1]).all() and np.isnan(sst[1]).all() and np.isfinite(sst[[0, 2]]).all()
    print('   land/NaN column passed through unchanged: ok')


def storm_forcing(x_km, t, vm_tau=2.5, rm=40.0, U=5.0, t_pass=24 * 3600.0, q_core=-500.0):
    """stress and heat flux at cross-track positions x_km (right of a northward track > 0) at time t (s)."""
    yc = U * (t - t_pass) / 1000.0                                         # storm centre north of the section (km)
    dx, dy = x_km, -yc; r = np.hypot(dx, dy) + 1e-6
    vr = np.where(r < rm, r / rm, (rm / r) ** 0.5) * np.exp(-(np.maximum(r - 400, 0) / 200) ** 2)
    ang = math.radians(20)                                                  # inflow angle
    ex, ey = -dy / r, dx / r                                                # counter-clockwise tangent
    ix, iy = -dx / r, -dy / r                                               # inward
    wx, wy = ex * math.cos(ang) + ix * math.sin(ang), ey * math.cos(ang) + iy * math.sin(ang)
    tau = vm_tau * vr ** 2; return tau * wx, tau * wy, q_core * vr


def run_storm(st, x, hours=72, dt=1200.0, lat=15.0, **kw):
    f = 2 * 7.292e-5 * math.sin(math.radians(lat)); sst0 = st['T'][0].copy(); n = int(hours * 3600 / dt); rec = {}
    tmax = np.zeros_like(x); dur = np.zeros_like(x)
    for i in range(n):
        t = i * dt; tx, ty, Q = storm_forcing(x, t, **kw)
        st, sst = oc.step(st, Q[:, None], np.zeros_like(Q)[:, None], tx[:, None], ty[:, None], f, dt)
        tmax = np.maximum(tmax, np.hypot(tx, ty)); dur = dur + (np.hypot(tx, ty) > 1.0) * dt / 3600
        for hh in (24, 36, 48, 72):
            if abs((i + 1) * dt - hh * 3600) < 1: rec[hh] = (sst - sst0)[:, 0].copy()
    return st, rec, tmax, dur


def test_storm():
    x = np.arange(-300, 301, 10.0); nx = len(x)
    S_bl = np.where(ZC < 25, 32.0, np.where(ZC < 45, 32.0 + 2.5 * (ZC - 25) / 20, 34.5))     # fresh barrier layer on top
    cases = [('thin warm layer (ML 30 m, 22 C at 100 m)', column(29.5, 30.0, ncol=nx)),
             ('deep warm layer (ML 80 m)', column(29.5, 80.0, ncol=nx)),
             ('thin layer + fresh top 25 m (S 32 -> 34.5)', column(29.5, 30.0, ncol=nx, S=S_bl))]
    print('2. moving storm: northward at 5 m/s, peak stress 2.5 N m-2 at 40 km radius, Q = -500 W m-2 under the core, 15N')
    res = {}
    for name, st in cases:
        st2, rec, tmax, dur = run_storm(st, x)
        h0, h1 = oc.ml_depth(st)[0, 0], oc.ml_depth(st2)
        j = int(np.argmin(rec[72])); jl = int(np.argmin(np.where(x < 0, rec[72], 9)))
        sp = np.hypot(st2['u'][0, :, 0], st2['v'][0, :, 0])
        print('   %-44s SST change at the centre line: %+.2f K (12 h after passage) %+.2f K (48 h after); '
              'coldest %+.2f K at x = %+d km (left side max %+.2f K); mixed layer %.0f -> %.0f m there; '
              'surface current up to %.2f m/s'
              % (name, rec[36][nx // 2], rec[72][nx // 2], rec[72][j], x[j], rec[72][jl], h0, h1[j, 0], sp.max()))
        res[name] = rec[72].min()
    print('   stress > 1 N m-2 lasted %.0f h at x = +40 km (peak %.1f N m-2)' % (dur[np.argmin(abs(x - 40))], tmax.max()))
    # sensitivity to m* (wind-stirring efficiency) for the thin layer
    for m in (0.5, 1.25):
        old = dict(oc.PRM); oc.PRM['mstar'] = m
        _, rec, _, _ = run_storm(column(29.5, 30.0, ncol=nx), x); oc.PRM.clear(); oc.PRM.update(old)
        print('   thin layer with m* = %.2f: coldest %+.2f K' % (m, rec[72].min()))
    # entrainment alone (no shear mixing) to show what the inertial current adds
    old = dict(oc.PRM); oc.PRM.update(rb_crit=0.0, rg_crit=0.0)
    _, rec, _, _ = run_storm(column(29.5, 30.0, ncol=nx), x); oc.PRM.clear(); oc.PRM.update(old)
    print('   thin layer, TKE entrainment only (no Richardson mixing): coldest %+.2f K' % rec[72].min())
    thin, deep = res[cases[0][0]], res[cases[1][0]]
    assert -3.5 < thin < -0.8, thin
    assert -1.0 < deep <= 0.0, deep
    assert res[cases[2][0]] > thin                                                       # barrier layer reduces cooling


def test_calm_day():
    st = column(29.5, 30.0, ncol=1); sst0 = st['T'][0, 0, 0]; dt = 1200.0; f = 3.77e-5; tr = []
    for i in range(int(86400 / dt)):
        hr = (i + 0.5) * dt / 3600
        sw = 900.0 * max(math.sin(math.pi * (hr - 6) / 12), 0.0)
        st, sst = oc.step(st, np.array([[-170.0]]), np.array([[sw]]), np.array([[0.01]]), np.array([[0.0]]), f, dt)
        tr.append(float(sst[0, 0]) - sst0)
        if abs(hr - 14.5) < 0.2: h15 = float(oc.ml_depth(st)[0, 0])
    tr = np.array(tr)
    print('3. calm sunny day (stress 0.01 N m-2, ~2.5 m/s wind; noon sun 900 W m-2, non-solar -170 W m-2, net +116 W m-2 daily mean):'
          ' SST %+.2f K at its warmest (hour %.0f), %+.2f K at the end of the day; mixed layer at 15 h %.0f m'
          % (tr.max(), (np.argmax(tr) + 0.5) * dt / 3600, tr[-1], h15))
    assert 0.05 < tr.max() < 2.0 and 0.0 < tr[-1] < tr.max()


def test_profile():
    import datetime as dt
    depth = np.array(list(range(0, 101, 5)) + list(range(125, 326, 25)), float); lat = np.arange(-40.5, 40.6, 1.5); lon = np.arange(30, 150.1, 1.5)
    Z = depth[:, None, None]; T = np.where(Z <= 40, 28.0, 28.0 - 0.06 * (Z - 40)) + 0 * lat[None, :, None] + 0 * lon[None, None]
    T = np.where((Z > 30) & (lon[None, None] < 33), np.nan, T)                       # a 30-m shelf on the west edge
    clim = dict(T=np.repeat(T[None], 12, 0), S=np.full((12,) + T.shape, 34.0), depth=depth, lat=lat, lon=lon)
    LO, LA = np.meshgrid(np.array([31.0, 88.0, 200.0]), np.array([15.0]), indexing='ij'); sst = np.full(LO.shape, 273.15 + 29.0)
    st = oc.profile_from_clim(clim, dt.datetime(2010, 10, 20), LA, LO, sst, np.ones(LO.shape, bool))
    t = st['T'][:, 1, 0] - K0
    print('4. start profile (climatology 28 C mixed layer 40 m, ERA5 SST 29 C): T at 2.5/37.5/62.5/150/285 m = %s C; '
          'shelf column depth %.0f m; outside the box generic profile, top %.1f C'
          % (np.round(np.interp([2.5, 37.5, 62.5, 150, 285], ZC, t), 2), st['dz'][:, 0, 0].sum(), st['T'][0, 2, 0] - K0))
    assert abs(t[0] - 29.0) < 1e-4 and abs(np.interp(150, ZC, t) - (28 - 0.06 * 110)) < 0.05
    assert 30 <= st['dz'][:, 0, 0].sum() < 40


if __name__ == '__main__':
    test_conservation(); test_storm(); test_calm_day(); test_profile(); print('all ok')
