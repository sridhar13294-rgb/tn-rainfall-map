"""End-to-end test of analysis.py on the CPU (numpy), no model: a coarse global grid (3.75 deg, 12 sigma levels), truth
and 20 background members drawn from the same smooth random distribution (so the ensemble describes its own error),
the OSSE network (network.py) observing the truth with noise. The analysis must be clearly closer to the truth near the radiosondes
(T, wind, q) and for surface pressure, never worse on the global average (far from data the toy's random cross-variable
covariances are pure sampling noise), O-A < O-B for every type, and the spread must shrink.
Runs in ~20-40 s.  python test_analysis.py"""
import os, sys, time, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scipy import ndimage as ndi
import analysis as AN, network as NW, obsop as OP

def setup(K=20, seed=0):
    rs = np.random.default_rng(seed)
    lon = np.arange(0, 360, 3.75); lat = np.linspace(-87.5, 87.5, 48); X, Y = len(lon), len(lat)
    LO, LA = np.meshgrid(lon, lat, indexing='ij'); sig = np.array([0.03, 0.07, 0.13, 0.2, 0.3, 0.4, 0.5, 0.62, 0.74, 0.85, 0.93, 0.99])
    land = ((np.sin(np.radians(2 * LO)) * np.cos(np.radians(1.5 * LA)) > 0.25) | (LA < -70)).astype(float)
    zs = land * (300.0 + 200 * np.cos(np.radians(LO)) ** 2)
    def smooth(shape, s, amp):
        a = rs.standard_normal(shape); a = ndi.gaussian_filter(a, s, mode=['nearest'] * (len(shape) - 2) + ['wrap', 'nearest'])
        return a / a.std() * amp
    base = dict(t=(288.0 * sig ** 0.19)[:, None, None] - 30 * (np.abs(LA[None]) / 90) ** 2, q=0.016 * sig[:, None, None] ** 3 * np.cos(np.radians(LA[None])) ** 2,
                u=15 * np.sin(np.radians(2 * LA[None])) * (1.2 - sig[:, None, None]) + 0 * sig[:, None, None], v=0.0 * sig[:, None, None] + 0 * LA[None],
                ps=1e5 * np.exp(-zs / 8000.0))
    amp = dict(t=1.5, q=0.0012, u=2.5, v=2.5, ps=150.0)
    draws = []
    for k in range(K + 1):
        d = {}
        for v in ('t', 'q', 'u', 'v'): d[v] = base[v] + smooth((len(sig), X, Y), (1.2, 2.0, 2.0), amp[v]) * np.ones((1, X, Y))
        d['q'] = np.maximum(d['q'], 1e-6); d['ps'] = base['ps'] + smooth((X, Y), (2.5, 2.5), amp['ps'])
        draws.append(d)
    truth = draws[0]; Fb = {v: np.stack([d[v] for d in draws[1:]]).astype(np.float32) for v in truth}
    static = dict(lon=lon, lat=lat, sig=sig, zs=zs, land=land)
    net = NW.build(lon, lat, land, zs, seed=3, stations=None)
    obs = NW.records(net, 0, lon, lat, land, 0)
    op = OP.Operator(static, obs); hx, _ = op({k: truth[k] for k in truth})
    qs = OP.NG.qsat(np.where(op.upper, 280.0, 285.0), np.where(op.upper, op.pobs, 9e4))          # q error scale (rough is fine here)
    obs['err'] = OP.obs_errors(obs, qs_ref=qs); obs['value'] = hx + rs.standard_normal(len(hx)) * obs['err']
    return static, truth, Fb, obs

def rmse(a, b, LA):
    w = np.cos(np.radians(LA)); w = np.broadcast_to(w, a.shape); return float(np.sqrt((w * (a - b) ** 2).sum() / w.sum()))

def test_analysis_toy():
    static, truth, Fb, obs = setup()
    LO, LA = np.meshgrid(static['lon'], static['lat'], indexing='ij')
    t = time.time(); A = AN.Analysis(static, dict(c_h=800.0, c_h_top=1000.0, rtps=0.0, chunk=1024))
    Fa, info = A(Fb, obs); dt = time.time() - t
    print('obs used %d of %d, mean local obs per group %s, %.1f s' % (info['n_used'], info['n_obs'], info['mean_local_obs'], dt))
    import letkf as LK
    from scipy.spatial import cKDTree
    m = obs['type'] == 'temp'; d, _ = cKDTree(LK.unit_xyz(obs['lat'][m], obs['lon'][m])).query(LK.unit_xyz(LA.ravel(), LO.ravel()))
    near = (LK.great_circle_km(d) < 400).reshape(LA.shape); mid = (static['sig'] >= 0.2) & (static['sig'] <= 0.93)
    res = {}
    for v in ('t', 'q', 'u', 'v', 'ps'):
        eb = rmse(Fb[v].mean(0), truth[v], LA); ea = rmse(Fa[v].mean(0), truth[v], LA)
        sb = float(np.sqrt(Fb[v].var(0, ddof=1).mean())); sa = float(np.sqrt(Fa[v].var(0, ddof=1).mean()))
        if v != 'ps':
            nb = float(np.sqrt(((Fb[v].mean(0) - truth[v])[mid][:, near] ** 2).mean())); na = float(np.sqrt(((Fa[v].mean(0) - truth[v])[mid][:, near] ** 2).mean()))
        else: nb, na = eb, ea
        res[v] = (eb, ea, nb, na)
        print('%-2s RMSE globe %.4g -> %.4g; within 400 km of a radiosonde (sigma 0.2-0.93) %.4g -> %.4g; spread %.4g -> %.4g' % (v, eb, ea, nb, na, sb, sa))
        assert ea < 1.03 * eb and sa < sb, v                                       # never worse on the whole
    assert res['t'][3] < 0.75 * res['t'][2] and res['u'][3] < 0.9 * res['u'][2] and res['v'][3] < 0.9 * res['v'][2] and res['q'][3] < 0.95 * res['q'][2]
    assert res['ps'][1] < 0.8 * res['ps'][0]
    for k, r in info['obs'].items():
        if r.get('used'): assert r['oma_rms'] < r['omb_rms'], (k, r)
    return res

if __name__ == '__main__':
    test_analysis_toy(); print('ok test_analysis_toy')
