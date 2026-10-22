"""Tests for nudge.py (numpy only; run: python test_nudge.py, or pytest).
1. observation operator: exact for fields linear in lat/lon/log p; both array layouts; MSLP as mm2's post().
2. OI on synthetic truth / background / observations: the analysis is closer to the truth than the background (near the
   observations, every variable), O-A < O-B, and gross errors (a +25 K radiosonde temperature, a +30 hPa pressure) are
   rejected.
3. LHN: heating profile shape, column heating = L_v x observed rain where the model is dry, ratio clipping 0.3-3,
   relative humidity kept, lightning proxy, regridding."""
import os, sys, math, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nudge as N
from scipy import ndimage as ndi

LATS = np.arange(-90, 90.1, 1.5); LONS = np.arange(0, 360, 1.5)
LEVS = np.array([50, 100, 150, 200, 250, 300, 400, 500, 600, 700, 850, 925, 1000], float)

def test_operator_linear():
    gl = np.sort(np.concatenate([np.linspace(-88, 88, 60) + 0.3 * np.sin(np.arange(60))]))        # irregular, like Gaussian
    lo = np.arange(0, 360, 2.0)
    LA, LO = np.meshgrid(gl, lo, indexing='ij')
    sig = np.linspace(0.05, 0.99, 20)
    ps = 95000.0 + 30.0 * LA + 10.0 * LO; zs = np.zeros_like(ps)
    p3 = sig[:, None, None] * ps[None]
    T = 200.0 + 20.0 * np.log(p3 / 1e4) + 0.1 * LA[None]                                          # linear in ln p and lat
    q = np.full_like(T, 0.005); u = 3.0 + 0.0 * T + 0.05 * LO[None]; v = 0.0 * T
    rs = np.random.default_rng(0); n = 50
    olat = rs.uniform(-60, 60, n); olon = rs.uniform(2.0, 356.0, n); opp = rs.uniform(150, 900, n)
    obs = dict(lat=olat, lon=olon, var=np.array(['t'] * n), type=np.array(['temp'] * n), p=opp, z=np.zeros(n))
    for layout in ('latlon', 'lonlat'):
        f = dict(t=T, q=q, u=u, v=v, ps=ps, zs=zs)
        if layout == 'lonlat': f = {k: np.swapaxes(a, -1, -2) for k, a in f.items()}
        E = N.model_equivalents(f, gl, lo, obs, sig=sig, layout=layout)
        psx = 95000.0 + 30.0 * olat + 10.0 * olon
        want = 200.0 + 20.0 * np.log(opp * 100 / 1e4) + 0.1 * olat
        assert np.allclose(E['psb'], psx, atol=1e-6), layout
        assert np.allclose(E['hx'], want, atol=1e-6), (layout, np.abs(E['hx'] - want).max())
    # MSLP = mm2 post() formula with the lowest-level temperature
    zs2 = np.full_like(ps, 500.0); f = dict(t=T, q=q, u=u, v=v, ps=ps, zs=zs2)
    ob2 = dict(lat=olat[:5], lon=olon[:5], var=np.array(['mslp'] * 5), type=np.array(['synop'] * 5), p=np.full(5, np.nan), z=np.full(5, 500.0))
    E = N.model_equivalents(f, gl, lo, ob2, sig=sig)
    Tl = 200.0 + 20.0 * np.log(0.99 * E['psb'] / 1e4) + 0.1 * olat[:5]
    assert np.allclose(E['hx'], E['psb'] * np.exp(N.G * 500.0 / (N.RD * (Tl + 0.0065 * 250.0))), rtol=1e-9)
    print('operator: exact for linear fields (both layouts), MSLP as post()')

# ------------------------------------------------------------------------------------------------- synthetic OI
def smooth_noise(rs, shape, sig_cells):
    x = rs.standard_normal(shape)
    s = (0,) * (len(shape) - 2) + (sig_cells, sig_cells)
    y = ndi.gaussian_filter(x, s, mode=['nearest'] * (len(shape) - 2) + ['nearest', 'wrap'])
    return y / y.std()

