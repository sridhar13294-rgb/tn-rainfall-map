"""Tests for obsop.py (numpy; run: python test_obsop.py, or pytest). Under a second.
1. Bilinear + ln-p interpolation are exact for fields linear in lon, lat and ln p (Gaussian-like irregular latitudes,
   mm2's [lon, lat] layout), with and without a member axis.
2. Station pressure: equals the model surface pressure at the model terrain height; a station 300 m higher reads the
   hypsometric value; MSLP the nudge.py way.
3. 2-m temperature lapse correction, 10-m wind factors (sea ~0.84, land ~0.68), radiosonde levels below ground -> NaN.
4. QC: gross errors rejected (and their wind partner), scatterometer over land rejected, terrain-height check.
5. Real records: one report per station (closest to t0), dew point -> q."""
import os, sys, math, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import obsop as OP

def grid():
    lat = np.sort(np.linspace(-87, 87, 48) + 0.3 * np.sin(np.arange(48))); lon = np.arange(0, 360, 3.75)
    LO, LA = np.meshgrid(lon, lat, indexing='ij'); sig = np.linspace(0.03, 0.99, 24).astype(np.float32)
    return lat, lon, LA, LO, sig

def fields(LA, LO, sig, zs=None, shift=0.0):
    ps = 98000.0 + 20.0 * LA + 5.0 * np.minimum(LO, 300.0) + shift
    lp = np.log(sig[:, None, None] * ps[None])
    T = 150.0 + 12.0 * lp + 0.05 * LA[None] + shift
    return dict(t=T, q=np.full_like(T, 0.008), u=2.0 + 0.0 * T + 0.01 * LO[None], v=0.0 * T - 1.0, ps=ps)

def test_linear_exact():
    lat, lon, LA, LO, sig = grid(); F = fields(LA, LO, sig)
    rs = np.random.default_rng(0); n = 60
    ob = dict(type=np.array(['temp'] * n), var=np.array(['t'] * n), lat=rs.uniform(-60, 60, n), lon=rs.uniform(1, 290, n), p=rs.uniform(150, 850, n), z=np.full(n, np.nan))
    st = dict(lon=lon, lat=lat, sig=sig, zs=np.zeros_like(LA), land=np.zeros_like(LA))
    H = OP.Operator(st, ob); hx, vert = H(F)
    want = 150.0 + 12.0 * np.log(ob['p'] * 100) + 0.05 * ob['lat']
    assert np.allclose(hx, want, atol=1e-6), np.abs(hx - want).max()
    psx = 98000.0 + 20.0 * ob['lat'] + 5.0 * ob['lon']
    assert np.allclose(vert, np.log(ob['p'] * 100 / psx), atol=1e-6)
    # member axis: [K, L, X, Y]
    F2 = {k: np.stack([fields(LA, LO, sig, shift=s)[k] for s in (0.0, 1.0, 2.0)]) for k in F}
    hk, _ = H(F2); assert hk.shape == (3, n)
    for i, s in enumerate((0.0, 1.0, 2.0)):
        assert np.allclose(hk[i], H(fields(LA, LO, sig, shift=s))[0], atol=1e-6)

def test_surface_ops():
    lat, lon, LA, LO, sig = grid(); F = fields(LA, LO, sig)
    zs = np.full_like(LA, 200.0); land = (LO < 180).astype(float)
    st = dict(lon=lon, lat=lat, sig=sig, zs=zs, land=land)
    la = np.array([10.0, 10.0, 10.0, 10.0, -20.0, -20.0, 10.0]); lo = np.array([90.0, 90.0, 90.0, 90.0, 250.0, 250.0, 90.0])
    ob = dict(type=np.array(['synop', 'synop', 'synop', 'synop', 'ship', 'ship', 'synop']), var=np.array(['ps', 'ps', 't', 'u', 'u', 'mslp', 'ps']),
              lat=la, lon=lo, p=np.full(7, np.nan), z=np.array([200.0, 500.0, 500.0, 200.0, np.nan, np.nan, 2000.0]))
    H = OP.Operator(st, ob); hx, _ = H(F)
    psb = 98000.0 + 20.0 * la + 5.0 * lo
    Tl = 150.0 + 12.0 * np.log(sig[-1] * psb) + 0.05 * la
    assert abs(hx[0] - psb[0]) < 5e-2                                              # station at the model terrain height
    z1 = OP.RD * Tl[1] * (1 + 0.608 * 0.008) / OP.G * math.log(1 / sig[-1])
    Ts = Tl[1] + OP.LAPSE * z1; want = psb[1] * math.exp(-OP.G * 300.0 / (OP.RD * (Ts - OP.LAPSE * 150.0) * (1 + 0.608 * 0.008)))
    assert abs(hx[1] - want) < 1e-2 and 3000 < psb[1] - hx[1] < 4000                # ~35 hPa per 300 m
    assert abs(hx[2] - (Tl[2] + OP.LAPSE * (z1 - 300.0 - 2.0))) < 1e-4             # 2-m T: lapse to the station
    u1 = 2.0 + 0.01 * lo
    assert 0.62 < hx[3] / u1[3] < 0.72 and 0.80 < hx[4] / u1[4] < 0.88             # land / sea 10-m wind factors
    assert hx[5] > psb[5] + 2000                                                   # MSLP over 200-m terrain
    # QC: the 2000-m station differs 1800 m from the model terrain -> 'height'
    d = np.zeros(7); d[0] = 5000.0
    ok, why = OP.quality_control(H, ob, d, np.full(7, 100.0), np.full(7, 50.0))
    assert why[0] == 'gross' and why[6] == 'height' and ok[1] and ok[2]

