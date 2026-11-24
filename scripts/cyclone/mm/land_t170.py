"""24 Nov: land BL by local hour at T170 (Land BL night resolution check, registered 16:3x). 20-40 N land, day 1 hourly, 3 starts.
python land_t170.py <library.npz> '<extra set json>' <tag> <out.json>; prints one '#' summary line."""
"""19 Nov: registered land HBL check for bl_lcl 0. 20-40N land, day 1 hourly mean hbl and daily max. T42 dt20 rad_every 1, 3 starts."""
import sys, os, json, datetime as dt, numpy as np, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, landinit, wxscore as WS
from dinosaur import spherical_harmonic
SET = dict(json.load(open(os.path.join(HERE, '..', '..', '..', 'data', 'cyclone', 'kaggle_cfg', 'suite_lcmix_wx.json')))['variants'][0]['set'], **json.loads(sys.argv[2])); Z = np.load(sys.argv[1]); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
glo = np.arange(0, 360, 1.5); gla = np.linspace(-90, 90, 121); Wg = np.cos(np.radians(gla))[:, None] * np.ones((1, 240)); out = {'mean': [], 'max': [], 'night': [], 'day': [], 'v1n': [], 'v1d': [], 'z1': []}; VV = None
for KEY in ('2020-10-07T00', '2020-11-01T00', '2020-11-26T00'):
    M = mm2.Model(os.environ.get('GRID', 'T170'), 32, 20.0, dict({'rad': 'radcloud', 'rad_every': 1}, **SET)); k = TT.index(KEY); t0 = dt.datetime.strptime(KEY, '%Y-%m-%dT%H')
    f2 = Z['f2'][k]; _f = Z['f3'][k].astype(np.float32); f3 = {v: _f[V3.index(v)] for v in V3}; del _f
    st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / 9.80616,
                    f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
    M.build(t0); st = M.dfi(st); hor = M.coords.horizontal; h0 = 0; H = []
    lnd = WS.to_grid(np.asarray(M.land, float), M.lon, M.lat) > 0.5; m = (gla[:, None] >= 20) & (gla[:, None] <= 40) & lnd
    for h in range(1, 25):
        st, cr = mm2.integrate(M, st, cr, h - h0); h0 = h
        T = (hor.to_nodal(st.temperature_variation) + M.ref_t[:, None, None]) / M.K; q = st.tracers['specific_humidity']
        ps = jnp.exp(hor.to_nodal(st.log_surface_pressure))[0] / M.PA; u, v = spherical_harmonic.vor_div_to_uv_nodal(hor, st.vorticity, st.divergence)
        tn, d = M.column(T, q, u / M.MPS, v / M.MPS, ps, dict(cr, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0)), rad_fresh=True, div=hor.to_nodal(st.divergence) * M.SEC)
        H.append(WS.to_grid(np.asarray(d['hbl'], float), M.lon, M.lat))
        if h == 1: VV = []; Z1 = []; HI = []; EX = []; RB = []
        HI.append(WS.to_grid(np.asarray(d['hbl_ifsi'], float), M.lon, M.lat)); EX.append(WS.to_grid(np.asarray(d['excess'], float), M.lon, M.lat)); RB.append(WS.to_grid(np.asarray(d['fst'], float), M.lon, M.lat)); Z1.append(WS.to_grid(np.asarray(d['H'], float), M.lon, M.lat)); VV.append(WS.to_grid(np.sqrt(np.asarray(u[-1] / M.MPS) ** 2 + np.asarray(v[-1] / M.MPS) ** 2), M.lon, M.lat))
    H = np.array(H); mean = lambda X: float((np.where(m, X, 0) * Wg).sum() / (Wg * m).sum())
    lh = (np.arange(1, 25)[:, None] + glo[None, :] / 15.0) % 24; nt = ((lh >= 21) | (lh <= 4))[:, None, :] * np.ones(H.shape, bool); dy = ((lh >= 10) & (lh <= 16))[:, None, :] * np.ones(H.shape, bool)
    out['night'].append(mean(np.where(nt, H, 0).sum(0) / np.maximum(nt.sum(0), 1))); out['day'].append(mean(np.where(dy, H, 0).sum(0) / np.maximum(dy.sum(0), 1)))
    RB = np.array(RB); out.setdefault('fsn', []).append(mean(np.where(nt, RB, 0).sum(0) / np.maximum(nt.sum(0), 1))); HI = np.array(HI); EX = np.array(EX); out.setdefault('hid', []).append(mean(np.where(dy, HI, 0).sum(0) / np.maximum(dy.sum(0), 1))); out.setdefault('hin', []).append(mean(np.where(nt, HI, 0).sum(0) / np.maximum(nt.sum(0), 1))); out.setdefault('exd', []).append(mean(np.where(dy, EX, 0).sum(0) / np.maximum(dy.sum(0), 1))); Z1 = np.array(Z1); out.setdefault('Hd', []).append(mean(np.where(dy, Z1, 0).sum(0) / np.maximum(dy.sum(0), 1))); out.setdefault('Hn', []).append(mean(np.where(nt, Z1, 0).sum(0) / np.maximum(nt.sum(0), 1))); VV = np.array(VV); out['v1n'].append(mean(np.where(nt, VV, 0).sum(0) / np.maximum(nt.sum(0), 1))); out['v1d'].append(mean(np.where(dy, VV, 0).sum(0) / np.maximum(dy.sum(0), 1)))
    out['mean'].append(mean(H.mean(0))); out['max'].append(mean(H.max(0))); print(KEY, out['mean'][-1], out['max'][-1], flush=True)
print('sigma_low', float(np.asarray(M.coords.vertical.centers)[-1]), flush=True); print('#', sys.argv[3], 'land 20-40N hbl day-1 mean', round(np.mean(out['mean'])), 'daily max', round(np.mean(out['max'])), 'night', round(np.mean(out['night'])), 'day', round(np.mean(out['day'])), 'V1 night %.2f day %.2f H day %.1f night %.1f' % (np.mean(out['v1n']), np.mean(out['v1d']), np.mean(out['Hd']), np.mean(out['Hn'])) + ' | night cd/cdn %.3f' % np.mean(out['fsn']) + ' | hbl_ifsi (IFS def, interp) day %.0f night %.0f, day excess %.2f K' % (np.mean(out['hid']), np.mean(out['hin']), np.mean(out['exd'])), flush=True)
json.dump({k: [float(x) for x in v] for k, v in out.items() if isinstance(v, list)}, open(sys.argv[4], 'w'))