def synth(seed=1):
    rs = np.random.default_rng(seed); ny, nx, K = len(LATS), len(LONS), len(LEVS)
    LA = LATS[:, None] * np.ones((1, nx))
    Tm = np.interp(np.log(LEVS), np.log([50, 100, 200, 300, 500, 700, 850, 1000]), [210, 195, 218, 240, 266, 282, 291, 299])
    truth = {}
    vc = np.exp(-(np.log(LEVS)[:, None] - np.log(LEVS)[None]) ** 2 / (2 * 0.4 ** 2)); Lc = np.linalg.cholesky(vc + 1e-6 * np.eye(K))
    def field3(scale, sc):
        z = np.stack([smooth_noise(rs, (ny, nx), sc) for _ in range(K)]); return scale * np.einsum('kl,lyx->kyx', Lc, z)
    truth['temperature'] = Tm[:, None, None] - 0.3 * np.abs(LA)[None] * (LEVS[:, None, None] > 300) + field3(3.0, 5)
    truth['u_component_of_wind'] = 10 * np.sin(np.radians(LA))[None] * (LEVS[:, None, None] / 1000) + field3(6.0, 4)
    truth['v_component_of_wind'] = field3(5.0, 4)
    rh = np.clip(0.7 + 0.15 * field3(1.0, 5), 0.2, 0.98)
    truth['specific_humidity'] = rh * N.qsat(truth['temperature'], LEVS[:, None, None] * 100) * (LEVS[:, None, None] >= 300)
    ps = 100800.0 + 600.0 * smooth_noise(rs, (ny, nx), 5)
    zs = np.zeros((ny, nx))
    # background = truth + errors with the OI's own statistics (sigma_b table; Gaussian correlation ~400 km horizontally)
    bg = {}; c = 1.7                                                       # gaussian-filter sigma in cells -> L ~ 400 km
    for v, key in (('temperature', 't'), ('u_component_of_wind', 'u'), ('v_component_of_wind', 'v')):
        sb = N.sigma_b_profile(key, LEVS)[:, None, None]
        vcv = np.exp(-(np.log(LEVS)[:, None] - np.log(LEVS)[None]) ** 2 / (2 * N.OI_DEFAULTS['Lv'][key] ** 2)); Lk = np.linalg.cholesky(vcv + 1e-6 * np.eye(K))
        e = np.einsum('kl,lyx->kyx', Lk, np.stack([smooth_noise(rs, (ny, nx), c) for _ in range(K)]))
        bg[v] = truth[v] + sb * e
    qs = N.qsat(truth['temperature'], LEVS[:, None, None] * 100)
    vcq = np.exp(-(np.log(LEVS)[:, None] - np.log(LEVS)[None]) ** 2 / (2 * 0.2 ** 2)); Lq = np.linalg.cholesky(vcq + 1e-6 * np.eye(K))
    eq = np.einsum('kl,lyx->kyx', Lq, np.stack([smooth_noise(rs, (ny, nx), c) for _ in range(K)]))
    bg['specific_humidity'] = np.maximum(truth['specific_humidity'] + 0.08 * qs * eq * (LEVS[:, None, None] >= 300), 0)
    psb = ps + 60.0 * smooth_noise(rs, (ny, nx), 1.3)
    return truth, ps, bg, psb, zs