def test_sonde_below_ground_and_qc_pairs():
    lat, lon, LA, LO, sig = grid(); F = fields(LA, LO, sig)
    st = dict(lon=lon, lat=lat, sig=sig, zs=np.zeros_like(LA), land=(LA > 0).astype(float))
    ob = dict(type=np.array(['temp', 'temp', 'temp', 'scat', 'scat', 'scat', 'scat']), var=np.array(['t', 'u', 'v', 'u', 'v', 'u', 'v']),
              lat=np.array([30.0, 0, 0, -30, -30, 40, 40]), lon=np.array([100.0, 100, 100, 200, 200, 200, 200]),
              p=np.array([1050.0, 500, 500, np.nan, np.nan, np.nan, np.nan]), z=np.full(7, np.nan), sid=np.array(['a', 'b', 'b', 's1', 's1', 's2', 's2']))
    H = OP.Operator(st, ob); hx, _ = H(F)
    assert np.isnan(hx[0]) and np.isfinite(hx[1:]).all()
    d = np.array([0.0, 30.0, 0.5, 0.5, 0.5, 0.5, 0.5]); so = np.full(7, 2.0); sp = np.full(7, 1.0)
    ok, why = OP.quality_control(H, ob, np.where(np.isfinite(hx), d, np.nan), so, sp)
    assert why[0] == 'undefined' and why[1] == 'gross' and why[2] == 'pair'
    assert ok[3] and ok[4] and why[5] == 'land' and why[6] in ('land', 'pair')

def test_prepare_real():
    t0 = 1_800_000_000
    obs = dict(type=np.array(['synop', 'synop', 'synop', 'temp', 'temp']), sid=np.array(['1', '1', '1', '2', '2']),
               lat=np.array([10.0] * 5), lon=np.array([-80.0] * 5), p=np.array([1000.0, 1000.0, 1000.0, 850.0, 850.0]), z=np.array([10.0] * 5),
               time=np.array([t0 - 3600, t0, t0, t0, t0]), var=np.array(['t', 't', 'td', 'td', 'z']), value=np.array([300.0, 301.0, 290.0, 280.0, 1500.0]))
    O = OP.prepare_real(obs, t0)
    assert len(O['value']) == 3 and set(O['var']) == {'t', 'q'}
    assert O['value'][O['var'] == 't'][0] == 301.0 and np.all(O['lon'] >= 0)
    q = O['value'][(O['var'] == 'q') & (O['type'] == 'synop')][0]; assert 0.010 < q < 0.014     # Td 17 C at 1000 hPa
    assert np.isnan(O['p'][O['type'] == 'synop']).all()

def test_errors():
    ob = dict(type=np.array(['temp', 'synop', 'scat', 'temp']), var=np.array(['t', 'ps', 'u', 'q']), p=np.array([500.0, np.nan, np.nan, 850.0]), z=np.array([np.nan, 1000.0, np.nan, np.nan]))
    e = OP.obs_errors(ob, qs_ref=np.array([1, 1, 1, 0.01]))
    assert abs(e[0] - 0.9) < 1e-6 and abs(e[1] - 200.0) < 1e-6 and abs(e[2] - 1.8) < 1e-6 and abs(e[3] - 0.001) < 1e-6

if __name__ == '__main__':
    for f in [test_linear_exact, test_surface_ops, test_sonde_below_ground_and_qc_pairs, test_prepare_real, test_errors]:
        f(); print('ok', f.__name__)