def make_obs(truth, ps, zs, rs, t0=0):
    """surface stations (mslp, td), ships and scatterometer winds, radiosondes (t, td, u, v on mandatory levels)."""
    rec = []
    def H(var, typ, la, lo, p):
        ob = dict(lat=np.array([la]), lon=np.array([lo]), var=np.array([var]), type=np.array([typ]), p=np.array([p]), z=np.array([0.0]))
        f = dict(t=truth['temperature'], q=truth['specific_humidity'], u=truth['u_component_of_wind'], v=truth['v_component_of_wind'], ps=ps, zs=zs)
        return float(N.model_equivalents(f, LATS, LONS, ob, p3=LEVS * 100.0)['hx'][0])
    def td_of_q(q, p):                                                     # invert q -> dew point (K)
        e = q * p / (0.622 + 0.378 * q); x = np.log(e / 611.2); return 273.15 + 243.5 * x / (17.67 - x)
    for i in range(250):                                                   # synop
        la, lo = rs.uniform(-35, 35), rs.uniform(35, 115); sid = f'S{i}'
        so = N.obs_error('synop', 'mslp', None, 0.0)
        rec.append(('synop', sid, la, lo, np.nan, 0.0, t0, 'mslp', H('mslp', 'synop', la, lo, np.nan) + rs.normal(0, so)))
        q = H('q', 'synop', la, lo, np.nan); pst = H('ps', 'synop', la, lo, np.nan)
        rec.append(('synop', sid, la, lo, np.nan, 0.0, t0, 'td', td_of_q(q * (1 + rs.normal(0, 0.08)), pst)))
    for i in range(600):                                                   # scatterometer + ships
        la, lo = rs.uniform(-35, 25), rs.uniform(45, 110); typ = 'scat' if i < 500 else 'ship'
        for v in ('u', 'v'): rec.append((typ, f'W{i}', la, lo, np.nan, 0.0, t0, v, H(v, typ, la, lo, np.nan) + rs.normal(0, N.obs_error(typ, v))))
    for i in range(40):                                                    # radiosondes
        la, lo = rs.uniform(-30, 35), rs.uniform(40, 115); sid = f'R{i}'
        for p in (1000, 925, 850, 700, 500, 400, 300, 250, 200, 150, 100):
            if p * 100 > ps[np.abs(LATS - la).argmin(), np.abs(LONS - lo).argmin()]: continue
            for v in ('t', 'u', 'v'): rec.append(('temp', sid, la, lo, float(p), 0.0, t0, v, H(v, 'temp', la, lo, p) + rs.normal(0, N.obs_error('temp', v, p))))
            if p >= 300:
                q = H('q', 'temp', la, lo, p); rec.append(('temp', sid, la, lo, float(p), 0.0, t0, 'td', td_of_q(q * (1 + rs.normal(0, 0.08)), p * 100.0)))
    cols = list(zip(*rec))
    return dict(type=np.array(cols[0]), sid=np.array(cols[1]), lat=np.array(cols[2], float), lon=np.array(cols[3], float), p=np.array(cols[4], float),
                z=np.array(cols[5], float), time=np.array(cols[6], np.int64), var=np.array(cols[7]), value=np.array(cols[8], float))

def test_oi_synthetic():
    import time
    truth, ps, bg, psb, zs = synth(1)
    rs = np.random.default_rng(5); obs = make_obs(truth, ps, zs, rs)
    # two gross errors
    i_t = np.where((obs['type'] == 'temp') & (obs['var'] == 't') & (obs['p'] == 500))[0][0]; obs['value'][i_t] += 25.0
    i_p = np.where(obs['var'] == 'mslp')[0][3]; obs['value'][i_p] += 3000.0
    t_a = time.time()
    inc, dps, rep = N.oi_analysis(bg, LEVS, LATS, LONS, psb, zs, obs, t0_unix=0, cfg=dict(region=(-45, 45, 25, 125)))
    dt_s = time.time() - t_a
    print(N.report_text(rep)); print('OI time %.1f s' % dt_s)
    A = N.apply_increments(dict(f3=bg, ps=psb, levs=LEVS), inc, dps)
    # where the observations are: 30S-30N, 45E-110E, levels 925-200
    jm = (LATS >= -30) & (LATS <= 30); im = (LONS >= 45) & (LONS <= 110); km = (LEVS >= 200) & (LEVS <= 925)
    out = {}
    for v in ('temperature', 'u_component_of_wind', 'v_component_of_wind', 'specific_humidity'):
        kk = km & (LEVS >= 300) if v == 'specific_humidity' else km
        eb = (bg[v] - truth[v])[kk][:, jm][:, :, im]; ea = (A['f3'][v] - truth[v])[kk][:, jm][:, :, im]
        out[v] = (float(np.sqrt((eb ** 2).mean())), float(np.sqrt((ea ** 2).mean())))
    eb = (psb - ps)[jm][:, im]; ea = (A['ps'] - ps)[jm][:, im]; out['ps'] = (float(np.sqrt((eb ** 2).mean())), float(np.sqrt((ea ** 2).mean())))
    for v, (b, a) in out.items():
        print(f'  {v:22s} background rms {b:.4g}  analysis rms {a:.4g}  ({100 * (1 - a / b):+.0f}% error reduction)')
        assert a < b, v
    assert rep['rejected'].get('gross', 0) >= 2, rep['rejected']
    I = N.innovations(bg, LEVS, LATS, LONS, psb, zs, obs, 0)
    for i_bad, name in ((i_t, 'T +25 K'), (i_p, 'MSLP +30 hPa')):
        hit = np.where((I['sid'] == obs['sid'][i_bad]) & (I['var'] == obs['var'][i_bad]) & ((I['p'] / 100 == obs['p'][i_bad]) | ~I['upper']))[0]
        assert any(I['why'][h] == 'gross' for h in hit), name
    print('gross errors rejected:', rep['rejected'])
    for r in rep['rows']:
        if r['oma_rms'] is not None and r['var'] in ('t', 'u', 'v', 'mslp'): assert r['oma_rms'] < r['omb_rms'], r
    return out

# ------------------------------------------------------------------------------------------------- LHN
def test_lhn():
    sig = np.linspace(0.02, 0.99, 32); dsig = np.full(32, 0.97 / 31)
    h = N.default_heating_profile(sig)
    assert (h[sig >= 0.95] == 0).all() and (h[sig <= 0.15] == 0).all() and (h > 0).sum() > 15
    assert abs(sig[np.argmax(h)] - 0.5) < 0.05, sig[np.argmax(h)]
    X = (32, 3, 2); ps = np.full(X[1:], 100000.0); p = sig[:, None, None] * ps[None]
    T = 300.0 - 80.0 * (1 - sig[:, None, None]) * np.ones(X); q = 0.8 * N.qsat(T, p)
    lh = 1e-4 * N.default_heating_profile(sig)[:, None, None] * np.ones(X)          # model heating profile (K/s)
    rm = np.array([[0.0, 2.0, 2.0], [0.5, 0.0, 1.0]]).T / 3600.0                 # model rain mm/h -> kg m-2 s-1
    ro = np.array([[10.0, 1.0, 40.0], [0.5, 0.0, 0.0]]).T / 3600.0
    dT, dq = N.lhn_tendency(lh, rm, ro, T, q, p, dsig, ps, sig)
    # (0,0): model dry, obs 10 mm/h -> default profile with column heating = Lv * rain
    col = (N.CP * dT[:, 0, 0] * dsig * ps[0, 0] / N.G).sum()
    assert abs(col - N.LV * ro[0, 0]) / (N.LV * ro[0, 0]) < 1e-6, col
    # (1,0): obs 1, model 2 -> alpha 0.5 -> dT = -0.5 lh
    assert np.allclose(dT[:, 1, 0], -0.5 * lh[:, 1, 0])
    # (2,0): obs 40, model 2 -> ratio 20 clipped to 3 -> dT = +2 lh
    assert np.allclose(dT[:, 2, 0], 2.0 * lh[:, 2, 0])
    # (0,1): equal -> nothing; (1,1): both dry -> nothing; (2,1): obs dry, model 1 -> alpha 0.3 -> -0.7 lh
    assert np.allclose(dT[:, 0, 1], 0) and np.allclose(dT[:, 1, 1], 0) and np.allclose(dT[:, 2, 1], -0.7 * lh[:, 2, 1])
    # relative humidity kept after a 10-min step
    dt = 600.0; rh0 = q / N.qsat(T, p); rh1 = (q + dt * dq) / N.qsat(T + dt * dT, p)
    assert np.abs(rh1 - rh0).max() < 2e-3, np.abs(rh1 - rh0).max()
    assert abs(N.lhn_weight(1.0) - 1) < 1e-12 and abs(N.lhn_weight(4.5) - 0.5) < 1e-12 and N.lhn_weight(7.0) == 0
    # lightning proxy
    rs = np.random.default_rng(3); ltg = rs.poisson(2.0, (40, 40)).astype(float); rain = 3.0 * ltg + rs.normal(0, 0.2, ltg.shape)
    rain[:5] = np.nan
    cf = N.lightning_rain_coef(rain, ltg); assert cf is not None and abs(cf - 3.0) < 0.3, cf
    r, conv = N.merge_rain(rain, ltg, cf); assert np.isfinite(r).all() and conv.any()
    # regrid 0.25 -> coarse: mean conserved for a constant field
    la = np.arange(-39.875, 40, 0.25); lo = np.arange(30.125, 120, 0.25); F = np.full((len(la), len(lo)), 7.0)
    R = N.regrid_mean(F, la, lo, LATS, LONS); assert np.nanmax(np.abs(R - 7.0)) < 1e-12 and np.isfinite(R).sum() > 1000
    print('LHN: profile, column heating = Lv x rain, ratio clipped 0.3-3, RH kept, weights, lightning proxy, regrid - ok')

def test_consensus_wrapper():
    """analyse_consensus (the live2 entry point) on a fake consensus with three 'centres': one equal to the truth, one
    with the background's error, one with three times it. centre_fit must rank them, and the analysed mean must be
    closer to the truth than the mean."""
    import tempfile, datetime as dt
    truth, ps, bg, psb, zs = synth(2); rs = np.random.default_rng(9); obs = make_obs(truth, ps, zs, rs, t0=1792627200)
    fn = os.path.join(tempfile.mkdtemp(), 'obs_2026102200.npz'); np.savez_compressed(fn, **obs)
    diffs = {'TRUE': {v: truth[v] - bg[v] for v in bg}, 'SAME': {v: 0.0 * bg[v] for v in bg}, 'BAD': {v: 2.0 * (bg[v] - truth[v]) for v in bg}}
    psd = {'TRUE': ps - psb, 'SAME': 0 * psb, 'BAD': 2.0 * (psb - ps)}
    CN = dict(f3=bg, f2={'surface_pressure': psb, 'geopotential_at_surface': zs * N.G}, diffs=diffs, ps_diffs=psd, levs=list(LEVS), lats=LATS, lons=LONS)
    fit = N.centre_fit(CN, N.load_obs(fn), 1792627200)
    print('centre fit (normalised O-B rms):', {c: round(r['all'], 2) for c, r in fit.items()})
    assert fit['TRUE']['all'] < fit['SAME']['all'] < fit['BAD']['all']
    CN2, rep = N.analyse_consensus(CN, fn, dt.datetime(2026, 10, 22, 0), cfg=dict(region=(-45, 45, 25, 125)), use_spread=False, verbose=False)
    jm = (LATS >= -30) & (LATS <= 30); im = (LONS >= 45) & (LONS <= 110)
    e0 = np.sqrt(((bg['temperature'] - truth['temperature'])[:, jm][:, :, im] ** 2).mean())
    e1 = np.sqrt(((CN2['f3']['temperature'] - truth['temperature'])[:, jm][:, :, im] ** 2).mean())
    assert e1 < e0 and CN2['obs_analysis'] and CN2['f2']['surface_pressure'] is not psb
    print(f'analyse_consensus: T rms vs truth {e0:.3f} -> {e1:.3f} K')

if __name__ == '__main__':
    test_operator_linear(); test_lhn(); test_oi_synthetic(); test_consensus_wrapper(); print('all nudge tests passed')
